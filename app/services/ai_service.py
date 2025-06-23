# === backend/app/services/ai_service.py ===
from openai import AsyncOpenAI
from app.core.config import settings
from typing import Optional
import json

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
async def generate_description(method: str, path: str, summary: str = "") -> str:
    prompt = (
        f"You are an API documentation generator.\n"
        f"Generate a clear, concise, and helpful 2 line description for the following API endpoint.\n"
        f"Use the summary as background info only — do NOT include or rephrase it.\n\n"
        f"- Method: {method}\n"
        f"- Path: {path}\n"
        f"- Summary (for context only): \"{summary or 'N/A'}\"\n\n"
        f"Focus on describing what this endpoint *does* technically:\n"
        f"- Mention required parameters, request/response behavior, or usage constraints.\n"
        f"- Avoid vague phrases like 'this endpoint allows you to...'\n"
        f"- Do NOT return any markdown, quotes, or formatting — just raw text.\n\n"
        f"Description:"
    )
    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"(AI description unavailable: {e})"