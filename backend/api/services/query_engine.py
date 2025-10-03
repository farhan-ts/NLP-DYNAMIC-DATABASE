# Placeholder for unified query engine
# Responsibilities (future):
# - Classify user query into SQL / doc / hybrid
# - For SQL: generate SQL from NL using schema + LLM or rules
# - For docs: embedding search over processed chunks
# - Hybrid: merge and rank results

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from sentence_transformers import SentenceTransformer
import numpy as np
try:
    from backend.nlp.intent_model import predict_intent as ml_predict_intent
except Exception:  # fallback if sklearn missing at runtime
    ml_predict_intent = None


STORAGE_DIR = os.path.join(os.getcwd(), "storage")
INGEST_DB = os.path.join(STORAGE_DIR, "ingestion.db")


# ------------------------- Simple LRU Cache -------------------------
class LRUCache:
    def __init__(self, capacity: int = 64):
        self.capacity = capacity
        self._cache: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)


_cache = LRUCache(capacity=100)
_history: List[Dict[str, Any]] = []
_model: SentenceTransformer | None = None

# ------------------------- Metrics -------------------------
_metrics = {
    "total_queries": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "exec_times": [],  # seconds list (trimmed)
    "active_queries": 0,
    "active_connections": 0,
}

def _record_time(elapsed: float) -> None:
    _metrics["exec_times"].append(elapsed)
    if len(_metrics["exec_times"]) > 500:
        del _metrics["exec_times"][:-500]

def _inc(name: str, delta: int = 1) -> None:
    _metrics[name] = _metrics.get(name, 0) + delta

def _with_active_query(fn, *args, **kwargs):
    _inc("active_queries", 1)
    try:
        return fn(*args, **kwargs)
    finally:
        _inc("active_queries", -1)


# ------------------------- Engine Pooling -------------------------
_engine_cache: Dict[str, Engine] = {}


def _get_engine(conn_str: str) -> Engine:
    eng = _engine_cache.get(conn_str)
    if eng is not None:
        return eng
    # SQLite needs special args for pooling/threading
    connect_args = {}
    if conn_str.startswith("sqlite:///"):
        connect_args = {"check_same_thread": False}
    eng = create_engine(
        conn_str,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
        connect_args=connect_args,
    )
    _engine_cache[conn_str] = eng
    return eng


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


# ------------------------- Classifier -------------------------
def _classify(query: str) -> str:
    q = query.lower()
    sql_keys = ["employee", "employees", "department", "dept", "hired", "salary", "role", "position"]
    doc_keys = ["resume", "document", "pdf", "contract", "clause", "policy", "termination"]

    # Treat common skill/role tokens as SQL intent too (since mapped to columns)
    skill_role_signals = re.findall(r"\b(python|javascript|sql|nlp|ml|developer|engineer|manager)\b", q)

    has_sql = any(k in q for k in sql_keys) or bool(skill_role_signals)
    has_doc = any(k in q for k in doc_keys)
    if has_sql and has_doc:
        return "hybrid"
    if has_sql:
        return "sql"
    if has_doc:
        return "document"
    # Default to SQL to avoid showing document results unless explicitly requested
    return "sql"


# ------------------------- SQL Generation -------------------------
def _normalize_tokens(query: str) -> str:
    q = query.lower()
    synonyms = {
        "dept": "department",
        "division": "department",
        "compensation": "salary",
        "pay": "salary",
        "staff": "employees",
        "emp": "employees",
        "departements": "departments",
    }
    for k, v in synonyms.items():
        q = re.sub(rf"\b{k}\b", v, q)
    return q


def _infer_intent(q: str) -> str:
    """Rudimentary intent detection to shape SQL.
    Returns one of: 'count', 'avg_by_dept', 'top_paid_each_dept', 'find_one', 'select'
    """
    if re.search(r"\b(how many|count|number of)\b", q):
        return "count"
    if re.search(r"\baverage\s+salary\b", q) and re.search(r"\bdepartment\b", q):
        return "avg_by_dept"
    if re.search(r"\btop\s*\d+\b", q) and re.search(r"\b(each\s+department|per\s+department)\b", q):
        return "top_paid_each_dept"
    # exact entity hints (email/id)
    if re.search(r"email\s*[:=]", q) or re.search(r"\bid\s*[:=]?\s*\d+\b", q) or re.search(r"\bwhich\s+employee\b", q):
        return "find_one"
    return "select"


