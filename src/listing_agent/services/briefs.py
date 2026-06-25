from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.models.conversation import Conversation
from listing_agent.models.v1_data import ProductBrief
from listing_agent.schemas.brief import BriefUpsertRequest
from listing_agent.services.conversations import ConversationNotFoundError

REQUIRED_BRIEF_FIELDS = ["product_name", "core_features"]


class BriefNotFoundError(Exception):
    """Raised when a product Brief ID does not exist in storage."""


class BriefValidationError(Exception):
    """Raised when a Brief cannot be created or updated with the supplied payload."""


def get_missing_required_fields(brief: ProductBrief) -> list[str]:
    """Return missing fields required before copy generation can run."""
    missing = []
    if not _has_text(brief.product_name):
        missing.append("product_name")
    if not _has_items(brief.core_features):
        missing.append("core_features")
    return missing


def calculate_completeness_score(brief: ProductBrief) -> int:
    """Calculate a simple percentage from the minimum required Brief fields."""
    filled_count = len(REQUIRED_BRIEF_FIELDS) - len(get_missing_required_fields(brief))
    return round(filled_count / len(REQUIRED_BRIEF_FIELDS) * 100)


def is_ready_for_generation(brief: ProductBrief) -> bool:
    """Return whether the Brief has enough information for the generation task."""
    return not get_missing_required_fields(brief)


class BriefService:
    """Persist product Brief data and keep related conversation state in sync."""

    async def create_brief(
        self,
        session: AsyncSession,
        payload: BriefUpsertRequest,
    ) -> ProductBrief:
        """Create a Brief linked to an existing conversation."""
        if payload.conversation_id is None:
            raise BriefValidationError("conversation_id is required")

        conversation = await self._get_conversation(session, payload.conversation_id)
        brief = ProductBrief(
            conversation_id=conversation.id,
            product_name=payload.product_name,
            brand=payload.brand,
            category=payload.category,
            marketplace=payload.marketplace,
            language=payload.language,
            core_features=payload.core_features,
            materials=payload.materials,
            color=payload.color,
            quantity=payload.quantity,
            size_info=payload.size_info,
            target_audience=payload.target_audience,
            keywords_seed=payload.keywords_seed,
        )
        self._apply_completeness(brief)
        session.add(brief)
        await session.flush()
        self._sync_conversation_state(conversation, brief)
        await session.commit()
        await session.refresh(brief)
        return brief

    async def update_brief(
        self,
        session: AsyncSession,
        brief_id: str,
        payload: BriefUpsertRequest,
    ) -> ProductBrief:
        """Update an existing Brief and recompute generation readiness."""
        brief = await self.get_brief(session, brief_id)
        conversation = await self._get_conversation(session, brief.conversation_id)

        for field_name in (
            "product_name",
            "brand",
            "category",
            "marketplace",
            "language",
            "core_features",
            "materials",
            "color",
            "quantity",
            "size_info",
            "target_audience",
            "keywords_seed",
        ):
            setattr(brief, field_name, getattr(payload, field_name))

        self._apply_completeness(brief)
        self._sync_conversation_state(conversation, brief)
        await session.commit()
        await session.refresh(brief)
        return brief

    async def get_brief(self, session: AsyncSession, brief_id: str) -> ProductBrief:
        """Load a single Brief by ID."""
        result = await session.execute(select(ProductBrief).where(ProductBrief.id == brief_id))
        brief = result.scalar_one_or_none()
        if brief is None:
            raise BriefNotFoundError(brief_id)
        return brief

    async def _get_conversation(self, session: AsyncSession, conversation_id: str) -> Conversation:
        """Load the owning conversation for Brief operations."""
        result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def _apply_completeness(self, brief: ProductBrief) -> None:
        """Persist the computed score for quick checks in later tasks."""
        brief.completeness_score = calculate_completeness_score(brief)

    def _sync_conversation_state(self, conversation: Conversation, brief: ProductBrief) -> None:
        """Move the conversation forward only when the minimum Brief is complete."""
        conversation.active_brief_id = brief.id
        conversation.current_step = (
            "import_competitors" if is_ready_for_generation(brief) else "collect_brief"
        )


def _has_text(value: str | None) -> bool:
    """Return whether a text field has meaningful content."""
    return bool(value and value.strip())


def _has_items(value: list | None) -> bool:
    """Return whether a list field has at least one non-empty item."""
    return bool(value and any(str(item).strip() for item in value))
