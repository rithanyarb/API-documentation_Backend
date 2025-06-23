# === backend/app/api/v1/endpoints/openapi.py ===
import json
import httpx
import re
from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.schemas.openapi import (
    OpenAPIUploadRequest,
    OpenAPIUploadResponse,
    EndpointResponse
)
from app.models.project import Project
from app.models.versionlog import VersionLog
from app.models.endpoint import Endpoint
from app.db.database import async_session
from app.services.openapi_parser import extract_endpoints, parse_openapi_content
from app.services.ai_service import generate_description

router = APIRouter()

@router.post("/upload", response_model=OpenAPIUploadResponse)
async def upload_openapi(payload: OpenAPIUploadRequest):
    """Upload OpenAPI specification from URL"""
    # Fetch the OpenAPI content from the provided URL
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(str(payload.openapi_url))
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to fetch OpenAPI from URL. Status: {response.status_code}"
                )
            
            # Parse content (JSON or YAML)
            try:
                openapi_json = parse_openapi_content(response.text)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
                
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to fetch OpenAPI from URL: {str(e)}"
            )

    try:
        project_name = openapi_json["info"]["title"]
    except KeyError:
        raise HTTPException(status_code=400, detail="Missing 'info.title' in OpenAPI specification")

    async with async_session() as session:
        project = Project(name=project_name, base_url=payload.base_url)
        session.add(project)
        await session.flush()

        version_log = VersionLog(
            project_id=project.id,
            raw_openapi=json.dumps(openapi_json)
        )
        session.add(version_log)

        await extract_endpoints(openapi_json, project.id, session)
        await session.commit()

    async with async_session() as session:
        result = await session.execute(
            select(Endpoint).where(Endpoint.project_id == project.id)
        )
        endpoints = result.scalars().all()

    endpoint_responses = [
        EndpointResponse(
            id=ep.id,
            project_id=ep.project_id,
            path=ep.path,
            method=ep.method,
            summary=ep.summary,
            requires_auth=ep.requires_auth,
            request_body=json.loads(ep.request_body) if ep.request_body else None
        )
        for ep in endpoints
    ]

    return OpenAPIUploadResponse(
        project_id=project.id,
        message="OpenAPI uploaded and parsed successfully.",
        endpoints=endpoint_responses
    )