def _infer_filters(q: str) -> Tuple[str, Dict[str, Any]]:
    where = []
    params: Dict[str, Any] = {}

    # --- Hire date filters ---
    # this year
    if "hired this year" in q or re.search(r"\bthis year\b", q):
        where.append("strftime('%Y', E_HIRE_COL) = strftime('%Y', 'now')")

    # explicit year: hired in 2024
    my = re.search(r"hired\s+(?:in|on)\s+(\d{4})", q)
    if my:
        params["year_in"] = my.group(1)
        where.append("strftime('%Y', E_HIRE_COL) = :year_in")

    # ranges: after/since, before, between
    my_after = re.search(r"hired\s+(?:after|since)\s+(\d{4})", q)
    if my_after:
        params["year_after"] = my_after.group(1)
        where.append("strftime('%Y', E_HIRE_COL) > :year_after")

    my_before = re.search(r"hired\s+before\s+(\d{4})", q)
    if my_before:
        params["year_before"] = my_before.group(1)
        where.append("strftime('%Y', E_HIRE_COL) < :year_before")

    my_between = re.search(r"hired\s+between\s+(\d{4})\s+and\s+(\d{4})", q)
    if my_between:
        y1, y2 = my_between.group(1), my_between.group(2)
        params["year_b1"], params["year_b2"] = y1, y2
        where.append("strftime('%Y', E_HIRE_COL) BETWEEN :year_b1 AND :year_b2")

    # --- Skills (allow multiple keywords) ---
    # Match tokens against both skills text and position/title to be forgiving.
    skills = re.findall(r"\b(python|java|javascript|sql|nlp|ml|react|django|postgresql)\b", q)
    for i, sk in enumerate(skills):
        key = f"skill_kw_{i}"
        params[key] = f"%{sk}%"
        # Use placeholders to resolve actual column names later
        where.append(f"(E_SKILLS_COL LIKE :{key} OR e.position LIKE :{key})")

    # --- Reports-to (manager) exact match ---
    # Matches: who reports to John Smith, reports to "John Smith"
    mrep = re.search(r"reports\s+to\s+(?:'|\")?([a-zA-Z]+(?:\s+[a-zA-Z]+)+)(?:'|\")?", q)
    if mrep:
        params["reports_to_name"] = mrep.group(1).strip()
        # Use equality on lowercase for robustness
        where.append("lower(e.reports_to) = lower(:reports_to_name)")

    # --- Exact ID lookup (emp_id or id) ---
    mid = re.search(r"\bemp_id\s*=?\s*(\d+)\b", q) or re.search(r"\bid\s*=?\s*(\d+)\b", q)
    if mid:
        params["id_exact"] = int(mid.group(1))
        where.append("E_ID_COL = :id_exact")

    # --- Exact email lookup ---
    memail = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", q)
    if memail:
        params["email_exact"] = memail.group(1)
        where.append("lower(E_EMAIL_COL) = lower(:email_exact)")

    # --- Missing/empty email filter ---
    if (
        re.search(r"\b(no|missing|empty)\s+emails?\b", q)
        or re.search(r"\b(no|missing|empty)\s+email\b", q)
        or "without email" in q
    ):
        # Use a placeholder to resolve after schema detection
        where.append("EMAIL_IS_MISSING")

    # --- Generic missing filters for other common fields ---
    def _has_missing(patterns: List[str]) -> bool:
        for pat in patterns:
            if re.search(pat, q):
                return True
        return False

    # name
    if _has_missing([r"\b(no|missing|empty)\s+name\b", r"without\s+name"]):
        where.append("NAME_IS_MISSING")
    # skills
    if _has_missing([r"\b(no|missing|empty)\s+skills?\b", r"without\s+skills?"]):
        where.append("SKILLS_IS_MISSING")
    # department
    if _has_missing([r"\b(no|missing|empty)\s+departments?\b", r"\b(no|missing|empty)\s+department\b", r"without\s+department"]):
        where.append("DEPARTMENT_IS_MISSING")
    # position
    if _has_missing([r"\b(no|missing|empty)\s+positions?\b", r"\b(no|missing|empty)\s+position\b", r"without\s+position"]):
        where.append("POSITION_IS_MISSING")
    # salary
    if _has_missing([r"\b(no|missing|empty)\s+salary\b", r"without\s+salary"]):
        where.append("SALARY_IS_MISSING")
    # hire date
    if _has_missing([r"\b(no|missing|empty)\s+(hire|join)\s+date\b", r"without\s+(hire|join)\s+date"]):
        where.append("HIRE_DATE_IS_MISSING")
    # reports_to
    if _has_missing([r"\b(no|missing|empty)\s+reports?\s*to\b", r"without\s+manager", r"without\s+reports?\s*to"]):
        where.append("REPORTS_TO_IS_MISSING")

    # --- Department name (word or quoted) ---
    md = re.search(r"department\s+(?:is\s+)?(?:'|\")?([a-zA-Z]+)(?:'|\")?", q)
    if md:
        params["dept_kw"] = f"%{md.group(1)}%"
        where.append("d.name LIKE :dept_kw")

    # --- Position keywords (simple substring on e.position) ---
    # Note: DO NOT include language tokens like 'python' here; they belong to skills filter.
    pos = re.findall(r"\b(senior|junior|developer|engineer|manager|full\s*stack|marketing|hr)\b", q)
    if pos:
        # Combine into one LIKE with ORs for compactness
        like_clauses = []
        for i, p in enumerate(pos):
            key = f"pos_kw_{i}"
            params[key] = f"%{p}%"
            like_clauses.append(f"e.position LIKE :{key}")
        where.append("(" + " OR ".join(like_clauses) + ")")

    # --- Name like filter (handles queries such as 'show me John') ---
    # Only apply a simple substring match on the employee name column
    mname = re.search(r"\b(?:show\s+me|find|employee(?:\s+named)?)\s+(?:'|\")?([a-zA-Z]+(?:\s+[a-zA-Z]+)?)(?:'|\")?\b", q)
    if mname:
        n = mname.group(1).strip()
        if n and len(n) >= 2:  # avoid single-letter noise
            params["name_like"] = f"%{n}%"
            where.append("E_NAME_COL LIKE :name_like")

    return (" AND ".join(where) if where else "", params)


