from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


class DocumentInfo(BaseModel):
    id: str
    name: str
    status: Literal["indexed", "not_indexed"]
    page_count: int | None
    size_bytes: int | None
    uploaded_at: datetime | None


DocumentID = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class SearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    document_ids: list[DocumentID] | None = Field(default=None, max_length=100)
    top_k: int | None = Field(default=None, ge=1, le=30)


class SearchHit(BaseModel):
    chunk_id: int
    document_id: str
    document_name: str
    page: int
    text: str
    score: float
