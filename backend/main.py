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
from concurrent.futures import ThreadPoolExecutor
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
    normalize,
)
from backend.football_api import (
    FootballAPIError,
    FEATURED_COMPETITIONS,
    available_leagues,
    fixture_details,
    infer_league_id,
    league_top_teams,
    league_teams,
    live_fixtures,
    resolve_entities_in_text,
    scheduled_fixtures,
    team_fixtures,
    team_last5_report,
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


class ChatImageAttachment(BaseModel):
    data: str = Field(..., min_length=10, max_length=6_000_000)
    mime_type: str = Field("image/jpeg", pattern=r"^image/(png|jpeg|webp|gif)$")


class ChatRequest(BaseModel):
    message: str = Field("", max_length=1000, description="Propuesta de apuesta del usuario")
    session_id: str = Field("default", min_length=1, max_length=64, pattern=r"^[\w-]+$")
    match_context: ChatFixtureContext | None = None
    image: ChatImageAttachment | None = None


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
        "title": "Resultado final, total de goles y ambos equipos marcan",
        "summary": "Revisa la racha de los últimos 5 partidos de ambos equipos, bajas confirmadas y cuotas antes de elegir un mercado.",
        "data_quality": "limitada",
        "basis": "",
    } for fixture in fixtures]


def _llm_error_message(error: LLMError) -> str:
    message = str(error).casefold()
    if any(token in message for token in ("503", "429", "service_unavailable", "high demand", "temporarily")):
        return "El analista IA está temporalmente saturado. El intento se reintentó; vuelve a probar en un momento."
    return "El analista IA no pudo completar la solicitud. Revisa la conexión o la configuración del proveedor."


