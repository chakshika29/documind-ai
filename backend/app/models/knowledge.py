from datetime import datetime

from sqlalchemy import ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from app.models.library import Base


class PdfMetadata(Base):
    __tablename__ = "pdf_metadata"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    sha256: Mapped[str] = mapped_column(unique=True)
    page_count: Mapped[int]
    size_bytes: Mapped[int]
    uploaded_at: Mapped[datetime]


class Chunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("pdf_metadata.document_id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int]
    text: Mapped[str]
    embedding: Mapped[bytes] = mapped_column(LargeBinary)


class FaissSnapshot(Base):
    __tablename__ = "faiss_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
