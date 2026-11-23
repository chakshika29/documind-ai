import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile

from app.core.errors import KnowledgeError
from app.schemas.knowledge import DocumentInfo, SearchHit, SearchRequest
from app.services.knowledge import KnowledgeBase

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def get_knowledge(request: Request) -> KnowledgeBase:
    return request.app.state.knowledge


Knowledge = Annotated[KnowledgeBase, Depends(get_knowledge)]


@router.post("/documents/upload", response_model=DocumentInfo, status_code=201)
def upload_document(file: Annotated[UploadFile, File()], knowledge: Knowledge):
    limit_mb = knowledge.settings.max_upload_mb
    limit = limit_mb * 1024 * 1024
    size_error = KnowledgeError(413, "pdf_too_large", f"PDFs must be at most {limit_mb} MB.")
    if file.size is not None and file.size > limit:
        raise size_error
    try:
        with knowledge.lock:
            content = file.file.read(limit + 1)
            if len(content) > limit:
                raise size_error
            return knowledge.ingest(file.filename or "", content)
    except OSError as exc:
        logger.exception("Could not store the uploaded PDF")
        raise KnowledgeError(503, "storage_unavailable", "The local PDF storage is unavailable.") from exc
    except RuntimeError as exc:
        logger.exception("Could not index the uploaded PDF")
        raise KnowledgeError(503, "index_unavailable", "The local FAISS index could not be updated.") from exc


@router.get("/documents", response_model=list[DocumentInfo])
def list_documents(knowledge: Knowledge):
    return knowledge.list_documents()


@router.get("/documents/{document_id}", response_model=DocumentInfo)
def get_document(document_id: str, knowledge: Knowledge):
    return knowledge.get_document(document_id)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, knowledge: Knowledge):
    knowledge.delete_document(document_id)
    return Response(status_code=204)


@router.post("/search", response_model=list[SearchHit])
def search_documents(body: SearchRequest, knowledge: Knowledge):
    return knowledge.search(body)
