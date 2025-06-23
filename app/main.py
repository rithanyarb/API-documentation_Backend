# === backend/app/main.py ===
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from app.api.v1.api import api_router
from app.db.database import create_db_and_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

# CORS middleware 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Session middleware (OAuth state management)
app.add_middleware(SessionMiddleware, secret_key="pxhSMRPWv_Xou6QbAb4jImHdUDIQD1sGGCSqEKlboAA")

app.include_router(api_router, prefix="/api/v1")