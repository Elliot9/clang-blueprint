"""
server.py — FastAPI AI query server for clang-blueprint.

Endpoints:
  GET  /health              — liveness check
  POST /query               — semantic search over blueprint index
  POST /rebuild-index       — re-fit TF-IDF index from blueprint_index.json
  GET  /stats               — index statistics

Run with:
  uvicorn ai_api.server:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from ai_api.indexer import BlueprintIndexer


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("blueprint.server")


# ---------------------------------------------------------------------------
# Configuration (env-var driven)
# ---------------------------------------------------------------------------

BLUEPRINT_INDEX_PATH = os.environ.get("BLUEPRINT_INDEX_PATH", "blueprint_index.json")
TFIDF_INDEX_PATH = os.environ.get("TFIDF_INDEX_PATH", ".blueprint_tfidf.pkl")
MAX_TOP_K = int(os.environ.get("MAX_TOP_K", "50"))
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

class AppState:
    indexer: Optional[BlueprintIndexer] = None
    startup_time: float = 0.0
    last_rebuild: Optional[float] = None
    rebuild_in_progress: bool = False


state = AppState()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the indexer on startup."""
    state.startup_time = time.time()
    logger.info("Starting clang-blueprint AI server...")

    state.indexer = BlueprintIndexer(
        blueprint_path=BLUEPRINT_INDEX_PATH,
        index_path=TFIDF_INDEX_PATH,
    )

    # Try to load existing index; if not present, try to build from blueprint
    try:
        if not state.indexer.load():
            blueprint_path = Path(BLUEPRINT_INDEX_PATH)
            if blueprint_path.exists():
                logger.info(f"Building TF-IDF index from {BLUEPRINT_INDEX_PATH}...")
                state.indexer.build()
                state.last_rebuild = time.time()
            else:
                logger.warning(
                    f"Blueprint index not found at {BLUEPRINT_INDEX_PATH}. "
                    "POST /rebuild-index after running `blueprint scan`."
                )
        else:
            state.last_rebuild = time.time()
    except Exception as exc:
        logger.error(f"Index initialization failed: {exc}")
        # Don't crash — server still starts, queries will return 503 until index is built

    logger.info("Server ready.")
    yield
    logger.info("Server shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="clang-blueprint AI Query Server",
    description="Semantic search over C++ codebase blueprint index",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Natural language query")
    top_k: int = Field(5, ge=1, le=MAX_TOP_K, description="Number of results to return")

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        return v.strip()


class QueryResultItem(BaseModel):
    score: float
    className: str
    responsibility: str
    fileLocation: str
    lineNumber: int
    namespace: str
    attributes: list[str] = Field(default_factory=list)
    interfaces: list[str]
    dependencies: list[dict[str, str]]
    baseClasses: list[str]
    templateParams: list[str]


class QueryResponse(BaseModel):
    query: str
    results: list[QueryResultItem]
    elapsed_ms: float
    total_indexed: int


class RebuildResponse(BaseModel):
    status: str
    message: str
    num_entries: int
    elapsed_ms: float


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    index_built: bool
    num_docs: int
    last_rebuild: Optional[float]


class StatsResponse(BaseModel):
    num_docs: int
    blueprint_path: str
    index_path: str
    index_built: bool
    last_rebuild: Optional[float]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    """Liveness/readiness check."""
    idx = state.indexer
    return HealthResponse(
        status="ok",
        uptime_seconds=round(time.time() - state.startup_time, 2),
        index_built=idx.is_built if idx else False,
        num_docs=idx.num_docs if idx else 0,
        last_rebuild=state.last_rebuild,
    )


@app.get("/stats", response_model=StatsResponse, tags=["system"])
async def stats():
    """Return detailed index statistics."""
    idx = state.indexer
    return StatsResponse(
        num_docs=idx.num_docs if idx else 0,
        blueprint_path=BLUEPRINT_INDEX_PATH,
        index_path=TFIDF_INDEX_PATH,
        index_built=idx.is_built if idx else False,
        last_rebuild=state.last_rebuild,
    )


@app.post("/query", response_model=QueryResponse, tags=["search"])
async def query_endpoint(request: QueryRequest):
    """
    Perform a semantic search over the blueprint index.

    Returns ranked blueprint entries with cosine similarity scores.
    """
    idx = state.indexer
    if idx is None or not idx.is_built:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Index not yet built. "
                "POST /rebuild-index to build it from blueprint_index.json."
            ),
        )

    t0 = time.perf_counter()
    try:
        raw_results = idx.query(request.query, top_k=request.top_k)
    except Exception as exc:
        logger.exception(f"Query failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing error: {str(exc)}",
        )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    results: list[QueryResultItem] = []
    for r in raw_results:
        entry = r["entry"]
        results.append(
            QueryResultItem(
                score=r["score"],
                className=entry.get("className", ""),
                responsibility=entry.get("responsibility", ""),
                fileLocation=entry.get("fileLocation", ""),
                lineNumber=entry.get("lineNumber", 0),
                namespace=entry.get("namespace", ""),
                attributes=entry.get("attributes", []),
                interfaces=entry.get("interfaces", []),
                dependencies=entry.get("dependencies", []),
                baseClasses=entry.get("baseClasses", []),
                templateParams=entry.get("templateParams", []),
            )
        )

    logger.info(
        f"Query '{request.query[:50]}' → {len(results)} results in {elapsed_ms:.1f}ms"
    )

    return QueryResponse(
        query=request.query,
        results=results,
        elapsed_ms=round(elapsed_ms, 2),
        total_indexed=idx.num_docs,
    )


@app.post("/rebuild-index", response_model=RebuildResponse, tags=["admin"])
async def rebuild_index(background_tasks: BackgroundTasks):
    """
    Re-fit the TF-IDF index from the current blueprint_index.json.

    This is synchronous by design — callers should await completion before
    issuing queries against the new index.
    """
    if state.rebuild_in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rebuild is already in progress.",
        )

    blueprint_path = Path(BLUEPRINT_INDEX_PATH)
    if not blueprint_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint index not found: {BLUEPRINT_INDEX_PATH}. "
                   "Run `blueprint scan` first.",
        )

    state.rebuild_in_progress = True
    t0 = time.perf_counter()

    try:
        with open(blueprint_path, "r", encoding="utf-8") as f:
            entries = json.load(f)

        if state.indexer is None:
            state.indexer = BlueprintIndexer(
                blueprint_path=BLUEPRINT_INDEX_PATH,
                index_path=TFIDF_INDEX_PATH,
            )

        state.indexer.build(entries)
        state.last_rebuild = time.time()
        elapsed_ms = (time.perf_counter() - t0) * 1000

        logger.info(
            f"Index rebuilt: {len(entries)} entries in {elapsed_ms:.1f}ms"
        )

        return RebuildResponse(
            status="ok",
            message=f"Index rebuilt successfully from {BLUEPRINT_INDEX_PATH}",
            num_entries=len(entries),
            elapsed_ms=round(elapsed_ms, 2),
        )

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON in blueprint index: {exc}",
        )
    except Exception as exc:
        logger.exception(f"Rebuild failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index rebuild failed: {str(exc)}",
        )
    finally:
        state.rebuild_in_progress = False


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception for {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ai_api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
