# === backend/app/models/endpoint.py ===
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from app.db.database import Base

class Endpoint(Base):
    __tablename__ = "endpoints"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    path = Column(String, nullable=False)
    method = Column(String, nullable=False)
    summary = Column(String, nullable=True)
    requires_auth = Column(Boolean, default=False)
    request_body = Column(Text, nullable=True)  