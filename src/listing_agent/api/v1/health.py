from fastapi import APIRouter

from listing_agent import __version__
from listing_agent.core.config import get_settings
from listing_agent.db.session import check_database, get_session_factory
from listing_agent.schemas.health import DatabaseStatus, HealthResponse, LangChainStatus
from listing_agent.services.admin import AdminService, NoActiveModelConfigError
from listing_agent.services.llm import is_langchain_installed

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()

    database = DatabaseStatus(status="ok")
    try:
        await check_database()
    except Exception as exc:
        database = DatabaseStatus(status="error", error=str(exc))

    provider_configured = False
    model = ""
    try:
        async with get_session_factory()() as session:
            active_model = await AdminService().get_active_model_config(session)
            provider_configured = bool(active_model.api_key)
            model = active_model.model_name
    except NoActiveModelConfigError:
        provider_configured = False
        model = ""
    except Exception:
        provider_configured = False
        model = ""

    langchain = LangChainStatus(
        installed=is_langchain_installed(),
        provider_configured=provider_configured,
        model=model,
    )

    service_status = "ok" if database.status == "ok" else "degraded"
    return HealthResponse(
        status=service_status,
        service=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        database=database,
        langchain=langchain,
    )
