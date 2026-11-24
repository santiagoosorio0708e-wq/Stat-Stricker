"""
ingest.py
---------
Script de inicialización de la base vectorial (ChromaDB).

Lee un JSON con datos de partidos (estadísticas, H2H, lesiones, clima, cuotas),
lo divide en fragmentos semánticos ("chunks") por categoría, genera los
embeddings y los guarda en ChromaDB con metadatos para poder filtrarlos.

Uso (desde la raíz del proyecto):
    python -m backend.ingest                 # ingesta incremental (upsert)
    python -m backend.ingest --reset         # borra la colección y re-ingesta
    python -m backend.ingest --file otra.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import settings
from backend.database import init_db
from backend.embeddings import get_embedding_provider
from backend.vector_store import VectorStore


# ====================================================================== #
# Conversión de JSON estructurado -> texto natural (mejores embeddings)
# ====================================================================== #
def _team_form_text(team: dict[str, Any], side: str) -> str:
    record_key = "home_record_season" if side == "local" else "away_record_season"
    return (
        f"Forma reciente de {team['name']} (juega como {side}). "
        f"Posición en liga: {team['league_position']}º. "
        f"Últimos 5 partidos: {', '.join(team['recent_form'])} "
        f"({'; '.join(team['last_5_results'])}). "
        f"Promedio de goles a favor: {team['goals_scored_avg']} y en contra: {team['goals_conceded_avg']}. "
        f"xG a favor: {team['xg_for_avg']} y xG en contra: {team['xg_against_avg']}. "
        f"Partidos con más de 2.5 goles: {team['over_2_5_pct']}%. "
        f"Ambos marcan (BTTS): {team['btts_pct']}%. "
        f"Porterías a cero en los últimos 10: {team['clean_sheets_last_10']}. "
        f"Promedio de córners: {team['corners_avg']}. "
        f"Récord como {side} esta temporada: {team.get(record_key, 'n/d')}. "
        f"Máximo goleador: {team['top_scorer']}."
    )


def _injuries_text(match: dict[str, Any]) -> str:
    def fmt(players: list[dict[str, str]]) -> str:
        if not players:
            return "sin bajas reportadas"
        return "; ".join(
            f"{p['player']} ({p['position']}) - {p['status']}, impacto {p['impact']}" for p in players
        )

    home, away = match["home_team"]["name"], match["away_team"]["name"]
    return (
        f"Lesiones y bajas para {home} vs {away}. "
        f"{home}: {fmt(match['injuries']['home'])}. "
        f"{away}: {fmt(match['injuries']['away'])}."
    )


def _odds_text(match: dict[str, Any]) -> str:
    o = match["odds"]
    home, away = match["home_team"]["name"], match["away_team"]["name"]
    extras = ", ".join(
        f"{k.replace('_', ' ')}: {v}" for k, v in o.items() if k not in {"1x2", "bookmaker_avg"}
    )
    return (
        f"Cuotas de mercado (promedio de casas) para {home} vs {away}. "
        f"1X2 -> victoria {home}: {o['1x2']['home']}, empate: {o['1x2']['draw']}, "
        f"victoria {away}: {o['1x2']['away']}. Otros mercados: {extras}."
    )


def build_chunks(match: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Devuelve una lista de (id, texto, metadatos) para un partido."""
    mid = match["match_id"]
    home, away = match["home_team"], match["away_team"]
    ref = match["referee"]
    w = match["weather"]

    base_meta = {
        "match_id": mid,
        "home_team": home["name"],
        "away_team": away["name"],
        "competition": match["competition"],
        "date": match["date"],
    }

    chunks: list[tuple[str, str, dict[str, Any]]] = [
        (
            "overview",
            f"Partido {home['name']} vs {away['name']} - {match['competition']}, "
            f"{match['date']} a las {match['kickoff']} en {match['venue']}. "
            f"Árbitro: {ref['name']} (media de {ref['avg_yellow_cards']} amarillas, "
            f"{ref['avg_red_cards']} rojas y {ref['penalties_per_game']} penaltis por partido). "
            f"Notas: {match.get('notes', '')}",
        ),
        ("forma_local", _team_form_text(home, "local")),
        ("forma_visitante", _team_form_text(away, "visitante")),
        (
            "h2h",
            f"Historial de enfrentamientos directos (H2H) {home['name']} vs {away['name']}. "
            f"Últimos 5: {'; '.join(match['h2h']['last_5'])}. Resumen: {match['h2h']['summary']}",
        ),
        ("lesiones", _injuries_text(match)),
        (
            "clima",
            f"Clima y estado del campo para {home['name']} vs {away['name']}: {w['condition']}, "
            f"{w['temperature_c']} °C, viento de {w['wind_kmh']} km/h, probabilidad de lluvia "
            f"{w['precipitation_pct']}%. Terreno: {w['pitch']}.",
        ),
        ("cuotas", _odds_text(match)),
    ]

    result = []
    for category, text in chunks:
        meta = {**base_meta, "category": category}
        if category == "overview":
            # Alias para el entity linking del sistema experto (Chroma solo admite escalares)
            meta["aliases"] = "|".join(home["aliases"] + away["aliases"] + match.get("match_aliases", []))
        result.append((f"{mid}::{category}", text, meta))
    return result


# ====================================================================== #
# Ejecución
# ====================================================================== #
def ingest(file_path: Path, reset: bool = False, if_empty: bool = False) -> int:
    with file_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    matches = data.get("matches", [])
    if not matches:
        raise ValueError(f"El archivo {file_path} no contiene la clave 'matches'.")

    print(f"⚙️  Proveedor de embeddings: {settings.embedding_provider}")
    embedder = get_embedding_provider(settings)
    store = VectorStore(settings.chroma_path, settings.chroma_collection, embedder)

    if if_empty and not reset and store.count() > 0:
        print(f"ℹ️  ChromaDB ya contiene {store.count()} fragmentos; se omite la ingesta.")
        return store.count()

    if reset:
        print("🧹 Reiniciando colección vectorial...")
        store.reset()
    else:
        store.check_compatibility()

    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
    ids, docs, metas = [], [], []
    for match in matches:
        chunks = build_chunks(match)
        for chunk_id, text, meta in chunks:
            parts = splitter.split_text(text) if len(text) > 1200 else [text]
            for idx, part in enumerate(parts):
                part_id = chunk_id if len(parts) == 1 else f"{chunk_id}::p{idx}"
                ids.append(part_id)
                docs.append(part)
                metas.append(meta)
        print(f"   • {match['home_team']['name']} vs {match['away_team']['name']}: {len(chunks)} fragmentos")

    print(f"🧠 Generando embeddings de {len(docs)} fragmentos...")
    store.upsert(ids, docs, metas)
    return store.count()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta de datos de fútbol en ChromaDB")
    parser.add_argument("--file", type=Path, default=settings.data_file, help="Ruta al JSON de partidos")
    parser.add_argument("--reset", action="store_true", help="Borra la colección antes de ingestar")
    parser.add_argument("--if-empty", action="store_true", help="Solo ingesta si la colección está vacía")
    args = parser.parse_args()

    if not args.file.exists():
        sys.exit(f"❌ No se encontró el archivo {args.file}")

    init_db()  # deja también lista la base SQLite del historial
    total = ingest(args.file, reset=args.reset, if_empty=args.if_empty)
    print(f"✅ Ingesta completada. Fragmentos en la colección: {total}")
    print(f"   ChromaDB: {settings.chroma_path}")
    print(f"   SQLite:   {settings.sqlite_path}")


if __name__ == "__main__":
    main()
