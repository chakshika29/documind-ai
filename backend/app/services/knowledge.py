import logging
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from threading import RLock
from uuid import uuid4

import numpy as np
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import KnowledgeError
from app.models.knowledge import Chunk, FaissSnapshot, PdfMetadata
from app.models.library import Document
from app.rag.embeddings import Embeddings
from app.rag.vector_store import VectorIndex
from app.schemas.knowledge import DocumentInfo, SearchHit, SearchRequest
from app.services.chunking import chunk_pages
from app.services.pdf import extract_pages

logger = logging.getLogger(__name__)


def document_info(document: Document, metadata: PdfMetadata | None) -> DocumentInfo:
    return DocumentInfo(
        id=document.id,
        name=document.name,
        status="indexed" if metadata else "not_indexed",
        page_count=metadata.page_count if metadata else None,
        size_bytes=metadata.size_bytes if metadata else None,
        uploaded_at=metadata.uploaded_at.replace(tzinfo=timezone.utc) if metadata else None,
    )


class KnowledgeBase:
    def __init__(self, engine: Engine, settings: Settings):
        self.engine = engine
        self.settings = settings
        self.uploads = settings.storage_dir / "uploads"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.embeddings = Embeddings(settings)
        self.lock = RLock()

        # Files can outlive a crash before an upload commits or after deletion.
        with Session(engine) as db:
            active = set(db.scalars(select(PdfMetadata.document_id)))
        for path in self.uploads.glob("*.pdf"):
            if len(path.stem) == 32 and all(char in "0123456789abcdef" for char in path.stem):
                if path.stem not in active:
                    self._unlink(path)

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not clean up a local PDF: %s", path.name)

    @staticmethod
    def _index(db: Session) -> VectorIndex:
        snapshot = db.get(FaissSnapshot, 1)
        try:
            if snapshot is not None:
                return VectorIndex(snapshot.data)
        except RuntimeError:
            logger.exception("Could not load the FAISS snapshot. Rebuilding from SQLite.")
        return KnowledgeBase._filtered_index(db, None)

    @staticmethod
    def _filtered_index(db: Session, document_ids: list[str] | None) -> VectorIndex:
        statement = select(Chunk.id, Chunk.embedding)
        if document_ids is not None:
            statement = statement.where(Chunk.document_id.in_(document_ids))
        rows = db.execute(statement).all()
        index = VectorIndex()
        if rows:
            index.add([row.id for row in rows], np.stack([
                np.frombuffer(row.embedding, dtype=np.float32) for row in rows
            ]))
        return index

    @staticmethod
    def _save_index(db: Session, index: VectorIndex) -> None:
        db.merge(FaissSnapshot(id=1, data=index.serialize()))

    @staticmethod
    def _check_duplicate(db: Session, digest: str) -> None:
        if db.scalar(select(PdfMetadata.document_id).where(PdfMetadata.sha256 == digest)):
            raise KnowledgeError(409, "duplicate_pdf", "This PDF is already in your document library.")

    def ingest(self, filename: str, content: bytes) -> DocumentInfo:
        name = PureWindowsPath(filename).name.strip()[:255] or "document.pdf"
        digest = sha256(content).hexdigest()
        # Serialize PDF parsing and embedding to keep local memory usage bounded.
        with self.lock, Session(self.engine) as db:
            self._check_duplicate(db, digest)
            pages = extract_pages(content, self.settings.max_pdf_pages)
            document_id = uuid4().hex
            chunks = chunk_pages(document_id, pages, self.settings.chunk_size, self.settings.chunk_overlap)
            vectors = self.embeddings.encode([chunk.normalized_text for chunk in chunks])
            path = self.uploads / f"{document_id}.pdf"
            created = False
            try:
                with path.open("xb") as file:
                    created = True
                    file.write(content)
                    file.flush()
                    os.fsync(file.fileno())
                index = self._index(db)
                document = Document(id=document_id, name=name)
                metadata = PdfMetadata(
                    document_id=document_id, sha256=digest, page_count=len(pages),
                    size_bytes=len(content), uploaded_at=datetime.now(timezone.utc),
                )
                db.add(document)
                db.flush()
                db.add(metadata)
                db.flush()
                rows = [
                    Chunk(document_id=chunk.document_id, page=chunk.page, text=chunk.text, embedding=vector.tobytes())
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ]
                db.add_all(rows)
                db.flush()
                index.add([row.id for row in rows], vectors)
                self._save_index(db, index)
                result = document_info(document, metadata)
                db.commit()
                return result
            except Exception:
                if created:
                    self._unlink(path)
                raise

    def list_documents(self) -> list[DocumentInfo]:
        with Session(self.engine) as db:
            rows = db.execute(
                select(Document, PdfMetadata).outerjoin(PdfMetadata)
                .order_by(PdfMetadata.uploaded_at.desc(), Document.name, Document.id)
            )
            return [document_info(document, metadata) for document, metadata in rows]

    @staticmethod
    def _get(db: Session, document_id: str) -> Document:
        document = db.get(Document, document_id)
        if document is None:
            raise KnowledgeError(404, "document_not_found", "That document is no longer in your library.")
        return document

    def get_document(self, document_id: str) -> DocumentInfo:
        with Session(self.engine) as db:
            return document_info(self._get(db, document_id), db.get(PdfMetadata, document_id))

    def delete_document(self, document_id: str) -> None:
        with self.lock, Session(self.engine) as db:
            document = self._get(db, document_id)
            metadata = db.get(PdfMetadata, document_id)
            if metadata is not None:
                index = self._index(db)
                index.remove(list(db.scalars(select(Chunk.id).where(Chunk.document_id == document_id))))
                self._save_index(db, index)
            db.delete(document)
            db.commit()
            if metadata is not None:
                self._unlink(self.uploads / f"{document_id}.pdf")

    def search(self, request: SearchRequest) -> list[SearchHit]:
        with self.lock, Session(self.engine) as db:
            index = (
                self._index(db) if request.document_ids is None
                else self._filtered_index(db, request.document_ids)
            )
            if not index.index.ntotal:
                return []
            query = self.embeddings.encode([request.query])
            matches = index.search(query, request.top_k or self.settings.search_top_k)
            rows = db.execute(
                select(Chunk.id, Chunk.document_id, Chunk.page, Chunk.text, Document.name)
                .join(Document, Document.id == Chunk.document_id)
                .where(Chunk.id.in_([chunk_id for chunk_id, _ in matches]))
            )
            by_id = {row.id: row for row in rows}
            return [
                SearchHit(chunk_id=chunk_id, document_id=row.document_id, document_name=row.name,
                          page=row.page, text=row.text, score=score)
                for chunk_id, score in matches if (row := by_id.get(chunk_id)) is not None
            ]