def _detect_schema(engine: Engine) -> Dict[str, Any]:
    """Detects which table/column naming variant is present and returns a mapping.
    Supports:
      - employees/departments
      - staff/documents
      - personnel/divisions
    """
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    # default mapping shape
    mapping = {
        "emp_table": "employees",
        "dept_table": "departments",
        "emp": {
            "id": "id",
            "name": "name",
            "email": "email",
            "position": "position",
            "salary": "salary",
            "hire_date": "hire_date",
            "skills": "skills",
            "dept_fk": "department_id",
            "reports_to": "reports_to",
        },
        "dept": {
            "id": "id",
            "name": "name",
        },
    }

    if "employees" in tables:
        # Inspect employees table for simplified schema
        emp_cols = {c.get("name") for c in insp.get_columns("employees")}
        dept_cols = {c.get("name") for c in insp.get_columns("departments")} if "departments" in tables else set()
        if {"emp_id", "full_name", "dept_id", "join_date"}.issubset(emp_cols):
            return {
                "emp_table": "employees",
                "dept_table": "departments" if "departments" in tables else None,
                "emp": {
                    "id": "emp_id",
                    "name": "full_name",
                    "email": "email" if "email" in emp_cols else None,
                    "position": "position",
                    "salary": "annual_salary",
                    "hire_date": "join_date",
                    "skills": "skills" if "skills" in emp_cols else None,
                    "dept_fk": "dept_id",
                    "reports_to": "reports_to" if "reports_to" in emp_cols else None,
                },
                "dept": {"id": "dept_id", "name": "dept_name"} if {"dept_id", "dept_name"}.issubset(dept_cols) else None,
            }
        # else use defaults
        return mapping
    if "staff" in tables:
        return {
            "emp_table": "staff",
            "dept_table": None,  # no separate table in this variant
            "emp": {
                "id": "id",
                "name": "name",
                "email": "email" if "email" in insp.get_columns("staff")[0].keys() else "email",
                "position": "role",
                "salary": "compensation",
                "hire_date": "hired_on",
                "skills": "skills" if any(c.get("name") == "skills" for c in insp.get_columns("staff")) else None,
                "dept_fk": "department",
                "reports_to": "reports_to",
            },
            "dept": None,
        }
    if "personnel" in tables:
        return {
            "emp_table": "personnel",
            "dept_table": "divisions" if "divisions" in tables else None,
            "emp": {
                "id": "person_id",
                "name": "employee_name",
                "email": "email" if any(c.get("name") == "email" for c in insp.get_columns("personnel")) else None,
                "position": "title",
                "salary": "pay_rate",
                "hire_date": "start_date",
                "skills": "skills" if any(c.get("name") == "skills" for c in insp.get_columns("personnel")) else None,
                "dept_fk": "division",
                "reports_to": "reports_to" if any(c.get("name") == "reports_to" for c in insp.get_columns("personnel")) else None,
            },
            "dept": {"id": "division_code", "name": "division_name"} if "divisions" in tables else None,
        }
    return mapping  # fallback to employees/departments


