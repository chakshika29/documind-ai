from datetime import datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.library import Base


class Message(Base):
    __tablename__ = "chat_messages"

    sequence: Mapped[int] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(unique=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str]
    text: Mapped[str]
    document_ids: Mapped[list] = mapped_column(JSON)
    citations: Mapped[list] = mapped_column(JSON)
    model: Mapped[str | None]
    created_at: Mapped[datetime]
