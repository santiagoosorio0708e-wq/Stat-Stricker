"""Small server-side client for API-Football (API-Sports)."""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

from backend.config import settings
from backend.football_catalog import champions_league_teams, complete_league_teams, ligue1_teams

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
    "143": "Copa del Rey",
}
THESPORTSDB_LEAGUES = {"39": "4328", "140": "4335", "135": "4332", "78": "4331", "61": "4334", "71": "4351", "2": "4480", "3": "4481", "13": "4501", "253": "4346"}
THESPORTSDB_TO_API_LEAGUE = {value: key for key, value in THESPORTSDB_LEAGUES.items()}
ESPN_SOCCER_LEAGUES = {
    "39": "eng.1", "140": "esp.1", "78": "ger.1", "135": "ita.1",
    "61": "fra.1", "2": "uefa.champions", "3": "uefa.europa",
    "13": "conmebol.libertadores", "71": "bra.1", "253": "usa.1", "143": "esp.copa_del_rey",
}
ESPN_LOGO_LOOKUP_LEAGUES = {
    "135": ["ita.2"],
    "3": ["eng.1", "ita.1", "esp.1", "ger.1", "ned.1", "por.1", "tur.1", "sco.1"],
    "13": ["arg.1", "bra.1", "chi.1", "ecu.1"],
    "71": ["bra.2"],
    "253": ["usa.1"],
}
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
        raise FootballAPIError("La tabla oficial de UEFA no está disponible en este momento.", 502) from exc
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        payload = payload[0]
    if not isinstance(payload, dict):
        raise FootballAPIError("UEFA devolvió un formato de tabla inesperado.", 502)
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
            "form": "", "description": "Clasificación oficial UEFA · fase liga 2026/27",
        })
    if len(rows) != 36:
        raise FootballAPIError("UEFA no devolvió los 36 equipos de la fase liga.", 502)
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
    if not any(str(league["id"]) == "143" for league in leagues):
        leagues.append({
            "id": "143", "name": "Copa del Rey", "type": "Cup", "logo": "https://media.api-sports.io/football/leagues/143.png",
            "country": "Spain", "country_code": "ES", "country_flag": "https://media.api-sports.io/flags/es.svg", "season": 2026,
        })
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
    if str(league_id) in {"39", "140", "78"} and season == 2026:
        provider_teams = []
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
            try:
                provider_teams = _thesportsdb_league_teams(str(league_id))
            except FootballAPIError:
                provider_teams = []
        return complete_league_teams(str(league_id), provider_teams) or provider_teams
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
    teams = _with_espn_team_badges(league_id, teams)
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 24 * 60 * 60, teams)
    return teams


def _clean_team_name_input(value: str) -> str:
    text = str(value or "")
    for _ in range(2):
        if "%" in text:
            decoded = unquote(text)
            if decoded == text:
                break
            text = decoded
    return " ".join(text.split())


def _espn_standings_rows(league_slug: str) -> list[dict[str, Any]]:
    """Fetch current league/competition standings from ESPN public endpoint."""
    slug = str(league_slug or "").strip()
    if not slug:
        return []
    cache_key = f"espn:standings:{slug}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]
    try:
        payload = _espn_json(f"https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings")
    except FootballAPIError:
        return []

    children = payload.get("children") or [payload]
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for child in children:
        entries = ((child.get("standings") or {}).get("entries")) or []
        for idx, entry in enumerate(entries, 1):
            team = entry.get("team") or {}
            tid = str(team.get("id") or "")
            name = str(team.get("displayName") or team.get("name") or "").strip()
            if not name or (tid and tid in seen_ids):
                continue
            if tid:
                seen_ids.add(tid)
            stats_map = {str(s.get("name") or ""): s.get("value") for s in (entry.get("stats") or []) if s.get("name")}
            note = entry.get("note") or {}
            rank_raw = stats_map.get("rank") if stats_map.get("rank") is not None else note.get("rank", idx)
            played_raw = stats_map.get("gamesPlayed")
            wins_raw = stats_map.get("wins")
            draws_raw = stats_map.get("ties")
            loses_raw = stats_map.get("losses")
            gf_raw = stats_map.get("pointsFor")
            ga_raw = stats_map.get("pointsAgainst")
            gd_raw = stats_map.get("pointDifferential")
            pts_raw = stats_map.get("points")

            def _to_int(val: Any) -> int | None:
                if val is None:
                    return None
                try:
                    return int(round(float(val)))
                except (TypeError, ValueError):
                    return None

            played = _to_int(played_raw)
            gf = _to_int(gf_raw)
            ga = _to_int(ga_raw)
            logos = team.get("logos") or []
            logo = str(team.get("logo") or (logos[0].get("href") if logos else "") or "")
            rows.append({
                "rank": _to_int(rank_raw),
                "team_id": tid,
                "name": name,
                "short_name": str(team.get("shortDisplayName") or team.get("name") or name),
                "logo": logo,
                "points": _to_int(pts_raw),
                "played": played,
                "wins": _to_int(wins_raw),
                "draws": _to_int(draws_raw),
                "loses": _to_int(loses_raw),
                "goals_for": gf,
                "goals_against": ga,
                "goal_difference": _to_int(gd_raw),
                "goals_for_avg": round(gf / played, 2) if gf is not None and played else None,
                "goals_against_avg": round(ga / played, 2) if ga is not None and played else None,
                "form": "",
                "description": str(note.get("description") or ""),
            })
    rows.sort(key=lambda row: row["rank"] if isinstance(row.get("rank"), int) else 999)
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 15 * 60, rows)
    return rows


def _find_standing_row(rows: list[dict[str, Any]], team_name: str, espn_team_id: str = "") -> dict[str, Any] | None:
    if not rows:
        return None
    if espn_team_id:
        by_id = next((r for r in rows if str(r.get("team_id") or "") == str(espn_team_id)), None)
        if by_id:
            return by_id
    clean = _clean_team_name_input(team_name)
    target = _normalized_team_name(clean)
    if not target:
        return None
    for row in rows:
        for candidate in (row.get("name", ""), row.get("short_name", "")):
            if candidate and _normalized_team_name(candidate) == target:
                return row
    target_tokens = {t for t in target.split() if t not in {"fc", "cf", "ac", "sc", "club", "de", "la", "el", "united", "city"}}
    best_row: dict[str, Any] | None = None
    best_score = 0
    for row in rows:
        cand_norm = _normalized_team_name(row.get("name", ""))
        if not cand_norm:
            continue
        if target in cand_norm or cand_norm in target:
            return row
        cand_tokens = {t for t in cand_norm.split() if t not in {"fc", "cf", "ac", "sc", "club", "de", "la", "el", "united", "city"}}
        overlap = len(target_tokens & cand_tokens)
        if overlap > best_score and overlap >= max(1, len(target_tokens)):
            best_score = overlap
            best_row = row
    return best_row


def _espn_standings_for_team(league_id: str, team_name: str, espn_team_id: str = "") -> tuple[dict[str, Any] | None, str]:
    slug = _resolve_espn_slug(str(league_id))
    clean_name = _clean_team_name_input(team_name)
    if slug:
        row = _find_standing_row(_espn_standings_rows(slug), clean_name, espn_team_id=espn_team_id)
        if row:
            return row, slug
    if clean_name:
        found = _search_espn_team(clean_name)
        if found and found.get("slug") and found["slug"] != slug:
            row = _find_standing_row(_espn_standings_rows(found["slug"]), clean_name, espn_team_id=found.get("id", ""))
            if row:
                return row, found["slug"]
    return None, slug


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
        espn_rows = _espn_standings_rows(_resolve_espn_slug(str(league_id)))
        if espn_rows:
            return espn_rows[:3]
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
                "description": "Clasificación parcial: solo partidos con resultado en la muestra pública.",
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


def _resolve_espn_slug(league_id: str) -> str:
    val = str(league_id or "").strip()
    if not val:
        return ""
    if val in ESPN_SOCCER_LEAGUES:
        return ESPN_SOCCER_LEAGUES[val]
    return val if "." in val else ""


