# backend/app/api/v1/endpoints/code.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.code_parser import unzip_backend_code, clone_github_repo, extract_python_files, generate_openapi_doc
from fastapi.responses import PlainTextResponse
import shutil

router = APIRouter()

@router.post("/upload-backend-zip")
async def upload_backend_zip(file: UploadFile = File(...), format: str = Form("json")):
    if format not in ("json", "yaml"):
        raise HTTPException(status_code=400, detail="Invalid format. Use 'json' or 'yaml'.")

    zip_bytes = await file.read()
    extracted_path = unzip_backend_code(zip_bytes)
    code = extract_python_files(extracted_path)
    openapi_doc = await generate_openapi_doc(code, format)

    shutil.rmtree(extracted_path.parent, ignore_errors=True)
    return PlainTextResponse(content=openapi_doc, media_type="application/x-yaml" if format == "yaml" else "application/json")

@router.post("/upload-github-repo")
async def upload_github_repo(repo_url: str = Form(...), format: str = Form("json")):
    if format not in ("json", "yaml"):
        raise HTTPException(status_code=400, detail="Invalid format. Use 'json' or 'yaml'.")

    repo_path = clone_github_repo(repo_url)
    code = extract_python_files(repo_path)
    openapi_doc = await generate_openapi_doc(code, format)

    shutil.rmtree(repo_path.parent, ignore_errors=True)
    return PlainTextResponse(content=openapi_doc, media_type="application/x-yaml" if format == "yaml" else "application/json")
