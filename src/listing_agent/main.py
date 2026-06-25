from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from listing_agent import __version__
from listing_agent.api.router import api_router
from listing_agent.core.config import get_settings
from listing_agent.core.logging import configure_logging, get_logger
from listing_agent.core.observability import RequestLoggingMiddleware
from listing_agent.db.session import dispose_engine, init_db

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    await init_db()
    yield
    await dispose_engine()
    logger.info("Stopped %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.include_router(api_router)
