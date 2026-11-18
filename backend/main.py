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
    uvicorn backend.main:app --reload --port 8011
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime, timezone
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen
from contextlib import asynccontextmanager
from typing import Any
from zoneinfo import ZoneInfo

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
from backend.football_api import (
    FootballAPIError,
    available_leagues,
    fixture_details,
    league_top_teams,
    league_teams,
    live_fixtures,
    scheduled_fixtures,
    team_fixtures,
    team_statistics,
)
from backend.llm_client import LLMClient, LLMError, OpenAIClient, get_llm_client
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
_quick_analysis_cache: dict[tuple[str, ...], tuple[float, list[dict[str, str]]]] = {}


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
    app.state.llm_fallback = None
    try:
        app.state.llm = get_llm_client(settings)
        logger.info("LLM listo: %s / %s", app.state.llm.provider, app.state.llm.model)
    except LLMError as exc:
        app.state.llm_error = str(exc)
        logger.warning("LLM no disponible: %s", exc)

    if settings.llm_provider == "gemini" and settings.openai_api_key:
        try:
            app.state.llm_fallback = OpenAIClient(
                settings.openai_api_key, settings.openai_model, settings.llm_max_output_tokens
            )
            logger.info("OpenAI listo como respaldo de Gemini")
        except Exception as exc:
            logger.warning("No se pudo inicializar el respaldo OpenAI: %s", type(exc).__name__)

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
class ChatFixtureContext(BaseModel):
    id: str = Field(..., min_length=1, max_length=32)
    home: str = Field(..., min_length=1, max_length=100)
    away: str = Field(..., min_length=1, max_length=100)
    home_logo: str = Field("", max_length=300)
    away_logo: str = Field("", max_length=300)
    competition: str = Field("Fútbol", max_length=120)
    kickoff: str = Field("", max_length=40)
    status: str = Field("NS", max_length=20)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="Propuesta de apuesta del usuario")
    session_id: str = Field("default", min_length=1, max_length=64, pattern=r"^[\w-]+$")
    match_context: ChatFixtureContext | None = None


class QuickAnalysisFixture(BaseModel):
    id: str = Field(..., min_length=1, max_length=32)
    home: str = Field(..., min_length=1, max_length=100)
    away: str = Field(..., min_length=1, max_length=100)
    competition: str = Field("Fútbol", max_length=120)
    kickoff: str = Field("", max_length=40)
    status: str = Field("NS", max_length=20)


class QuickAnalysisRequest(BaseModel):
    fixtures: list[QuickAnalysisFixture] = Field(..., min_length=1, max_length=10)


