from fastapi import APIRouter

from listing_agent.api.v1 import health
from listing_agent.api.v1.router import router as v1_router

api_router = APIRouter()
api_router.include_router(v1_router, prefix="/api/v1")
api_router.include_router(health.router)
