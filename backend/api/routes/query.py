from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.services.query_engine import process_query, recent_history, get_metrics, reset_metrics

router = APIRouter()


class QueryPayload(BaseModel):
    query: str
    connection_string: str | None = None
    limit: int = 50
    offset: int = 0
    doc_limit: int = 8
    doc_offset: int = 0


@router.post("/query")
async def query_endpoint(payload: QueryPayload):
    result = process_query(
        payload.query,
        connection_string=payload.connection_string,
        limit=payload.limit,
        offset=payload.offset,
        doc_limit=payload.doc_limit,
        doc_offset=payload.doc_offset,
    )
    return {"ok": True, **result}


@router.get("/query/history")
async def query_history():
    return {"ok": True, "history": recent_history()}


@router.get("/metrics")
async def metrics():
    return {"ok": True, "metrics": get_metrics()}


@router.post("/metrics/reset")
async def metrics_reset():
    reset_metrics()
    return {"ok": True}
