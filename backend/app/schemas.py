from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


CATEGORIES = [
    "登录与账号",
    "支付与订单",
    "功能故障",
    "退款申请",
    "安全问题",
    "功能咨询",
    "其他",
]
PRIORITIES = ["普通", "紧急", "严重"]
TEAMS = ["客服团队", "技术团队", "财务团队", "安全团队"]
ACTIONS = ["自动回复", "转人工", "分派团队", "立即升级", "人工复核"]


class TicketCreate(BaseModel):
    content: str = Field(min_length=2, max_length=5000)


class TicketResult(BaseModel):
    id: Optional[int] = None
    content: str
    category: str
    priority: str
    team: str
    action: str
    confidence: float = Field(ge=0, le=1)
    reason: str
    needs_review: bool
    source: Literal["jev", "llm_fallback", "mock"]
    created_at: Optional[str] = None


class Stats(BaseModel):
    total: int
    needs_review: int
    auto_routed: int
    by_team: dict[str, int]


class Health(BaseModel):
    status: str
    jev_configured: bool
    llm_fallback_configured: bool


def criteria() -> dict[str, list[str]]:
    return {
        "category": CATEGORIES,
        "priority": PRIORITIES,
        "team": TEAMS,
        "action": ACTIONS,
    }


def normalize_result(content: str, raw: dict[str, Any], source: str) -> dict[str, Any]:
    category = raw.get("category", "其他")
    priority = raw.get("priority", "普通")
    team = raw.get("team", "客服团队")
    action = raw.get("action", "人工复核")
    confidence = float(raw.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))
    reason = str(raw.get("reason", "模型未提供详细原因"))

    needs_review = bool(raw.get("needs_review", False))
    if category not in CATEGORIES:
        category = "其他"
        needs_review = True
    if priority not in PRIORITIES:
        priority = "普通"
        needs_review = True
    if team not in TEAMS:
        team = "客服团队"
        needs_review = True
    if action not in ACTIONS:
        action = "人工复核"
        needs_review = True

    if confidence < 0.8:
        needs_review = True
        action = "人工复核"
    if category == "安全问题":
        team = "安全团队"
        action = "立即升级"
        needs_review = True
    if priority == "严重":
        action = "立即升级"

    return {
        "content": content,
        "category": category,
        "priority": priority,
        "team": team,
        "action": action,
        "confidence": confidence,
        "reason": reason,
        "needs_review": needs_review,
        "source": source,
    }
