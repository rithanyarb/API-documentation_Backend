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
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(str(payload.openapi_url))
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to fetch OpenAPI from URL. Status: {response.status_code}"
                )
            
            # Parse JSON/YAML
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

    return await _build_upload_response(project.id, "OpenAPI uploaded and parsed successfully.")

@router.post("/upload-file", response_model=OpenAPIUploadResponse)
async def upload_openapi_file(
    file: UploadFile = File(...),
    base_url: str = None
):
    
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

    return await _build_upload_response(project.id, "OpenAPI file uploaded and parsed successfully.")

async def _build_upload_response(project_id: int, message: str) -> OpenAPIUploadResponse:
    async with async_session() as session:
        result = await session.execute(
            select(Endpoint).where(Endpoint.project_id == project_id)
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
        project_id=project_id,
        message=message,
        endpoints=endpoint_responses
    )

@router.get("/project/{project_id}/templates")
async def get_project_templates(project_id: int):
    """testing api templates"""
    
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

        version_log_result = await session.execute(
            select(VersionLog).where(VersionLog.project_id == project_id).order_by(VersionLog.timestamp.desc())
        )
        version_log = version_log_result.scalar_one_or_none()
        
        if not version_log:
            raise HTTPException(status_code=404, detail="No OpenAPI specification found for this project")
        
        openapi_spec = json.loads(version_log.raw_openapi)
    
    templates = []
    
    for endpoint in endpoints:
        print(f"\n=== Processing endpoint: {endpoint.method} {endpoint.path} ===")
        print(f"Request body raw: {endpoint.request_body}")
        
        parameters = []
        body = None
        content_type = "application/json" 
        
        content_type = extract_content_type_from_openapi(openapi_spec, endpoint.method, endpoint.path)
        print(f"Extracted content type: {content_type}")

        if endpoint.request_body:
            try:
                request_body_data = json.loads(endpoint.request_body)
                print(f"Parsed request body: {request_body_data}")
                
                if "content_type" in request_body_data:
                    content_type = request_body_data["content_type"]
                    print(f"Using content type from request body data: {content_type}")

                if "fields" in request_body_data:
                    fields = request_body_data["fields"]
                    print(f"Found fields: {fields}")
                    
                    for field_name, field_data in fields.items():
                        param_in = field_data.get("in", "body")
                        print(f"Processing field '{field_name}': in={param_in}")
                        
                        if param_in in ["query", "path", "header"]:
                            param = {
                                "name": field_name,
                                "in": param_in,
                                "required": field_data.get("required", False),
                                "schema": {
                                    "type": field_data.get("type", "string"),
                                    "title": field_data.get("title", field_name.replace("_", " ").title())
                                }
                            }
                            parameters.append(param)
                            print(f"Added parameter: {param}")
                        else:
                            if body is None:
                                body = {}
                            body[field_name] = generate_field_example(field_data)
                            print(f"Added body field: {field_name} = {body[field_name]}")
                
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
        
        # Fallback for path parameters 
        if "{" in endpoint.path and "}" in endpoint.path:
            path_params = re.findall(r'\{(\w+)\}', endpoint.path)
            for param_name in path_params:
                if not any(p["name"] == param_name for p in parameters):
                    param = {
                        "name": param_name,
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "integer" if param_name.endswith("_id") else "string",
                            "title": param_name.replace("_", " ").title()
                        }
                    }
                    parameters.append(param)
                    print(f"Added path parameter: {param}")

        url_path = endpoint.path
        if "{" in url_path and "}" in url_path:
            url_path = re.sub(r'\{(\w+)\}', lambda m: f"{{sample_{m.group(1)}}}", url_path)
        
        full_url = f"{project.base_url.rstrip('/')}{url_path}"

        headers = build_headers(content_type, endpoint.requires_auth, body is not None)

        description = await generate_description(endpoint.method, endpoint.path)
        
        #Finaltemplate
        template = {
            "endpoint_id": endpoint.id,
            "method": endpoint.method,
            "url": full_url,
            "headers": headers,
            "summary": endpoint.summary,
            "description": description,
            "requires_auth": endpoint.requires_auth,
            "parameters": parameters  
        }
        
        if body is not None:
            template["body"] = body
        
        templates.append(template)
        
        print(f"Final parameters count: {len(parameters)}")
        for i, param in enumerate(parameters):
            print(f"  {i+1}. {param['name']} ({param['in']}) - {param['schema']['type']} - required: {param['required']}")
        print(f"Template created for endpoint {endpoint.id} with Content-Type: {content_type}")
    
    print(f"\nReturning {len(templates)} templates total")
    return templates

def extract_content_type_from_openapi(openapi: dict, method: str, path: str) -> str:
    """Extract the correct content type from OpenAPI specification"""
    paths = openapi.get("paths", {})
    method_lower = method.lower()

    for openapi_path, methods in paths.items():
        if normalize_path(openapi_path) == normalize_path(path) or openapi_path == path:
            operation = methods.get(method_lower)
            if not operation:
                continue

            request_body = operation.get("requestBody", {})
            content = request_body.get("content", {})

            content_type_priority = [
                "application/x-www-form-urlencoded",
                "multipart/form-data", 
                "application/json",
                "application/xml",
                "text/plain"
            ]

            for ct in content_type_priority:
                if ct in content:
                    print(f"Found content type '{ct}' in OpenAPI spec for {method} {path}")
                    return ct

            if content:
                first_ct = list(content.keys())[0]
                print(f"Using first available content type '{first_ct}' for {method} {path}")
                return first_ct

            consumes = operation.get("consumes", [])
            for ct in content_type_priority:
                if ct in consumes:
                    print(f"Found content type '{ct}' in consumes for {method} {path}")
                    return ct
            
            if consumes:
                print(f"Using first consume type '{consumes[0]}' for {method} {path}")
                return consumes[0]

    print(f"No specific content type found for {method} {path}, using default 'application/json'")
    return "application/json"

def normalize_path(path: str) -> str:
    return re.sub(r'{\w+}', '', path.strip('/'))

def build_headers(content_type: str, requires_auth: bool, has_body: bool) -> dict:
    headers = {
        "accept": "application/json"  
    }
    
    if requires_auth:
        headers["Authorization"] = "Bearer YOUR_ACCESS_TOKEN_HERE"
    
    if has_body:
        headers["Content-Type"] = content_type
    
    return headers

def generate_request_body_template(request_body_data: dict) -> dict:
    """template request body based on the schema fields"""
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

    template = {}
    for field_name, field_info in body_fields.items():
        template[field_name] = generate_field_example(field_info)
    
    return template

def generate_field_example(field_info: dict) -> any:
    """example values"""
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
        elif "role" in title.lower():
            return "admin"
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
        elif "top_n" in title.lower():
            return 10
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