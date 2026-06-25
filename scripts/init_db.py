import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from listing_agent.core.config import get_settings  # noqa: E402
from listing_agent.core.logging import configure_logging, get_logger  # noqa: E402
from listing_agent.db.session import dispose_engine, init_db  # noqa: E402

logger = get_logger(__name__)


async def main() -> None:
    """Create missing database tables and seed fixed reference data."""
    settings = get_settings()
    configure_logging(settings.log_level)
    await init_db()
    await dispose_engine()
    logger.info("Database initialized: %s", settings.resolved_database_url)


if __name__ == "__main__":
    asyncio.run(main())
