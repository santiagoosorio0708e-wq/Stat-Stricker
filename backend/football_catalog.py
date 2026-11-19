"""Pinned club catalogs for competitions where free API plans truncate teams."""

from __future__ import annotations


def _api_badge(team_id: int) -> str:
    return f"https://media.api-sports.io/football/teams/{team_id}.png"


# Complete 2026/27 rosters for the three leagues whose free API responses are
# truncated on some plans. IDs are API-Football IDs, so the comparison screen
# can still request real team statistics for every club.
PINNED_LEAGUE_TEAMS_2026 = {
    "39": [
        ("Arsenal", 42), ("Aston Villa", 66), ("AFC Bournemouth", 35), ("Brentford", 55),
        ("Brighton & Hove Albion", 51), ("Chelsea", 49), ("Coventry City", 1346),
        ("Crystal Palace", 52), ("Everton", 45), ("Fulham", 36), ("Hull City", 64),
        ("Ipswich Town", 57), ("Leeds United", 63), ("Liverpool", 40), ("Manchester City", 50),
        ("Manchester United", 33), ("Newcastle United", 34), ("Nottingham Forest", 65),
        ("Sunderland", 746), ("Tottenham Hotspur", 47),
    ],
    "140": [
        ("Athletic Club", 531), ("Atlético de Madrid", 530), ("CA Osasuna", 727),
        ("Celta Vigo", 538), ("Deportivo Alavés", 542), ("Elche CF", 797),
        ("FC Barcelona", 529), ("Getafe CF", 546), ("Levante UD", 539),
        ("Málaga CF", 535), ("Racing de Santander", 4665), ("Rayo Vallecano", 728),
        ("Deportivo La Coruña", 544), ("RCD Espanyol", 540), ("Real Betis", 543),
        ("Real Madrid", 541), ("Real Sociedad", 548), ("Sevilla FC", 536),
        ("Valencia CF", 532), ("Villarreal CF", 533),
    ],
    "78": [
        ("FC Augsburg", 170), ("1. FC Union Berlin", 182), ("Werder Bremen", 162),
        ("Borussia Dortmund", 165), ("SV Elversberg", 1660), ("Eintracht Frankfurt", 169),
        ("SC Freiburg", 160), ("Hamburger SV", 175), ("TSG Hoffenheim", 167),
        ("1. FC Köln", 192), ("RB Leipzig", 173), ("Bayer Leverkusen", 168),
        ("1. FSV Mainz 05", 164), ("Borussia Mönchengladbach", 163),
        ("Bayern Munich", 157), ("SC Paderborn 07", 185), ("FC Schalke 04", 174),
        ("VfB Stuttgart", 172),
    ],
}


def complete_league_teams(league_id: str, provider_teams: list[dict] | None = None) -> list[dict[str, str]] | None:
    """Merge provider data with a complete current-season roster for capped plans."""
    roster = PINNED_LEAGUE_TEAMS_2026.get(str(league_id))
    if not roster:
        return None

    aliases = {
        "afc bournemouth": "bournemouth", "brighton and hove albion": "brighton & hove albion",
        "athletic bilbao": "athletic club", "atletico madrid": "atletico de madrid",
        "barcelona": "fc barcelona", "alaves": "deportivo alaves", "elche": "elche cf",
        "getafe": "getafe cf", "levante": "levante ud", "malaga": "malaga cf",
        "santander": "racing de santander", "depor": "deportivo la coruna",
        "espanyol": "rcd espanyol", "real betis balompie": "real betis",
        "real madrid cf": "real madrid", "real sociedad": "real sociedad",
        "sevilla": "sevilla fc", "valencia": "valencia cf", "villarreal": "villarreal cf",
        "augsburg": "fc augsburg", "union berlin": "1 fc union berlin",
        "werder bremen": "werder bremen", "frankfurt": "eintracht frankfurt",
        "freiburg": "sc freiburg", "hamburg": "hamburger sv", "hoffenheim": "tsg hoffenheim",
        "koeln": "1 fc koln", "cologne": "1 fc koln", "leverkusen": "bayer leverkusen",
        "mainz": "1 fsv mainz 05", "gladbach": "borussia monchengladbach",
        "bayern": "bayern munich", "paderborn": "sc paderborn 07", "schalke": "fc schalke 04",
        "stuttgart": "vfb stuttgart", "elversberg": "sv elversberg", "dortmund": "borussia dortmund",
    }

    def normalized(value: str) -> str:
        import unicodedata
        import re
        plain = "".join(char for char in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(char))
        plain = re.sub(r"[^a-z0-9&]+", " ", plain).strip()
        return aliases.get(plain, plain)

    by_name = {normalized(str(team.get("name", ""))): team for team in (provider_teams or []) if team.get("name")}
    result = []
    for name, team_id in roster:
        source = by_name.get(normalized(name), {})
        result.append({"id": str(team_id), "name": name, "badge": source.get("badge") or _api_badge(team_id)})
    return result