def _run_sql(query_text: str, connection_string: str | None, limit: int = 50, offset: int = 0, intent: str = "select") -> Dict[str, Any]:
    # Fallback to local SQLite example if no connection string provided
    conn_str = connection_string or f"sqlite:///{os.path.join(os.getcwd(), 'example.db')}"
    engine = _get_engine(conn_str)

    qn = _normalize_tokens(query_text)
    where, params = _infer_filters(qn)
    # Use ML intent model when available; fallback to rules
    ml_intent = None
    if ml_predict_intent:
        try:
            pred, conf = ml_predict_intent(qn)
            if conf >= 0.55:  # simple threshold
                ml_intent = pred
        except Exception:
            ml_intent = None
    intent = ml_intent or intent or _infer_intent(qn)

    # Detect schema and build column references
    mapping = _detect_schema(engine)
    et, dt = mapping["emp_table"], mapping.get("dept_table")
    e = mapping["emp"]
    d = mapping.get("dept")

    # column aliases to use consistently
    col_id = e["id"]
    col_name = e["name"]
    col_email = e.get("email")
    col_pos = e.get("position")
    col_sal = e.get("salary") or "annual_salary"
    col_hire = e.get("hire_date")
    col_skills = e.get("skills")
    col_deptfk = e.get("dept_fk")
    col_reports = e.get("reports_to") or "reports_to"

    # Missing/unknown-entity handling
    try:
        insp_tables = set(inspect(engine).get_table_names())
    except Exception:
        insp_tables = set()
    # Map entity keywords to expected table names
    entity_tables = {
        "contractors": "contractors",
        "vendor": "vendors",
        "vendors": "vendors",
        "intern": "interns",
        "interns": "interns",
        "project": "projects",
        "projects": "projects",
    }
    for kw, table in entity_tables.items():
        if re.search(rf"\b{kw}\b", qn) and table not in insp_tables:
            return {
                "type": "sql",
                "sql": None,
                "params": {},
                "rows": [],
                "error": f"error: not present in your database (missing entity: '{table}')",
                "pagination": None,
            }

    # Replace placeholder columns for filters if present
    if "e.salary_col" in (where or ""):
        where = where.replace("e.salary_col", f"e.{col_sal}")
    if "E_HIRE_COL" in (where or ""):
        hire_col = col_hire or "join_date"
        where = where.replace("E_HIRE_COL", f"e.{hire_col}")
    if "E_ID_COL" in (where or ""):
        where = where.replace("E_ID_COL", f"e.{col_id}")
    if "E_EMAIL_COL" in (where or "") and col_email:
        where = where.replace("E_EMAIL_COL", f"e.{col_email}")
    elif "E_EMAIL_COL" in (where or "") and not col_email:
        # Email lookup requested but email column not present: return error
        return {
            "type": "sql",
            "sql": None,
            "params": {},
            "rows": [],
            "error": "error: not present in your database (email column missing)",
            "pagination": None,
        }
    if "E_NAME_COL" in (where or ""):
        where = where.replace("E_NAME_COL", f"e.{col_name}")
    if "E_SKILLS_COL" in (where or ""):
        if col_skills:
            where = where.replace("E_SKILLS_COL", f"e.{col_skills}")
        else:
            # No skills column; drop skills side of the OR safely
            where = where.replace("E_SKILLS_COL LIKE", "0 /* no skills col */ LIKE")

    # Resolve missing email placeholder
    if "EMAIL_IS_MISSING" in (where or ""):
        if col_email:
            where = where.replace("EMAIL_IS_MISSING", f"(e.{col_email} IS NULL OR e.{col_email} = '')")
        else:
            # No email column available; return empty result with warning
            return {
                "type": "sql",
                "sql": None,
                "params": {},
                "rows": [],
                "warning": "Email column not present; cannot filter for missing email.",
                "pagination": None,
            }

    # Resolve other missing placeholders based on schema
    if "NAME_IS_MISSING" in (where or ""):
        where = where.replace("NAME_IS_MISSING", f"(e.{col_name} IS NULL OR e.{col_name} = '')")
    if "SKILLS_IS_MISSING" in (where or ""):
        if col_skills:
            where = where.replace("SKILLS_IS_MISSING", f"(e.{col_skills} IS NULL OR e.{col_skills} = '')")
        else:
            where = where.replace("SKILLS_IS_MISSING", "1=0")
    if "DEPARTMENT_IS_MISSING" in (where or ""):
        # consider missing as no department FK
        if col_deptfk:
            where = where.replace("DEPARTMENT_IS_MISSING", f"(e.{col_deptfk} IS NULL)")
        else:
            where = where.replace("DEPARTMENT_IS_MISSING", "1=0")
    if "POSITION_IS_MISSING" in (where or ""):
        if col_pos:
            where = where.replace("POSITION_IS_MISSING", f"(e.{col_pos} IS NULL OR e.{col_pos} = '')")
        else:
            where = where.replace("POSITION_IS_MISSING", "1=0")
    if "SALARY_IS_MISSING" in (where or ""):
        where = where.replace("SALARY_IS_MISSING", f"(e.{col_sal} IS NULL)")
    if "HIRE_DATE_IS_MISSING" in (where or ""):
        hire_col = col_hire or "join_date"
        where = where.replace("HIRE_DATE_IS_MISSING", f"(e.{hire_col} IS NULL OR e.{hire_col} = '')")
    if "REPORTS_TO_IS_MISSING" in (where or ""):
        if col_reports:
            where = where.replace("REPORTS_TO_IS_MISSING", f"(e.{col_reports} IS NULL OR e.{col_reports} = '')")
        else:
            where = where.replace("REPORTS_TO_IS_MISSING", "1=0")

    # Build base FROM/JOIN with schema mapping
    # Deduplicate by email if email exists
    dedup_cte = ""
    if col_email:
        dedup_cte = f"WITH latest AS (SELECT {col_email} AS email, MAX({col_id}) AS max_id FROM {et} GROUP BY {col_email}) "
    # Select all columns from employee table to surface full schema in results
    select_cols = ["e.*"]
    dept_join = ""
    if dt and d:
        dept_join = f" LEFT JOIN {dt} d ON e.{col_deptfk} = d.{d['id']}"
        select_cols.append("d." + d["name"] + " AS department")
    else:
        # no dept table; expose dept_fk as department if it is a text column (best-effort)
        select_cols.append(f"e.{col_deptfk} AS department")

    base = (
        f"{dedup_cte}SELECT {', '.join(select_cols)} "
        f"FROM {et} e "
        + ("JOIN latest l ON l.max_id = e." + col_id + " " if dedup_cte else "")
        + dept_join
    )
    # Support direct departments listing queries
    if re.search(r"\bdepartments?\b", qn) and not re.search(r"\bemployees?\b", qn):
        # Simple departments table listing
        dname = d["name"] if d else "dept_name"
        did = d["id"] if d else "dept_id"
        sql = f"SELECT d.{did} AS dept_id, d.{dname} AS dept_name, d.manager_id FROM {dt or 'departments'} d"
        if where and "D_NAME_COL" in where:
            where = where.replace("D_NAME_COL", f"d.{dname}")
        if where:
            sql += f" WHERE {where}"
        sql += f" ORDER BY d.{did} ASC LIMIT :limit OFFSET :offset"
        params["limit"] = max(1, int(limit))
        params["offset"] = max(0, int(offset))
    else:
        sql = base
    if where and not re.search(r"\bFROM\s+departments\b", sql):
        # If WHERE contains department name placeholder, patch it
        if "D_NAME_COL" in where and dt and d:
            where = where.replace("D_NAME_COL", f"d.{d['name']}")
        elif "D_NAME_COL" in where:
            where = where.replace("D_NAME_COL", f"e.{col_deptfk}")
        sql += f" WHERE {where}"
    if intent in ("avg_by_dept",) and dt and d:
        sql = f"SELECT d.{d['name']} AS department, AVG(e.{col_sal}) AS avg_salary FROM {et} e LEFT JOIN {dt} d ON e.{col_deptfk} = d.{d['id']}"
        if where:
            sql += f" WHERE {where}"
        sql += f" GROUP BY d.{d['name']} ORDER BY avg_salary DESC"
        count_sql = None
    elif intent == "count":
        count_expr = "COUNT(1) AS count"
        sql = f"SELECT {count_expr} FROM (" + base + (f" WHERE {where}" if where else "") + ") t"
        count_sql = None
    elif intent == "top_paid_each_dept" and dt and d:
        # ROW_NUMBER per department by salary desc
        part = (
            f"SELECT e.{col_id} AS id, e.{col_name} AS name, e.{col_sal} AS salary, d.{d['name']} AS department, "
            f"ROW_NUMBER() OVER (PARTITION BY d.{d['name']} ORDER BY e.{col_sal} DESC) AS rn "
            f"FROM {et} e LEFT JOIN {dt} d ON e.{col_deptfk} = d.{d['id']}"
        )
        if where:
            part += f" WHERE {where}"
        # try to extract top N
        mtop = re.search(r"top\s*(\d+)", qn)
        topn = int(mtop.group(1)) if mtop else 5
        sql = f"SELECT * FROM ( {part} ) z WHERE z.rn <= :topn ORDER BY z.department, z.salary DESC"
        params["topn"] = topn
        count_sql = None
    elif intent in ("departments_list",) and dt:
        # Already handled earlier for departments direct listing; nothing to change
        count_sql = None
    else:
        # total count (without limit/offset)
        count_sql = f"SELECT COUNT(1) AS total FROM ({sql}) t"
        # limit/offset and default ordering (ascending)
        order_col = col_id
        sql += f" ORDER BY e.{order_col} ASC LIMIT :limit OFFSET :offset"
        params["limit"] = max(1, int(1 if intent == "find_one" else limit))
        params["offset"] = max(0, int(0 if intent == "find_one" else offset))

    with engine.connect() as conn:
        _inc("active_connections", 1)
        try:
            total = None
            if count_sql:
                total = conn.execute(text(count_sql), params).scalar_one()
            rows = conn.execute(text(sql), params).mappings().all()
            data = [dict(r) for r in rows]
        finally:
            _inc("active_connections", -1)
    return {
        "type": "sql",
        "sql": sql,
        "params": params,
        "rows": data,
        "pagination": ({"limit": params.get("limit", 0), "offset": params.get("offset", 0), "total": total} if count_sql else None),
    }


