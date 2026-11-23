from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"]
    database: Literal["connected"]


class AIStatus(BaseModel):
    status: Literal["unavailable", "cached", "loading", "ready", "error"]
    detail: str
    model: str
    files_available: bool
    embedding_files_available: bool
    loaded: bool
    ready: bool
    busy: bool
    error: str | None


class Activity(BaseModel):
    id: str
    kind: Literal["document", "conversation"]
    title: str
    occurred_at: datetime


class Dashboard(BaseModel):
    document_count: int
    conversation_count: int
    indexed_chunk_count: int
    recent_activity: list[Activity]
    ai: AIStatus
