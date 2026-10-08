import json
from typing import Any

import httpx

from ..config import get_settings
from ..schemas import criteria


def _extract_content(data: dict[str, Any]) -> str:
    choices = data.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        return message.get("content", "")
    return str(data.get("output", data.get("content", "")))


async def classify_with_llm(content: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_enabled or not settings.llm_base_url or not settings.llm_api_key:
        raise RuntimeError("普通大模型兜底未配置")

    base_url = settings.llm_base_url.rstrip("/")
    url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    prompt = f"""请对下面的用户工单做结构化分流，只返回 JSON。
候选项如下：
{json.dumps(criteria(), ensure_ascii=False)}
JSON 字段必须为 category、priority、team、action、confidence、reason、needs_review。
工单内容：
{content}"""
    payload = {
        "model": settings.llm_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "你是严谨的工单分流助手。"},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        text = _extract_content(response.json()).strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)

