# NLP Dynamic DB (Query Engine + Document Search)

Lightweight, schema-aware query engine for employee data with optional document semantic search. Frontend in React (Vite), backend in FastAPI. Ships with a custom sample SQLite database for instant testing.

## Requirements
- Python 3.11+
- Node.js 20+
- npm 9+
- Optional: Docker Desktop (Windows/macOS/Linux) for containerized dev/deploy

## Quick Start (Local, no Docker)

Open two terminals in the repository root.

1) Backend (FastAPI)

Windows PowerShell:
```powershell
# Create venv (optional) and install deps
python -m venv .venv
 .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Seed the sample DB (creates example.db with employees/departments)
python .\create_sample_db.py

# Run API
python -c "import uvicorn, backend.main as m; uvicorn.run(m.app, host='127.0.0.1', port=8000)"
```

Backend URL: http://localhost:8000

2) Frontend (Vite React)

```powershell
cd frontend
npm install
$env:VITE_API_BASE = "http://localhost:8000/api"
npm run dev
```

Frontend URL: http://localhost:5173

## What’s the custom database?

This repo includes `create_sample_db.py` which generates `example.db` (SQLite) with:
- `employees` table: id, name, email, position, salary, hire_date, skills, department_id, reports_to
- `departments` table: id, name

It lets you query immediately without connecting to an external DB. You can later call `POST /api/connect-database` with your own connection string to switch.

## Running With Docker (optional, lightweight)

Dev-oriented compose (bind mounts; installs on startup):
```bash
docker compose up --build
```
- Backend: http://localhost:8000
- Frontend (if enabled in compose): http://localhost:5173

Note: On Windows, install Docker Desktop first and enable WSL2 engine.

## Project Structure

```
nlp-dynamic-db/
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── query.py            # /api/query, /api/connect-database, history/metrics
│   │   │   ├── ingestion.py        # document ingestion endpoints (optional)
│   │   │   └── schema.py           # schema discovery endpoints
│   │   └── services/
│   │       ├── query_engine.py     # classifier, SQL builder, doc search
│   │       ├── document_processor.py# (optional) chunking/embedding ingestion
│   │       └── schema_discovery.py # DB introspection helpers
│   └── main.py                     # FastAPI app wiring
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── QueryPanel.jsx      # input, sends query to API
│   │   │   ├── ResultsView.jsx     # shows SQL/doc/hybrid results, exports
│   │   │   ├── DocumentUploader.jsx# upload & index docs (optional)
│   │   │   └── ...
│   │   └── App.jsx
│   └── index.html
├── storage/                        # runtime data: ingestion.db, caches (created on demand)
├── create_sample_db.py             # builds example.db with sample data
├── docker-compose.yml              # dev compose (optional)
├── requirements.txt                # backend deps
└── README.md
```

## API Tips
- Connect to your own DB: `POST /api/connect-database` with JSON `{ "connection_string": "sqlite:///./example.db" }` (or Postgres/MySQL URI).
- Query endpoint: `POST /api/query` with `{ "query": "employee who is a python developer" }`.
- Metrics: `GET /api/metrics`.

## How to push this repo to GitHub

You need a repository under your account (e.g., `farhan-ts/nlp-dynamic-db`). Choose one approach:

- Web UI (simple)
  1. Create a new empty repo on GitHub: https://github.com/new
  2. In the local project root, run:
     ```powershell
     git init
     git add .
     git commit -m "Initial commit"
     git branch -M main
     git remote add origin https://github.com/farhan-ts/nlp-dynamic-db.git
     git push -u origin main
     ```

- GitHub CLI (if installed)
  ```powershell
  git init
  git add .
  git commit -m "Initial commit"
  gh repo create farhan-ts/nlp-dynamic-db --public --source . --remote origin --push
  ```

If `git` or `gh` is not installed, install Git (https://git-scm.com/downloads) and GitHub CLI (https://cli.github.com/) first.

## Notes
- Frontend expects `VITE_API_BASE` to point to the backend (default dev: `http://localhost:8000/api`).
- Document search uses `sentence-transformers/all-MiniLM-L6-v2` and stores embeddings in `storage/ingestion.db`.
- CORS is permissive for local dev.