# ------------------------- Document Search -------------------------
def _search_documents(query_text: str, top_k: int = 8, offset: int = 0) -> Dict[str, Any]:
    if not os.path.exists(INGEST_DB):
        return {"type": "document", "results": []}
    model = _get_model()
    q_vec = model.encode([query_text], convert_to_numpy=True, normalize_embeddings=True).astype("float32")[0]

    conn = sqlite3.connect(INGEST_DB)
    cur = conn.cursor()
    cur.execute("SELECT c.text, c.embedding, c.dim, d.filename, d.doc_type FROM chunks c JOIN documents d ON c.document_id = d.id")
    rows = cur.fetchall()
    conn.close()

    results: List[Tuple[float, Dict[str, Any]]] = []
    for text_chunk, emb_blob, dim, filename, doc_type in rows:
        vec = np.frombuffer(emb_blob, dtype=np.float32)
        if vec.shape[0] != dim:
            continue
        score = float(np.dot(vec, q_vec))  # cosine similarity (normalized)
        results.append((score, {"text": text_chunk, "filename": filename, "doc_type": doc_type, "score": score}))

    results.sort(key=lambda x: x[0], reverse=True)
    total = len(results)
    start = max(0, int(offset))
    end = start + max(1, int(top_k))
    page = [item for _, item in results[start:end]]
    return {"type": "document", "results": page, "pagination": {"limit": max(1, int(top_k)), "offset": start, "total": total}}


