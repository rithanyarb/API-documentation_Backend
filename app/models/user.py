# === backend/app/models/user.py ===
from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    google_id = Column(String, unique=True, index=True, nullable=True)  
    picture = Column(String, nullable=True)