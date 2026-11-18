"""Small server-side client for API-Football (API-Sports)."""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from datetime import date, timedelta
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.config import settings
from backend.football_catalog import champions_league_teams, ligue1_teams

logger = logging.getLogger("statstriker.football")
BASE_URL = "https://v3.football.api-sports.io"
FEATURED_COMPETITIONS = {
    "39": "Premier League",
    "140": "LaLiga",
    "78": "Bundesliga",
    "135": "Serie A",
    "61": "Ligue 1",
    "2": "UEFA Champions League",
    "3": "UEFA Europa League",
    "13": "Copa Libertadores",
    "71": "Brasileirão Série A",
    "253": "MLS",
}
THESPORTSDB_LEAGUES = {"39": "4328", "140": "4335", "135": "4332", "78": "4331", "61": "4334", "71": "4351", "2": "4480", "3": "4481", "13": "4501", "253": "4346"}
THESPORTSDB_TO_API_LEAGUE = {value: key for key, value in THESPORTSDB_LEAGUES.items()}
THESPORTSDB_LEAGUE_NAMES = {
    "39": "English_Premier_League",
    "140": "Spanish_La_Liga",
    "135": "Italian_Serie_A",
    "78": "German_Bundesliga",
    "61": "French_Ligue_1",
    "71": "Brazilian_Serie_A",
    "253": "American_Major_League_Soccer",
}
THESPORTSDB_SEASON_SCHEDULES = {
    "2": ("4480", "2026-2027"),
    "3": ("4481", "2026-2027"),
    "13": ("4501", "2026"),
    "71": ("4351", "2026"),
    "253": ("4346", "2026"),
}
# Last-resort club catalog so every competition remains selectable when the
# configured API plan or the public fallback is rate-limited. These are club
# names only; they are never used as current standings or match results.
FALLBACK_CLUBS = {
    "39": ["Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Chelsea", "Crystal Palace", "Everton", "Fulham", "Liverpool", "Manchester City", "Manchester United", "Newcastle United", "Nottingham Forest", "Tottenham Hotspur", "West Ham United", "Wolverhampton Wanderers", "Leeds United", "Burnley", "Sunderland"],
    "140": ["Real Madrid", "Barcelona", "Atlético Madrid", "Athletic Club", "Real Sociedad", "Real Betis", "Villarreal", "Sevilla", "Valencia", "Girona", "Celta Vigo", "Osasuna", "Getafe", "Mallorca", "Espanyol", "Rayo Vallecano", "Alavés", "Elche", "Levante", "Real Oviedo"],
    "78": ["Bayern Munich", "Borussia Dortmund", "Bayer Leverkusen", "RB Leipzig", "Eintracht Frankfurt", "VfB Stuttgart", "SC Freiburg", "Hoffenheim", "Wolfsburg", "Mainz 05", "Borussia Mönchengladbach", "Werder Bremen", "Union Berlin", "Augsburg", "Heidenheim", "St. Pauli", "Hamburger SV", "Cologne"],
    "135": ["Inter Milan", "AC Milan", "Juventus", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina", "Bologna", "Torino", "Udinese", "Genoa", "Cagliari", "Lecce", "Parma", "Como", "Sassuolo", "Pisa", "Cremonese", "Verona"],
    "61": ["Paris Saint-Germain", "Marseille", "Monaco", "Lyon", "Lille", "Nice", "Lens", "Rennes", "Strasbourg", "Toulouse", "Nantes", "Montpellier", "Brest", "Auxerre", "Angers", "Le Havre", "Lorient", "Metz"],
    "2": ["Real Madrid", "Barcelona", "Manchester City", "Liverpool", "Arsenal", "Bayern Munich", "Borussia Dortmund", "Paris Saint-Germain", "Inter Milan", "AC Milan", "Juventus", "Atlético Madrid", "Benfica", "Porto", "Ajax", "Sporting CP", "Napoli", "Chelsea", "Tottenham Hotspur", "Atalanta"],
    "3": ["Manchester United", "Tottenham Hotspur", "Roma", "Lazio", "Athletic Club", "Real Sociedad", "Lyon", "Marseille", "Eintracht Frankfurt", "Freiburg", "Ajax", "Feyenoord", "PSV Eindhoven", "Porto", "Benfica", "Fenerbahçe", "Galatasaray", "Rangers", "Celtic", "Olympiacos"],
    "13": ["Flamengo", "Palmeiras", "River Plate", "Boca Juniors", "Fluminense", "Botafogo", "São Paulo", "Atlético Mineiro", "Internacional", "Grêmio", "Corinthians", "Racing Club", "Independiente", "San Lorenzo", "Peñarol", "Nacional", "Colo-Colo", "Universidad de Chile", "LDU Quito", "Barcelona SC"],
    "71": ["Flamengo", "Palmeiras", "Corinthians", "São Paulo", "Santos", "Grêmio", "Internacional", "Atlético Mineiro", "Cruzeiro", "Botafogo", "Fluminense", "Vasco da Gama", "Bahia", "Fortaleza", "Ceará", "Vitória", "Red Bull Bragantino", "Athletico Paranaense", "Coritiba", "Sport Recife"],
    "253": ["Inter Miami", "LA Galaxy", "Los Angeles FC", "Seattle Sounders", "Portland Timbers", "Vancouver Whitecaps", "San Diego FC", "San Jose Earthquakes", "Colorado Rapids", "Real Salt Lake", "Houston Dynamo", "FC Dallas", "Austin FC", "Minnesota United", "Sporting Kansas City", "St. Louis City", "New York City FC", "New York Red Bulls", "Atlanta United", "Orlando City", "Inter Miami", "Philadelphia Union", "Columbus Crew", "FC Cincinnati", "Nashville SC", "Charlotte FC", "New England Revolution", "Toronto FC", "CF Montréal", "Chicago Fire"],
}
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = Lock()
UEFA_UCL_STANDINGS_URL = "https://standings.uefa.com/v1/standings?competitionId=1&seasonYear=2027&limit=50&offset=0"
# The UEFA table is the reliable current-season source when the API-Sports plan blocks UCL statistics.
UCL_OFFICIAL_NAME_ALIASES = {
    "real madrid c f": "real madrid", "arsenal f c": "arsenal", "arsenal fc": "arsenal", "como 1907": "como",
    "fc barcelona": "barcelona", "liverpool f c": "liverpool", "liverpool fc": "liverpool", "club brugge kv": "club brugge",
    "sporting clube de portugal": "sporting cp", "real betis balompie": "real betis",
    "fc bayern munchen": "bayern munich", "vfb stuttgart": "stuttgart",
    "rb leipzig": "leipzig",
    "fc internazionale milano": "inter", "galatasaray a s": "galatasaray",
    "fenerbahce sk": "fenerbahce", "as roma": "roma", "fc shakhtar donetsk": "shakhtar donetsk",
    "viking fk": "viking", "atletico de madrid": "atletico madrid", "psv eindhoven": "psv",
    "fk bodo glimt": "bodo glimt", "fk bod glimt": "bodo glimt", "fc porto": "porto", "ssc napoli": "napoli",
    "villarreal cf": "villarreal", "aek athens fc": "aek athens", "rc lens": "lens",
    "sk slavia praha": "slavia praha", "losc lille": "lille",
    "sk slovan bratislava": "slovan bratislava", "sabah fc": "sabah baku",
}


class FootballAPIError(Exception):
    """A safe-to-display error from the football data provider."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _normalized_team_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9]+", " ", plain).strip()
    return UCL_OFFICIAL_NAME_ALIASES.get(normalized, normalized)


def _uefa_champions_standings() -> list[dict[str, Any]]:
    """Official UEFA league-phase table, including current stats and crests."""
    cache_key = "uefa:ucl:standings:2027"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]
    request = Request(UEFA_UCL_STANDINGS_URL, headers={"Accept": "application/json", "User-Agent": "StatStriker/1.0"})
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("No se pudo consultar la tabla UEFA (%s)", type(exc).__name__)
        raise FootballAPIError("La tabla oficial de UEFA no estÃ¡ disponible en este momento.", 502) from exc
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        payload = payload[0]
    if not isinstance(payload, dict):
        raise FootballAPIError("UEFA devolviÃ³ un formato de tabla inesperado.", 502)
    items = payload.get("items") or []
    rows = []
    for item in items:
        team = item.get("team") or {}
        translations = team.get("translations") or {}
        official_names = translations.get("displayOfficialName") or {}
        name = official_names.get("EN") or team.get("internationalName") or ""
        if not name:
            continue
        played = item.get("played")
        rows.append({
            "rank": item.get("rank"), "team_id": str(team.get("id") or item.get("teamId") or ""),
            "name": name, "logo": team.get("logoUrl") or "", "points": item.get("points"),
            "played": played, "wins": item.get("won"), "draws": item.get("drawn"), "loses": item.get("lost"),
            "goals_for": item.get("goalsFor"), "goals_against": item.get("goalsAgainst"),
            "goal_difference": item.get("goalDifference"),
            "goals_for_avg": round(item["goalsFor"] / played, 2) if isinstance(item.get("goalsFor"), (int, float)) and isinstance(played, (int, float)) and played else None,
            "goals_against_avg": round(item["goalsAgainst"] / played, 2) if isinstance(item.get("goalsAgainst"), (int, float)) and isinstance(played, (int, float)) and played else None,
            "form": "", "description": "ClasificaciÃ³n oficial UEFA · fase liga 2026/27",
        })
    if len(rows) != 36:
        raise FootballAPIError("UEFA no devolviÃ³ los 36 equipos de la fase liga.", 502)
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 10 * 60, rows)
    return rows


def _request(endpoint: str, params: dict[str, str], ttl: int) -> dict[str, Any]:
    if not settings.football_api_key:
        raise FootballAPIError("Configura API_SPORTS_KEY en el archivo .env.", 503)

    query = urlencode(sorted(params.items()))
    cache_key = f"{endpoint}?{query}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    request = Request(
        f"{BASE_URL}/{endpoint}?{query}",
        headers={"x-apisports-key": settings.football_api_key, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Never log the request URL or headers: they contain credential material.
        logger.warning("API-Football devolvió HTTP %s en %s", exc.code, endpoint)
        raise FootballAPIError("El proveedor de fútbol rechazó la consulta.", 502) from exc
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("API-Football no está disponible (%s)", type(exc).__name__)
        raise FootballAPIError("No se pudo conectar con el proveedor de fútbol.", 502) from exc

    errors = payload.get("errors") or {}
    if errors:
        # Log field names only: provider error values can contain account details.
        error_fields = sorted(str(field) for field in errors) if isinstance(errors, dict) else ["provider"]
        logger.warning("API-Football reportó un error en %s (campos: %s)", endpoint, ", ".join(error_fields))
        raise FootballAPIError("API-Football reportó un error. Revisa la clave y el plan de la cuenta.", 502)

    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + ttl, payload)
    return payload


def _fixture(item: dict[str, Any]) -> dict[str, Any]:
    fixture = item.get("fixture") or {}
    league = item.get("league") or {}
    teams = item.get("teams") or {}
    home, away = teams.get("home") or {}, teams.get("away") or {}
    goals = item.get("goals") or {}
    status = fixture.get("status") or {}
    elapsed, extra = status.get("elapsed"), status.get("extra")
    status_short = str(status.get("short") or "NS")
    if status_short in {"FT", "AET", "PEN"}:
        status_text = "Finalizado"
    elif status_short == "HT":
        status_text = "Descanso"
    elif elapsed is not None:
        status_text = f"{elapsed}{f'+{extra}' if extra else ''}'"
    elif status_short == "NS":
        status_text = "Programado"
    else:
        status_text = str(status.get("long") or status_short)

    return {
        "id": str(fixture.get("id") or ""),
        "slug": str(fixture.get("id") or ""),
        "time": fixture.get("date"),
        "start_time": fixture.get("date"),
        "status": "LIVE" if status_short in {"1H", "2H", "ET", "BT", "P", "INT", "LIVE"} else status_short,
        "status_text": status_text,
        "elapsed": elapsed,
        "home": home.get("name") or "Local",
        "away": away.get("name") or "Visitante",
        "home_id": home.get("id"),
        "away_id": away.get("id"),
        "home_logo": home.get("logo"),
        "away_logo": away.get("logo"),
        "home_score": goals.get("home"),
        "away_score": goals.get("away"),
        "competition": FEATURED_COMPETITIONS.get(str(league.get("id") or ""), league.get("name") or "Fútbol"),
        "competition_id": league.get("id"),
        "competition_logo": league.get("logo"),
        "round": league.get("round") or "",
        "country": league.get("country"),
        "competition_country": league.get("country"),
        "venue": (fixture.get("venue") or {}).get("name") or "",
        "timezone": fixture.get("timezone") or "UTC",
    }


def live_fixtures() -> list[dict[str, Any]]:
    payload = _request("fixtures", {"live": "all", "timezone": "America/Bogota"}, ttl=45)
    return [
        _fixture(item) for item in payload.get("response", [])
        if isinstance(item, dict) and str(((item.get("league") or {}).get("id") or "")) in FEATURED_COMPETITIONS
    ]


def available_leagues() -> list[dict[str, Any]]:
    payload = _request("leagues", {}, ttl=60 * 60)
    leagues = []
    for item in payload.get("response", []):
        league, country = item.get("league") or {}, item.get("country") or {}
        seasons = item.get("seasons") or []
        season = next((entry for entry in seasons if entry.get("current")), None)
        if season is None:
            season = max(seasons, key=lambda entry: entry.get("year") or 0, default={})
        if not league.get("id") or not league.get("name") or not season.get("year"):
            continue
        league_id = str(league["id"])
        if league_id not in FEATURED_COMPETITIONS:
            continue
        leagues.append({
            "id": league_id,
            "name": FEATURED_COMPETITIONS[league_id],
            "type": league.get("type") or "League",
            "logo": league.get("logo") or f"https://media.api-sports.io/football/leagues/{league['id']}.png",
            "country": country.get("name") or "International",
            "country_code": country.get("code"),
            "country_flag": country.get("flag"),
            "season": int(season["year"]),
        })
    positions = {league_id: index for index, league_id in enumerate(FEATURED_COMPETITIONS)}
    return sorted(leagues, key=lambda league: positions[league["id"]])


def league_teams(league_id: int, season: int) -> list[dict[str, Any]]:
    if str(league_id) == "2":
        teams = champions_league_teams()
        try:
            official_by_name = {_normalized_team_name(row["name"]): row for row in _uefa_champions_standings()}
            for team in teams:
                official = official_by_name.get(_normalized_team_name(team["name"]))
                if official and official.get("logo"):
                    team["badge"] = official["logo"]
        except FootballAPIError:
            pass
        return teams
    if str(league_id) == "61":
        try:
            payload = _request("teams", {"league": str(league_id), "season": str(season)}, ttl=24 * 60 * 60)
            provider_teams = [
                {"id": str((item.get("team") or {}).get("id") or ""),
                 "name": str((item.get("team") or {}).get("name") or ""),
                 "badge": (item.get("team") or {}).get("logo") or ""}
                for item in payload.get("response", [])
                if (item.get("team") or {}).get("name")
            ]
        except FootballAPIError:
            provider_teams = _thesportsdb_league_teams(str(league_id))
        return ligue1_teams(provider_teams)
    try:
        payload = _request("teams", {"league": str(league_id), "season": str(season)}, ttl=24 * 60 * 60)
    except FootballAPIError:
        return _thesportsdb_league_teams(str(league_id))
    teams = []
    for item in payload.get("response", []):
        team = item.get("team") or {}
        if not team.get("id") or not team.get("name"):
            continue
        teams.append({
            "id": str(team["id"]),
            "name": team["name"],
            "badge": team.get("logo") or f"https://media.api-sports.io/football/teams/{team['id']}.png",
        })
    return teams or _thesportsdb_league_teams(str(league_id))


def _static_league_teams(league_id: str) -> list[dict[str, Any]]:
    """Return a clearly non-statistical club catalog as a final UI fallback."""
    if league_id == "61":
        return ligue1_teams()
    if league_id == "2":
        return champions_league_teams()
    return [
        {"id": str(900000 + int(league_id) * 100 + index), "name": name, "badge": ""}
        for index, name in enumerate(dict.fromkeys(FALLBACK_CLUBS.get(league_id, [])), 1)
    ]


def _thesportsdb_season_events(league_id: str) -> list[dict[str, Any]]:
    schedule = THESPORTSDB_SEASON_SCHEDULES.get(league_id)
    if not schedule:
        return []
    external_id, season = schedule
    cache_key = f"thesportsdb:season-events:{external_id}:{season}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]
    request = Request(
        f"https://www.thesportsdb.com/api/v1/json/123/eventsseason.php?id={external_id}&s={season}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("No se pudo consultar el calendario de temporada (%s)", type(exc).__name__)
        with _cache_lock:
            _cache[cache_key] = (time.monotonic() + 15 * 60, [])
        return []
    events = payload.get("events") or []
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 6 * 60 * 60, events)
    return events


def _teams_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    teams: dict[str, dict[str, Any]] = {}
    for event in events:
        for side in ("Home", "Away"):
            team_id = str(event.get(f"id{side}Team") or "")
            name = event.get(f"str{side}Team") or ""
            if team_id and name:
                teams[team_id] = {
                    "id": team_id,
                    "name": name,
                    "badge": event.get(f"str{side}TeamBadge") or "",
                }
    return sorted(teams.values(), key=lambda team: team["name"].casefold())


def _thesportsdb_league_teams(league_id: str) -> list[dict[str, Any]]:
    cache_key = f"thesportsdb:teams:{league_id}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now and cached[1]:
            return cached[1]
    teams: list[dict[str, Any]] = []
    league_name = THESPORTSDB_LEAGUE_NAMES.get(league_id)
    if league_name:
        request = Request(
            f"https://www.thesportsdb.com/api/v1/json/123/search_all_teams.php?l={league_name}",
            headers={"Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
            teams = [
                {"id": str(item["idTeam"]), "name": item["strTeam"], "badge": item.get("strBadge") or item.get("strTeamBadge") or ""}
                for item in payload.get("teams") or []
                if item.get("idTeam") and item.get("strTeam")
            ]
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("No se pudo consultar el cat??logo de respaldo (%s)", type(exc).__name__)
    schedule_teams = _teams_from_events(_thesportsdb_season_events(league_id))
    if schedule_teams:
        combined = {item["id"]: item for item in teams}
        combined.update({item["id"]: item for item in schedule_teams})
        teams = sorted(combined.values(), key=lambda item: item["name"].casefold())
    if not teams:
        teams = _static_league_teams(league_id)
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 24 * 60 * 60, teams)
    return teams


def league_top_teams(league_id: int, season: int) -> list[dict[str, Any]]:
    """Devuelve los tres primeros puestos de la tabla oficial disponible."""
    if str(league_id) == "2":
        try:
            return _uefa_champions_standings()[:3]
        except FootballAPIError:
            pass
    if str(league_id) not in FEATURED_COMPETITIONS:
        raise FootballAPIError("La competición no está dentro de las ligas destacadas.", 404)
    try:
        payload = _request("standings", {"league": str(league_id), "season": str(season)}, ttl=6 * 60 * 60)
    except FootballAPIError:
        # Fall back to public tables, then calculate a clearly labeled partial
        # ranking for competitions whose public provider exposes match results only.
        try:
            rows = _thesportsdb_top_teams(str(league_id))
        except FootballAPIError:
            rows = []
        return (rows or _thesportsdb_season_leaders(str(league_id)))[:3]
    rows: list[dict[str, Any]] = []
    for item in payload.get("response", []):
        league = item.get("league") or {}
        for group in league.get("standings") or []:
            for row in group:
                team = row.get("team") or {}
                if not team.get("id") or not team.get("name"):
                    continue
                rows.append({
                    "rank": row.get("rank"),
                    "team_id": str(team["id"]),
                    "name": team["name"],
                    "logo": team.get("logo"),
                    "points": row.get("points"),
                    "form": row.get("form"),
                    "description": row.get("description"),
                })
    rows.sort(key=lambda row: row["rank"] if isinstance(row["rank"], int) else 999)
    if rows:
        return rows[:3]
    try:
        fallback_rows = _thesportsdb_top_teams(str(league_id))
    except FootballAPIError:
        fallback_rows = []
    partial_rows = fallback_rows or _thesportsdb_season_leaders(str(league_id))
    if partial_rows:
        return partial_rows[:3]
    return [
        {"rank": None, "team_id": team["id"], "name": team["name"], "logo": "", "points": None,
         "description": "Club destacado; la clasificación actual no se pudo verificar."}
        for team in _static_league_teams(str(league_id))[:3]
    ]


def _thesportsdb_top_teams(league_id: str) -> list[dict[str, Any]]:
    external_league_id = THESPORTSDB_LEAGUES.get(league_id)
    if not external_league_id:
        return []
    cache_key = f"thesportsdb:standings:{external_league_id}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]
    request = Request(
        f"https://www.thesportsdb.com/api/v1/json/123/lookuptable.php?l={external_league_id}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("No se pudo consultar la tabla de respaldo (%s)", type(exc).__name__)
        with _cache_lock:
            _cache[cache_key] = (time.monotonic() + 15 * 60, [])
        return []
    rows = []
    for item in payload.get("table") or []:
        if not item.get("strTeam") or not item.get("intRank"):
            continue
        try:
            rank = int(item["intRank"])
        except (TypeError, ValueError):
            continue
        points = item.get("intPoints")
        rows.append({
            "rank": rank,
            "team_id": str(item.get("idTeam") or ""),
            "name": item["strTeam"],
            "logo": item.get("strBadge"),
            "points": int(points) if str(points or "").isdigit() else None,
            "form": item.get("strForm"),
            "description": item.get("strDescription"),
            "played": int(item["intPlayed"]) if str(item.get("intPlayed") or "").isdigit() else None,
            "wins": int(item["intWin"]) if str(item.get("intWin") or "").isdigit() else None,
            "draws": int(item["intDraw"]) if str(item.get("intDraw") or "").isdigit() else None,
            "loses": int(item["intLoss"]) if str(item.get("intLoss") or "").isdigit() else None,
            "goals_for": int(item["intGoalsFor"]) if str(item.get("intGoalsFor") or "").isdigit() else None,
            "goals_against": int(item["intGoalsAgainst"]) if str(item.get("intGoalsAgainst") or "").isdigit() else None,
            "goal_difference": int(item["intGoalDifference"]) if str(item.get("intGoalDifference") or "").lstrip("-").isdigit() else None,
        })
    rows.sort(key=lambda row: row["rank"])
    top_teams = rows
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 6 * 60 * 60, top_teams)
    return top_teams


def _thesportsdb_season_leaders(league_id: str) -> list[dict[str, Any]]:
    """Build a partial standings snapshot only from played games in the free schedule."""
    events = _thesportsdb_season_events(league_id)
    table: dict[str, dict[str, Any]] = {}
    for event in events:
        try:
            home_goals = int(event.get("intHomeScore"))
            away_goals = int(event.get("intAwayScore"))
        except (TypeError, ValueError):
            continue
        for side, name, scored, conceded in (
            ("Home", event.get("strHomeTeam"), home_goals, away_goals),
            ("Away", event.get("strAwayTeam"), away_goals, home_goals),
        ):
            team_id = str(event.get(f"id{side}Team") or name or "")
            if not team_id or not name:
                continue
            row = table.setdefault(team_id, {
                "team_id": team_id, "name": name, "logo": event.get(f"str{side}TeamBadge") or "",
                "played": 0, "wins": 0, "draws": 0, "loses": 0,
                "goals_for": 0, "goals_against": 0, "points": 0, "form": "",
                "description": "Clasificaci?n parcial: solo partidos con resultado en la muestra p?blica.",
            })
            row["played"] += 1
            row["goals_for"] += scored
            row["goals_against"] += conceded
            if scored > conceded:
                row["wins"] += 1; row["points"] += 3; result = "W"
            elif scored == conceded:
                row["draws"] += 1; row["points"] += 1; result = "D"
            else:
                row["loses"] += 1; result = "L"
            row["form"] = (row["form"] + result)[-5:]
    rows = list(table.values())
    rows.sort(key=lambda row: (-row["points"], -(row["goals_for"] - row["goals_against"]), -row["goals_for"], row["name"].casefold()))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
        row["goal_difference"] = row["goals_for"] - row["goals_against"]
    return rows


def team_fixtures(team_id: int, season: int, limit: int = 10) -> list[dict[str, Any]]:
    """Próximos encuentros destacados de un club para responder consultas del chat."""
    try:
        payload = _request(
            "fixtures",
            {"team": str(team_id), "season": str(season), "next": str(limit), "timezone": "America/Bogota"},
            ttl=15 * 60,
        )
    except FootballAPIError:
        return _thesportsdb_team_fixtures(str(team_id))
    fixtures = [
        _fixture(item) for item in payload.get("response", [])
        if isinstance(item, dict) and str(((item.get("league") or {}).get("id") or "")) in FEATURED_COMPETITIONS
    ]
    return fixtures or _thesportsdb_team_fixtures(str(team_id))


def team_statistics(league_id: int, season: int, team_id: int, team_name: str = "") -> dict[str, Any]:
    """Return a compact set of current team stats for side-by-side comparison."""
    if str(league_id) == "2":
        try:
            normalized_name = _normalized_team_name(team_name)
            row = next((item for item in _uefa_champions_standings() if _normalized_team_name(item["name"]) == normalized_name), None)
            if row:
                return {
                    "team": {"id": str(team_id), "name": row["name"], "logo": row.get("logo")},
                    "form": row.get("form") or "", "played": row.get("played"), "wins": row.get("wins"),
                    "draws": row.get("draws"), "loses": row.get("loses"),
                    "goals_for": row.get("goals_for"), "goals_against": row.get("goals_against"),
                    "goals_for_avg": row.get("goals_for_avg"), "goals_against_avg": row.get("goals_against_avg"),
                    "rank": row.get("rank"), "points": row.get("points"),
                    "goal_difference": row.get("goal_difference"), "clean_sheets": None,
                    "failed_to_score": None, "league": {"id": league_id},
                    "source": "UEFA · tabla oficial de fase liga 2026/27",
                }
        except FootballAPIError:
            logger.info("Se usarÃ¡ el respaldo para comparar este club de Champions.")
    try:
        payload = _request(
            "teams/statistics",
            {"league": str(league_id), "season": str(season), "team": str(team_id)},
            ttl=6 * 60 * 60,
        )
    except FootballAPIError:
        return _thesportsdb_team_statistics(str(league_id), str(team_id), team_name)
    item = payload.get("response") or {}
    if not isinstance(item, dict) or not item.get("team"):
        return _thesportsdb_team_statistics(str(league_id), str(team_id), team_name)
    fixtures, goals = item.get("fixtures") or {}, item.get("goals") or {}
    for_goals = goals.get("for") or {}
    against_goals = goals.get("against") or {}
    return {
        "team": item["team"],
        "form": item.get("form") or "",
        "played": (fixtures.get("played") or {}).get("total"),
        "wins": (fixtures.get("wins") or {}).get("total"),
        "draws": (fixtures.get("draws") or {}).get("total"),
        "loses": (fixtures.get("loses") or {}).get("total"),
        "goals_for": for_goals.get("total"),
        "goals_against": against_goals.get("total"),
        "goals_for_avg": for_goals.get("average", {}).get("total"),
        "goals_against_avg": against_goals.get("average", {}).get("total"),
        "clean_sheets": (item.get("clean_sheet") or {}).get("total"),
        "failed_to_score": (item.get("failed_to_score") or {}).get("total"),
        "league": item.get("league") or {},
        "source": "API-Football",
    }


def _thesportsdb_team_statistics(league_id: str, team_id: str, team_name: str = "") -> dict[str, Any]:
    table_rows = []
    try:
        table_rows = _thesportsdb_top_teams(league_id)
    except FootballAPIError:
        pass
    rows = table_rows or _thesportsdb_season_leaders(league_id)
    normalized_name = " ".join(team_name.casefold().split())
    row = next((item for item in rows if item["team_id"] == team_id or (normalized_name and " ".join(item["name"].casefold().split()) == normalized_name)), None)
    if not row:
        if league_id in {"2", "61"}:
            catalog = _static_league_teams(league_id)
            catalog_team = next((item for item in catalog if item["id"] == team_id or " ".join(item["name"].casefold().split()) == normalized_name), None)
        else:
            catalog_team = None
        # Preserve both selected clubs in the comparison view without inventing
        # current-season numbers when all real data providers are unavailable.
        return {
            "team": {
                "id": team_id,
                "name": (catalog_team or {}).get("name") or team_name or "Equipo",
                "logo": (catalog_team or {}).get("badge") or "",
            },
            "form": "",
            "played": None, "wins": None, "draws": None, "loses": None,
            "goals_for": None, "goals_against": None, "goals_for_avg": None,
            "goals_against_avg": None, "rank": None, "points": None,
            "goal_difference": None, "clean_sheets": None, "failed_to_score": None,
            "league": {"id": league_id},
            "source": "Estadísticas actuales no verificadas; no se muestran cifras inventadas",
        }
    played, goals_for, goals_against = row.get("played"), row.get("goals_for"), row.get("goals_against")
    return {
        "team": {"id": row["team_id"], "name": row["name"], "logo": row.get("logo")},
        "form": row.get("form") or "",
        "played": played,
        "wins": row.get("wins"),
        "draws": row.get("draws"),
        "loses": row.get("loses"),
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goals_for_avg": round(goals_for / played, 2) if isinstance(goals_for, int) and isinstance(played, int) and played else None,
        "goals_against_avg": round(goals_against / played, 2) if isinstance(goals_against, int) and isinstance(played, int) and played else None,
        "rank": row.get("rank"),
        "points": row.get("points"),
        "goal_difference": row.get("goal_difference"),
        "clean_sheets": None,
        "failed_to_score": None,
        "league": {"id": league_id},
        "source": "TheSportsDB · tabla de liga",
    }


def _thesportsdb_team_fixtures(team_id: str) -> list[dict[str, Any]]:
    cache_key = f"thesportsdb:team-fixtures:{team_id}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]
    request = Request(
        f"https://www.thesportsdb.com/api/v1/json/123/eventsnext.php?id={team_id}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("No se pudo consultar el calendario de respaldo (%s)", type(exc).__name__)
        raise FootballAPIError("No se pudo consultar el calendario de este equipo.", 502) from exc
    fixtures = []
    for event in payload.get("events") or []:
        home, away = event.get("strHomeTeam"), event.get("strAwayTeam")
        kickoff = event.get("strTimestamp") or event.get("dateEvent")
        if not home or not away or not kickoff:
            continue
        if isinstance(kickoff, str) and len(kickoff) == 19 and kickoff[10] == "T":
            kickoff += "-05:00"
        fixtures.append({
            "id": str(event.get("idEvent") or ""),
            "home": home,
            "away": away,
            "home_id": str(event.get("idHomeTeam") or ""),
            "away_id": str(event.get("idAwayTeam") or ""),
            "home_logo": event.get("strHomeTeamBadge") or "",
            "away_logo": event.get("strAwayTeamBadge") or "",
            "competition": event.get("strLeague") or "Football",
            "competition_id": event.get("idLeague"),
            "competition_logo": event.get("strLeagueBadge") or "",
            "round": event.get("intRound") or "",
            "time": kickoff,
            "start_time": kickoff,
            "status": event.get("strStatus") or "NS",
            "status_text": event.get("strStatus") or "Programado",
            "home_score": event.get("intHomeScore"),
            "away_score": event.get("intAwayScore"),
            "venue": event.get("strVenue") or "",
        })
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 15 * 60, fixtures)
    return fixtures


def scheduled_fixtures(start_date: str, end_date: str, league_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Carga el calendario por fecha y combina los resultados.

    La consulta por ``date`` funciona para recuperar partidos de todas las ligas.
    En esta integración el proveedor rechazó el rango ``from`` / ``to``, por lo
    que consultamos cada día por separado y combinamos los resultados.
    """
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    fixtures: dict[str, dict[str, Any]] = {}
    current = start
    while current <= end:
        try:
            payload = _request(
                "fixtures",
                {"date": current.isoformat(), "timezone": "America/Bogota"},
                ttl=300,
            )
            day_fixtures = [
                _fixture(item) for item in payload.get("response", [])
                if isinstance(item, dict) and str(((item.get("league") or {}).get("id") or "")) in FEATURED_COMPETITIONS
            ]
            if not day_fixtures:
                day_fixtures = _thesportsdb_day_fixtures(current, league_ids)
        except FootballAPIError:
            day_fixtures = _thesportsdb_day_fixtures(current, league_ids)
        for match in day_fixtures:
            fixtures[match["id"] or f"{match['home']}|{match['away']}|{match['time']}"] = match
        current += timedelta(days=1)
    return sorted(fixtures.values(), key=lambda match: match.get("time") or "")


def _thesportsdb_day_fixtures(day: date, preferred_leagues: list[str] | None = None) -> list[dict[str, Any]]:
    """Fallback schedule, prioritizing supported leagues selected by the user."""
    external_ids = list(dict.fromkeys(THESPORTSDB_LEAGUES[league] for league in (preferred_leagues or []) if league in THESPORTSDB_LEAGUES))[:5]
    if not external_ids:
        external_ids = [""]
    fixtures: list[dict[str, Any]] = []
    errors: list[Exception] = []
    for external_id in external_ids:
        cache_key = f"thesportsdb:fixtures:{day.isoformat()}:{external_id or 'all'}"
        now = time.monotonic()
        with _cache_lock:
            cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            events = cached[1]
        else:
            league_filter = f"&l={external_id}" if external_id else ""
            request = Request(
                f"https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d={day.isoformat()}&s=Soccer{league_filter}",
                headers={"Accept": "application/json"},
            )
            try:
                with urlopen(request, timeout=12) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                events = payload.get("events") or []
                with _cache_lock:
                    _cache[cache_key] = (time.monotonic() + 15 * 60, events)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors.append(exc)
                continue
        for event in events:
            external_league_id = str(event.get("idLeague") or "")
            league_id = THESPORTSDB_TO_API_LEAGUE.get(external_league_id)
            if league_id not in FEATURED_COMPETITIONS:
                continue
            home, away = event.get("strHomeTeam"), event.get("strAwayTeam")
            kickoff = event.get("strTimestamp") or event.get("dateEvent")
            if not home or not away or not kickoff:
                continue
            if isinstance(kickoff, str) and len(kickoff) == 19 and kickoff[10] == "T":
                kickoff += "-05:00"
            fixtures.append({
                "id": str(event.get("idEvent") or ""),
                "home": home,
                "away": away,
                "home_id": str(event.get("idHomeTeam") or ""),
                "away_id": str(event.get("idAwayTeam") or ""),
                "home_logo": event.get("strHomeTeamBadge") or "",
                "away_logo": event.get("strAwayTeamBadge") or "",
                "competition": FEATURED_COMPETITIONS[league_id],
                "competition_id": league_id,
                "competition_logo": event.get("strLeagueBadge") or "",
                "round": event.get("intRound") or "",
                "time": kickoff,
                "start_time": kickoff,
                "status": event.get("strStatus") or "NS",
                "status_text": event.get("strStatus") or "Programado",
                "home_score": event.get("intHomeScore"),
                "away_score": event.get("intAwayScore"),
                "venue": event.get("strVenue") or "",
            })
    if errors and not fixtures:
        logger.warning("No se pudo consultar el calendario de respaldo (%s)", type(errors[0]).__name__)
        raise FootballAPIError("No se pudo consultar el calendario de esta fecha.", 502) from errors[0]
    unique = {item["id"] or f"{item['home']}|{item['away']}|{item['time']}": item for item in fixtures}
    return list(unique.values())


def fixture_details(fixture_id: int) -> dict[str, Any]:
    payload = _request("fixtures", {"id": str(fixture_id)}, ttl=30)
    items = payload.get("response", [])
    if not items:
        raise FootballAPIError("No se encontraron detalles para este partido.", 404)

    item = items[0]
    match = _fixture(item)
    team_rows = item.get("statistics") or []
    statistics: list[dict[str, Any]] = []
    if len(team_rows) >= 2:
        home_id = match.get("home_id")
        home_rows = next((row.get("statistics", []) for row in team_rows if (row.get("team") or {}).get("id") == home_id), [])
        away_rows = next((row.get("statistics", []) for row in team_rows if (row.get("team") or {}).get("id") != home_id), [])
        away_values = {row.get("type"): row.get("value") for row in away_rows}
        statistics = [
            {"name": row.get("type"), "home": row.get("value"), "away": away_values.get(row.get("type"))}
            for row in home_rows
            if row.get("type")
        ]

    events = []
    for event in item.get("events") or []:
        minute = (event.get("time") or {}).get("elapsed")
        extra = (event.get("time") or {}).get("extra")
        events.append({
            "time": f"{minute}{f'+{extra}' if extra else ''}′" if minute is not None else "—",
            "text": " · ".join(str(value) for value in (
                (event.get("team") or {}).get("name"),
                event.get("type"),
                event.get("detail"),
                (event.get("player") or {}).get("name"),
            ) if value),
        })
    match["statistics"] = statistics
    match["events"] = events
    return match
