# === backend/app/models/versionlog.py ===
from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime, func
from app.db.database import Base

class VersionLog(Base):
    __tablename__ = "version_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    raw_openapi = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
