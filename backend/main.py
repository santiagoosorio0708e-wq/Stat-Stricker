"""
main.py
-------
API REST de StatStriker (FastAPI).

Endpoints:
    GET    /api/health              Estado de los 3 pilares (LLM, Sistema Experto, Vector DB)
    GET    /api/matches             Partidos disponibles en la base vectorial
    POST   /api/chat                Flujo RAG completo
    GET    /api/history/{session}   Historial persistido en SQLite
    DELETE /api/history/{session}   Borra el historial de la sesión
    GET    /                        Frontend estático (index.html, style.css, app.js)

Ejecutar desde la raíz del proyecto:
    uvicorn backend.main:app --reload
"""

from __future__ import annotations

import json
import logging
import time
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import database
from backend.config import settings
from backend.embeddings import get_embedding_provider
from backend.expert_system import (
    analyze_query,
    assess_context_quality,
    build_system_prompt,
    build_user_prompt,
)
from backend.llm_client import LLMClient, LLMError, get_llm_client
from backend.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("statstriker")

# Catálogo de clubes y escudos. Se consulta bajo demanda y se mantiene en memoria
# para evitar repetir peticiones al proveedor en cada visita.
SPORTSDB_LEAGUES = {
    "4328": "English_Premier_League",
    "4335": "Spanish_La_Liga",
    "4332": "Italian_Serie_A",
    "4331": "German_Bundesliga",
    "4334": "French_Ligue_1",
}
_team_catalog_cache: dict[str, tuple[float, list[dict[str, str | None]]]] = {}


# ====================================================================== #
# Ciclo de vida: inicializa SQLite, ChromaDB y el cliente LLM una sola vez
# ====================================================================== #
@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    logger.info("SQLite listo en %s", settings.sqlite_path)

    embedder = get_embedding_provider(settings)
    app.state.vector_store = VectorStore(settings.chroma_path, settings.chroma_collection, embedder)
    logger.info("ChromaDB listo (%d fragmentos, embeddings=%s)", app.state.vector_store.count(), embedder.name)

    # Si falta la API key no tumbamos el servidor: /api/chat devolverá 503 con el motivo.
    app.state.llm, app.state.llm_error = None, None
    try:
        app.state.llm = get_llm_client(settings)
        logger.info("LLM listo: %s / %s", app.state.llm.provider, app.state.llm.model)
    except LLMError as exc:
        app.state.llm_error = str(exc)
        logger.warning("LLM no disponible: %s", exc)

    yield


app = FastAPI(
    title="StatStriker API",
    description="Agente predictivo de apuestas deportivas basado en RAG + Sistema Experto.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS abierto solo para desarrollo local (p. ej. abrir index.html con Live Server).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ====================================================================== #
# Esquemas
# ====================================================================== #
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="Propuesta de apuesta del usuario")
    session_id: str = Field("default", min_length=1, max_length=64, pattern=r"^[\w-]+$")


class ChatResponse(BaseModel):
    id: int
    answer: str
    active_rules: list[str]
    context_quality: str
    sources: list[dict[str, Any]]
    analysis: dict[str, Any]
    provider: str


# ====================================================================== #
# Endpoints
# ====================================================================== #
@app.get("/api/health")
def health(request: Request) -> dict[str, Any]:
    store: VectorStore = request.app.state.vector_store
    llm: LLMClient | None = request.app.state.llm
    return {
        "status": "ok",
        "llm": {
            "ready": llm is not None,
            "provider": llm.provider if llm else settings.llm_provider,
            "model": llm.model if llm else None,
            "error": request.app.state.llm_error,
        },
        "vector_db": {"engine": "chromadb", "documents": store.count()},
        "embedding_provider": settings.embedding_provider,
    }


@app.get("/api/matches")
def list_matches(request: Request) -> list[dict[str, Any]]:
    return request.app.state.vector_store.list_matches()


