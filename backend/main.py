from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.schema import router as schema_router
from backend.api.routes.ingestion import router as ingestion_router
from backend.api.routes.query import router as query_router

app = FastAPI(title="NLP Query Engine for Employee Data")

# CORS for local dev (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(schema_router, prefix="/api", tags=["schema"])
app.include_router(ingestion_router, prefix="/api", tags=["ingestion"])
app.include_router(query_router, prefix="/api", tags=["query"])


@app.get("/")
async def root():
    return {"status": "ok", "service": "nlp-query-engine"}


if __name__ == "__main__":
    import uvicorn
    # Start uvicorn server in-process (no reloader, no subprocess spawn)
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, reload=False)
    server = uvicorn.Server(config)
    server.run()