# ------------------------- Hybrid Merge -------------------------
def _merge_hybrid(sql_res: Dict[str, Any], doc_res: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "hybrid",
        "sql": sql_res,
        "documents": doc_res,
    }


# ------------------------- Public API -------------------------
def process_query(user_query: str, connection_string: str | None = None, limit: int = 50, offset: int = 0, doc_limit: int = 8, doc_offset: int = 0) -> Dict[str, Any]:
    t0 = time.time()
    _inc("total_queries", 1)
    cache_key = json.dumps({"q": user_query, "cs": connection_string, "l": limit}, sort_keys=True)
    cached = _cache.get(cache_key)
    if cached is not None:
        elapsed = time.time() - t0
        result = {**cached, "metrics": {"elapsed_sec": elapsed, "cache": "hit"}}
        _inc("cache_hits", 1)
        _record_time(elapsed)
        _history.append({"q": user_query, "time": elapsed, "type": cached.get("type"), "cache": "hit"})
        return result

    qtype = _classify(user_query)
    sql_res = None
    doc_res = None

    if qtype in ("sql", "hybrid"):
        try:
            intent = _infer_intent(_normalize_tokens(user_query))
            sql_res = _with_active_query(_run_sql, user_query, connection_string, limit, offset, intent)
        except Exception as e:
            sql_res = {"type": "sql", "error": str(e), "rows": []}
    if qtype in ("document", "hybrid"):
        try:
            doc_res = _with_active_query(_search_documents, user_query, doc_limit, doc_offset)
        except Exception as e:
            doc_res = {"type": "document", "error": str(e), "results": []}

    if qtype == "sql":
        final = sql_res or {"type": "sql", "rows": []}
    elif qtype == "document":
        final = doc_res or {"type": "document", "results": []}
    else:
        final = _merge_hybrid(sql_res or {"type": "sql", "rows": []}, doc_res or {"type": "document", "results": []})

    elapsed = time.time() - t0
    final_with_metrics = {**final, "metrics": {"elapsed_sec": elapsed, "cache": "miss"}}
    _inc("cache_misses", 1)
    _record_time(elapsed)
    _cache.set(cache_key, final)
    _history.append({"q": user_query, "time": elapsed, "type": final_with_metrics.get("type"), "cache": "miss"})
    if len(_history) > 100:
        del _history[:-100]
    return final_with_metrics


