import json
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from ..config import get_settings
from ..schemas import ACTIONS, CATEGORIES, PRIORITIES, TEAMS


SYSTEMONE_PATH = "/v1/systemone"
DEFAULT_MODEL = "jev-latest"


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


def resolve_systemone_url(raw_url: str) -> str:
    url = (raw_url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith(SYSTEMONE_PATH):
        return url
    if url.endswith("/v1"):
        return f"{url}/systemone"
    return urljoin(url + "/", "v1/systemone")


def resolve_model_name(raw_model: str) -> str:
    model = (raw_model or "").strip()
    if not model or model.lower() in {"jev", "systemone", "system-one"}:
        return DEFAULT_MODEL
    return model


def _choice(instructions: str, options: list[str], descriptions: Optional[dict[str, str]] = None) -> dict[str, Any]:
    descriptions = descriptions or {}
    return {
        "type": "choice",
        "instructions": instructions,
        "criteria": {option: descriptions.get(option) for option in options},
    }


def _noul(instructions: str, true: str, false: str) -> dict[str, Any]:
    return {
        "type": "noul",
        "instructions": instructions,
        "criteria": {"true": true, "false": false},
    }


def build_questions() -> dict[str, Any]:
    return {
        "category": _choice(
            "Pick exactly one primary support category for this ticket.",
            CATEGORIES,
            {
                "登录与账号": "Cannot log in, password reset, account locked, session expired",
                "支付与订单": "Top-up not credited, payment failed, missing order, billing mismatch",
                "功能故障": "App/page crash, error message, feature broken, service unavailable",
                "退款申请": "User explicitly asks for a refund or refund progress",
                "安全问题": "Stolen account, suspicious login, verification abuse, fraud risk",
                "功能咨询": "How-to question with no outage, no payment loss, no security risk",
                "其他": "Only if the ticket does not clearly fit any category above",
            },
        ),
        "priority": _choice(
            "Choose priority using blast radius, not how upset the user sounds.",
            PRIORITIES,
            {
                "普通": "One user or a few users; core platform still works. Includes single-user payment/refund issues.",
                "紧急": "Many users impacted, or a core workflow is blocked for a group of users right now.",
                "严重": "Company-wide outage, confirmed security incident, or systemic financial risk.",
            },
        ),
        "team": _choice(
            "Which team should own the next handling step?",
            TEAMS,
            {
                "客服团队": "Clarification, status check, or general customer support",
                "技术团队": "Engineering investigation for bugs, login outages, product failures",
                "财务团队": "Payments, top-ups, refunds, billing records, finance verification",
                "安全团队": "Account compromise, fraud, abuse, security incidents",
            },
        ),
        "action": _choice(
            "Choose the best next routing action. Prefer concrete routing over review when category and team are clear.",
            ACTIONS,
            {
                "自动回复": "Simple FAQ that can be answered with a standard template",
                "转人工": "Needs an agent conversation, but destination team is already clear",
                "分派团队": "Information is enough to put the ticket into the owning team queue",
                "立即升级": "Severe outage/security/financial risk that must escalate now",
                "人工复核": "Only when category or owning team is still unclear",
            },
        ),
        "needs_review": _noul(
            "Is a pre-routing human review required before assigning the owning team?",
            true="Category or owning team is ambiguous, conflicting, or missing key facts needed for routing",
            false="Category and owning team are already clear enough to route now, even if an agent still needs to process payment/refund details later",
        ),
    }


def _extract_answers(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for key in ("answers", "result", "data", "output"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    # Some responses may put question ids at the top level.
    if any(isinstance(payload.get(key), dict) and "type" in payload.get(key, {}) for key in build_questions()):
        return payload
    return {}


def _choice_value(answer: Optional[dict[str, Any]], fallback: str) -> tuple[str, float]:
    if not isinstance(answer, dict):
        return fallback, 0.0
    value = answer.get("choice") or fallback
    confidence = answer.get("confidence")
    if confidence is None:
        probs = answer.get("probabilities") or {}
        confidence = max(probs.values()) if probs else 0.0
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    return str(value), max(0.0, min(1.0, confidence))


def _noul_value(answer: Optional[dict[str, Any]]) -> tuple[bool, float]:
    if not isinstance(answer, dict):
        return True, 0.0
    probability = answer.get("noul")
    try:
        probability = float(probability)
    except (TypeError, ValueError):
        probability = 0.5
    return probability >= 0.5, probability


def map_systemone_result(payload: dict[str, Any]) -> dict[str, Any]:
    answers = _extract_answers(payload)
    if not answers:
        raise ValueError(f"JEV 返回中没有 answers 字段: {json.dumps(payload, ensure_ascii=False)[:500]}")

    category, category_conf = _choice_value(answers.get("category"), "其他")
    priority, priority_conf = _choice_value(answers.get("priority"), "普通")
    team, team_conf = _choice_value(answers.get("team"), "客服团队")
    action, action_conf = _choice_value(answers.get("action"), "人工复核")
    _, review_prob = _noul_value(answers.get("needs_review"))

    # 主置信度只看「类别 + 团队」
    confidence = min(category_conf, team_conf)
    routing_clear = category != "其他" and confidence >= 0.8

    # 关键分流清晰时，不再因为 JEV 把“后续要人处理”说成 review
    # 就显示“需要人工复核”。支付核实、退款沟通 = 转人工/分派团队。
    needs_review = False
    override_note = ""
    if category == "安全问题":
        needs_review = True
        action = "立即升级"
        team = "安全团队"
        override_note = "命中安全问题，强制升级安全团队。"
    elif not routing_clear:
        needs_review = True
        action = "人工复核"
        override_note = "主分流结论不够清晰，进入预分流人工复核。"
    else:
        # 主结论已清楚：覆盖 JEV 的“人工复核”动作
        if action == "人工复核" or review_prob >= 0.5:
            action = "转人工" if category in {"支付与订单", "退款申请", "功能咨询", "登录与账号"} else "分派团队"
            override_note = (
                f"JEV 给出的预分流复核概率为 {review_prob:.0%}，"
                "但类别和团队已足够清晰，改为自动分流到目标团队。"
            )
        needs_review = False

    reason = (
        f"主置信度按「类别+团队」计算：类别「{category}」({category_conf:.0%})，"
        f"团队「{team}」({team_conf:.0%})；"
        f"优先级「{priority}」({priority_conf:.0%})，"
        f"动作「{action}」({action_conf:.0%})。"
    )
    if override_note:
        reason += override_note
    else:
        reason += f"预分流复核概率约为 {review_prob:.0%}。"

    return {
        "category": category,
        "priority": priority,
        "team": team,
        "action": action,
        "confidence": confidence,
        "reason": reason,
        "needs_review": needs_review,
        "category_confidence": category_conf,
        "team_confidence": team_conf,
        "priority_confidence": priority_conf,
        "action_confidence": action_conf,
        "review_probability": review_prob,
    }


async def classify_with_jev(content: str) -> tuple[dict[str, Any], str]:
    settings = get_settings()
    if not settings.jev_api_url or not settings.jev_api_key:
        return mock_classify(content), "mock"

    url = resolve_systemone_url(settings.jev_api_url)
    model = resolve_model_name(settings.jev_model)
    payload = {
        "state": content,
        "model": model,
        "questions": build_questions(),
    }
    headers = {
        "Authorization": f"Bearer {settings.jev_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.jev_timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            detail = response.text[:800]
            raise RuntimeError(f"JEV HTTP {response.status_code}: {detail}")
        raw = map_systemone_result(response.json())
        return raw, "jev"
