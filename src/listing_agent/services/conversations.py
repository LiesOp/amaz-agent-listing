from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from listing_agent.models.conversation import Conversation, Message
from listing_agent.schemas.conversation import CreateConversationRequest, SendMessageRequest


class ConversationNotFoundError(Exception):
    """Raised when a conversation ID does not exist in storage."""


class ConversationService:
    """Coordinate conversation state and message persistence."""

    async def create_conversation(
        self,
        session: AsyncSession,
        payload: CreateConversationRequest,
    ) -> Conversation:
        """Create the initial active conversation in the brief collection step."""
        conversation = Conversation(
            marketplace=payload.marketplace,
            language=payload.language,
            status="active",
            current_step="collect_brief",
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

    async def get_conversation(
        self,
        session: AsyncSession,
        conversation_id: str,
    ) -> Conversation:
        """Load a conversation with its ordered message history."""
        result = await session.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    async def append_user_message(
        self,
        session: AsyncSession,
        conversation_id: str,
        payload: SendMessageRequest,
    ) -> tuple[Conversation, Message, Message]:
        """Persist a user message, add a deterministic assistant reply, and keep state current."""
        conversation = await self.get_conversation(session, conversation_id)

        user_message = Message(
            conversation_id=conversation.id,
            role=payload.role,
            content=payload.content,
        )
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=self._build_brief_collection_reply(conversation),
        )

        # Task 2 only maintains state; later tasks will replace this with intent routing.
        conversation.current_step = "collect_brief"
        session.add_all([user_message, assistant_message])
        await session.commit()
        await session.refresh(conversation)
        await session.refresh(user_message)
        await session.refresh(assistant_message)
        return conversation, user_message, assistant_message

    def _build_brief_collection_reply(self, conversation: Conversation) -> str:
        """Return a stable reply that guides users toward the upcoming Brief fields."""
        return (
            f"This conversation targets marketplace {conversation.marketplace} "
            f"with language {conversation.language}. "
            "Please continue with product name, brand, category, core selling points, "
            "materials, or specifications."
        )
