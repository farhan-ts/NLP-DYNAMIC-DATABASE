from __future__ import annotations

import secrets
from typing import List

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel

from backend.api.services.document_processor import (
    start_ingestion_job,
    get_job_status,
    init_storage,
    create_job_record,
    reset_ingestion,
)

router = APIRouter()


@router.post("/upload-documents")
async def upload_documents(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """Accept multiple files, start background ingestion job, return job_id."""
    init_storage()
    job_id = secrets.token_hex(8)

    # Read files into memory (small to moderate docs; OK for assignment scope)
    file_payload = []
    for f in files:
        data = await f.read()
        file_payload.append((f.filename, data, f.content_type))

    # Create job row now so clients can poll immediately
    create_job_record(job_id, total_files=len(file_payload))
    background_tasks.add_task(start_ingestion_job, job_id, file_payload)
    return {"ok": True, "job_id": job_id}


@router.get("/ingestion-status/{job_id}")
def ingestion_status(job_id: str):
    status = get_job_status(job_id)
    return {"ok": True, **status}


class ResetPayload(BaseModel):
    confirm: bool = False


@router.post("/ingestion/reset")
async def ingestion_reset(payload: ResetPayload):
    """Destructively delete all documents, chunks, and jobs. Requires confirm=true."""
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Set 'confirm': true to proceed. This deletes all ingested data.")
    reset_ingestion()
    return {"ok": True}
