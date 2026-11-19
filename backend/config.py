"""
config.py
---------
Configuración centralizada de StatStriker.

Todas las claves y parámetros se leen EXCLUSIVAMENTE desde variables de
entorno (o un archivo .env local ignorado por git). Nunca se escriben
API keys en el código fuente.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Raíz del proyecto (carpeta que contiene /backend, /frontend, /data)
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Carga el .env de la raíz si existe (no sobrescribe variables ya definidas).
load_dotenv(BASE_DIR / ".env")


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Parámetros inmutables de la aplicación."""

    # --- LLM ---
    llm_provider: str = field(default_factory=lambda: _env_str("LLM_PROVIDER", "gemini").lower())
    gemini_api_key: str = field(default_factory=lambda: _env_str("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: _env_str("GEMINI_MODEL", "gemini-3.5-flash-lite"))
    openai_api_key: str = field(default_factory=lambda: _env_str("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _env_str("OPENAI_MODEL", "gpt-4o-mini"))
    llm_max_output_tokens: int = field(default_factory=lambda: _env_int("LLM_MAX_OUTPUT_TOKENS", 1500))

    # --- API-Football (API-Sports) ---
    football_api_key: str = field(default_factory=lambda: _env_str("API_SPORTS_KEY"))

    # --- Embeddings ---
    embedding_provider: str = field(default_factory=lambda: _env_str("EMBEDDING_PROVIDER", "local").lower())
    gemini_embedding_model: str = field(
        default_factory=lambda: _env_str("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    )
    openai_embedding_model: str = field(
        default_factory=lambda: _env_str("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )

    # --- RAG ---
    rag_top_k: int = field(default_factory=lambda: _env_int("RAG_TOP_K", 6))
    rag_max_distance: float = field(default_factory=lambda: _env_float("RAG_MAX_DISTANCE", 0.6))
    history_turns: int = field(default_factory=lambda: _env_int("HISTORY_TURNS", 3))

    # --- Rutas de persistencia local ---
    storage_dir: Path = BASE_DIR / "storage"
    chroma_path: Path = BASE_DIR / "storage" / "chroma_db"
    chroma_collection: str = "statstriker_football"
    sqlite_path: Path = BASE_DIR / "storage" / "statstriker.db"
    data_file: Path = BASE_DIR / "data" / "mock_matches.json"
    frontend_dir: Path = BASE_DIR / "frontend"


settings = Settings()
