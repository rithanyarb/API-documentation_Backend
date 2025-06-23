# backend/app/api/v1/endpoints/curl.py
from fastapi import APIRouter, HTTPException
from app.schemas.curl import CurlUploadRequest, CurlUploadResponse
from app.models.project import Project
from app.models.endpoint import Endpoint
from app.models.versionlog import VersionLog
from app.services.curl_parser import parse_curl
from app.db.database import async_session
import json

router = APIRouter()

@router.post("/upload", response_model=CurlUploadResponse)
async def upload_curl(payload: CurlUploadRequest):
    try:
        parsed = parse_curl(payload.curl)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse curl: {str(e)}")

    async with async_session() as session:
        project = Project(name="From cURL", base_url=parsed["base_url"])
        session.add(project)
        await session.flush()  # Get project.id

        endpoint = Endpoint(
            project_id=project.id,
            path=parsed["path"],
            method=parsed["method"],
            summary="Parsed from cURL",
            requires_auth=parsed["requires_auth"],
            request_body=parsed["request_body"]
        )
        session.add(endpoint)

        version_log = VersionLog(
            project_id=project.id,
            raw_openapi=json.dumps({
                "parsed_from": "curl",
                "curl": payload.curl,
                "headers": parsed["headers"],
                "body": parsed["body"]
            })
        )
        session.add(version_log)

        await session.commit()

        return CurlUploadResponse(project_id=project.id, message="cURL command uploaded and parsed.")
