import logging
from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import KnowledgeError
from app.models.chat import Message
from app.models.library import Conversation
from app.rag.llm import LocalLLM
from app.rag.pipeline import INSUFFICIENT, build_prompt, verify_answer
from app.schemas.chat import ChatRequest, ChatResponse, ConversationDetail, ConversationSummary, MessageInfo
from app.schemas.knowledge import SearchRequest
from app.services.knowledge import KnowledgeBase

logger = logging.getLogger(__name__)


def _conversation(db: Session, conversation_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise KnowledgeError(404, "conversation_not_found", "This conversation no longer exists.")
    return conversation


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value is not None else None


class ChatService:
    def __init__(self, knowledge: KnowledgeBase, llm: LocalLLM):
        self.knowledge = knowledge
        self.engine = knowledge.engine
        self.llm = llm

    def ask(self, request: ChatRequest) -> ChatResponse:
        started = monotonic()
        if request.conversation_id:
            with Session(self.engine) as db:
                _conversation(db, request.conversation_id)
        document_ids = list(dict.fromkeys(request.document_ids))
        try:
            with self.knowledge.lock:
                for document_id in document_ids:
                    document = self.knowledge.get_document(document_id)
                    if document.status != "indexed":
                        raise KnowledgeError(422, "document_unindexed", f"{document.name} needs to be indexed before chat.")
                hits = self.knowledge.search(SearchRequest(query=request.question, document_ids=document_ids))
        except RuntimeError as exc:
            logger.exception("Chat retrieval failed")
            raise KnowledgeError(503, "retrieval_failed", "The local search index is unavailable.") from exc

        relevant = [hit for hit in hits if hit.score >= self.llm.settings.chat_min_similarity]
        if relevant:
            generated, context = self.llm.generate(
                lambda tokenizer, limit: build_prompt(request.question, relevant, tokenizer, limit)
            )
            answer, citations = verify_answer(generated, context)
        else:
            answer, citations = INSUFFICIENT, []

        conversation_id = request.conversation_id or uuid4().hex
        message_id = uuid4().hex
        now = datetime.now(timezone.utc)
        model = self.llm.settings.llm_model
        with Session(self.engine) as db:
            if request.conversation_id:
                _conversation(db, conversation_id)
            else:
                db.add(Conversation(id=conversation_id, title=request.question[:90]))
                db.flush()
            db.add_all([
                Message(id=uuid4().hex, conversation_id=conversation_id, role="user", text=request.question,
                        document_ids=document_ids, citations=[], created_at=now),
                Message(id=message_id, conversation_id=conversation_id, role="assistant", text=answer,
                        document_ids=document_ids, citations=[citation.model_dump() for citation in citations],
                        model=model, created_at=now),
            ])
            db.commit()

        return ChatResponse(answer=answer, conversation_id=conversation_id, message_id=message_id,
                            citations=citations, model=model, elapsed_ms=round((monotonic() - started) * 1000),
                            insufficient_evidence=not citations)

    def list(self) -> list[ConversationSummary]:
        timestamp = func.max(Message.created_at).label("last_message")
        statement = (
            select(Conversation.id, Conversation.title, timestamp)
            .outerjoin(Message, Message.conversation_id == Conversation.id)
            .group_by(Conversation.id, Conversation.title)
            .order_by(timestamp.desc(), Conversation.id)
        )
        with Session(self.engine) as db:
            return [ConversationSummary(id=row.id, title=row.title, updated_at=_utc(row.last_message))
                    for row in db.execute(statement)]

    def get(self, conversation_id: str) -> ConversationDetail:
        with Session(self.engine) as db:
            conversation = _conversation(db, conversation_id)
            rows = list(db.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.sequence)
            ))
            return ConversationDetail(
                id=conversation.id, title=conversation.title,
                updated_at=_utc(rows[-1].created_at) if rows else None,
                messages=[
                    MessageInfo(id=row.id, role=row.role, text=row.text, citations=row.citations,
                                document_ids=row.document_ids, model=row.model)
                    for row in rows
                ],
            )

    def delete(self, conversation_id: str) -> None:
        with Session(self.engine) as db:
            db.delete(_conversation(db, conversation_id))
            db.commit()