def recent_history(limit: int = 20) -> List[Dict[str, Any]]:
    return list(_history[-limit:])[::-1]


def get_metrics() -> Dict[str, Any]:
    # query stats
    times = _metrics.get("exec_times", [])
    avg = sum(times) / len(times) if times else 0.0
    p95 = 0.0
    if times:
        s = sorted(times)
        p95 = s[min(len(s) - 1, int(0.95 * len(s)))]

    # document stats from ingestion.db
    docs = 0
    chunks = 0
    if os.path.exists(INGEST_DB):
        conn = sqlite3.connect(INGEST_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documents")
        docs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM chunks")
        chunks = cur.fetchone()[0]
        conn.close()

    return {
        "total_queries": _metrics.get("total_queries", 0),
        "cache_hits": _metrics.get("cache_hits", 0),
        "cache_misses": _metrics.get("cache_misses", 0),
        "active_queries": _metrics.get("active_queries", 0),
        "active_connections": _metrics.get("active_connections", 0),
        "avg_exec_sec": avg,
        "p95_exec_sec": p95,
        "recent_exec_times": times[-20:],
        "indexed_documents": docs,
        "indexed_chunks": chunks,
    }


def reset_metrics() -> Dict[str, Any]:
    _metrics["total_queries"] = 0
    _metrics["cache_hits"] = 0
    _metrics["cache_misses"] = 0
    _metrics["exec_times"] = []
    _metrics["active_queries"] = 0
    _metrics["active_connections"] = 0
    return {"ok": True}

