import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.models.conversation import Conversation
from listing_agent.models.v1_data import CompetitorInput, ProductBrief
from listing_agent.schemas.competitor import CompetitorImportItem, CompetitorImportRequest
from listing_agent.services.briefs import BriefNotFoundError
from listing_agent.services.conversations import ConversationNotFoundError

ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
ASIN_PATH_PATTERN = re.compile(r"/(?:dp|gp/product|product)/([A-Z0-9]{10})(?:[/?#]|$)", re.I)


@dataclass(slots=True)
class NormalizedCompetitorInput:
    """Validated and normalized competitor input ready for persistence."""

    input_type: str
    input_value: str
    normalized_url: str | None
    asin: str | None


class CompetitorInputValidationError(Exception):
    """Raised when a competitor URL or ASIN is invalid."""


class CompetitorImportService:
    """Validate and save competitor inputs for later analysis."""

    async def import_competitors(
        self,
        session: AsyncSession,
        payload: CompetitorImportRequest,
    ) -> list[CompetitorInput]:
        """Persist competitor inputs for one analysis job per item."""
        conversation = await self._get_conversation(session, payload.conversation_id)
        brief = await self._get_brief(session, payload.brief_id)
        if brief.conversation_id != conversation.id:
            raise CompetitorInputValidationError("brief does not belong to conversation")

        normalized_items = [normalize_competitor_item(item) for item in payload.items]
        competitor_inputs = [
            CompetitorInput(
                conversation_id=conversation.id,
                brief_id=brief.id,
                input_type=item.input_type,
                input_value=item.input_value,
                normalized_url=item.normalized_url,
                asin=item.asin,
                status="pending",
            )
            for item in normalized_items
        ]
        session.add_all(competitor_inputs)
        await session.flush()

        conversation.current_step = "analyze_competitors"
        await session.commit()

        for item in competitor_inputs:
            await session.refresh(item)
        return competitor_inputs

    async def _get_conversation(self, session: AsyncSession, conversation_id: str) -> Conversation:
        """Load the conversation that owns the competitor import."""
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    async def _get_brief(self, session: AsyncSession, brief_id: str) -> ProductBrief:
        """Load the Brief that owns the competitor import."""
        result = await session.execute(select(ProductBrief).where(ProductBrief.id == brief_id))
        brief = result.scalar_one_or_none()
        if brief is None:
            raise BriefNotFoundError(brief_id)
        return brief


def normalize_competitor_item(item: CompetitorImportItem) -> NormalizedCompetitorInput:
    """Validate and normalize a competitor import item."""
    raw_value = item.input_value.strip()
    if item.input_type == "asin":
        asin = normalize_asin(raw_value)
        return NormalizedCompetitorInput(
            input_type="asin",
            input_value=raw_value,
            normalized_url=f"https://www.amazon.com/dp/{asin}",
            asin=asin,
        )

    normalized_url, asin = normalize_amazon_url(raw_value)
    return NormalizedCompetitorInput(
        input_type="url",
        input_value=raw_value,
        normalized_url=normalized_url,
        asin=asin,
    )


def normalize_asin(value: str) -> str:
    """Normalize and validate an Amazon ASIN."""
    asin = value.strip().upper()
    if not ASIN_PATTERN.fullmatch(asin):
        raise CompetitorInputValidationError("invalid asin")
    return asin


def normalize_amazon_url(value: str) -> tuple[str, str | None]:
    """Normalize an Amazon URL and extract an ASIN when present."""
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CompetitorInputValidationError("invalid url")

    host = parsed.netloc.lower()
    if "amazon." not in host:
        raise CompetitorInputValidationError("url must be an amazon domain")

    normalized = urlunparse(("https", host, parsed.path.rstrip("/") or "/", "", "", ""))
    asin_match = ASIN_PATH_PATTERN.search(parsed.path)
    asin = asin_match.group(1).upper() if asin_match else None
    return normalized, asin
