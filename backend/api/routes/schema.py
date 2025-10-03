from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.services.schema_discovery import analyze_database

router = APIRouter()


class ConnectRequest(BaseModel):
    connection_string: str


@router.post("/connect-database")
def connect_database(payload: ConnectRequest):
    try:
        cs = (payload.connection_string or "").strip()
        if not cs:
            raise ValueError("Connection string is required")
        schema = analyze_database(cs)
        return {"ok": True, "schema": schema}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
