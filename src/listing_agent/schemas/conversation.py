from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    """Input for starting a new listing copy workflow conversation."""

    marketplace: str = Field(default="US", min_length=1, max_length=16)
    language: str = Field(default="en-US", min_length=2, max_length=32)


class ConversationResponse(BaseModel):
    """Public conversation state returned by API endpoints."""

    id: str
    status: str
    current_step: str
    marketplace: str
    language: str
    active_brief_id: str | None
    active_draft_id: str | None
    created_at: datetime
    updated_at: datetime


class SendMessageRequest(BaseModel):
    """User message payload accepted by the conversation API."""

    role: Literal["user"] = "user"
    content: str = Field(min_length=1)


class MessageResponse(BaseModel):
    """Persisted message shape exposed in conversation history."""

    id: str
    role: str
    content: str
    created_at: datetime


class SendMessageResponse(BaseModel):
    """Result of appending a user message and the system reply."""

    reply: str
    current_step: str
    user_message: MessageResponse
    assistant_message: MessageResponse


class ConversationDetailResponse(ConversationResponse):
    """Conversation state plus message history for verification and debugging."""

    messages: list[MessageResponse]