@router.post("/upload-file", response_model=OpenAPIUploadResponse)
async def upload_openapi_file(
    file: UploadFile = File(...),
    base_url: str = None
):
    """Upload OpenAPI specification from file (JSON or YAML)"""
    
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(e)}")
    
    try:
        openapi_json = parse_openapi_content(content_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        project_name = openapi_json["info"]["title"]
    except KeyError:
        raise HTTPException(status_code=400, detail="Missing 'info.title' in OpenAPI specification")

    async with async_session() as session:
        # Create new project entry
        project = Project(name=project_name, base_url=base_url)
        session.add(project)
        await session.flush()

        version_log = VersionLog(
            project_id=project.id,
            raw_openapi=json.dumps(openapi_json)
        )
        session.add(version_log)

        await extract_endpoints(openapi_json, project.id, session)
        await session.commit()

    async with async_session() as session:
        result = await session.execute(
            select(Endpoint).where(Endpoint.project_id == project.id)
        )
        endpoints = result.scalars().all()

    endpoint_responses = [
        EndpointResponse(
            id=ep.id,
            project_id=ep.project_id,
            path=ep.path,
            method=ep.method,
            summary=ep.summary,
            requires_auth=ep.requires_auth,
            request_body=json.loads(ep.request_body) if ep.request_body else None
        )
        for ep in endpoints
    ]

    return OpenAPIUploadResponse(
        project_id=project.id,
        message="OpenAPI file uploaded and parsed successfully.",
        endpoints=endpoint_responses
    )

@router.get("/project/{project_id}/templates")
async def get_project_templates(project_id: int):
    """Generate API testing templates for all endpoints in a project"""
    
    async with async_session() as session:
        project_result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        endpoints_result = await session.execute(
            select(Endpoint).where(Endpoint.project_id == project_id)
        )
        endpoints = endpoints_result.scalars().all()
        
        if not endpoints:
            raise HTTPException(status_code=404, detail="No endpoints found for this project")
    
    templates = []
    
    for endpoint in endpoints:
        request_body_data = None
        if endpoint.request_body:
            try:
                request_body_data = json.loads(endpoint.request_body)
            except json.JSONDecodeError:
                request_body_data = None

        url_path = endpoint.path
        if "{" in url_path and "}" in url_path:
            url_path = re.sub(r'\{(\w+)\}', lambda m: f"{{sample_{m.group(1)}}}", url_path)
        
        full_url = f"{project.base_url.rstrip('/')}{url_path}"

        headers = {"accept": "application/json"}

        if endpoint.requires_auth:
            headers["Authorization"] = "Bearer YOUR_ACCESS_TOKEN_HERE"

        if request_body_data and "content_type" in request_body_data:
            headers["Content-Type"] = request_body_data["content_type"]
        elif request_body_data:
            headers["Content-Type"] = "application/json"

        body = None
        if request_body_data and "fields" in request_body_data:
            body = generate_request_body_template(request_body_data)
        
        description = await generate_description(endpoint.method, endpoint.path)
        
        template = {
            "endpoint_id": endpoint.id,
            "method": endpoint.method,
            "url": full_url,
            "headers": headers,
            "summary": endpoint.summary,
            "description": description,
            "requires_auth": endpoint.requires_auth,  
        }
        
        if body is not None:
            template["body"] = body
            
        templates.append(template)
    
    return templates

def generate_request_body_template(request_body_data: dict) -> dict:
    """Generate a template request body based on the schema fields"""
    fields = request_body_data.get("fields", {})
    content_type = request_body_data.get("content_type", "application/json")
    
    if not fields:
        return None

    body_fields = {
        name: field for name, field in fields.items() 
        if field.get("in") not in ["path", "header", "query"]
    }
    
    if not body_fields:
        return None

    if content_type == "application/x-www-form-urlencoded":
        template = {}
        for field_name, field_info in body_fields.items():
            template[field_name] = generate_field_example(field_info)
        return template
    else:
        template = {}
        for field_name, field_info in body_fields.items():
            template[field_name] = generate_field_example(field_info)
        return template

def generate_field_example(field_info: dict) -> any:
    """Generate an example value for a field based on its type and constraints"""
    field_type = field_info.get("type", "string")
    field_format = field_info.get("format")
    min_length = field_info.get("minLength")
    max_length = field_info.get("maxLength")
    title = field_info.get("title", "")
    
    if field_type == "string":
        if field_format == "password":
            return "your_password_here"
        elif field_format == "email":
            return "user@example.com"
        elif "email" in title.lower():
            return "user@example.com"
        elif "username" in title.lower() or "user_name" in title.lower():
            return "your_username"
        elif "token" in title.lower():
            return "your_token_here"
        elif "title" in title.lower():
            return "Sample Title"
        elif "content" in title.lower():
            return "Sample content"
        elif "name" in title.lower():
            return "Sample Name"
        else:
            base_text = "sample_text"
            if min_length:
                if len(base_text) < min_length:
                    base_text = base_text + "_" + "x" * (min_length - len(base_text) - 1)
            if max_length:
                base_text = base_text[:max_length]
            return base_text
    
    elif field_type == "integer":
        minimum = field_info.get("minimum", 1)
        maximum = field_info.get("maximum", 100)
        if "id" in title.lower():
            return 1
        return max(minimum, 1) if minimum else 1
    
    elif field_type == "number":
        return 1.0
    
    elif field_type == "boolean":
        return True
    
    elif field_type == "array":
        return []
    
    elif field_type == "object":
        return {}
    
    else:
        return f"sample_{field_type}"