import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import get_stats, init_db, insert_ticket, list_tickets
from .schemas import Health, Stats, TicketCreate, TicketResult, normalize_result
from .services.jev_client import classify_with_jev, resolve_model_name, resolve_systemone_url
from .services.llm_client import classify_with_llm

logger = logging.getLogger("ticket_router")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=Health)
def health() -> Health:
    return Health(
        status="ok",
        jev_configured=bool(settings.jev_api_url and settings.jev_api_key),
        llm_fallback_configured=bool(
            settings.llm_enabled and settings.llm_base_url and settings.llm_api_key
        ),
        jev_endpoint=resolve_systemone_url(settings.jev_api_url) if settings.jev_api_url else "",
        jev_model=resolve_model_name(settings.jev_model) if settings.jev_api_url else "",
    )


@app.post("/api/tickets/analyze", response_model=TicketResult)
async def analyze_ticket(payload: TicketCreate) -> TicketResult:
    fallback_note = ""
    try:
        raw, source = await classify_with_jev(payload.content)
    except Exception as jev_error:
        logger.exception("JEV classify failed: %s", jev_error)
        if not settings.llm_enabled:
            raise HTTPException(
                status_code=502,
                detail=f"JEV 调用失败，且未启用普通大模型兜底：{jev_error}",
            ) from jev_error
        try:
            raw = await classify_with_llm(payload.content)
            source = "llm_fallback"
            fallback_note = f"JEV 失败后已切换大模型兜底：{jev_error}"
            logger.warning(fallback_note)
        except Exception as llm_error:
            raise HTTPException(
                status_code=502,
                detail=f"JEV 和普通大模型兜底均调用失败。JEV: {jev_error}; LLM: {llm_error}",
            ) from llm_error

    try:
        normalized = normalize_result(payload.content, raw, source)
        if fallback_note:
            normalized["reason"] = f"{normalized['reason']}（{fallback_note}）"
        saved = insert_ticket(normalized)
    except Exception as persist_error:
        logger.exception("Persist ticket failed: %s", persist_error)
        raise HTTPException(
            status_code=500,
            detail=f"结果落库失败：{persist_error}",
        ) from persist_error

    saved["needs_review"] = bool(saved["needs_review"])
    return TicketResult(**saved)


@app.get("/api/tickets", response_model=list[TicketResult])
def tickets(limit: int = Query(default=50, ge=1, le=200)) -> list[TicketResult]:
    items = list_tickets(limit)
    for item in items:
        item["needs_review"] = bool(item["needs_review"])
    return [TicketResult(**item) for item in items]


@app.get("/api/stats", response_model=Stats)
def stats() -> Stats:
    return Stats(**get_stats())
