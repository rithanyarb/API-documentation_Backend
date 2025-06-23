# backend/app/core/config.py
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost/api_docs_db")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    CLIENT_ID: str = os.getenv("CLIENT_ID", "")
    CLIENT_SECRET: str = os.getenv("CLIENT_SECRET", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", " http://localhost:5173")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    
    class Config:
        env_file = ".env"

settings = Settings()

