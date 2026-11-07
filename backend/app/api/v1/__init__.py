from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.rate_cards import router as rate_cards_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.mappings import router as mappings_router
from app.api.v1.sources import router as sources_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(rate_cards_router)
api_router.include_router(uploads_router)
api_router.include_router(mappings_router)
api_router.include_router(sources_router)