LIGUE1_2026_27 = [
    ("Paris Saint-Germain", 85), ("Lens", 116), ("Lille", 79), ("Lyon", 80),
    ("Marseille", 81), ("Rennes", 94), ("Monaco", 91), ("Strasbourg", 95),
    ("Toulouse", 96), ("Lorient", 97), ("Paris FC", 114), ("Brest", 106),
    ("Angers", 77), ("Le Havre", 111), ("Auxerre", 89), ("Nice", 84),
    ("Troyes", 110), ("Le Mans", 133848),
]

UCL_2026_27_POTS = {
    "1": [
        "Paris Saint-Germain", "Bayern Munich", "Real Madrid", "Liverpool", "Inter",
        "Manchester City", "Arsenal", "Barcelona", "Atletico Madrid",
    ],
    "2": [
        "Borussia Dortmund", "Roma", "Sporting CP", "Aston Villa", "Porto",
        "Manchester United", "Club Brugge", "Real Betis", "PSV",
    ],
    "3": [
        "Feyenoord", "Lille", "Bodo/Glimt", "Napoli", "Leipzig", "Villarreal",
        "Fenerbahce", "Shakhtar Donetsk", "Galatasaray",
    ],
    "4": [
        "Slavia Praha", "Slovan Bratislava", "Stuttgart", "AEK Athens", "LASK",
        "Como", "Lens", "Viking", "Sabah Baku",
    ],
}

UCL_API_TEAM_IDS = {
    "AEK Athens": 278, "Arsenal": 42, "Aston Villa": 66, "Atletico Madrid": 530,
    "Barcelona": 529, "Bayern Munich": 157, "Bodo/Glimt": 327,
    "Borussia Dortmund": 165, "Club Brugge": 569, "Como": 895, "Fenerbahce": 611,
    "Feyenoord": 209, "Galatasaray": 645, "Inter": 505, "LASK": 805,
    "Leipzig": 173, "Lens": 116, "Lille": 79, "Liverpool": 40,
    "Manchester City": 50, "Manchester United": 33, "Napoli": 492,
    "Paris Saint-Germain": 85, "Porto": 212, "PSV": 197, "Real Betis": 543,
    "Real Madrid": 541, "Roma": 497, "Shakhtar Donetsk": 550, "Slavia Praha": 560,
    "Slovan Bratislava": 663, "Sporting CP": 228, "Stuttgart": 172, "Villarreal": 533,
}
UCL_FALLBACK_BADGES = {
    "Sabah Baku": "https://a.espncdn.com/i/teamlogos/soccer/500/21922.png",
    "Viking": "https://a.espncdn.com/i/teamlogos/soccer/500/510.png",
}


def ligue1_teams(provider_teams: list[dict] | None = None) -> list[dict[str, str]]:
    """Merge the full season roster with any badges returned by the live catalog."""
    provider_teams = provider_teams or []
    normalized = {" ".join(team.get("name", "").casefold().split()): team for team in provider_teams}
    result = []
    for name, team_id in LIGUE1_2026_27:
        source = normalized.get(" ".join(name.casefold().split()), {})
        badge = source.get("badge") or _api_badge(team_id)
        if name == "Le Mans" and not source.get("badge"):
            badge = "https://r2.thesportsdb.com/images/media/team/badge/wjhziv1700145026.png"
        result.append({"id": str(team_id), "name": name, "badge": badge})
    return result


def champions_league_teams() -> list[dict[str, str]]:
    """All 36 2026/27 participants, tagged with their official draw pot."""
    result = []
    for pot, names in UCL_2026_27_POTS.items():
        for index, name in enumerate(names, start=1):
            team_id = UCL_API_TEAM_IDS.get(name)
            badge = _api_badge(team_id) if team_id else UCL_FALLBACK_BADGES.get(name, "")
            result.append({
                "id": str(team_id or 950000 + int(pot) * 100 + index),
                "name": name,
                "badge": badge,
                "pot": pot,
            })
    return result
