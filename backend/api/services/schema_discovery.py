from __future__ import annotations

from typing import Any, Dict, List
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL
from sqlalchemy.engine.url import make_url


def _safe_str(x: Any) -> str:
    try:
        return str(x)
    except Exception:
        return repr(x)


def _normalize_name(name: str) -> str:
    return name.lower().strip()


def analyze_database(connection_string: str) -> Dict[str, Any]:
    """
    Analyze a SQL database via SQLAlchemy reflection and return a JSON-like dict:
    {
      "tables": [table, ...],
      "columns": {table: ["col:type", ...]},
      "relationships": [
          {
            "from_table": str,
            "from_columns": [str, ...],
            "to_table": str,
            "to_columns": [str, ...],
            "name": str | None
          }
      ]
    }

    Supports Postgres/MySQL/SQLite given their proper connection strings.
    Examples:
      - sqlite: sqlite:///path/to.db  or sqlite:///:memory:
      - postgres: postgresql+psycopg2://user:pass@host:5432/dbname
      - mysql: mysql+pymysql://user:pass@host:3306/dbname
    """
    # Fail fast for sqlite files that do not exist (avoid creating empty file silently)
    try:
        url = make_url(connection_string)
        if url.get_backend_name().startswith("sqlite"):
            db_path = url.database or ""
            # Allow :memory:
            if db_path and db_path != ":memory:":
                # If relative path, check relative to CWD
                if not os.path.isabs(db_path):
                    db_path_to_check = os.path.join(os.getcwd(), db_path)
                else:
                    db_path_to_check = db_path
                if not os.path.exists(db_path_to_check):
                    raise FileNotFoundError(f"SQLite database file not found: {db_path}")
    except Exception:
        # If make_url fails, let normal engine creation raise a clearer error below
        pass

    # Create engine and verify connectivity before reflection
    engine = create_engine(connection_string)
    with engine.connect() as conn:
        pass
    inspector = inspect(engine)

    # Collect tables
    tables: List[str] = sorted(inspector.get_table_names())

    # Collect columns per table
    columns: Dict[str, List[str]] = {}
    for table in tables:
        cols_info = inspector.get_columns(table)
        columns[table] = [f"{c['name']}:{_safe_str(c.get('type'))}" for c in cols_info]

    # Collect relationships via foreign keys
    relationships: List[Dict[str, Any]] = []
    for table in tables:
        fks = inspector.get_foreign_keys(table)
        for fk in fks:
            relationships.append(
                {
                    "from_table": table,
                    "from_columns": fk.get("constrained_columns", []) or [],
                    "to_table": fk.get("referred_table"),
                    "to_columns": fk.get("referred_columns", []) or [],
                    "name": fk.get("name"),
                }
            )

    # Optional: simple naming variation hints (not required in output, but helps future logic)
    # We keep it internal for now.
    def is_employee_like(name: str) -> bool:
        n = _normalize_name(name)
        return any(k in n for k in ["employee", "employees", "emp", "staff", "personnel", "people"])

    def is_department_like(name: str) -> bool:
        n = _normalize_name(name)
        return any(k in n for k in ["dept", "department", "division", "team", "org", "unit"])    

    _ = {
        "employee_like_tables": [t for t in tables if is_employee_like(t)],
        "department_like_tables": [t for t in tables if is_department_like(t)],
    }

    return {
        "tables": tables,
        "columns": columns,
        "relationships": relationships,
    }
