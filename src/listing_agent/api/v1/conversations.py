from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.db.session import get_db_session
from listing_agent.models.conversation import Conversation, Message
from listing_agent.schemas.conversation import (
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from listing_agent.services.conversations import ConversationNotFoundError, ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])
conversation_service = ConversationService()


def _to_conversation_response(conversation: Conversation) -> ConversationResponse:
    """Map ORM conversation objects to stable API responses."""
    return ConversationResponse(
        id=conversation.id,
        status=conversation.status,
        current_step=conversation.current_step,
        marketplace=conversation.marketplace,
        language=conversation.language,
        active_brief_id=conversation.active_brief_id,
        active_draft_id=conversation.active_draft_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _to_message_response(message: Message) -> MessageResponse:
    """Map ORM message objects to stable API responses."""
    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: CreateConversationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    """Create a new active conversation for collecting product information."""
    conversation = await conversation_service.create_conversation(session, payload)
    return _to_conversation_response(conversation)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ConversationDetailResponse:
    """Return a conversation and its persisted message history."""
    try:
        conversation = await conversation_service.get_conversation(session, conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found") from exc

    base = _to_conversation_response(conversation)
    return ConversationDetailResponse(
        **base.model_dump(),
        messages=[_to_message_response(message) for message in conversation.messages],
    )


@router.post("/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SendMessageResponse:
    """Append a user message and persist the assistant reply for the same conversation."""
    try:
        conversation, user_message, assistant_message = await conversation_service.append_user_message(
            session,
            conversation_id,
            payload,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found") from exc

    return SendMessageResponse(
        reply=assistant_message.content,
        current_step=conversation.current_step,
        user_message=_to_message_response(user_message),
        assistant_message=_to_message_response(assistant_message),
    )