@app.get("/api/teams/{league_id}")
def list_league_teams(league_id: str) -> list[dict[str, str | None]]:
    """Devuelve todos los clubes de una liga y el escudo disponible."""
    league = SPORTSDB_LEAGUES.get(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="Liga no disponible.")
    cached = _team_catalog_cache.get(league_id)
    if cached and cached[0] > time.time():
        return cached[1]

    url = f"https://www.thesportsdb.com/api/v1/json/123/search_all_teams.php?l={league}"
    try:
        request = UrlRequest(url, headers={"User-Agent": "StatStriker/1.0"})
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError) as exc:
        if cached:
            return cached[1]
        logger.warning("No se pudo cargar el catálogo %s: %s", league, exc)
        raise HTTPException(status_code=502, detail="No se pudo cargar el catálogo de equipos.") from exc

    teams = [
        {"id": str(team.get("idTeam", "")), "name": str(team.get("strTeam", "")), "badge": team.get("strBadge") or team.get("strTeamBadge")}
        for team in payload.get("teams", [])
        if team.get("idTeam") and team.get("strTeam")
    ]
    _team_catalog_cache[league_id] = (time.time() + 6 * 60 * 60, teams)
    return teams


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    """
    Flujo RAG:
      1. Sistema experto analiza la consulta (hechos).
      2. Búsqueda semántica en ChromaDB (embedding de la consulta).
      3. Inyección dinámica del System Prompt según reglas.
      4. Llamada REST al LLM.
      5. Persistencia en SQLite.
    """
    store: VectorStore = request.app.state.vector_store
    llm: LLMClient | None = request.app.state.llm
    if llm is None:
        raise HTTPException(status_code=503, detail=request.app.state.llm_error or "LLM no configurado.")

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío.")

    # 1) Hechos de la consulta (entity linking contra el catálogo de partidos)
    analysis = analyze_query(message, store.list_matches())

    # 2) Recuperación semántica
    try:
        store.check_compatibility()
        chunks = store.search(message, top_k=settings.rag_top_k, match_ids=analysis.matched_match_ids or None)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    entity_matched = bool(analysis.matched_match_ids)
    if not entity_matched:
        # Sin equipo reconocido, descartamos fragmentos poco similares.
        chunks = [c for c in chunks if c.distance <= settings.rag_max_distance]
    context_quality = assess_context_quality(chunks, entity_matched)

    # 3) System Prompt dinámico + prompt de usuario con contexto y memoria
    system_prompt, active_rules = build_system_prompt(analysis, context_quality)
    history = database.get_history(payload.session_id, limit=settings.history_turns)
    user_prompt = build_user_prompt(message, chunks, history, analysis)
    logger.info("Reglas activas: %s | fragmentos: %d", active_rules, len(chunks))

    # 4) Llamada al LLM
    try:
        answer = llm.generate(system_prompt, user_prompt)
    except LLMError as exc:
        logger.error("%s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not answer:
        answer = "No he podido generar un análisis en este momento. Inténtalo de nuevo."

    # 5) Persistencia
    sources = [c.to_source() for c in chunks]
    row_id = database.save_interaction(
        payload.session_id, message, answer, active_rules, sources, f"{llm.provider}:{llm.model}"
    )

    return ChatResponse(
        id=row_id,
        answer=answer,
        active_rules=active_rules,
        context_quality=context_quality,
        sources=sources,
        analysis=analysis.to_dict(),
        provider=f"{llm.provider}:{llm.model}",
    )


@app.get("/api/history/{session_id}")
def get_history(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return database.get_history(session_id, limit=max(1, min(limit, 200)))


@app.delete("/api/history/{session_id}")
def delete_history(session_id: str) -> dict[str, int]:
    return {"deleted": database.clear_history(session_id)}


# ====================================================================== #
# Frontend estático (montado al final para no interceptar /api/*)
# ====================================================================== #
app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
