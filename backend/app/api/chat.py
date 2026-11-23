from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.schemas.chat import ChatRequest, ChatResponse, ConversationDetail, ConversationSummary
from app.services.chat import ChatService

router = APIRouter(prefix="/api")


def get_chat(request: Request) -> ChatService:
    return request.app.state.chat


Chat = Annotated[ChatService, Depends(get_chat)]


@router.post("/chat", response_model=ChatResponse)
def ask_question(body: ChatRequest, chat: Chat):
    return chat.ask(body)


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(chat: Chat):
    return chat.list()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, chat: Chat):
    return chat.get(conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, chat: Chat):
    chat.delete(conversation_id)
    return Response(status_code=204)