def _quick_analysis_from_tables(fixtures: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return useful market prompts immediately without making live provider calls."""
    return [{
        "fixture_id": str(fixture.get("id", "")),
        "title": "Compara 1X2, goles y ambos marcan",
        "summary": "Revisa la forma reciente de ambos equipos, alineaciones y cuotas antes de elegir un mercado.",
        "data_quality": "limitada",
        "basis": "",
    } for fixture in fixtures]


def _llm_error_message(error: LLMError) -> str:
    message = str(error).casefold()
    if any(token in message for token in ("503", "429", "service_unavailable", "high demand", "temporarily")):
        return "El analista IA está temporalmente saturado. El intento se reintentó; vuelve a probar en un momento."
    return "El analista IA no pudo completar la solicitud. Revisa la conexión o la configuración del proveedor."


def _generate_with_fallback(request: Request, system_prompt: str, user_prompt: str) -> tuple[str, LLMClient]:
    primary: LLMClient | None = request.app.state.llm
    fallback: LLMClient | None = request.app.state.llm_fallback
    if primary is None:
        if fallback is not None:
            try:
                return fallback.generate(system_prompt, user_prompt), fallback
            except LLMError as exc:
                raise HTTPException(status_code=503, detail=_llm_error_message(exc)) from exc
        raise HTTPException(status_code=503, detail=request.app.state.llm_error or "LLM no configurado.")
    try:
        return primary.generate(system_prompt, user_prompt), primary
    except LLMError as exc:
        logger.warning("Falló el proveedor LLM principal (%s)", primary.provider)
        if fallback is not None:
            try:
                return fallback.generate(system_prompt, user_prompt), fallback
            except LLMError:
                logger.warning("También falló el proveedor LLM de respaldo (%s)", fallback.provider)
        raise HTTPException(status_code=503, detail=_llm_error_message(exc)) from exc


def _is_schedule_question(message: str) -> bool:
    text = message.casefold()
    return bool(re.search(r"\b(cu[aá]ndo|qu[eé] d[ií]a|a qu[eé] hora|fecha|horario|hora de inicio|pr[oó]xim[oa]s? partido|siguiente partido|kick.?off|schedule)\b", text))


def _fixture_schedule_answer(match: ChatFixtureContext) -> str:
    if not match.kickoff:
        return f"El partido **{match.home} vs {match.away}** está en el calendario de **{match.competition}**, pero el proveedor aún no confirma la fecha y hora."
    try:
        kickoff = datetime.fromisoformat(match.kickoff.replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        kickoff = kickoff.astimezone(ZoneInfo("America/Bogota"))
        date_text, time_text = kickoff.strftime("%d/%m/%Y"), kickoff.strftime("%H:%M")
    except ValueError:
        date_text, time_text = match.kickoff, ""
    when = f"el {date_text} a las {time_text}" if time_text else f"el {date_text}"
    status = match.status.upper()
    if status in {"FT", "AET", "PEN"}:
        verb = "se jugó"
    elif status in {"LIVE", "1H", "2H", "HT", "ET", "BT", "P"}:
        verb = "está en juego desde"
    else:
        verb = "está programado para"
    return f"El partido **{match.home} vs {match.away}** de **{match.competition}** {verb} {when} (hora de Colombia)."


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


@app.get("/api/football/live")
def football_live() -> dict[str, Any]:
    """Marcadores en vivo de todas las ligas cubiertas por API-Football."""
    try:
        return {"matches": live_fixtures(), "updated": datetime.now(timezone.utc).isoformat()}
    except FootballAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/football/leagues")
def football_leagues() -> dict[str, Any]:
    """Ligas y copas activas con escudos, países y temporada disponible."""
    try:
        return {"leagues": available_leagues()}
    except FootballAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/football/teams")
def football_teams(league: int, season: int) -> dict[str, Any]:
    """Clubes y escudos de la liga y temporada seleccionadas."""
    if league < 1 or not 1900 <= season <= 2200:
        raise HTTPException(status_code=422, detail="La liga o la temporada no son válidas.")
    try:
        return {"teams": league_teams(league, season)}
    except FootballAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/football/standings")
def football_standings(league: int, season: int) -> dict[str, Any]:
    """Top tres equipos según la tabla actual de la competición y temporada."""
    if league < 1 or not 1900 <= season <= 2200:
        raise HTTPException(status_code=422, detail="La liga o la temporada no son válidas.")
    try:
        return {"teams": league_top_teams(league, season)}
    except FootballAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/football/team-fixtures")
def football_team_fixtures(team_id: int, season: int, limit: int = 10) -> dict[str, Any]:
    """Siguientes partidos del club, limitado a las diez competiciones de la app."""
    if team_id < 1 or not 1900 <= season <= 2200 or not 1 <= limit <= 20:
        raise HTTPException(status_code=422, detail="El equipo, la temporada o el límite no son válidos.")
    try:
        return {"matches": team_fixtures(team_id, season, limit)}
    except FootballAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/football/team-statistics")
def football_team_statistics(league: int, season: int, team: int, team_name: str = "") -> dict[str, Any]:
    """Team statistics used by the interactive league comparison screen."""
    if league < 1 or team < 1 or not 1900 <= season <= 2200:
        raise HTTPException(status_code=422, detail="La liga, el equipo o la temporada no son válidos.")
    try:
        return team_statistics(league, season, team, team_name)
    except FootballAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/football/fixtures")
def football_fixtures(from_date: str, to_date: str, leagues: str = "") -> dict[str, Any]:
    """Calendario de todas las ligas cubiertas para un rango de hasta siete días."""
    try:
        start, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Usa fechas válidas con formato YYYY-MM-DD.") from exc
    if end < start or (end - start).days > 6:
        raise HTTPException(status_code=422, detail="El rango debe ser de uno a siete días.")
    try:
        preferred_leagues = list(dict.fromkeys(value for value in leagues.split(",") if value.isdigit()))[:10]
        matches = scheduled_fixtures(start.isoformat(), end.isoformat(), preferred_leagues)
        return {"matches": matches, "updated": datetime.now(timezone.utc).isoformat()}
    except FootballAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/football/fixtures/{fixture_id}")
def football_fixture_details(fixture_id: int) -> dict[str, Any]:
    """Detalles, estadísticas y eventos disponibles de un partido."""
    try:
        return fixture_details(fixture_id)
    except FootballAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/api/quick-analysis")
def quick_analysis(payload: QuickAnalysisRequest) -> dict[str, Any]:
    """Return immediate, data-grounded match suggestions without depending on LLM uptime."""
    fixtures = [fixture.model_dump() for fixture in payload.fixtures]
    cache_key = tuple(f"{item['id']}:{item['home']}:{item['away']}:{item['competition']}:{item['kickoff']}:{item['status']}" for item in fixtures)
    cached = _quick_analysis_cache.get(cache_key)
    if cached and cached[0] > time.time():
        return {"provider": "Análisis de datos de fútbol", "suggestions": cached[1], "cached": True}
    suggestions = _quick_analysis_from_tables(fixtures)
    _quick_analysis_cache[cache_key] = (time.time() + 10 * 60, suggestions)
    return {"provider": "Análisis de datos de fútbol", "suggestions": suggestions, "cached": False}


@app.get("/api/analytics")
def analytics() -> dict[str, Any]:
    """Métricas calculadas desde el dataset de demostración del proyecto."""
    try:
        dataset = json.loads(settings.data_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("No se pudo leer el dataset de analíticas: %s", exc)
        raise HTTPException(status_code=503, detail="El dataset de estadísticas no está disponible.") from exc

    teams: dict[str, dict[str, Any]] = {}
    matches: list[dict[str, Any]] = []
    for match in dataset.get("matches", []):
        home, away = match.get("home_team", {}), match.get("away_team", {})
        for team, side in ((home, "home"), (away, "away")):
            name = team.get("name")
            form = team.get("recent_form", [])
            if not name:
                continue
            teams[name] = {
                "name": name,
                "competition": match.get("competition", ""),
                "league_position": team.get("league_position"),
                "form": form,
                "recent_win_rate": round(100 * form.count("W") / len(form)) if form else None,
                "goals_scored_avg": team.get("goals_scored_avg"),
                "goals_conceded_avg": team.get("goals_conceded_avg"),
                "xg_for_avg": team.get("xg_for_avg"),
                "xg_against_avg": team.get("xg_against_avg"),
                "over_2_5_pct": team.get("over_2_5_pct"),
                "btts_pct": team.get("btts_pct"),
                "corners_avg": team.get("corners_avg"),
                "side": side,
            }

        odds = match.get("odds", {}).get("1x2", {})
        implied = [1 / odds[key] if odds.get(key) else 0 for key in ("home", "draw", "away")]
        total = sum(implied)
        probabilities = [round(value * 100 / total) for value in implied] if total else []
        if probabilities:
            probabilities[2] = 100 - probabilities[0] - probabilities[1]
        h2h = match.get("h2h", {})
        h2h_scores = []
        for result in h2h.get("last_5", []):
            score_text = result.split("|", 1)[-1]
            score = re.search(r"\b(\d+)\s*[-–:]\s*(\d+)\b", score_text)
            if score:
                h2h_scores.append((int(score.group(1)), int(score.group(2))))
        h2h_total = len(h2h_scores)
        matches.append({
            "id": match.get("match_id", ""),
            "competition": match.get("competition", ""),
            "date": match.get("date", ""),
            "kickoff": match.get("kickoff", ""),
            "home": home.get("name", ""),
            "away": away.get("name", ""),
            "home_form": home.get("recent_form", []),
            "away_form": away.get("recent_form", []),
            "home_xg": home.get("xg_for_avg"),
            "away_xg": away.get("xg_for_avg"),
            "home_corners": home.get("corners_avg"),
            "away_corners": away.get("corners_avg"),
            "h2h": h2h.get("last_5", []),
            "h2h_summary": h2h.get("summary", ""),
            "h2h_goal_average": round(sum(a + b for a, b in h2h_scores) / h2h_total, 1) if h2h_total else None,
            "h2h_btts_pct": round(100 * sum(a > 0 and b > 0 for a, b in h2h_scores) / h2h_total) if h2h_total else None,
            "h2h_over_2_5_pct": round(100 * sum(a + b > 2.5 for a, b in h2h_scores) / h2h_total) if h2h_total else None,
            "probabilities": dict(zip(("home", "draw", "away"), probabilities)),
        })

    return {
        "source": dataset.get("metadata", {}).get("source", "Dataset de demostración"),
        "generated_at": dataset.get("metadata", {}).get("generated_at"),
        "simulated": True,
        "matches": matches,
        "teams": sorted(teams.values(), key=lambda team: (team["recent_win_rate"] or 0, team["xg_for_avg"] or 0), reverse=True),
    }


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
    if llm is None and request.app.state.llm_fallback is None:
        raise HTTPException(status_code=503, detail=request.app.state.llm_error or "LLM no configurado.")

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío.")

    if payload.match_context and _is_schedule_question(message):
        analysis = analyze_query(message, store.list_matches())
        _, active_rules = build_system_prompt(analysis, "good")
        answer = _fixture_schedule_answer(payload.match_context)
        row_id = database.save_interaction(
            payload.session_id, message, answer, active_rules, [], "api-football:fixture-context"
        )
        return ChatResponse(
            id=row_id,
            answer=answer,
            active_rules=active_rules,
            context_quality="good",
            sources=[],
            analysis=analysis.to_dict(),
            provider="api-football:fixture-context",
        )

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
    sources = [c.to_source() for c in chunks]
    history = database.get_history(payload.session_id, limit=settings.history_turns)
    user_prompt = build_user_prompt(message, chunks, history, analysis)
    if payload.match_context:
        match = payload.match_context
        kickoff = match.kickoff or "fecha y hora no disponibles"
        system_prompt += (
            "\n\n## Partido validado por el calendario en vivo\n"
            f"El partido disponible es {match.home} vs {match.away}, de {match.competition}. "
            f"Su inicio registrado es {kickoff} y su estado es {match.status}. "
            "Puedes responder sobre este encuentro usando estos datos. Si la consulta pide análisis deportivo, "
            "aclara que no se proporcionaron estadísticas adicionales y no las inventes."
        )
        user_prompt += (
            "\n\n<partido_consultado>\n"
            f"ID: {match.id}\nCompetición: {match.competition}\n"
            f"Partido: {match.home} vs {match.away}\n"
            f"Fecha y hora del inicio (ISO 8601): {kickoff}\nEstado: {match.status}\n"
            "Usa estos datos exactos para responder preguntas sobre cuándo y dónde aparece este partido. "
            "No inventes otros horarios ni fechas.\n</partido_consultado>"
        )
    logger.info("Reglas activas: %s | fragmentos: %d", active_rules, len(chunks))

    # 4) Llamada al LLM
    answer, used_llm = _generate_with_fallback(request, system_prompt, user_prompt)
    if not answer:
        answer = "No he podido generar un análisis en este momento. Inténtalo de nuevo."

    # 5) Persistencia
    row_id = database.save_interaction(
        payload.session_id, message, answer, active_rules, sources, f"{used_llm.provider}:{used_llm.model}"
    )

    return ChatResponse(
        id=row_id,
        answer=answer,
        active_rules=active_rules,
        context_quality=context_quality,
        sources=sources,
        analysis=analysis.to_dict(),
        provider=f"{used_llm.provider}:{used_llm.model}",
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
