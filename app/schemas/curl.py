# backend/app/schemas/curl.py
from pydantic import BaseModel

class CurlUploadRequest(BaseModel):
    curl: str

class CurlUploadResponse(BaseModel):
    project_id: int
    message: str
