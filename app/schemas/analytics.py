# === backend/app/schemas/analytics.py ===
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime

class TrackUsageRequest(BaseModel):
    feature: str
    user_id: Optional[int] = None

class GlobalStatsResponse(BaseModel):
    total_users: int
    feature_usage: Dict[str, int]

class UserStatsResponse(BaseModel):
    openapijson: int
    curl: int
    backendzip: int
    githubrepo: int