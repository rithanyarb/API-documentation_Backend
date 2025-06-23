# === backend/app/schemas/openapi.py ===
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any

class OpenAPIUploadRequest(BaseModel):
    base_url: str
    openapi_url: HttpUrl

class EndpointResponse(BaseModel):
    id: int
    project_id: int
    path: str
    method: str
    summary: Optional[str]
    requires_auth: bool
    request_body: Optional[Dict[str, Any]]  

class OpenAPIUploadResponse(BaseModel):
    project_id: int
    message: str
    endpoints: List[EndpointResponse]