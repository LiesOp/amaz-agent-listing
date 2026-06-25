from fastapi import APIRouter

from listing_agent.api.v1 import (
    admin,
    audits,
    briefs,
    copywriting,
    competitors,
    conversations,
    drafts,
    health,
    jobs,
    rules,
)

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(conversations.router)
router.include_router(briefs.router)
router.include_router(copywriting.router)
router.include_router(competitors.router)
router.include_router(drafts.router)
router.include_router(audits.router)
router.include_router(rules.router)
router.include_router(jobs.router)
router.include_router(admin.router)
