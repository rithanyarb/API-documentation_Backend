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
        print(f"Parsed cURL data: {parsed}")
    except Exception as e:
        print(f"Failed to parse curl: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to parse curl: {str(e)}")

    async with async_session() as session:
        try:
            #project table
            project = Project(name="From cURL", base_url=parsed["base_url"])
            session.add(project)
            await session.flush()  

            request_body_data = None
            if parsed["request_body"]:
                request_body_data = parsed["request_body"]
            elif parsed["parameters"]:
                fields = {}
                for param in parsed["parameters"]:
                    fields[param["name"]] = {
                        "type": param["schema"]["type"],
                        "title": param.get("description", param["name"]),
                        "in": param["in"],
                        "required": param["required"],
                        "example": param["schema"].get("example", "")
                    }
                
                request_body_data = json.dumps({
                    "fields": fields,
                    "content_type": "application/json"
                })

            #endpoint table
            endpoint = Endpoint(
                project_id=project.id,
                path=parsed["path"],
                method=parsed["method"],
                summary="Parsed from cURL",
                requires_auth=parsed["requires_auth"],
                request_body=request_body_data
            )
            session.add(endpoint)

            #version log table
            version_log = VersionLog(
                project_id=project.id,
                raw_openapi=json.dumps({
                    "parsed_from": "curl",
                    "curl": payload.curl,
                    "headers": parsed["headers"],
                    "body": parsed["body"],
                    "parameters": parsed["parameters"]
                })
            )
            session.add(version_log)

            await session.commit()
            print(f"Successfully created project {project.id} with endpoint")

            return CurlUploadResponse(
                project_id=project.id, 
                message="cURL command uploaded and parsed."
            )
            
        except Exception as e:
            await session.rollback()
            print(f"Database error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")