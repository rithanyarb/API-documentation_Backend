# === backend/app/api/v1/endpoints/authentication.py ===
from fastapi import APIRouter, Request, HTTPException, Depends, Cookie
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from datetime import datetime, timedelta
from jose import jwt, ExpiredSignatureError, JWTError
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.database import get_db
from app.models.user import User
import requests
import os

router = APIRouter()

# OAuth setup
oauth = OAuth()
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=settings.CLIENT_ID,
    client_secret=settings.CLIENT_SECRET,
    client_kwargs={
        'scope': 'openid email profile',
    }
)

# JWT 
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"

FRONTEND_URL = settings.FRONTEND_URL

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.get("/login")
async def login(request: Request):
    """Minimal login endpoint"""
    redirect_uri = request.url_for('auth_callback')
    print(f"=== DEBUG LOGIN ===")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Request URL: {request.url}")
    print(f"Request base URL: {request.base_url}")
    print(f"Frontend URL: {FRONTEND_URL}")
    print(f"==================")
    
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/callback")
async def auth_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Enhanced callback endpoint with better cookie handling"""
    print(f"=== DEBUG CALLBACK ===")
    print(f"Query params: {dict(request.query_params)}")
    print(f"Request URL: {request.url}")
    print(f"Frontend URL: {FRONTEND_URL}")
    print(f"=====================")
    
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
            raise HTTPException(status_code=400, detail="No user info from Google")
        
        user_email = user_info.get('email')
        user_name = user_info.get('name')
        user_id = user_info.get('sub')
        user_pic = user_info.get('picture')
        
        print(f"User info: {user_email}, {user_name}")
        
        result = await db.execute(select(User).where(User.email == user_email))
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            print(f"Creating new user: {user_email}")
            db_user = User(
                email=user_email,
                name=user_name or user_email.split("@")[0],
                is_active=True,
                google_id=user_id,
                picture=user_pic or ""
            )
            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)
            print(f"New user created with ID: {db_user.id}")
        else:
            print(f"Updating existing user: {user_email}")
            if user_name:
                db_user.name = user_name
            if user_pic:
                db_user.picture = user_pic
            db_user.google_id = user_id
            await db.commit()
        
        access_token = create_access_token(data={"sub": user_id, "email": user_email})
        
        redirect_url = f"{FRONTEND_URL}/?auth=success&token={access_token}"
        response = RedirectResponse(url=redirect_url)
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,  
            samesite="none",  
            max_age=86400,  
            domain=None,  
            path="/"  
        )
        
        print(f"Setting cookie and redirecting to: {redirect_url}")
        return response
        
    except Exception as e:
        print(f"Auth error: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url=f"{FRONTEND_URL}/?auth=error&message=auth_failed")

@router.get("/user")
async def get_user(request: Request, access_token: str = Cookie(None), db: AsyncSession = Depends(get_db)):
    """Get current user with enhanced token handling"""
    print(f"=== DEBUG USER ENDPOINT ===")
    print(f"Cookie access_token: {'Present' if access_token else 'Missing'}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request cookies: {dict(request.cookies)}")
    
    token = access_token
    
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    if not token:
        print("No token found in cookie or header")
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        user_email = payload.get("email")
        
        print(f"Token decoded successfully for user: {user_email}")
        
        result = await db.execute(
            select(User).where(User.google_id == user_id)
        )
        db_user = result.scalar_one_or_none()
        
        if db_user:
            return {
                "id": db_user.id,  
                "user_id": user_id,  
                "email": user_email,
                "name": db_user.name,
                "picture": db_user.picture
            }
        else:
            return {
                "id": user_id,  
                "user_id": user_id,
                "email": user_email,
                "name": user_email.split("@")[0],  
                "picture": ""
            }
                
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url=FRONTEND_URL)
    response.delete_cookie("access_token", path="/", samesite="none", secure=True)
    return response

# Debug endpoints
@router.get("/debug-urls")
async def debug_urls(request: Request):
    """Debug URL generation"""
    return {
        "base_url": str(request.base_url),
        "url": str(request.url),
        "callback_url": str(request.url_for('auth_callback')),
        "frontend_url": FRONTEND_URL,
        "client_id": settings.CLIENT_ID[:10] + "..." if settings.CLIENT_ID else "NOT_SET"
    }