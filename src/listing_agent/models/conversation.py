from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from listing_agent.core.time import now_app_timezone
from listing_agent.db.base import Base


def _app_now() -> datetime:
    """Return timezone-aware UTC+8 timestamps for persisted records."""
    return now_app_timezone()


def _prefixed_id(prefix: str) -> str:
    """Create readable public IDs while keeping enough uniqueness for V1."""
    return f"{prefix}_{uuid4().hex}"


def new_conversation_id() -> str:
    """Generate a conversation ID matching the API examples."""
    return _prefixed_id("conv")


def new_message_id() -> str:
    """Generate a message ID matching the API examples."""
    return _prefixed_id("msg")


class Conversation(Base):
    """A persisted user workflow session."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_conversation_id)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    current_step: Mapped[str] = mapped_column(String(64), nullable=False, default="collect_brief")
    marketplace: Mapped[str] = mapped_column(String(16), nullable=False, default="US")
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en-US")
    active_brief_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_draft_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_app_now,
        onupdate=_app_now,
    )

    # Message history is loaded in creation order for conversation detail endpoints.
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    """A single user, assistant, or system message inside a conversation."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_message_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
