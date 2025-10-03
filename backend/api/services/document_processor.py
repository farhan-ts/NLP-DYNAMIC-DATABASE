from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import threading
import time
from typing import Any, Dict, List, Tuple

from sentence_transformers import SentenceTransformer
from docx import Document as DocxDocument
from pypdf import PdfReader


STORAGE_DIR = os.path.join(os.getcwd(), "storage")
DB_PATH = os.path.join(STORAGE_DIR, "ingestion.db")

_model_lock = threading.Lock()
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    with _model_lock:
        if _model is None:
            # all-MiniLM-L6-v2: compact, fast
            _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return _model


def init_storage() -> None:
    os.makedirs(STORAGE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Jobs track ingestion progress
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT,
            total_files INTEGER,
            processed_files INTEGER,
            created_at REAL,
            updated_at REAL,
            error TEXT
        )
        """
    )
    # Documents table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            filename TEXT,
            doc_type TEXT
        )
        """
    )
    # Chunks table (store embedding as BLOB of float32 bytes)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            chunk_index INTEGER,
            text TEXT,
            embedding BLOB,
            dim INTEGER,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
        """
    )
    conn.commit()
    conn.close()


def _detect_doc_type(filename: str, content_type: str | None) -> str:
    fname = filename.lower()
    if fname.endswith(".pdf") or (content_type and "pdf" in content_type.lower()):
        return "pdf"
    if fname.endswith(".docx") or (content_type and "word" in content_type.lower()):
        return "docx"
    if fname.endswith(".csv") or (content_type and "csv" in content_type.lower()):
        return "csv"
    return "txt"


def _extract_text(file_bytes: bytes, doc_type: str) -> str:
    if doc_type == "pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        texts: List[str] = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                texts.append("")
        return "\n\n".join(texts).strip()
    if doc_type == "docx":
        f = io.BytesIO(file_bytes)
        doc = DocxDocument(f)
        return "\n\n".join(p.text for p in doc.paragraphs).strip()
    if doc_type == "csv":
        # Parse CSV into a simple markdown-like table textual form
        buf = io.StringIO(file_bytes.decode("utf-8", errors="ignore"))
        reader = csv.reader(buf)
        lines = [", ".join(row) for row in reader]
        return "\n".join(lines)
    # txt
    try:
        return file_bytes.decode("utf-8")
    except Exception:
        return file_bytes.decode("latin-1", errors="ignore")


def dynamic_chunking(content: str, doc_type: str) -> List[str]:
    content = content.strip()
    if not content:
        return []

    # Heuristics:
    if doc_type in ("pdf", "docx", "txt"):
        lowered = content.lower()
        # Resumes: try to keep sections together
        if any(k in lowered for k in ["skills", "experience", "education", "projects"]):
            sections = re.split(r"\n\s*(?=skills|experience|education|projects)\b", lowered)
            chunks = [s.strip() for s in sections if s.strip()]
            if chunks:
                return chunks
        # Contracts: split by numbered clauses
        if re.search(r"\n\s*\d+\.\s+", content):
            clauses = re.split(r"\n\s*(?=\d+\.)", content)
            return [c.strip() for c in clauses if c.strip()]
        # Reviews / general: paragraph-based
        paragraphs = re.split(r"\n\s*\n", content)
        # Further chunk paragraphs to ~500-800 chars for embedding efficiency
        return _chunk_by_size(paragraphs, max_chars=800)
    if doc_type == "csv":
        lines = content.splitlines()
        return _chunk_by_size(lines, max_chars=800)
    # Fallback
    return _chunk_by_size([content], max_chars=800)


def _chunk_by_size(units: List[str], max_chars: int = 800) -> List[str]:
    chunks: List[str] = []
    buf = ""
    for u in units:
        if len(buf) + len(u) + 1 <= max_chars:
            buf = f"{buf}\n{u}" if buf else u
        else:
            if buf:
                chunks.append(buf.strip())
            buf = u
    if buf:
        chunks.append(buf.strip())
    return [c for c in chunks if c]


def _embed_chunks(chunks: List[str], batch_size: int = 64) -> Tuple[List[bytes], int]:
    """Embed in batches to avoid memory spikes on large documents."""
    model = _get_model()
    all_blobs: List[bytes] = []
    dim: int | None = None
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vecs = model.encode(batch, convert_to_numpy=True, normalize_embeddings=True)
        vecs = vecs.astype("float32")
        if dim is None:
            dim = vecs.shape[1] if len(vecs.shape) == 2 else len(vecs)
        all_blobs.extend([v.tobytes() for v in vecs])
    return all_blobs, int(dim or 0)


def _update_job(job_id: str, **fields: Any) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    sets = ", ".join([f"{k} = ?" for k in fields.keys()])
    params = list(fields.values()) + [job_id]
    cur.execute(f"UPDATE jobs SET {sets}, updated_at = ? WHERE id = ?", params[:-1] + [time.time()] + [job_id])
    conn.commit()
    conn.close()


def _insert_job(job_id: str, total_files: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO jobs (id, status, total_files, processed_files, created_at, updated_at, error) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (job_id, "running", total_files, 0, time.time(), time.time(), None),
    )
    conn.commit()
    conn.close()


def _insert_document(job_id: str, filename: str, doc_type: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documents (job_id, filename, doc_type) VALUES (?, ?, ?)",
        (job_id, filename, doc_type),
    )
    doc_id = cur.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def _insert_chunks(document_id: int, chunks: List[str], embeddings: List[bytes], dim: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    rows = [(document_id, i, chunks[i], embeddings[i], dim) for i in range(len(chunks))]
    cur.executemany(
        "INSERT INTO chunks (document_id, chunk_index, text, embedding, dim) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def start_ingestion_job(job_id: str, files: List[Tuple[str, bytes, str | None]]) -> None:
    """Process files sequentially; update job status; store embeddings in SQLite.
    files: list of (filename, content_bytes, content_type)
    """
    init_storage()
    _insert_job(job_id, total_files=len(files))

    processed = 0
    try:
        for (filename, data, content_type) in files:
            doc_type = _detect_doc_type(filename, content_type)
            text = _extract_text(data, doc_type)
            chunks = dynamic_chunking(text, doc_type)
            if not chunks:
                processed += 1
                _update_job(job_id, processed_files=processed)
                continue
            # Safety: cap chunks to avoid extreme sizes
            if len(chunks) > 5000:
                chunks = chunks[:5000]
            embs, dim = _embed_chunks(chunks, batch_size=64)
            doc_id = _insert_document(job_id, filename, doc_type)
            _insert_chunks(doc_id, chunks, embs, dim)
            processed += 1
            _update_job(job_id, processed_files=processed)

        _update_job(job_id, status="completed")
    except Exception as e:
        _update_job(job_id, status="failed", error=str(e))


def create_job_record(job_id: str, total_files: int) -> None:
    """Create a job row synchronously so clients can poll immediately."""
    init_storage()
    _insert_job(job_id, total_files=total_files)


def get_job_status(job_id: str) -> Dict[str, Any]:
    init_storage()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, status, total_files, processed_files, created_at, updated_at, error FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"job_id": job_id, "status": "not_found"}
    return {
        "job_id": row[0],
        "status": row[1],
        "total_files": row[2],
        "processed_files": row[3],
        "created_at": row[4],
        "updated_at": row[5],
        "error": row[6],
    }


def reset_ingestion() -> None:
    """Destructively clear all ingestion data: jobs, documents, chunks."""
    init_storage()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Order matters due to FK from chunks -> documents
    cur.execute("DELETE FROM chunks")
    cur.execute("DELETE FROM documents")
    cur.execute("DELETE FROM jobs")
    conn.commit()
    try:
        cur.execute("VACUUM")
    except Exception:
        pass
    conn.close()