def recent_team_player_events(
    team_name: str, competition_id: str, season: int, limit: int = 5,
) -> list[dict[str, Any]]:
    """Return recent completed matches and verified goal/assist events from ESPN summaries."""
    league = _resolve_espn_slug(competition_id)
    if not league or not team_name.strip():
        return []
    team_id = _espn_team_id(league, team_name)
    if not team_id:
        found = _search_espn_team(team_name, preferred_slug=league)
        if found:
            team_id = found["id"]
            league = found["slug"]
    if not team_id:
        return []
    cache_key = f"espn:team-history:{league}:{team_id}:{season}:{limit}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    schedule_url = (
        "https://site.api.espn.com/apis/site/v2/sports/soccer/"
        f"{league}/teams/{team_id}/schedule?season={season}"
    )
    try:
        schedule = _espn_json(schedule_url)
    except FootballAPIError:
        return []
    played = []
    for event in schedule.get("events") or []:
        competitions = event.get("competitions") or []
        competition = competitions[0] if competitions else {}
        status = competition.get("status") or {}
        if not (status.get("type") or {}).get("completed"):
            continue
        teams = competition.get("competitors") or []
        home = next((item for item in teams if item.get("homeAway") == "home"), None)
        away = next((item for item in teams if item.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        played.append({
            "id": str(event.get("id") or ""),
            "date": str(event.get("date") or competition.get("date") or ""),
            "home": (home.get("team") or {}).get("displayName") or "",
            "away": (away.get("team") or {}).get("displayName") or "",
            "home_score": _espn_score(home.get("score")),
            "away_score": _espn_score(away.get("score")),
            "status": (status.get("type") or {}).get("detail") or "Final",
        })
    played.sort(key=lambda item: item["date"], reverse=True)
    played = played[:max(1, min(limit, 8))]

    def load_events(match: dict[str, Any]) -> tuple[str, list[dict[str, str]], list[dict[str, Any]]]:
        try:
            summary = _espn_json(
                "https://site.api.espn.com/apis/site/v2/sports/soccer/"
                f"{league}/summary?event={match['id']}"
            )
        except FootballAPIError:
            return match["id"], [], []
        goals = []
        for event in summary.get("keyEvents") or []:
            if not event.get("scoringPlay"):
                continue
            participants = event.get("participants") or []
            scorer = ""
            if participants:
                scorer = ((participants[0].get("athlete") or {}).get("displayName") or "")
            text = str(event.get("text") or "")
            assist_match = re.search(r"Assisted by (.+?)(?:\s+with\s+|\s+from\s+|\s+after\s+|\.|$)", text, re.IGNORECASE)
            assist = assist_match.group(1).strip(" ,.") if assist_match else ""
            goals.append({
                "minute": (event.get("clock") or {}).get("displayValue") or "",
                "scorer": scorer,
                "assist": assist,
                "description": text,
            })
        players = []
        for roster in summary.get("rosters") or []:
            for player in roster.get("roster") or []:
                athlete = player.get("athlete") or {}
                name = athlete.get("displayName") or athlete.get("fullName") or ""
                if not name:
                    continue
                stats = {
                    str(item.get("name") or ""): _espn_score(item.get("value"))
                    for item in player.get("stats") or []
                }
                players.append({
                    "name": name,
                    "team": (roster.get("team") or {}).get("displayName") or "",
                    "started": bool(player.get("starter")),
                    "goals": stats.get("totalGoals"),
                    "assists": stats.get("goalAssists"),
                    "shots": stats.get("totalShots"),
                    "shots_on_target": stats.get("shotsOnTarget"),
                })
        return match["id"], goals, players

    goals_by_match: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(load_events, match) for match in played]
        for future in as_completed(futures):
            try:
                fixture_id, goals, players = future.result()
                goals_by_match[fixture_id] = {"goals": goals, "players": players}
            except Exception as exc:
                logger.debug("No se pudo leer un resumen ESPN (%s)", type(exc).__name__)
    for match in played:
        details = goals_by_match.get(match["id"], {})
        match["goals"] = details.get("goals", [])
        match["players"] = details.get("players", [])
        match["source"] = "ESPN match summary"
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 30 * 60, played)
    return played


def _espn_team_id(league: str, team_name: str) -> str:
    teams = _espn_team_catalog(league)
    if not teams:
        return ""
    wanted = _normalized_team_name(team_name)
    aliases = {
        "real madrid": {"real madrid", "madrid"},
        "barcelona": {"barcelona", "fc barcelona"},
        "atletico madrid": {"atletico madrid", "atletico de madrid", "atletico"},
        "inter milan": {"inter milan", "inter", "internazionale"},
        "ac milan": {"ac milan", "milan"},
        "bayern munich": {"bayern munich", "fc bayern munich", "bayern munchen", "bayern"},
        "borussia dortmund": {"borussia dortmund", "dortmund"},
        "paris saint germain": {"paris saint germain", "psg"},
        "tottenham hotspur": {"tottenham hotspur", "tottenham", "spurs"},
        "manchester united": {"manchester united", "man utd"},
        "manchester city": {"manchester city", "man city"},
        "athletic club": {"athletic club", "athletic bilbao"},
    }
    accepted = aliases.get(wanted, {wanted})
    for team in teams:
        names = {
            _normalized_team_name(str(team.get(key) or ""))
            for key in ("displayName", "name", "shortDisplayName", "location")
        }
        if names & accepted:
            return str(team.get("id") or "")
    for team in teams:
        names = [
            _normalized_team_name(str(team.get(key) or ""))
            for key in ("displayName", "name", "shortDisplayName")
        ]
        if any(wanted in n or n in wanted for n in names if n and len(n) >= 4):
            return str(team.get("id") or "")
    return ""


def _espn_team_catalog(league: str) -> list[dict[str, Any]]:
    cache_key = f"espn:teams:{league}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            teams = cached[1]
        else:
            teams = None
    if teams is None:
        try:
            payload = _espn_json(
                "https://site.api.espn.com/apis/site/v2/sports/soccer/"
                f"{league}/teams?limit=100"
            )
        except FootballAPIError:
            return []
        teams = [
            row.get("team") or {}
            for sport in payload.get("sports") or []
            for row in ((sport.get("leagues") or [{}])[0].get("teams") or [])
        ]
        with _cache_lock:
            _cache[cache_key] = (time.monotonic() + 6 * 60 * 60, teams)
    return teams