def _local_fallback_answer(
    analysis: Any,
    chunks: list[Any],
    match: ChatFixtureContext | None = None,
    live_reports: list[dict[str, Any]] | None = None,
) -> str:
    """Respuesta estructurada con los últimos 5 partidos si el LLM externo no responde."""
    if live_reports:
        sections: list[str] = [
            "### 📊 Análisis y recomendación (datos verificados de los últimos 5 partidos)",
            "*(El modelo de lenguaje externo no respondió a tiempo; este resumen se construyó directamente con los datos reales recuperados.)*",
        ]
        team_rows = [
            "| Equipo | Forma (5P) | V-E-D | Goles a favor (Prom.) | Goles en contra (Prom.) | Total goles/P | Ambos marcan | +2.5 goles |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
        for rep in live_reports:
            avg = rep.get("averages") or {}
            played = avg.get("played") or 0
            team_rows.append(
                f"| **{rep.get('team')}** | {avg.get('form', '—')} | "
                f"{avg.get('wins', 0)}-{avg.get('draws', 0)}-{avg.get('losses', 0)} | "
                f"{avg.get('goals_for_total', 0)} ({avg.get('goals_for_avg', 0)}) | "
                f"{avg.get('goals_against_total', 0)} ({avg.get('goals_against_avg', 0)}) | "
                f"{avg.get('total_goals_avg', 0)} | "
                f"{avg.get('btts_count', 0)}/{played} ({avg.get('btts_pct', 0)}%) | "
                f"{avg.get('over_2_5_count', 0)}/{played} ({avg.get('over_2_5_pct', 0)}%) |"
            )
        sections.append("### 📈 Estadísticas de los últimos 5 partidos y promedios\n" + "\n".join(team_rows))

        player_blocks: list[str] = []
        for rep in live_reports:
            for p in (rep.get("players") or [])[:2]:
                p_rows = [
                    f"**{p['name']} ({rep.get('team')}) — últimos {p['appearances']} partidos:**",
                    "| Fecha | Partido | Marcador | Goles | Asistencias | Tiros (al arco) |",
                    "|---|---|---|---:|---:|---:|",
                ]
                for pm in p.get("matches") or []:
                    p_rows.append(
                        f"| {pm['date']} | {pm['match']} | {pm['score']} | "
                        f"{pm['goals']} | {pm['assists']} | {pm['shots']} ({pm['shots_on_target']}) |"
                    )
                p_rows.append(
                    f"| **Promedio / partido** | **{p['appearances']} PJ** | — | "
                    f"**{p['goals_avg']}** | **{p['assists_avg']}** | "
                    f"**{p['shots_avg']} ({p['shots_on_target_avg']})** |"
                )
                player_blocks.append("\n".join(p_rows))
        if player_blocks:
            sections.append("### 🏃 Estadísticas de jugador (últimos 5 partidos y promedios)\n" + "\n\n".join(player_blocks))

        avg_btts = round(sum((r.get("averages") or {}).get("btts_pct", 0) for r in live_reports) / len(live_reports))
        avg_over25 = round(sum((r.get("averages") or {}).get("over_2_5_pct", 0) for r in live_reports) / len(live_reports))
        avg_goals = round(sum((r.get("averages") or {}).get("total_goals_avg", 0) for r in live_reports) / len(live_reports), 2)
        recs: list[str] = []
        if "btts" in analysis.markets or avg_btts >= 60:
            fair = round(100 / max(1, avg_btts), 2)
            verdict = "Tendencia favorable" if avg_btts >= 60 else "Precaución / evitar si la cuota es baja"
            recs.append(f"- **Ambos marcan (BTTS)**: frecuencia reciente promedio de **{avg_btts}%** → cuota mínima justa **{fair}** ({verdict}).")
        if "over_under" in analysis.markets or avg_over25 >= 60 or avg_goals >= 2.6:
            fair = round(100 / max(1, avg_over25), 2)
            verdict = "Tendencia a +2.5 goles" if avg_over25 >= 60 else "Tendencia moderada / valorar -2.5 si la cuota acompaña"
            recs.append(f"- **Más/Menos 2.5 goles**: promedio conjunto de **{avg_goals} goles/partido** y **{avg_over25}%** con +2.5 → cuota mínima justa +2.5 **{fair}** ({verdict}).")
        if not recs:
            best = max(live_reports, key=lambda r: (r.get("averages") or {}).get("wins", 0))
            b_avg = best.get("averages") or {}
            win_pct = round(100 * (b_avg.get("wins", 0)) / max(1, b_avg.get("played", 1)))
            recs.append(
                f"- **Resultado / Doble oportunidad**: **{best.get('team')}** presenta mejor racha reciente ({b_avg.get('form')}, {win_pct}% victorias); "
                "considera **doble oportunidad** o **+1.5 goles** para menor varianza (🟡 Riesgo medio)."
            )
        sections.append(
            "### 🎯 Recomendación basada en la muestra\n"
            + "\n".join(recs)
            + "\n\n⚠️ *Ninguna apuesta es segura; evalúa cuotas reales antes de entrar y limita el stake al 1-2% del bankroll.*"
        )
        return "\n\n".join(sections)

    market_names = {
        "1x2": "resultado 1X2", "doble_oportunidad": "doble oportunidad",
        "over_under": "más/menos goles", "btts": "ambos marcan", "handicap": "hándicap",
        "corners": "córners", "tarjetas": "tarjetas",
    }
    markets = [market_names.get(item, item) for item in analysis.markets]
    if match:
        context = _fixture_schedule_answer(match)
    elif chunks:
        teams = list(dict.fromkeys(
            f"{chunk.metadata.get('home_team', '')} vs {chunk.metadata.get('away_team', '')}"
            for chunk in chunks if chunk.metadata.get("home_team") and chunk.metadata.get("away_team")
        ))
        context = (
            f"La base local encontró contexto para **{', '.join(teams[:3])}**."
            if teams else "Encontré contexto limitado en la base local."
        )
    else:
        context = "No identifiqué un equipo o partido concreto en las ligas conectadas."
    market_text = f"Mercado detectado: **{', '.join(markets)}**." if markets else ""
    return (
        "El proveedor de IA está temporalmente saturado. "
        f"{context} {market_text} "
        "Indica los nombres completos de los equipos (por ejemplo *Arsenal vs Chelsea* o *Real Madrid vs Barcelona*) para consultar sus últimos 5 partidos y calcular promedios."
    )


def _generate_with_fallback(
    request: Request,
    system_prompt: str,
    user_prompt: str,
    image_b64: str | None = None,
    image_mime_type: str | None = None,
    max_output_tokens: int | None = None,
    use_web_search: bool = False,
) -> tuple[str, LLMClient]:
    primary: LLMClient | None = request.app.state.llm
    fallback: LLMClient | None = request.app.state.llm_fallback
    if primary is None:
        if fallback is not None:
            try:
                return fallback.generate(
                    system_prompt, user_prompt, image_b64=image_b64,
                    image_mime_type=image_mime_type, max_output_tokens=max_output_tokens,
                    use_web_search=use_web_search,
                ), fallback
            except LLMError as exc:
                raise HTTPException(status_code=503, detail=_llm_error_message(exc)) from exc
        raise HTTPException(status_code=503, detail=request.app.state.llm_error or "LLM no configurado.")
    try:
        return primary.generate(
            system_prompt, user_prompt, image_b64=image_b64,
            image_mime_type=image_mime_type, max_output_tokens=max_output_tokens,
            use_web_search=use_web_search,
        ), primary
    except LLMError as exc:
        logger.warning("Falló el proveedor LLM principal (%s)", primary.provider)
        if fallback is not None:
            try:
                return fallback.generate(
                    system_prompt, user_prompt, image_b64=image_b64,
                    image_mime_type=image_mime_type, max_output_tokens=max_output_tokens,
                    use_web_search=use_web_search,
                ), fallback
            except LLMError:
                logger.warning("También falló el proveedor LLM de respaldo (%s)", fallback.provider)
        raise HTTPException(status_code=503, detail=_llm_error_message(exc)) from exc


def _extract_bet_slip_entities(request: Request, image: ChatImageAttachment) -> dict[str, Any]:
    """Lee equipos, jugadores, selecciones y cuotas de la foto para enriquecer el RAG."""
    primary: LLMClient | None = request.app.state.llm
    if primary is not None and primary.provider == "mock":
        return {}
    extract_sys = (
        "Extrae los datos visibles de la imagen de un boleto de apuesta deportiva. "
        "Responde SOLO con JSON válido sin bloques markdown: "
        '{"teams": ["..."], "players": ["..."], "selections": ["..."], "odds": [1.85], "stake": ""}. '
        "Si un campo no aparece, déjalo como lista vacía."
    )
    try:
        raw, _ = _generate_with_fallback(
            request,
            extract_sys,
            "Extrae los equipos, jugadores, selecciones de apuesta, cuotas y stake visibles en esta imagen.",
            image_b64=image.data,
            image_mime_type=image.mime_type,
            max_output_tokens=300,
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        parsed = json.loads(match.group(0) if match else cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as exc:
        logger.info("No se pudieron pre-extraer entidades del boleto (%s)", type(exc).__name__)
        return {}


def _is_schedule_question(message: str) -> bool:
    text = message.casefold()
    asks_time = bool(re.search(r"\b(cu[aá]ndo|qu[eé] d[ií]a|a qu[eé] hora|fecha|horario|hora de inicio|kick.?off|schedule)\b", text))
    asks_analysis = bool(
        re.search(
            r"\b(apuest\w*|recomiend\w*|estad[ií]stic\w*|promedio\w*|tabla\w*|gol(?:es)?|btts|ambos|cuota\w*|gana\w*|jugador\w*|analiz\w*|datos disponibles)\b",
            text,
        )
    )
    return asks_time and not asks_analysis


def _fixture_schedule_answer(match: ChatFixtureContext) -> str:
    if not match.kickoff:
        return f"El partido **{match.home} vs {match.away}** está en el calendario de **{match.competition}**, pero el proveedor aún no confirma la fecha y hora."
    try:
        kickoff = datetime.fromisoformat(match.kickoff.replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        kickoff = kickoff.astimezone(ZoneInfo("America/Bogota"))
        weekdays = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
        date_text = f"{weekdays[kickoff.weekday()]}, {kickoff.strftime('%d/%m/%Y')}"
        time_text = kickoff.strftime("%H:%M")
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
        "history_storage": {"engine": "SQLite", "persistent": True, "scope": "local"},
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
    raw_message = payload.message.strip()
    if not raw_message and not payload.image:
        raise HTTPException(status_code=422, detail="Escribe una consulta o adjunta una foto de tu apuesta.")

    message = raw_message or (
        "Analiza la foto de mi apuesta: indica qué selecciones aparecen, cruza los equipos o jugadores "
        "con sus estadísticas de los últimos 5 partidos (tabla y promedios), detecta las problemáticas "
        "o riesgos del boleto y dame una recomendación objetiva."
    )
    stored_user_message = raw_message or "📸 Foto de apuesta adjunta"

    if payload.match_context and not payload.image and _is_schedule_question(message):
        analysis = analyze_query(message, store.list_matches())
        _, active_rules = build_system_prompt(analysis, "good")
        answer = _fixture_schedule_answer(payload.match_context)
        row_id = database.save_interaction(
            payload.session_id, stored_user_message, answer, active_rules, [], "api-football:fixture-context"
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

    slip_info: dict[str, Any] = _extract_bet_slip_entities(request, payload.image) if payload.image else {}
    slip_teams = [str(item) for item in (slip_info.get("teams") or []) if item]
    slip_players = [str(item) for item in (slip_info.get("players") or []) if item]
    slip_selections = [str(item) for item in (slip_info.get("selections") or []) if item]
    analysis_text = " ".join([message, *slip_teams, *slip_players, *slip_selections]).strip()

    # 1) Resolver equipos mencionados (de match_context, texto libre y boleto adjunto)
    extra_teams: list[dict[str, str]] = []
    if payload.match_context:
        comp_id = infer_league_id(payload.match_context.competition)
        extra_teams = [
            {"name": payload.match_context.home, "league_id": comp_id or infer_league_id("", payload.match_context.home)},
            {"name": payload.match_context.away, "league_id": comp_id or infer_league_id("", payload.match_context.away)},
        ]
    resolved_teams, resolved_players = resolve_entities_in_text(analysis_text, extra_teams=extra_teams)
    for sp in slip_players:
        if sp not in resolved_players:
            resolved_players.append(sp)

    # Alcance de la base vectorial: si hay match_context o equipos en vivo fuera de mock_matches,
    # evitamos mezclar fragmentos de otros partidos no relacionados.
    known_matches = store.list_matches()
    if payload.match_context:
        target_pair = {normalize(payload.match_context.home), normalize(payload.match_context.away)}
        relevant_matches = [
            item for item in known_matches
            if {normalize(item.get("home_team", "")), normalize(item.get("away_team", ""))} == target_pair
        ]
    else:
        relevant_matches = known_matches

    # 2) Hechos de la consulta (Sistema Experto)
    analysis = analyze_query(analysis_text, relevant_matches)
    analysis.has_image = payload.image is not None
    if slip_info.get("odds"):
        for raw_odd in slip_info["odds"]:
            try:
                odd_val = float(str(raw_odd).replace(",", "."))
                if 1.01 <= odd_val <= 100 and odd_val not in analysis.odds:
                    analysis.odds.append(odd_val)
            except ValueError:
                pass
    if len(slip_selections) >= 2:
        analysis.is_parlay = True
    if resolved_players:
        analysis.mentions_player = True
    if payload.match_context and relevant_matches:
        analysis.matched_match_ids = list(dict.fromkeys(
            [item["match_id"] for item in relevant_matches if item.get("match_id")]
        ))
        analysis.matched_teams = [payload.match_context.home, payload.match_context.away]
    elif resolved_teams:
        for t in resolved_teams:
            if t["name"] not in analysis.matched_teams:
                analysis.matched_teams.append(t["name"])

    # 3) Estadísticas reales de los últimos 5 partidos (equipos y, si aplica, jugadores)
    live_reports: list[dict[str, Any]] = []
    if resolved_teams:
        try:
            season_year = int(payload.match_context.kickoff[:4]) if payload.match_context and payload.match_context.kickoff else datetime.now().year
        except (TypeError, ValueError):
            season_year = datetime.now().year

        player_search_text = " ".join([analysis_text, *resolved_players]).strip()

        def _fetch_report(team_info: dict[str, str]) -> dict[str, Any] | None:
            try:
                return team_last5_report(
                    team_info["name"],
                    team_info.get("league_id", ""),
                    season=season_year,
                    include_players=analysis.mentions_player,
                    player_query=player_search_text,
                    limit=5,
                )
            except Exception as exc:
                logger.info("No se pudo cargar reporte últimos 5 de %s (%s)", team_info.get("name"), type(exc).__name__)
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            for rep in pool.map(_fetch_report, resolved_teams[:2]):
                if rep:
                    live_reports.append(rep)

    # 4) Recuperación semántica en ChromaDB (solo si el partido completo coincide con el catálogo local o no hay reporte en vivo)
    query_norm = normalize(message)
    resolved_norms = [normalize(t["name"]) for t in resolved_teams]

    def _team_in_resolved(mock_team: str) -> bool:
        mt = normalize(mock_team)
        return any(rn == mt or rn in mt or mt in rn for rn in resolved_norms)

    matched_mock_ids = [
        item["match_id"]
        for item in relevant_matches
        if item.get("match_id") in analysis.matched_match_ids
        and (
            payload.match_context is not None
            or "clasico" in query_norm
            or (_team_in_resolved(item.get("home_team", "")) and _team_in_resolved(item.get("away_team", "")))
        )
    ]
    if not matched_mock_ids and not live_reports:
        matched_mock_ids = list(analysis.matched_match_ids)

    try:
        store.check_compatibility()
        should_search_chroma = bool(matched_mock_ids) or not resolved_teams
        chunks = (
            store.search(message, top_k=settings.rag_top_k, match_ids=matched_mock_ids or None)
            if should_search_chroma else []
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    entity_matched = bool(matched_mock_ids)
    if not entity_matched:
        chunks = [c for c in chunks if c.distance <= settings.rag_max_distance]
    context_quality = assess_context_quality(chunks, entity_matched, has_live_reports=bool(live_reports))

    # 5) System Prompt dinámico + prompt de usuario con datos de últimos 5 partidos, RAG y memoria
    system_prompt, active_rules = build_system_prompt(analysis, context_quality)
    if live_reports and "ultimos_5_partidos" not in active_rules:
        active_rules.append("ultimos_5_partidos")
    sources = [c.to_source() for c in chunks]
    for rep in live_reports:
        sources.append({
            "id": f"espn::{normalize(rep['team'])}",
            "match_id": rep.get("league_id", ""),
            "match": f"{rep['team']} ({rep.get('source', 'últimos 5 partidos')})",
            "category": "ultimos_5",
            "similarity": 1.0,
        })
    history = database.get_history(payload.session_id, limit=settings.history_turns)
    user_prompt = build_user_prompt(message, chunks, history, analysis, live_reports=live_reports)
    if payload.match_context:
        match = payload.match_context
        kickoff = match.kickoff or "fecha y hora no disponibles"
        system_prompt += (
            "\n\n## Partido validado por el calendario en vivo\n"
            f"El partido seleccionado es {match.home} vs {match.away}, de {match.competition}. "
            f"Su inicio registrado es {kickoff} y su estado es {match.status}."
        )
        user_prompt += (
            "\n\n<partido_consultado>\n"
            f"ID: {match.id}\nCompetición: {match.competition}\n"
            f"Partido: {match.home} vs {match.away}\n"
            f"Fecha y hora del inicio (ISO 8601): {kickoff}\nEstado: {match.status}\n"
            "Usa estos datos exactos para responder preguntas sobre cuándo y dónde aparece este partido.\n"
            "</partido_consultado>"
        )
    logger.info("Reglas activas: %s | fragmentos: %d | reportes_5p: %d", active_rules, len(chunks), len(live_reports))

    # 6) Llamada al LLM (con búsqueda web si falta contexto local + respaldo estructurado)
    try:
        answer, used_llm = _generate_with_fallback(
            request,
            system_prompt,
            user_prompt,
            image_b64=payload.image.data if payload.image else None,
            image_mime_type=payload.image.mime_type if payload.image else None,
            use_web_search=(context_quality != "good"),
        )
        provider = f"{used_llm.provider}:{used_llm.model}"
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        answer = _local_fallback_answer(analysis, chunks, payload.match_context, live_reports=live_reports)
        provider = "local-fallback"
    if not answer:
        answer = "No he podido generar un análisis en este momento. Inténtalo de nuevo."

    # 7) Persistencia
    row_id = database.save_interaction(
        payload.session_id,
        stored_user_message,
        answer,
        active_rules,
        sources,
        provider,
        user_image_data=payload.image.data if payload.image else "",
        user_image_mime=payload.image.mime_type if payload.image else "",
    )

    return ChatResponse(
        id=row_id,
        answer=answer,
        active_rules=active_rules,
        context_quality=context_quality,
        sources=sources,
        analysis=analysis.to_dict(),
        provider=provider,
    )


@app.get("/api/history")
def list_history_sessions(limit: int = 50) -> list[dict[str, Any]]:
    return database.list_sessions(limit=max(1, min(limit, 200)))


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
