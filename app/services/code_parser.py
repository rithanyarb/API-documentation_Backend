# backend/app/services/code_parser.py

import os
import zipfile
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Literal
import re
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

def unzip_backend_code(zip_bytes: bytes) -> Path:
    tmp_dir = Path(tempfile.mkdtemp())
    zip_path = tmp_dir / "upload.zip"
    with open(zip_path, "wb") as f:
        f.write(zip_bytes)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(tmp_dir / "unzipped")
    
    return tmp_dir / "unzipped"

def clone_github_repo(repo_url: str) -> Path:
    tmp_dir = Path(tempfile.mkdtemp()) / "repo"
    subprocess.run(["git", "clone", repo_url, str(tmp_dir)], check=True)
    return tmp_dir

def extract_python_files(root_path: Path) -> str:
    code = ""
    for path in root_path.rglob("*.py"):
        try:
            code += f"\n\n# File: {path.relative_to(root_path)}\n" + path.read_text(encoding="utf-8")
        except Exception:
            continue
    return code[:15000]  # token limits

async def generate_openapi_doc(code: str, format: Literal["json", "yaml"]) -> str:
    system_msg = (
        "You're an expert in backend development. Your task is to generate only a valid OpenAPI 3.1.0 "
        f"{format.upper()} document without any explanation or markdown formatting. "
        "Return only the OpenAPI content with no extra text, no markdown, no comments. "
        "\n\nIMPORTANT AUTH DETECTION RULES:\n"
        "- If an endpoint uses @login_required, jwt_required, Depends(get_current_user), "
        "OAuth2PasswordBearer, or any authentication decorator/dependency, add security requirements\n"
        "- Add 'security': [{'OAuth2PasswordBearer': []}] to endpoints that require authentication\n"
        "- Include securitySchemes in components with OAuth2PasswordBearer configuration\n"
        "- Endpoints like /auth/login, /auth/register, /auth/token should NOT have security requirements\n"
        "- Protected endpoints (like user data, protected resources) MUST have security requirements"
    )

    user_msg = (
        f"Analyze the following backend code (FastAPI/Django/Flask). "
        f"Return only a valid OpenAPI 3.1.0 specification in raw {format.upper()} format. "
        f"Do not include explanation, markdown, or code fences.\n\n"
        f"CRITICAL: Pay special attention to authentication patterns in the code:\n"
        f"- Look for authentication decorators, dependencies, or middleware\n"
        f"- Identify which endpoints require authentication vs public endpoints\n"
        f"- Add proper security requirements to protected endpoints\n"
        f"- Include securitySchemes definition in components\n\n"
        f"CODE TO ANALYZE:\n{code}"
    )

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,  
    )

    content = response.choices[0].message.content.strip()

    # Remove markdown fences and any prefix
    cleaned = re.sub(r"^.*?```(?:json|yaml)?\n", "", content, flags=re.DOTALL)
    cleaned = re.sub(r"\n```$", "", cleaned, flags=re.DOTALL)
    
    return cleaned.strip()