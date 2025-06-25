# === backend/app/main.py ===
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from app.api.v1.api import api_router
from app.db.database import create_db_and_tables
from app.core.config import settings
import time
import logging

#logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    await create_db_and_tables()
    yield
    logger.info("Shutting down...")

app = FastAPI(
    lifespan=lifespan,
    title="API Documentation Generator",
    description="Generate OpenAPI documentation from various sources",
    version="1.0.0"
)

#middleware security
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

#CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # 24 hours
)

#Session middleware (OAuth state management)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log slow requests
    if process_time > 100:  
        logger.warning(f"Slow request: {request.method} {request.url} took {process_time:.2f}s")
    
    return response

#API router
app.include_router(api_router, prefix="/api/v1")

#health check 
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }

#root 
@app.get("/")
async def root():
    return {
        "message": "API Documentation Generator",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