def _with_espn_team_badges(league_id: str, teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fill badge gaps in team catalogs without changing their comparison IDs."""
    league = ESPN_SOCCER_LEAGUES.get(str(league_id))
    if not league or not teams or all(team.get("badge") for team in teams):
        return teams
    espn_teams = _espn_team_catalog(league)
    if not espn_teams:
        return teams

    def names(team: dict[str, Any]) -> set[str]:
        return {
            _normalized_team_name(str(team.get(key) or ""))
            for key in ("name", "displayName", "shortDisplayName", "location")
            if team.get(key)
        }

    aliases = {
        "atletico mineiro": {"atletico mineiro", "atletico mg"},
        "athletico paranaense": {"athletico paranaense", "athletico pr"},
        "red bull bragantino": {"red bull bragantino", "bragantino"},
        "inter miami": {"inter miami", "inter miami cf"},
        "new york red bulls": {"new york red bulls", "new york rb", "red bull new york"},
        "los angeles fc": {"los angeles fc", "la fc", "lafc"},
        "sao paulo": {"sao paulo", "sao paulo fc"},
        "ldu quito": {"ldu quito", "liga de quito"},
    }
    candidates = list(espn_teams)
    extra_leagues = ESPN_LOGO_LOOKUP_LEAGUES.get(str(league_id), [])
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_espn_team_catalog, extra) for extra in extra_leagues if extra != league]
        for future in as_completed(futures):
            try:
                candidates.extend(future.result())
            except Exception:
                continue
    for team in teams:
        if team.get("badge"):
            continue
        wanted = names(team)
        if not wanted:
            continue
        expanded = set(wanted)
        for name in wanted:
            expanded.update(aliases.get(name, set()))
        best = None
        for candidate in candidates:
            candidate_names = names(candidate)
            if expanded & candidate_names or any(
                min(len(left), len(right)) >= 7 and (left in right or right in left)
                for left in expanded for right in candidate_names
            ):
                best = candidate
                break
        if best:
            logos = best.get("logos") or []
            team["badge"] = best.get("logo") or (logos[0].get("href") if logos else "") or ""
    fallback_api_teams = {
        "135": {"pisa": 801, "cremonese": 520, "verona": 504},
        "71": {"sport recife": 123},
    }
    for team in teams:
        api_team_id = fallback_api_teams.get(str(league_id), {}).get(_normalized_team_name(str(team.get("name") or "")))
        if api_team_id:
            if str(team.get("id", "")).isdigit() and int(team["id"]) >= 900000:
                team["id"] = str(api_team_id)
            if not team.get("badge"):
                team["badge"] = _api_badge(api_team_id)
    return teams


def _espn_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "StatStriker/1.0"})
    try:
        with urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FootballAPIError("No se pudo consultar el historial de partidos.", 502) from exc
    return payload if isinstance(payload, dict) else {}


def _espn_score(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("displayValue", value.get("value"))
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _enrich_rank_and_points(stats: dict[str, Any], league_id: str, team_name: str, espn_team_id: str = "") -> dict[str, Any]:
    """Ensure rank and points are filled from official ESPN/UEFA tables whenever available."""
    if stats.get("rank") is not None and stats.get("points") is not None:
        return stats
    row: dict[str, Any] | None = None
    if str(league_id) == "2":
        try:
            row = _find_standing_row(_uefa_champions_standings(), team_name)
        except FootballAPIError:
            row = None
    if not row:
        row, _ = _espn_standings_for_team(str(league_id), team_name, espn_team_id=espn_team_id)
    if row:
        if stats.get("rank") is None and row.get("rank") is not None:
            stats["rank"] = row.get("rank")
        if stats.get("points") is None and row.get("points") is not None:
            stats["points"] = row.get("points")
    return stats


def team_statistics(league_id: int, season: int, team_id: int, team_name: str = "") -> dict[str, Any]:
    """Return a compact set of current team stats for side-by-side comparison."""
    clean_name = _clean_team_name_input(team_name)
    if str(league_id) == "2":
        try:
            row = _find_standing_row(_uefa_champions_standings(), clean_name)
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
            logger.info("Se usará el respaldo ESPN para comparar este club de Champions.")
        espn_ucl = _espn_team_recent_statistics("2", season, clean_name)
        if espn_ucl:
            return espn_ucl
    try:
        payload = _request(
            "teams/statistics",
            {"league": str(league_id), "season": str(season), "team": str(team_id)},
            ttl=6 * 60 * 60,
        )
    except FootballAPIError:
        return _espn_team_recent_statistics(str(league_id), season, clean_name) or _thesportsdb_team_statistics(str(league_id), str(team_id), clean_name)
    item = payload.get("response") or {}
    if not isinstance(item, dict) or not item.get("team"):
        return _espn_team_recent_statistics(str(league_id), season, clean_name) or _thesportsdb_team_statistics(str(league_id), str(team_id), clean_name)
    fixtures, goals = item.get("fixtures") or {}, item.get("goals") or {}
    for_goals = goals.get("for") or {}
    against_goals = goals.get("against") or {}
    result = {
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
        "rank": None,
        "points": None,
        "clean_sheets": (item.get("clean_sheet") or {}).get("total"),
        "failed_to_score": (item.get("failed_to_score") or {}).get("total"),
        "league": item.get("league") or {},
        "source": "API-Football",
    }
    return _enrich_rank_and_points(result, str(league_id), clean_name or str((item.get("team") or {}).get("name") or ""))


def _espn_team_recent_statistics(league_id: str, season: int, team_name: str) -> dict[str, Any] | None:
    """Return official standings (rank/points/totals) merged with recent 5-match form from ESPN."""
    clean_name = _clean_team_name_input(team_name)
    league = _resolve_espn_slug(str(league_id))
    if not clean_name:
        return None
    espn_team_id = _espn_team_id(league, clean_name) if league else None
    if not espn_team_id:
        for alternate_league in ESPN_LOGO_LOOKUP_LEAGUES.get(str(league_id), []):
            espn_team_id = _espn_team_id(alternate_league, clean_name)
            if espn_team_id:
                league = alternate_league
                break
    standing_row, standing_slug = _espn_standings_for_team(str(league_id), clean_name, espn_team_id=espn_team_id or "")
    if not espn_team_id and standing_row:
        espn_team_id = str(standing_row.get("team_id") or "")
        if standing_slug:
            league = standing_slug
    if not espn_team_id:
        found = _search_espn_team(clean_name, preferred_slug=league)
        if found:
            espn_team_id = found["id"]
            league = found["slug"]
    if not espn_team_id and not standing_row:
        return None

    cache_key = f"espn:team-stats-v2:{league}:{espn_team_id}:{season}:{_normalized_team_name(clean_name)}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    results = []
    if league and espn_team_id:
        try:
            schedule = _espn_json(
                "https://site.api.espn.com/apis/site/v2/sports/soccer/"
                f"{league}/teams/{espn_team_id}/schedule?season={season}"
            )
        except FootballAPIError:
            schedule = {}
        for event in schedule.get("events") or []:
            competition = next(iter(event.get("competitions") or []), {})
            status = (competition.get("status") or {}).get("type") or {}
            if not status.get("completed"):
                continue
            competitors = competition.get("competitors") or []
            home = next((item for item in competitors if item.get("homeAway") == "home"), None)
            away = next((item for item in competitors if item.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            home_score, away_score = _espn_score(home.get("score")), _espn_score(away.get("score"))
            if home_score is None or away_score is None:
                continue
            home_team, away_team = home.get("team") or {}, away.get("team") or {}
            is_home = str(home_team.get("id") or "") == espn_team_id
            if not is_home and str(away_team.get("id") or "") != espn_team_id:
                continue
            scored, conceded = (home_score, away_score) if is_home else (away_score, home_score)
            result_letter = "W" if scored > conceded else "D" if scored == conceded else "L"
            results.append({"date": str(event.get("date") or ""), "scored": scored, "conceded": conceded, "result": result_letter})

    results.sort(key=lambda row: row["date"], reverse=True)
    sample = results[:5]
    if not sample and not standing_row:
        return None

    catalog_team = (
        next((team for team in _espn_team_catalog(league) if str(team.get("id") or "") == espn_team_id), {})
        if league and espn_team_id
        else {}
    )
    logos = catalog_team.get("logos") or []
    team_display = (
        (standing_row or {}).get("name")
        or catalog_team.get("displayName")
        or clean_name
    )
    team_logo = (
        (standing_row or {}).get("logo")
        or catalog_team.get("logo")
        or (logos[0].get("href") if logos else "")
        or ""
    )

    if sample:
        s_played = len(sample)
        s_gf = sum(row["scored"] for row in sample)
        s_ga = sum(row["conceded"] for row in sample)
        s_wins = sum(row["result"] == "W" for row in sample)
        s_draws = sum(row["result"] == "D" for row in sample)
        s_losses = sum(row["result"] == "L" for row in sample)
        form = "".join(row["result"] for row in reversed(sample))
        clean_sheets = sum(row["conceded"] == 0 for row in sample)
        failed_to_score = sum(row["scored"] == 0 for row in sample)
    else:
        s_played = s_gf = s_ga = s_wins = s_draws = s_losses = None
        form = ""
        clean_sheets = None
        failed_to_score = None

    has_table = standing_row is not None and (
        standing_row.get("rank") is not None or standing_row.get("points") is not None
    )
    played = (standing_row or {}).get("played") if has_table and (standing_row or {}).get("played") is not None else s_played
    goals_for = (standing_row or {}).get("goals_for") if has_table and (standing_row or {}).get("goals_for") is not None else s_gf
    goals_against = (standing_row or {}).get("goals_against") if has_table and (standing_row or {}).get("goals_against") is not None else s_ga
    wins = (standing_row or {}).get("wins") if has_table and (standing_row or {}).get("wins") is not None else s_wins
    draws = (standing_row or {}).get("draws") if has_table and (standing_row or {}).get("draws") is not None else s_draws
    loses = (standing_row or {}).get("loses") if has_table and (standing_row or {}).get("loses") is not None else s_losses
    gf_avg = (
        (standing_row or {}).get("goals_for_avg")
        if has_table and (standing_row or {}).get("goals_for_avg") is not None
        else (round(s_gf / s_played, 2) if s_gf is not None and s_played else None)
    )
    ga_avg = (
        (standing_row or {}).get("goals_against_avg")
        if has_table and (standing_row or {}).get("goals_against_avg") is not None
        else (round(s_ga / s_played, 2) if s_ga is not None and s_played else None)
    )

    response = {
        "team": {
            "id": espn_team_id or (standing_row or {}).get("team_id") or "",
            "name": team_display,
            "logo": team_logo,
        },
        "form": form,
        "played": played,
        "wins": wins,
        "draws": draws,
        "loses": loses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goals_for_avg": gf_avg,
        "goals_against_avg": ga_avg,
        "rank": (standing_row or {}).get("rank"),
        "points": (standing_row or {}).get("points"),
        "sample_points": (s_wins * 3 + s_draws) if s_wins is not None and s_draws is not None else None,
        "goal_difference": (standing_row or {}).get("goal_difference") if has_table else ((s_gf - s_ga) if s_gf is not None and s_ga is not None else None),
        "clean_sheets": clean_sheets,
        "failed_to_score": failed_to_score,
        "league": {"id": league_id},
        "source": (
            f"ESPN · tabla oficial y últimos {s_played} partidos"
            if has_table and s_played
            else "ESPN · tabla oficial de competición"
            if has_table
            else f"ESPN · últimos {s_played} partidos"
        ),
    }
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 20 * 60, response)
    return response


def _thesportsdb_team_statistics(league_id: str, team_id: str, team_name: str = "") -> dict[str, Any]:
    clean_name = _clean_team_name_input(team_name)
    table_rows = []
    try:
        table_rows = _thesportsdb_top_teams(league_id)
    except FootballAPIError:
        pass
    rows = table_rows or _thesportsdb_season_leaders(league_id)
    normalized_name = " ".join(clean_name.casefold().split())
    row = next((item for item in rows if item["team_id"] == team_id or (normalized_name and " ".join(item["name"].casefold().split()) == normalized_name)), None)
    if not row:
        if league_id in {"2", "61"}:
            catalog = _static_league_teams(league_id)
            catalog_team = next((item for item in catalog if item["id"] == team_id or " ".join(item["name"].casefold().split()) == normalized_name), None)
        else:
            catalog_team = None
        fallback = {
            "team": {
                "id": team_id,
                "name": (catalog_team or {}).get("name") or clean_name or "Equipo",
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
        return _enrich_rank_and_points(fallback, league_id, fallback["team"]["name"])
    played, goals_for, goals_against = row.get("played"), row.get("goals_for"), row.get("goals_against")
    result = {
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
    return _enrich_rank_and_points(result, league_id, row["name"])


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
            # TheSportsDB strTimestamp is UTC; adding Bogota's offset here shifted kickoff 5 hours late.
            kickoff += "+00:00"
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
                # Normalize the UTC timestamp here, then let the frontend display Bogota time.
                kickoff += "+00:00"
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


# ====================================================================== #
# Resolución de equipos/jugadores y reporte de últimos 5 partidos (Chat)
# ====================================================================== #
_TEAM_NICKNAMES: dict[str, tuple[str, str]] = {
    "city": ("Manchester City", "39"),
    "man city": ("Manchester City", "39"),
    "manchester city": ("Manchester City", "39"),
    "citizens": ("Manchester City", "39"),
    "liverpool": ("Liverpool", "39"),
    "reds": ("Liverpool", "39"),
    "united": ("Manchester United", "39"),
    "man utd": ("Manchester United", "39"),
    "manchester united": ("Manchester United", "39"),
    "arsenal": ("Arsenal", "39"),
    "gunners": ("Arsenal", "39"),
    "chelsea": ("Chelsea", "39"),
    "spurs": ("Tottenham Hotspur", "39"),
    "tottenham": ("Tottenham Hotspur", "39"),
    "newcastle": ("Newcastle United", "39"),
    "aston villa": ("Aston Villa", "39"),
    "real madrid": ("Real Madrid", "140"),
    "madrid": ("Real Madrid", "140"),
    "merengues": ("Real Madrid", "140"),
    "barcelona": ("Barcelona", "140"),
    "fc barcelona": ("Barcelona", "140"),
    "barca": ("Barcelona", "140"),
    "cules": ("Barcelona", "140"),
    "atletico": ("Atlético Madrid", "140"),
    "atleti": ("Atlético Madrid", "140"),
    "atletico madrid": ("Atlético Madrid", "140"),
    "atletico de madrid": ("Atlético Madrid", "140"),
    "sevilla": ("Sevilla", "140"),
    "valencia": ("Valencia", "140"),
    "betis": ("Real Betis", "140"),
    "real betis": ("Real Betis", "140"),
    "villarreal": ("Villarreal", "140"),
    "athletic": ("Athletic Club", "140"),
    "athletic bilbao": ("Athletic Club", "140"),
    "bayern": ("Bayern Munich", "78"),
    "bayern munich": ("Bayern Munich", "78"),
    "dortmund": ("Borussia Dortmund", "78"),
    "borussia dortmund": ("Borussia Dortmund", "78"),
    "leverkusen": ("Bayer Leverkusen", "78"),
    "bayer leverkusen": ("Bayer Leverkusen", "78"),
    "leipzig": ("RB Leipzig", "78"),
    "inter": ("Inter Milan", "135"),
    "inter milan": ("Inter Milan", "135"),
    "milan": ("AC Milan", "135"),
    "ac milan": ("AC Milan", "135"),
    "juventus": ("Juventus", "135"),
    "juve": ("Juventus", "135"),
    "napoli": ("Napoli", "135"),
    "roma": ("Roma", "135"),
    "atalanta": ("Atalanta", "135"),
    "psg": ("Paris Saint-Germain", "61"),
    "paris saint germain": ("Paris Saint-Germain", "61"),
    "marsella": ("Marseille", "61"),
    "marseille": ("Marseille", "61"),
    "monaco": ("Monaco", "61"),
    "lyon": ("Lyon", "61"),
    "flamengo": ("Flamengo", "71"),
    "palmeiras": ("Palmeiras", "71"),
    "boca": ("Boca Juniors", "13"),
    "boca juniors": ("Boca Juniors", "13"),
    "river": ("River Plate", "13"),
    "river plate": ("River Plate", "13"),
    "inter miami": ("Inter Miami", "253"),
}

_STAR_PLAYER_TEAMS: dict[str, tuple[str, str]] = {
    "mbappe": ("Real Madrid", "140"),
    "kylian": ("Real Madrid", "140"),
    "vinicius": ("Real Madrid", "140"),
    "vini": ("Real Madrid", "140"),
    "bellingham": ("Real Madrid", "140"),
    "rodrygo": ("Real Madrid", "140"),
    "valverde": ("Real Madrid", "140"),
    "yamal": ("Barcelona", "140"),
    "lamine": ("Barcelona", "140"),
    "lewandowski": ("Barcelona", "140"),
    "raphinha": ("Barcelona", "140"),
    "pedri": ("Barcelona", "140"),
    "griezmann": ("Atlético Madrid", "140"),
    "julian alvarez": ("Atlético Madrid", "140"),
    "haaland": ("Manchester City", "39"),
    "foden": ("Manchester City", "39"),
    "salah": ("Liverpool", "39"),
    "palmer": ("Chelsea", "39"),
    "cole palmer": ("Chelsea", "39"),
    "saka": ("Arsenal", "39"),
    "gyokeres": ("Arsenal", "39"),
    "kane": ("Bayern Munich", "78"),
    "harry kane": ("Bayern Munich", "78"),
    "musiala": ("Bayern Munich", "78"),
    "lautaro": ("Inter Milan", "135"),
    "dembele": ("Paris Saint-Germain", "61"),
    "messi": ("Inter Miami", "253"),
}


def _plain_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def _club_index() -> dict[str, tuple[str, str]]:
    """Mapa normalizado alias -> (Nombre canonico, league_id)."""
    index: dict[str, tuple[str, str]] = {}
    # Orden de prioridad: ligas domesticas primero, copas continentales despues.
    for league_id in ("39", "140", "78", "135", "61", "71", "253", "13", "2", "3"):
        for club in FALLBACK_CLUBS.get(league_id, []):
            index.setdefault(_plain_text(club), (club, league_id))
    index.update(_TEAM_NICKNAMES)
    return index


def infer_league_id(competition_name: str, team_name: str = "") -> str:
    comp = _plain_text(competition_name)
    for league_id, label in FEATURED_COMPETITIONS.items():
        if _plain_text(label) in comp or comp in _plain_text(label):
            if league_id in ESPN_SOCCER_LEAGUES:
                return league_id
    if team_name:
        found = _club_index().get(_plain_text(team_name))
        if found:
            return found[1]
    return ""


_PLAYER_QUERY_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "en", "con", "para", "por",
    "que", "si", "como", "cual", "quien", "cuanto", "cuantos", "sobre", "entre", "contra", "vs", "y", "o",
    "partido", "partidos", "equipo", "equipos", "jugador", "jugadores", "futbol", "liga", "jornada",
    "apuesta", "apuestas", "apostar", "cuota", "cuotas", "buena", "mejor", "menor", "objetiva", "valor",
    "arco", "puerta", "gol", "goles", "tiro", "tiros", "remate", "remates", "disparo", "disparos",
    "asistencia", "asistencias", "estadistica", "estadisticas", "promedio", "promedios", "tabla",
    "ultimos", "ultima", "ultimo", "recientes", "reciente", "proximo", "proxima", "hoy", "ayer", "manana",
    "crees", "dime", "quiero", "necesito", "recomienda", "recomiendas", "recomiende", "analiza", "vale",
    "pena", "fijarse", "hace", "dispara", "remata", "tira", "anota", "marca", "mete", "asiste", "juega",
    "hara", "metera", "marcara", "anotara", "apuesto", "por", "cual", "mas", "menos", "over", "under", "btts", "ambos", "marcan", "gana", "ganar", "empate", "victoria",
    "vienen", "viene", "estan", "esta", "juegan", "entre", "contra", "hoy", "sera",
    "alineacion", "alineaciones", "titular", "titulares", "once", "inicial", "formacion",
    "rentable", "rentables", "quienes", "muestra", "dame", "ver", "ambos",
}

_GENERIC_NAME_TOKENS = {
    "jose", "juan", "luis", "carlos", "david", "daniel", "lucas", "marco", "pedro", "pablo",
    "diego", "mateo", "junior", "silva", "santos", "costa", "garcia", "lopez", "martinez",
}

_ESPN_SLUG_TO_LEAGUE_ID = {v: k for k, v in ESPN_SOCCER_LEAGUES.items()}


def _extract_player_candidates(message: str, known_team_names: set[str]) -> list[str]:
    """Extrae posibles nombres de jugadores de consultas en texto libre."""
    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(raw: str) -> None:
        cleaned = _plain_text(raw)
        if not cleaned or cleaned in seen or cleaned in known_team_names:
            return
        tokens = [
            t for t in cleaned.split()
            if len(t) >= 3 and t not in _PLAYER_QUERY_STOPWORDS and t not in known_team_names
        ]
        if not tokens or len(tokens) > 3:
            return
        joined = " ".join(tokens)
        if joined in seen or joined in known_team_names:
            return
        seen.add(joined)
        candidates.append(joined)

    # 1) Patrones contextuales (funcionan incluso todo en minúsculas)
    patterns = (
        r"(?:que|si|para|sobre|de|a|y|o|con)\s+([a-zñáéíóúü]{3,}(?:\s+[a-zñáéíóúü]{3,}){0,2})\s+(?:dispar\w*|remat\w*|tir\w*|anot\w*|marc\w*|met\w*|har[aá]\w*|hace\w*|asist\w*|jueg\w*|en\s+los)",
        r"(?:tiros?(?:\s+al\s+arco|\s+a\s+puerta)?|remates?|disparos?|goles?|gol|asistencias?|estad[ií]sticas?|promedios?|datos?)\s+(?:de|del|para)\s+([a-zñáéíóúü]{3,}(?:\s+[a-zñáéíóúü]{3,}){0,2})",
        r"(?:anota|anotar[aá]|marca|marcar[aá]|dispara|remata|jugador)\s+(?:de\s+)?([a-zñáéíóúü]{3,}(?:\s+[a-zñáéíóúü]{3,}){0,2})",
    )
    lowered = message.casefold()
    for pat in patterns:
        for m in re.finditer(pat, lowered):
            add_candidate(m.group(1))

    # 2) Nombres propios con mayúscula (p. ej. "Ollie Watkins", "Wirtz")
    for m in re.finditer(r"\b([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,}(?:\s+[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,}){0,2})\b", message):
        add_candidate(m.group(1))

    return candidates[:4]


def _search_espn_team(team_query: str, preferred_slug: str = "") -> dict[str, str] | None:
    """Busca cualquier club del mundo en el buscador público de ESPN."""
    norm = _plain_text(team_query)
    if not norm or len(norm) < 3:
        return None
    cache_key = f"espn:team-search:{norm}:{preferred_slug}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]
    result: dict[str, str] | None = None
    try:
        u = "https://site.web.api.espn.com/apis/common/v3/search?" + urlencode(
            {"query": team_query, "type": "team", "sport": "soccer", "limit": 6}
        )
        data = _espn_json(u)
        candidates = []
        for item in data.get("items") or []:
            tid = str(item.get("id") or "").strip()
            dname = str(item.get("displayName") or "").strip()
            slug = str(item.get("league") or item.get("defaultLeagueSlug") or "").strip().lower()
            if not tid or not dname or not slug:
                continue
            # Evitamos equipos femeninos, juveniles o amistosos salvo coincidencia exacta
            if ".w." in slug or "wchampions" in slug or slug in {"club.friendly", "fifa.world", "uefa.nations"}:
                continue
            dnorm = _plain_text(dname)
            if norm not in dnorm and dnorm not in norm and not all(tok in dnorm for tok in norm.split() if len(tok) >= 3):
                continue
            score = 0
            if preferred_slug and slug == preferred_slug:
                score += 10
            if dnorm == norm:
                score += 5
            if not dnorm.endswith((" b", " ii", " u21", " u19")):
                score += 3
            candidates.append((score, tid, dname, slug))
        if candidates:
            candidates.sort(key=lambda c: -c[0])
            _, tid, dname, slug = candidates[0]
            result = {"id": tid, "name": dname, "slug": slug}
    except FootballAPIError:
        pass
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 6 * 60 * 60, result)
    return result


def _extract_team_candidates(message: str, known_tokens: set[str]) -> list[str]:
    """Extrae nombres de equipos cuando la consulta menciona un partido X vs Y fuera del catálogo fijo."""
    candidates: list[str] = []
    seen: set[str] = set()

    def add_chunk(raw: str) -> None:
        cleaned = _plain_text(raw)
        tokens = [t for t in cleaned.split() if len(t) >= 3 and t not in _PLAYER_QUERY_STOPWORDS]
        if not tokens or len(tokens) > 3:
            return
        joined = " ".join(tokens)
        if joined in seen or joined in known_tokens:
            return
        seen.add(joined)
        candidates.append(joined)

    # 1) Patrones explícitos "Equipo A vs/contra Equipo B"
    m = re.search(
        r"(?:entre|partido|para|vienen|juegan|de|del|en)?\s*([a-zñáéíóúü0-9.\- ]{3,32}?)\s+(?:vs\.?|contra)\s+([a-zñáéíóúü0-9.\- ]{3,32}?)(?:[?,!.]|$|\s+(?:de|en|para|y|quien|que|hoy|manana))",
        message.casefold(),
    )
    if m:
        left_tokens = [t for t in _plain_text(m.group(1)).split() if t not in _PLAYER_QUERY_STOPWORDS]
        right_tokens = [t for t in _plain_text(m.group(2)).split() if t not in _PLAYER_QUERY_STOPWORDS]
        if left_tokens:
            add_chunk(" ".join(left_tokens[-2:]))
        if right_tokens:
            add_chunk(" ".join(right_tokens[:2]))

    # 2) Nombres propios capitalizados que podrían ser clubes (p. ej. "Millonarios", "Benfica")
    for cap in re.finditer(r"\b([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,}(?:\s+[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,}){0,2})\b", message):
        add_chunk(cap.group(1))

    return candidates[:4]


def _search_player_club(player_query: str) -> dict[str, str] | None:
    """Resuelve dinámicamente club y liga de cualquier jugador vía ESPN / TheSportsDB."""
    norm = _plain_text(player_query)
    if not norm:
        return None
    if norm in _STAR_PLAYER_TEAMS:
        team, lid = _STAR_PLAYER_TEAMS[norm]
        return {"player": player_query.title(), "team": team, "league_id": lid}

    cache_key = f"player-club:{norm}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    club_idx = _club_index()
    espn_athlete_id = ""
    espn_display = ""
    result: dict[str, str] | None = None

    # 1) ESPN Search
    try:
        u1 = "https://site.web.api.espn.com/apis/common/v3/search?" + urlencode(
            {"query": player_query, "type": "player", "sport": "soccer", "limit": 5}
        )
        data = _espn_json(u1)
        for item in data.get("items") or []:
            dname = str(item.get("displayName") or "").strip()
            if not dname:
                continue
            dnorm = _plain_text(dname)
            d_tokens = set(dnorm.split())
            if not all(tok in d_tokens for tok in norm.split()):
                continue
            slug = str(item.get("league") or "").strip().lower()
            lid = _ESPN_SLUG_TO_LEAGUE_ID.get(slug, "") or (slug if slug and "." in slug and slug not in {"fifa.world", "uefa.nations"} else "")
            teams = [(tr.get("core") or {}).get("displayName") for tr in (item.get("teamRelationships") or [])]
            team_name = next((str(t) for t in teams if t), "")
            if lid and team_name:
                result = {"player": dname, "team": team_name, "league_id": lid}
                break
            if not espn_athlete_id and item.get("id"):
                espn_athlete_id = str(item["id"])
                espn_display = dname
    except FootballAPIError:
        pass

    # 2) TheSportsDB Search (resuelve club actual cuando ESPN solo devuelve selección nacional)
    if result is None:
        try:
            u2 = "https://www.thesportsdb.com/api/v1/json/123/searchplayers.php?" + urlencode({"p": player_query})
            req = Request(u2, headers={"Accept": "application/json", "User-Agent": "StatStriker/1.0"})
            with urlopen(req, timeout=6) as resp:
                tsdb = json.loads(resp.read().decode("utf-8"))
            for p in tsdb.get("player") or []:
                if p.get("strSport") != "Soccer":
                    continue
                pname = str(p.get("strPlayer") or "").strip()
                tname = str(p.get("strTeam") or "").strip()
                if not pname or not tname or tname.startswith("_Retired"):
                    continue
                pnorm = _plain_text(pname)
                p_tokens = set(pnorm.split())
                if not all(tok in p_tokens for tok in norm.split()):
                    continue
                mapped = club_idx.get(_plain_text(tname))
                if mapped:
                    result = {"player": pname, "team": mapped[0], "league_id": mapped[1]}
                    break
                espn_club = _search_espn_team(tname)
                if espn_club:
                    result = {"player": pname, "team": espn_club["name"], "league_id": espn_club["slug"]}
                    break
        except Exception:
            pass

    # 3) ESPN Athlete overview fallback (p. ej. "Pedri")
    if result is None and espn_athlete_id:
        try:
            info = _espn_json(
                f"https://site.web.api.espn.com/apis/common/v3/sports/soccer/eng.1/athletes/{espn_athlete_id}"
            )
            tname = str(((info.get("athlete") or {}).get("team") or {}).get("displayName") or "").strip()
            if tname:
                mapped = club_idx.get(_plain_text(tname))
                if mapped:
                    result = {"player": espn_display or player_query.title(), "team": mapped[0], "league_id": mapped[1]}
                else:
                    espn_club = _search_espn_team(tname)
                    result = {
                        "player": espn_display or player_query.title(),
                        "team": espn_club["name"] if espn_club else tname,
                        "league_id": espn_club["slug"] if espn_club else "39",
                    }
        except FootballAPIError:
            pass

    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 6 * 60 * 60, result)
    return result


def _teams_match(team_a: str, team_b: str) -> bool:
    """Compara dos nombres de club tolerando variaciones (Real Madrid vs Real Madrid C.F., PSG, Man City)."""
    na = _normalized_team_name(_clean_team_name_input(team_a))
    nb = _normalized_team_name(_clean_team_name_input(team_b))
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ta = {t for t in _plain_text(team_a).split() if len(t) >= 3 and t not in {"fc", "cf", "ac", "sc", "club", "de", "la", "el"}}
    tb = {t for t in _plain_text(team_b).split() if len(t) >= 3 and t not in {"fc", "cf", "ac", "sc", "club", "de", "la", "el"}}
    return bool(ta and tb and (ta <= tb or tb <= ta))


def validate_players_for_match(
    text: str,
    active_teams: list[dict[str, str]],
    extra_players: list[str] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Valida si los jugadores mencionados pertenecen a los equipos del partido activo.
    Devuelve `(valid_players, mismatched_players)` donde `mismatched_players` detalla
    el club real de cada jugador que no juega en ninguno de los dos equipos consultados.
    """
    if not active_teams:
        return list(extra_players or []), []

    team_tokens: set[str] = set()
    for t in active_teams:
        team_tokens.update(_plain_text(t.get("name", "")).split())

    query = _plain_text(text)
    candidates: list[str] = []
    seen_cands: set[str] = set()

    def _add_cand(name: str) -> None:
        norm = _plain_text(name)
        if norm and norm not in seen_cands and norm not in team_tokens:
            seen_cands.add(norm)
            candidates.append(name)

    for star_alias in sorted(_STAR_PLAYER_TEAMS, key=lambda s: -len(s)):
        if re.search(rf"\b{re.escape(star_alias)}\b", query):
            _add_cand(star_alias)
    for cand in _extract_player_candidates(text, team_tokens):
        _add_cand(cand)
    for ep in extra_players or []:
        _add_cand(ep)

    if not candidates:
        return [], []

    valid_players: list[str] = []
    mismatched: list[dict[str, Any]] = []
    seen_mismatch: set[str] = set()

    with ThreadPoolExecutor(max_workers=min(3, len(candidates))) as pool:
        resolved_infos = list(pool.map(_search_player_club, candidates))

    match_team_names = [t["name"] for t in active_teams if t.get("name")]
    for cand, info in zip(candidates, resolved_infos):
        if info and info.get("team"):
            actual_team = info["team"]
            player_label = info.get("player") or cand.title()
            if any(_teams_match(actual_team, mt) for mt in match_team_names):
                if player_label not in valid_players:
                    valid_players.append(player_label)
            else:
                key = _plain_text(player_label)
                if key not in seen_mismatch:
                    seen_mismatch.add(key)
                    mismatched.append({
                        "player": player_label,
                        "actual_team": actual_team,
                        "league_id": info.get("league_id", ""),
                        "match_teams": match_team_names,
                    })
        else:
            if cand not in valid_players:
                valid_players.append(cand)

    return valid_players, mismatched


def _translate_position(pos: str) -> str:
    code = str(pos or "").strip().upper()
    if code in {"G", "GK", "GOALKEEPER"}:
        return "POR"
    if code in {"D", "DF", "DEF", "DEFENDER", "CB", "LB", "RB", "WB", "CD"}:
        return "DEF"
    if code in {"M", "MF", "MID", "MIDFIELDER", "CM", "CDM", "CAM", "LM", "RM", "DM", "AM"}:
        return "MED"
    if code in {"F", "FW", "FWD", "ST", "CF", "LW", "RW", "STRIKER", "FORWARD", "ATTACKER"}:
        return "DEL"
    return code or "JUG"


def team_lineup_report(
    team_name: str,
    league_id: str,
    season: int | None = None,
    event_id: str = "",
) -> dict[str, Any] | None:
    """
    Obtiene la alineación oficial del partido si ya fue publicada en ESPN, o el último
    XI titular registrado del equipo, cruzado con los jugadores más rentables recientes.
    """
    from datetime import datetime as _dt

    target_season = season or _dt.now().year
    league = _resolve_espn_slug(league_id)
    if not team_name.strip():
        return None
    espn_team_id = _espn_team_id(league, team_name) if league else None
    if not espn_team_id:
        found = _search_espn_team(team_name, preferred_slug=league)
        if found:
            espn_team_id = found["id"]
            league = found["slug"]
    if not league or not espn_team_id:
        return None

    cache_key = f"espn:lineup:{league}:{espn_team_id}:{target_season}:{event_id}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    selected_roster: dict[str, Any] | None = None
    lineup_status = "Último XI titular registrado (referencia previa al anuncio oficial)"
    ref_match = ""
    ref_date = ""

    def _extract_roster_from_summary(ev_id: str) -> tuple[dict[str, Any] | None, str, str]:
        try:
            summ = _espn_json(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary?event={ev_id}")
        except FootballAPIError:
            return None, "", ""
        rosters = summ.get("rosters") or []
        header_comp = ((summ.get("header") or {}).get("competitions") or [{}])[0]
        comp_date = str(header_comp.get("date") or "")[:10]
        comp_names = [
            str(((c.get("team") or {}).get("displayName") or ""))
            for c in (header_comp.get("competitors") or [])
        ]
        comp_label = " vs ".join([n for n in comp_names if n])
        for r in rosters:
            r_team = r.get("team") or {}
            if str(r_team.get("id") or "") == espn_team_id or _teams_match(str(r_team.get("displayName") or ""), team_name):
                starters = [p for p in (r.get("roster") or []) if p.get("starter")]
                if len(starters) >= 7:
                    return r, comp_label, comp_date
        return None, comp_label, comp_date

    if event_id and str(event_id).isdigit() and len(str(event_id)) >= 7:
        cand_roster, comp_label, comp_date = _extract_roster_from_summary(str(event_id))
        if cand_roster:
            selected_roster = cand_roster
            lineup_status = "Alineación oficial confirmada del partido"
            ref_match = comp_label
            ref_date = comp_date

    if selected_roster is None:
        for yr in (target_season, target_season - 1):
            try:
                sched = _espn_json(
                    f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{espn_team_id}/schedule?season={yr}"
                )
            except FootballAPIError:
                continue
            completed = []
            for ev in sched.get("events") or []:
                st = ((ev.get("competitions") or [{}])[0].get("status") or {}).get("type") or {}
                if st.get("completed") and ev.get("id"):
                    completed.append((str(ev.get("date") or ""), str(ev["id"])))
            completed.sort(key=lambda x: x[0], reverse=True)
            for _, ev_id in completed[:3]:
                cand_roster, comp_label, comp_date = _extract_roster_from_summary(ev_id)
                if cand_roster:
                    selected_roster = cand_roster
                    ref_match = comp_label
                    ref_date = comp_date
                    break
            if selected_roster is not None:
                break

    if not selected_roster:
        return None

    player_stats_by_key: dict[str, dict[str, Any]] = {}
    try:
        events = recent_team_player_events(team_name, league, target_season, limit=5)
    except Exception:
        events = []
    team_norm = _plain_text(team_name)
    for ev in events:
        for p in ev.get("players") or []:
            p_team = _plain_text(str(p.get("team") or ""))
            if team_norm and p_team and not _teams_match(team_name, str(p.get("team") or "")):
                continue
            pname = str(p.get("name") or "").strip()
            if not pname:
                continue
            pkey = _plain_text(pname)
            entry = player_stats_by_key.setdefault(pkey, {
                "name": pname, "appearances": 0, "goals": 0, "assists": 0,
                "shots": 0, "shots_on_target": 0, "matches_with_sot": 0, "matches_with_goal": 0,
            })
            g = int(p.get("goals") or 0)
            a = int(p.get("assists") or 0)
            s = int(p.get("shots") or 0)
            sot = int(p.get("shots_on_target") or 0)
            entry["appearances"] += 1
            entry["goals"] += g
            entry["assists"] += a
            entry["shots"] += s
            entry["shots_on_target"] += sot
            if sot > 0:
                entry["matches_with_sot"] += 1
            if g > 0:
                entry["matches_with_goal"] += 1

    starters_out: list[dict[str, Any]] = []
    substitutes_out: list[str] = []
    profitable_candidates: list[dict[str, Any]] = []

    for p in selected_roster.get("roster") or []:
        pname = str((p.get("athlete") or {}).get("displayName") or "").strip()
        if not pname:
            continue
        pos = _translate_position((p.get("position") or {}).get("abbreviation") or (p.get("position") or {}).get("displayName") or "")
        jersey = str(p.get("jersey") or "")
        if p.get("starter"):
            st = player_stats_by_key.get(_plain_text(pname))
            app = max(1, st["appearances"]) if st else 0
            starter_item = {
                "name": pname,
                "position": pos,
                "jersey": jersey,
                "appearances": st["appearances"] if st else 0,
                "goals": st["goals"] if st else 0,
                "assists": st["assists"] if st else 0,
                "shots": st["shots"] if st else 0,
                "shots_on_target": st["shots_on_target"] if st else 0,
                "goals_avg": round(st["goals"] / app, 2) if st else 0.0,
                "shots_on_target_avg": round(st["shots_on_target"] / app, 2) if st else 0.0,
                "matches_with_sot": st["matches_with_sot"] if st else 0,
            }
            starters_out.append(starter_item)
            if pos != "POR" and st and st["appearances"] >= 2:
                score_val = (st["goals"] * 3.0) + (st["shots_on_target"] * 1.4) + (st["assists"] * 1.8) + (st["shots"] * 0.4)
                profitable_candidates.append({**starter_item, "_score": score_val})
        else:
            substitutes_out.append(f"{pname} ({pos})")

    profitable_candidates.sort(key=lambda x: -x["_score"])
    for item in profitable_candidates:
        item.pop("_score", None)

    result = {
        "team": team_name,
        "formation": str(selected_roster.get("formation") or "No especificada"),
        "status": lineup_status,
        "reference_match": ref_match,
        "reference_date": ref_date,
        "starters": starters_out,
        "substitutes": substitutes_out[:7],
        "profitable_players": profitable_candidates[:4],
    }
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 15 * 60, result)
    return result


def resolve_teams_in_text(
    text: str,
    extra_teams: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Detecta equipos (y jugadores conocidos o buscados) mencionados en la consulta."""
    resolved, _ = resolve_entities_in_text(text, extra_teams=extra_teams)
    return resolved


def resolve_entities_in_text(
    text: str,
    extra_teams: list[dict[str, str]] | None = None,
    allow_player_lookup: bool = True,
) -> tuple[list[dict[str, str]], list[str]]:
    """Detecta equipos y nombres de jugadores (estrellas + búsqueda dinámica)."""
    resolved: list[dict[str, str]] = []
    player_names: list[str] = []
    seen_names: set[str] = set()

    def add_team(name: str, league_id: str) -> None:
        key = _plain_text(name)
        if not key or key in seen_names:
            return
        seen_names.add(key)
        resolved.append({"name": name, "league_id": league_id})

    for item in extra_teams or []:
        name = str(item.get("name") or "").strip()
        if name:
            add_team(name, str(item.get("league_id") or infer_league_id("", name) or "39"))

    query = _plain_text(text)
    if not query:
        return resolved[:2], player_names

    if re.search(r"\bel clasico\b|\bclasico espanol\b", query):
        add_team("Real Madrid", "140")
        add_team("Barcelona", "140")

    index = _club_index()
    matches: list[tuple[int, int, str, str]] = []
    for alias, (canonical, league_id) in index.items():
        if len(alias) < 3:
            continue
        # Evita confundir la palabra española "cómo/como" con el club italiano "Como" salvo mayúscula explícita.
        if alias == "como" and not re.search(r"\bComo\b", text):
            continue
        m = re.search(rf"\b{re.escape(alias)}\b", query)
        if m:
            matches.append((m.start(), -len(alias), canonical, league_id))

    matches.sort(key=lambda item: (item[0], item[1]))
    for _, _, canonical, league_id in matches:
        add_team(canonical, league_id)

    for player_alias, (canonical, league_id) in sorted(
        _STAR_PLAYER_TEAMS.items(), key=lambda kv: -len(kv[0])
    ):
        if re.search(rf"\b{re.escape(player_alias)}\b", query):
            if player_alias not in player_names:
                player_names.append(player_alias)
            if len(resolved) < 2:
                add_team(canonical, league_id)

    # Búsqueda dinámica de cualquier jugador X (aunque no esté en _STAR_PLAYER_TEAMS)
    if allow_player_lookup and not player_names:
        known_tokens = set(seen_names)
        for t in resolved:
            known_tokens.update(_plain_text(t["name"]).split())
        candidates = _extract_player_candidates(text, known_tokens)
        if candidates:
            with ThreadPoolExecutor(max_workers=min(3, len(candidates))) as pool:
                found_list = list(pool.map(_search_player_club, candidates))
            for found in found_list:
                if not found:
                    continue
                if found["player"] not in player_names:
                    player_names.append(found["player"])
                if len(resolved) < 2:
                    add_team(found["team"], found["league_id"])

    # Búsqueda dinámica global de equipos fuera del catálogo fijo (p. ej. Liga BetPlay, Portugal, Eredivisie...)
    if len(resolved) < 2:
        known_tokens = set(seen_names)
        for t in resolved:
            known_tokens.update(_plain_text(t["name"]).split())
        for pn in player_names:
            known_tokens.update(_plain_text(pn).split())
        team_candidates = _extract_team_candidates(text, known_tokens)
        if team_candidates:
            with ThreadPoolExecutor(max_workers=min(3, len(team_candidates))) as pool:
                found_teams = list(pool.map(_search_espn_team, team_candidates))
            for ft in found_teams:
                if ft and len(resolved) < 2:
                    add_team(ft["name"], ft["slug"])

    return resolved[:2], player_names


def _espn_team_recent_matches(league_id: str, team_name: str, season: int, limit: int = 5) -> list[dict[str, Any]]:
    """Devuelve los últimos `limit` partidos completados del equipo desde ESPN."""
    league = _resolve_espn_slug(league_id)
    if not league or not team_name.strip():
        return []
    espn_team_id = _espn_team_id(league, team_name)
    if not espn_team_id:
        for alt in ESPN_LOGO_LOOKUP_LEAGUES.get(str(league_id), []):
            espn_team_id = _espn_team_id(alt, team_name)
            if espn_team_id:
                league = alt
                break
    if not espn_team_id:
        found = _search_espn_team(team_name, preferred_slug=league)
        if found:
            espn_team_id = found["id"]
            league = found["slug"]
    if not espn_team_id:
        return []

    cache_key = f"espn:last5-matches:{league}:{espn_team_id}:{season}:{limit}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    try:
        schedule = _espn_json(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{espn_team_id}/schedule?season={season}"
        )
    except FootballAPIError:
        return []

    matches: list[dict[str, Any]] = []
    for event in schedule.get("events") or []:
        comp = next(iter(event.get("competitions") or []), {})
        status = (comp.get("status") or {}).get("type") or {}
        if not status.get("completed"):
            continue
        competitors = comp.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        hs, as_ = _espn_score(home.get("score")), _espn_score(away.get("score"))
        if hs is None or as_ is None:
            continue
        home_team, away_team = home.get("team") or {}, away.get("team") or {}
        is_home = str(home_team.get("id") or "") == espn_team_id
        if not is_home and str(away_team.get("id") or "") != espn_team_id:
            continue
        gf, ga = (hs, as_) if is_home else (as_, hs)
        opponent = (away_team.get("displayName") if is_home else home_team.get("displayName")) or "Rival"
        res = "V" if gf > ga else "E" if gf == ga else "D"
        matches.append({
            "date": str(event.get("date") or "")[:10],
            "home": home_team.get("displayName") or "",
            "away": away_team.get("displayName") or "",
            "opponent": opponent,
            "side": "Local" if is_home else "Visitante",
            "goals_for": gf,
            "goals_against": ga,
            "total_goals": gf + ga,
            "result": res,
            "btts": gf > 0 and ga > 0,
            "over_2_5": (gf + ga) > 2,
        })

    matches.sort(key=lambda m: m["date"], reverse=True)
    sample = matches[:limit]
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + 30 * 60, sample)
    return sample


def team_last5_report(
    team_name: str,
    league_id: str,
    season: int | None = None,
    include_players: bool = False,
    player_query: str = "",
    limit: int = 5,
) -> dict[str, Any] | None:
    """Genera un reporte completo de los últimos 5 partidos (equipo y opcionalmente jugadores)."""
    from datetime import datetime as _dt

    target_season = season or _dt.now().year
    candidate_leagues = [league_id] if league_id else []
    for fallback_lid in ("39", "140", "78", "135", "61", "2"):
        if fallback_lid not in candidate_leagues:
            candidate_leagues.append(fallback_lid)

    matches: list[dict[str, Any]] = []
    used_league = league_id
    used_season = target_season
    for lid in candidate_leagues[:3]:
        for yr in (target_season, target_season - 1):
            matches = _espn_team_recent_matches(lid, team_name, yr, limit=limit)
            if matches:
                used_league = lid
                used_season = yr
                break
        if matches:
            break

    if not matches:
        return None

    played = len(matches)
    gf_tot = sum(m["goals_for"] for m in matches)
    ga_tot = sum(m["goals_against"] for m in matches)
    tot_goals = gf_tot + ga_tot
    wins = sum(m["result"] == "V" for m in matches)
    draws = sum(m["result"] == "E" for m in matches)
    losses = sum(m["result"] == "D" for m in matches)
    btts_cnt = sum(1 for m in matches if m["btts"])
    over25_cnt = sum(1 for m in matches if m["over_2_5"])
    clean_sheets = sum(1 for m in matches if m["goals_against"] == 0)
    failed_score = sum(1 for m in matches if m["goals_for"] == 0)

    players_summary: list[dict[str, Any]] = []
    if include_players:
        try:
            events = recent_team_player_events(team_name, used_league, used_season, limit=limit)
        except Exception:
            events = []
        if events:
            by_player: dict[str, dict[str, Any]] = {}
            target_norm = _plain_text(player_query)
            team_norm = _plain_text(team_name)
            for ev in events:
                day = str(ev.get("date") or "")[:10]
                match_label = f"{ev.get('home', '?')} vs {ev.get('away', '?')}"
                score_label = f"{ev.get('home_score', '—')}-{ev.get('away_score', '—')}"
                for p in ev.get("players") or []:
                    p_team = _plain_text(str(p.get("team") or ""))
                    if team_norm and p_team and team_norm not in p_team and p_team not in team_norm:
                        # Permite siglas o variaciones como "Manchester City" vs "Man City"
                        if not any(tok in p_team for tok in team_norm.split() if len(tok) > 3):
                            continue
                    p_name = str(p.get("name") or "").strip()
                    if not p_name:
                        continue
                    key = _plain_text(p_name)
                    entry = by_player.setdefault(key, {
                        "name": p_name,
                        "appearances": 0,
                        "goals": 0,
                        "assists": 0,
                        "shots": 0,
                        "shots_on_target": 0,
                        "matches": [],
                    })
                    g = int(p.get("goals") or 0)
                    a = int(p.get("assists") or 0)
                    s = int(p.get("shots") or 0)
                    sot = int(p.get("shots_on_target") or 0)
                    entry["appearances"] += 1
                    entry["goals"] += g
                    entry["assists"] += a
                    entry["shots"] += s
                    entry["shots_on_target"] += sot
                    entry["matches"].append({
                        "date": day,
                        "match": match_label,
                        "score": score_label,
                        "goals": g,
                        "assists": a,
                        "shots": s,
                        "shots_on_target": sot,
                    })

            matched_players = []
            exact_matches = []
            token_matches = []
            for p_key, entry in by_player.items():
                if not target_norm:
                    continue
                if p_key in target_norm:
                    exact_matches.append(entry)
                    continue
                parts = [t for t in p_key.split() if len(t) >= 4 and t not in _GENERIC_NAME_TOKENS]
                if any(re.search(rf"\b{re.escape(tok)}\b", target_norm) for tok in parts):
                    token_matches.append(entry)
            matched_players = exact_matches or token_matches

            pool = matched_players if player_query else sorted(
                by_player.values(),
                key=lambda x: (x["goals"], x["assists"], x["shots_on_target"], x["shots"]),
                reverse=True,
            )[:4]

            for item in pool:
                app_n = max(1, item["appearances"])
                item["team_matches_checked"] = len(events)
                item["goals_avg"] = round(item["goals"] / app_n, 2)
                item["assists_avg"] = round(item["assists"] / app_n, 2)
                item["shots_avg"] = round(item["shots"] / app_n, 2)
                item["shots_on_target_avg"] = round(item["shots_on_target"] / app_n, 2)
                item["matches_with_sot"] = sum(1 for m in item["matches"] if m["shots_on_target"] > 0)
                item["matches_with_goal"] = sum(1 for m in item["matches"] if m["goals"] > 0)
            players_summary = pool

    return {
        "team": team_name,
        "league_id": used_league,
        "league_name": FEATURED_COMPETITIONS.get(str(used_league), str(used_league) or "Fútbol"),
        "source": f"ESPN · últimos {played} partidos",
        "matches": matches,
        "averages": {
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "form": "-".join(m["result"] for m in matches),
            "goals_for_total": gf_tot,
            "goals_against_total": ga_tot,
            "goals_for_avg": round(gf_tot / played, 2),
            "goals_against_avg": round(ga_tot / played, 2),
            "total_goals_avg": round(tot_goals / played, 2),
            "btts_count": btts_cnt,
            "btts_pct": round(100 * btts_cnt / played),
            "over_2_5_count": over25_cnt,
            "over_2_5_pct": round(100 * over25_cnt / played),
            "clean_sheets": clean_sheets,
            "failed_to_score": failed_score,
        },
        "players": players_summary,
    }
