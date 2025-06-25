#backend/app/api/v1/endpoints/test.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Union, Dict
import httpx
import json
import re
from app.services.ai_service import generate_description
from app.db.database import get_db
from app.models.endpoint import Endpoint
from app.models.project import Project
from app.models.versionlog import VersionLog
import yaml
from fastapi import UploadFile, File
from uuid import uuid4
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

class EndpointTestRequest(BaseModel):
    method: str
    url: str
    headers: Dict[str, str] = {}
    body: Union[str, dict, None] = None


@router.post("/test-endpoint")
async def test_single_endpoint(data: EndpointTestRequest):
    try:
        logger.info(f"Testing endpoint: {data.method} {data.url}")
        
        timeout = httpx.Timeout(100.0, connect=10.0)  # 100s total, 10s connect
        
        async with httpx.AsyncClient(
            follow_redirects=True, 
            timeout=timeout,
            verify=False  
        ) as client:
            headers = data.headers.copy()
            content_type = headers.get("Content-Type", "application/json")

            headers = {k: v for k, v in headers.items() if v is not None and v != ""}
            
            logger.info(f"Request headers: {headers}")
            logger.info(f"Request body: {data.body}")

            if content_type == "application/x-www-form-urlencoded" and isinstance(data.body, dict):
                response = await client.request(
                    method=data.method.upper(),
                    url=data.url,
                    headers=headers,
                    data=data.body
                )
            elif content_type == "multipart/form-data" and isinstance(data.body, dict):
                multipart_headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
                multipart_data = {k: (None, v) for k, v in data.body.items()}
                response = await client.request(
                    method=data.method.upper(),
                    url=data.url,
                    headers=multipart_headers,
                    files=multipart_data
                )
            else:
                if data.body is None:
                    response = await client.request(
                        method=data.method.upper(),
                        url=data.url,
                        headers=headers
                    )
                elif isinstance(data.body, str):
                    response = await client.request(
                        method=data.method.upper(),
                        url=data.url,
                        headers=headers,
                        content=data.body
                    )
                else:
                    response = await client.request(
                        method=data.method.upper(),
                        url=data.url,
                        headers=headers,
                        json=data.body
                    )

        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")

        return {
            "status_code": response.status_code,
            "response_body": response.text,
            "response_headers": dict(response.headers),
            "request_url": str(response.request.url),
            "method": data.method.upper()
        }

    except httpx.TimeoutException as e:
        logger.error(f"Timeout error: {str(e)}")
        raise HTTPException(
            status_code=408, 
            detail=f"Request timeout: The target server took too long to respond"
        )
    except httpx.ConnectError as e:
        logger.error(f"Connection error: {str(e)}")
        raise HTTPException(
            status_code=503, 
            detail=f"Cannot connect to target server: {data.url}. Make sure the server is running and accessible."
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP status error: {str(e)}")
        return {
            "status_code": e.response.status_code,
            "response_body": e.response.text,
            "response_headers": dict(e.response.headers),
            "request_url": str(e.request.url),
            "method": data.method.upper()
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Test failed: {str(e)}"
        )


def normalize_path(p: str) -> str:
    return re.sub(r'{\w+}', '', p.strip('/'))


def extract_content_type_from_openapi(openapi: dict, method: str, path: str) -> str:
    paths = openapi.get("paths", {})
    method = method.lower()

    for openapi_path, methods in paths.items():
        if normalize_path(openapi_path) == normalize_path(path):
            op = methods.get(method)
            if not op:
                continue

            content = op.get("requestBody", {}).get("content", {})
            for ct in ["multipart/form-data", "application/x-www-form-urlencoded", "application/json"]:
                if ct in content:
                    return ct

            consumes = op.get("consumes", [])
            for ct in consumes:
                if ct in ["multipart/form-data", "application/x-www-form-urlencoded", "application/json"]:
                    return ct

    return "application/json"


def generate_sample_value(prop: dict) -> Union[str, int, float, bool, list, dict]:
    t = prop.get("type", "string")
    fmt = prop.get("format", "")
    enum = prop.get("enum")

    if enum:
        return enum[0]

    if t == "string":
        return prop.get("example", prop.get("title", "string"))
    if t == "integer":
        return 0
    if t == "number":
        return 0.0
    if t == "boolean":
        return True
    if t == "array":
        item_schema = prop.get("items", {})
        return [generate_sample_value(item_schema)]
    if t == "object":
        return generate_sample_body(prop)

    return "string"


def generate_sample_body(schema: dict) -> dict:
    result = {}
    props = schema.get("properties", {})
    for key, prop in props.items():
        if "$ref" in prop:
            continue 
        result[key] = generate_sample_value(prop)
    return result