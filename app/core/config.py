# backend/app/core/config.py
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    CLIENT_ID: str = os.getenv("CLIENT_ID", "")
    CLIENT_SECRET: str = os.getenv("CLIENT_SECRET", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    
    class Config:
        env_file = ".env"

settings = Settings()

