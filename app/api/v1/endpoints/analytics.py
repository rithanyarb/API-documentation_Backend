# === backend/app/api/v1/endpoints/analytics.py ===
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.schemas.analytics import TrackUsageRequest, GlobalStatsResponse, UserStatsResponse
from app.models.analytics import FeatureUsage
from app.models.user import User
from app.db.database import get_db

router = APIRouter()

@router.post("/track")
async def track_feature_usage(payload: TrackUsageRequest, db: AsyncSession = Depends(get_db)):
    usage = FeatureUsage(
        user_id=payload.user_id,
        feature=payload.feature
    )
    db.add(usage)
    await db.commit()
    return {"message": "Usage tracked successfully"}

@router.get("/global", response_model=GlobalStatsResponse)
async def get_global_stats(db: AsyncSession = Depends(get_db)):
    #total users
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0
    
    # feature usage counts
    features = ["openapijson", "curl", "backendzip", "githubrepo"]
    feature_usage = {}
    
    for feature in features:
        result = await db.execute(
            select(func.count(FeatureUsage.id)).where(FeatureUsage.feature == feature)
        )
        feature_usage[feature] = result.scalar() or 0
    
    return GlobalStatsResponse(
        total_users=total_users,
        feature_usage=feature_usage
    )

@router.get("/user/{user_id}", response_model=UserStatsResponse)
async def get_user_stats(user_id: int, db: AsyncSession = Depends(get_db)):
    features = ["openapijson", "curl", "backendzip", "githubrepo"]
    user_stats = {}
    
    for feature in features:
        result = await db.execute(
            select(func.count(FeatureUsage.id)).where(
                FeatureUsage.user_id == user_id,
                FeatureUsage.feature == feature
            )
        )
        user_stats[feature] = result.scalar() or 0
    
    return UserStatsResponse(**user_stats)
