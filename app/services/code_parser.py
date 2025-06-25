# backend/app/services/code_parser.py
import os
import zipfile
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Literal, Tuple
import re
from openai import AsyncOpenAI
from app.core.config import settings
from fastapi import HTTPException
import asyncio

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Constants
MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100MB 
MAX_REPO_SIZE = 500 * 1024 * 1024  # 500MB for git repos 
MAX_CODE_LENGTH = 50000  #token limit

def get_directory_size(path: Path) -> int:
    """Calculate total size of directory """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    except (OSError, IOError):
        pass  
    return total_size

def unzip_backend_code(zip_bytes: bytes) -> Path:
    """Unzip backend code and size validation"""
    zip_size = len(zip_bytes)
    if zip_size > MAX_ZIP_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"ZIP file too large. Maximum size allowed: {MAX_ZIP_SIZE // (1024*1024)}MB, got: {zip_size // (1024*1024)}MB"
        )
    
    tmp_dir = Path(tempfile.mkdtemp())
    zip_path = tmp_dir / "upload.zip"
    
    try:
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        extracted_dir = tmp_dir / "unzipped"
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            total_size = sum(file.file_size for file in zip_ref.infolist())
            if total_size > MAX_ZIP_SIZE * 10:  
                raise HTTPException(
                    status_code=413,
                    detail=f"Uncompressed size too large. Maximum allowed: {(MAX_ZIP_SIZE * 10) // (1024*1024)}MB"
                )
            
            zip_ref.extractall(extracted_dir)
        
        actual_size = get_directory_size(extracted_dir)
        if actual_size > MAX_ZIP_SIZE * 10:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=413,
                detail=f"Extracted content too large: {actual_size // (1024*1024)}MB"
            )
            
        return extracted_dir
        
    except zipfile.BadZipFile:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Invalid ZIP file format")
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to extract ZIP: {str(e)}")

def run_git_clone_sync(repo_url: str, target_dir: str) -> Tuple[int, str, str]:
    """Synchronous git clone with timeout"""
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, target_dir],
            capture_output=True,
            text=True,
            timeout=300,  # 5mins timeout
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail="Repository cloning timed out. Repository might be too large or network is slow."
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Git is not installed or not available in PATH"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during git clone: {str(e)}"
        )

