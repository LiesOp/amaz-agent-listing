from pydantic import BaseModel


class DatabaseStatus(BaseModel):
    status: str
    error: str | None = None


class LangChainStatus(BaseModel):
    installed: bool
    provider_configured: bool
    model: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: DatabaseStatus
    langchain: LangChainStatus
