"""Pinned club catalogs for competitions where free API plans truncate teams."""

from __future__ import annotations


def _api_badge(team_id: int) -> str:
    return f"https://media.api-sports.io/football/teams/{team_id}.png"


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
            badge = _api_badge(team_id) if team_id else "https://r2.thesportsdb.com/images/media/team/badge/5cw7q91723051971.png"
            result.append({
                "id": str(team_id or 950000 + int(pot) * 100 + index),
                "name": name,
                "badge": badge,
                "pot": pot,
            })
    return result