async def clone_github_repo(repo_url: str) -> Tuple[Path, int]:
    """Clone GitHub repositoryand size validation with timeout"""
    if not repo_url.strip():
        raise HTTPException(status_code=400, detail="Repository URL cannot be empty")
    
    #GitHub URL format
    github_patterns = [
        r'^https://github\.com/[\w.-]+/[\w.-]+/?$',
        r'^https://github\.com/[\w.-]+/[\w.-]+\.git$',
        r'^git@github\.com:[\w.-]+/[\w.-]+\.git$'
    ]
    
    if not any(re.match(pattern, repo_url.strip()) for pattern in github_patterns):
        raise HTTPException(
            status_code=400, 
            detail="Invalid GitHub URL format. Use: https://github.com/user/repo or https://github.com/user/repo.git"
        )
    
    tmp_dir = Path(tempfile.mkdtemp()) / "repo"
    
    try:
        returncode, stdout, stderr = await asyncio.to_thread(
            run_git_clone_sync, repo_url, str(tmp_dir)
        )
        
        if returncode != 0:
            error_msg = stderr if stderr else "Unknown git error"
            shutil.rmtree(tmp_dir.parent, ignore_errors=True)
            
            if "not found" in error_msg.lower() or "repository not found" in error_msg.lower():
                raise HTTPException(status_code=404, detail="Repository not found or not accessible")
            elif "permission denied" in error_msg.lower():
                raise HTTPException(status_code=403, detail="Permission denied. Repository might be private.")
            else:
                raise HTTPException(status_code=400, detail=f"Failed to clone repository: {error_msg}")
        
        repo_size = get_directory_size(tmp_dir)
        if repo_size > MAX_REPO_SIZE:
            shutil.rmtree(tmp_dir.parent, ignore_errors=True)
            raise HTTPException(
                status_code=413,
                detail=f"Repository too large: {repo_size // (1024*1024)}MB. Maximum allowed: {MAX_REPO_SIZE // (1024*1024)}MB"
            )
        
        return tmp_dir, repo_size
        
    except HTTPException:
        raise
    except Exception as e:
        shutil.rmtree(tmp_dir.parent, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error during cloning: {str(e)}")

def extract_python_files(root_path: Path) -> Tuple[str, dict]:
    """Extracting of Python files with metadata """
    code_parts = []
    file_count = 0
    total_lines = 0
    skipped_files = []
    
    skip_patterns = [
        r'__pycache__',
        r'\.pyc$',
        r'\.git/',
        r'node_modules/',
        r'venv/',
        r'env/',
        r'\.env',
        r'migrations/',
        r'tests?/',
        r'test_.*\.py$',
        r'.*_test\.py$'
    ]
    
    for path in root_path.rglob("*.py"):
        try:
            relative_path = str(path.relative_to(root_path))
            if any(re.search(pattern, relative_path) for pattern in skip_patterns):
                skipped_files.append(relative_path)
                continue
            
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines = len(content.split('\n'))

            if lines > 1000:
                skipped_files.append(f"{relative_path} (too large: {lines} lines)")
                continue
                
            code_parts.append(f"\n\n# File: {relative_path}\n{content}")
            file_count += 1
            total_lines += lines

            if len('\n'.join(code_parts)) > MAX_CODE_LENGTH:
                break
                
        except Exception as e:
            skipped_files.append(f"{path.relative_to(root_path)} (error: {str(e)})")
            continue
    
    final_code = '\n'.join(code_parts)[:MAX_CODE_LENGTH]
    
    metadata = {
        "files_processed": file_count,
        "total_lines": total_lines,
        "skipped_files": len(skipped_files),
        "code_length": len(final_code),
        "truncated": len('\n'.join(code_parts)) > MAX_CODE_LENGTH
    }
    
    return final_code, metadata

async def generate_openapi_doc(code: str, format: Literal["json", "yaml"], metadata: dict = None) -> str:
    """OpenAPI documentation """
    if not code.strip():
        raise HTTPException(status_code=400, detail="No Python code found to analyze")
    
    system_msg = (
        "You're an expert in backend development and OpenAPI specification. "
        f"Generate a comprehensive, valid OpenAPI 3.1.0 {format.upper()} document. "
        "Return ONLY the OpenAPI content with no explanations, markdown formatting, or code fences.\n\n"
        "AUTHENTICATION DETECTION RULES:\n"
        "- Detect @login_required, @jwt_required, Depends(get_current_user), OAuth2PasswordBearer\n"
        "- Add security requirements to protected endpoints\n"
        "- Include proper securitySchemes in components\n"
        "- Public endpoints (login, register, health) should not have security requirements\n\n"
        "ANALYSIS GUIDELINES:\n"
        "- Infer request/response schemas from code patterns\n"
        "- Include proper HTTP status codes and error responses\n"
        "- Add meaningful descriptions and examples\n"
        "- Detect path parameters, query parameters, and request bodies\n"
        "- Include proper data types and validation rules"
    )

    user_msg = (
        f"Analyze this backend code and generate a complete OpenAPI 3.1.0 specification in {format.upper()} format.\n"
        f"Focus on accuracy and completeness. Do not include any explanatory text.\n\n"
    )
    
    if metadata:
        user_msg += (
            f"CODE ANALYSIS METADATA:\n"
            f"- Files processed: {metadata['files_processed']}\n"
            f"- Total lines: {metadata['total_lines']}\n"
            f"- Code truncated: {'Yes' if metadata['truncated'] else 'No'}\n\n"
        )
    
    user_msg += f"CODE TO ANALYZE:\n{code}"

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=4000,
        )

        content = response.choices[0].message.content.strip()

        content = re.sub(r"^.*?```(?:json|yaml)?\n", "", content, flags=re.DOTALL)
        content = re.sub(r"\n```.*$", "", content, flags=re.DOTALL)
        content = content.strip()
        
        if not content:
            raise HTTPException(status_code=500, detail="AI generated empty response")
            
        return content
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to generate OpenAPI documentation: {str(e)}")