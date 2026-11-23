from fastapi import APIRouter, Request
from datetime import timezone

from sqlalchemy import func, literal, select, union_all

from app.models.chat import Message
from app.models.knowledge import Chunk, PdfMetadata
from app.models.library import Conversation, Document
from app.schemas.status import Activity, AIStatus, Dashboard, Health

router = APIRouter(prefix="/api")


@router.get("/health", response_model=Health)
def health(request: Request):
    with request.app.state.engine.connect() as connection:
        connection.execute(select(1))
    return Health(status="ok", database="connected")


@router.get("/ai/status", response_model=AIStatus)
def ai_status(request: Request):
    return request.app.state.llm.status()


@router.get("/dashboard", response_model=Dashboard)
def dashboard(request: Request):
    with request.app.state.engine.connect() as connection:
        documents = connection.scalar(select(func.count()).select_from(Document))
        conversations = connection.scalar(select(func.count()).select_from(Conversation))
        chunks = connection.scalar(select(func.count()).select_from(Chunk))
        activity = union_all(
            select(Document.id, literal("document").label("kind"), Document.name.label("title"),
                   PdfMetadata.uploaded_at.label("occurred_at")).join(PdfMetadata),
            select(Conversation.id, literal("conversation"), Conversation.title, func.max(Message.created_at))
            .join(Message).group_by(Conversation.id, Conversation.title),
        ).subquery()
        recent = [
            Activity(id=row.id, kind=row.kind, title=row.title,
                     occurred_at=row.occurred_at.replace(tzinfo=timezone.utc))
            for row in connection.execute(select(activity).order_by(
                activity.c.occurred_at.desc(), activity.c.kind, activity.c.id
            ).limit(6))
        ]
    return Dashboard(document_count=documents, conversation_count=conversations,
                     indexed_chunk_count=chunks, recent_activity=recent, ai=ai_status(request))
