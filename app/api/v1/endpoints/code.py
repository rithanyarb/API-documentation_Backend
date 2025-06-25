# backend/app/api/v1/endpoints/code.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from app.services.code_parser import (
    unzip_backend_code, 
    clone_github_repo, 
    extract_python_files, 
    generate_openapi_doc,
    MAX_ZIP_SIZE,
    MAX_REPO_SIZE
)
import shutil
import asyncio
from typing import Optional
import logging

#logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

operation_status = {}

@router.post("/upload-backend-zip")
async def upload_backend_zip(
    file: UploadFile = File(...), 
    format: str = Form("json")
):
    
    #format check
    if format not in ("json", "yaml"):
        raise HTTPException(
            status_code=400, 
            detail="Invalid format. Use 'json' or 'yaml'."
        )
    
    #file type
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=400,
            detail="Only ZIP files are allowed"
        )
    
    # check file size 
    if hasattr(file, 'size') and file.size and file.size > MAX_ZIP_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_ZIP_SIZE // (1024*1024)}MB"
        )
    
    extracted_path = None
    try:
        logger.info(f"Processing ZIP file: {file.filename}")
        
        zip_bytes = await file.read()

        extracted_path = unzip_backend_code(zip_bytes)

        code, metadata = extract_python_files(extracted_path)
        
        if not code.strip():
            raise HTTPException(
                status_code=400,
                detail="No Python code files found in the ZIP archive"
            )
        
        logger.info(f"Extracted {metadata['files_processed']} Python files")
        
        #OpenAPI documentation
        openapi_doc = await generate_openapi_doc(code, format, metadata)
        
        logger.info("Successfully generated OpenAPI documentation")

        response_headers = {
            "X-Files-Processed": str(metadata['files_processed']),
            "X-Total-Lines": str(metadata['total_lines']),
            "X-Code-Truncated": str(metadata['truncated']).lower()
        }
        
        media_type = "application/x-yaml" if format == "yaml" else "application/json"
        
        return PlainTextResponse(
            content=openapi_doc, 
            media_type=media_type,
            headers=response_headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing ZIP: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )
    finally:
        if extracted_path and extracted_path.parent.exists():
            shutil.rmtree(extracted_path.parent, ignore_errors=True)

@router.post("/upload-github-repo")
async def upload_github_repo(
    repo_url: str = Form(...), 
    format: str = Form("json")
):
    
    #format Check
    if format not in ("json", "yaml"):
        raise HTTPException(
            status_code=400, 
            detail="Invalid format. Use 'json' or 'yaml'."
        )
    
    repo_path = None
    try:
        logger.info(f"Cloning repository: {repo_url}")
        
        #repository clone with size check
        repo_path, repo_size = await clone_github_repo(repo_url)
        
        logger.info(f"Repository cloned successfully. Size: {repo_size // (1024*1024)}MB")
        
        #Python files extract
        code, metadata = extract_python_files(repo_path)
        
        if not code.strip():
            raise HTTPException(
                status_code=400,
                detail="No Python code files found in the repository"
            )
        
        logger.info(f"Extracted {metadata['files_processed']} Python files from repository")
        
        #OpenAPI documentation
        openapi_doc = await generate_openapi_doc(code, format, metadata)
        
        logger.info("Successfully generated OpenAPI documentation")

        response_headers = {
            "X-Repo-Size": str(repo_size),
            "X-Files-Processed": str(metadata['files_processed']),
            "X-Total-Lines": str(metadata['total_lines']),
            "X-Code-Truncated": str(metadata['truncated']).lower()
        }
        
        media_type = "application/x-yaml" if format == "yaml" else "application/json"
        
        return PlainTextResponse(
            content=openapi_doc, 
            media_type=media_type,
            headers=response_headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing repository: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )
    finally:
        if repo_path and repo_path.parent.exists():
            shutil.rmtree(repo_path.parent, ignore_errors=True)

@router.get("/limits")
async def get_upload_limits():
    return JSONResponse({
        "max_zip_size_mb": MAX_ZIP_SIZE // (1024 * 1024),
        "max_zip_size_bytes": MAX_ZIP_SIZE,
        "max_repo_size_mb": MAX_REPO_SIZE // (1024 * 1024),
        "max_repo_size_bytes": MAX_REPO_SIZE,
        "supported_formats": ["json", "yaml"],
        "supported_file_types": [".zip"],
        "git_clone_timeout_seconds": 300
    })

@router.post("/validate-repo-url")
async def validate_repo_url(repo_url: str = Form(...)):
    """Validate GitHub repository URL without cloning"""
    import re
    
    github_patterns = [
        r'^https://github\.com/[\w.-]+/[\w.-]+/?$',
        r'^https://github\.com/[\w.-]+/[\w.-]+\.git$',
        r'^git@github\.com:[\w.-]+/[\w.-]+\.git$'
    ]
    
    is_valid = any(re.match(pattern, repo_url.strip()) for pattern in github_patterns)
    
    return JSONResponse({
        "valid": is_valid,
        "url": repo_url.strip(),
        "message": "Valid GitHub URL" if is_valid else "Invalid GitHub URL format"
    })