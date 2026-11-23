from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.knowledge import DocumentID

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]


class ChatRequest(BaseModel):
    question: Question
    document_ids: list[DocumentID] = Field(min_length=1, max_length=20)
    conversation_id: DocumentID | None = None


class Citation(BaseModel):
    document_id: str
    document_name: str
    page: int
    chunk_id: int
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    message_id: str
    citations: list[Citation]
    elapsed_ms: int
    model: str
    insufficient_evidence: bool


class ConversationSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime | None


class MessageInfo(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    text: str
    document_ids: list[str]
    citations: list[Citation]
    model: str | None


class ConversationDetail(ConversationSummary):
    messages: list[MessageInfo]
