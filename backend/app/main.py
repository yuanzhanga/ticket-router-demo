from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import get_stats, init_db, insert_ticket, list_tickets
from .schemas import Health, Stats, TicketCreate, TicketResult, normalize_result
from .services.jev_client import classify_with_jev
from .services.llm_client import classify_with_llm


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
    )


@app.post("/api/tickets/analyze", response_model=TicketResult)
async def analyze_ticket(payload: TicketCreate) -> TicketResult:
    try:
        raw, source = await classify_with_jev(payload.content)
    except Exception as jev_error:
        if not settings.llm_enabled:
            raise HTTPException(
                status_code=502,
                detail=f"JEV 调用失败，且未启用普通大模型兜底：{jev_error}",
            ) from jev_error
        try:
            raw = await classify_with_llm(payload.content)
            source = "llm_fallback"
        except Exception as llm_error:
            raise HTTPException(
                status_code=502,
                detail=f"JEV 和普通大模型兜底均调用失败：{llm_error}",
            ) from llm_error

    normalized = normalize_result(payload.content, raw, source)
    saved = insert_ticket(normalized)
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
