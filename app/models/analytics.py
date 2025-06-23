# === backend/app/models/analytics.py ===
from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey
from app.db.database import Base

class FeatureUsage(Base):
    __tablename__ = "feature_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) 
    feature = Column(String, nullable=False)  # openapijson, curl, backendzip, githubrepo
    timestamp = Column(DateTime(timezone=True), server_default=func.now())