import json
from typing import Any

import httpx

from ..config import get_settings
from ..schemas import criteria


SYSTEM_PROMPT = """你是一个工单分流分类器。只根据输入工单，在给定候选项中进行判断。
必须返回 JSON 对象，不要返回 Markdown，不要添加候选项之外的值。
字段：category、priority、team、action、confidence、reason、needs_review。
confidence 是 0 到 1 之间的数字。无法确定时降低 confidence，并将 needs_review 设为 true。"""


def mock_classify(content: str) -> dict[str, Any]:
    text = content.lower()
    if any(word in text for word in ["盗", "异常登录", "验证码", "被封", "安全"]):
        return {
            "category": "安全问题",
            "priority": "严重",
            "team": "安全团队",
            "action": "立即升级",
            "confidence": 0.94,
            "reason": "内容涉及账号或安全风险，需要安全团队介入。",
            "needs_review": True,
        }
    if any(word in text for word in ["充值", "支付", "付款", "扣款", "余额", "订单"]):
        return {
            "category": "支付与订单",
            "priority": "普通",
            "team": "财务团队",
            "action": "转人工",
            "confidence": 0.92,
            "reason": "内容涉及支付、充值或订单状态，需要核查业务记录。",
            "needs_review": False,
        }
    if any(word in text for word in ["登录", "登陆", "密码", "账号"]):
        return {
            "category": "登录与账号",
            "priority": "紧急" if "所有人" in text or "都无法" in text else "普通",
            "team": "技术团队",
            "action": "分派团队",
            "confidence": 0.9,
            "reason": "内容涉及登录或账号使用问题，建议由技术团队排查。",
            "needs_review": False,
        }
    if any(word in text for word in ["退款", "退钱", "退回"]):
        return {
            "category": "退款申请",
            "priority": "普通",
            "team": "财务团队",
            "action": "转人工",
            "confidence": 0.91,
            "reason": "内容明确提到退款，需要人工核验订单和退款条件。",
            "needs_review": False,
        }
    if any(word in text for word in ["报错", "打不开", "崩溃", "异常", "故障"]):
        return {
            "category": "功能故障",
            "priority": "紧急" if "全部" in text or "无法使用" in text else "普通",
            "team": "技术团队",
            "action": "分派团队",
            "confidence": 0.86,
            "reason": "内容描述了功能异常，建议交由技术团队定位。",
            "needs_review": False,
        }
    return {
        "category": "其他",
        "priority": "普通",
        "team": "客服团队",
        "action": "人工复核",
        "confidence": 0.58,
        "reason": "无法从文本中稳定识别工单类型，建议人工补充判断。",
        "needs_review": True,
    }


def _extract_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        for key in ("result", "data", "output", "classification"):
            if key in value and isinstance(value[key], (dict, str)):
                return _extract_json(value[key])
        return value
    if isinstance(value, list) and value:
        return _extract_json(value[0])
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(text)
            return _extract_json(parsed)
        except json.JSONDecodeError:
            return {}
    return {}


async def classify_with_jev(content: str) -> tuple[dict[str, Any], str]:
    settings = get_settings()
    if not settings.jev_api_url or not settings.jev_api_key:
        return mock_classify(content), "mock"

    payload = {
        "model": settings.jev_model,
        "input": content,
        "criteria": criteria(),
        "system": SYSTEM_PROMPT,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.jev_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.jev_timeout_seconds) as client:
        response = await client.post(settings.jev_api_url, json=payload, headers=headers)
        response.raise_for_status()
        raw = _extract_json(response.json())
        if not raw:
            raise ValueError("JEV 返回中没有找到可解析的 JSON 分类结果")
        return raw, "jev"

