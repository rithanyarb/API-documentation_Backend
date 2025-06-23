# === backend/app/api/v1/api.py ===
from fastapi import APIRouter
from .endpoints import openapi, curl, test, code, analytics, authentication

api_router = APIRouter()
api_router.include_router(openapi.router, prefix="/openapi", tags=["OpenAPI"])
api_router.include_router(curl.router, prefix="/curl", tags=["cURL"])
api_router.include_router(test.router, tags=["Testing"])
api_router.include_router(code.router, prefix="/code", tags=["Code"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(authentication.router, prefix="/authentication", tags=["Google OAuth"])