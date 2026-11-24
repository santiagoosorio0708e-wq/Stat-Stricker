"""
database.py
-----------
Persistencia local del historial de consultas con SQLite (librería estándar).

Tabla `queries`:
    id, session_id, user_message, bot_response, active_rules (JSON),
    sources (JSON), provider, created_at
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from backend.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT    NOT NULL,
    user_message    TEXT    NOT NULL,
    user_image_data TEXT    NOT NULL DEFAULT '',
    user_image_mime TEXT    NOT NULL DEFAULT '',
    bot_response    TEXT    NOT NULL,
    active_rules    TEXT    NOT NULL DEFAULT '[]',
    sources         TEXT    NOT NULL DEFAULT '[]',
    provider        TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_queries_session ON queries (session_id, id);
"""


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Abre una conexión SQLite, hace commit al salir y siempre la cierra."""
    path = db_path or settings.sqlite_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Crea las tablas si no existen y migra columnas faltantes (idempotente)."""
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(queries)").fetchall()}
        if "user_image_data" not in cols:
            conn.execute("ALTER TABLE queries ADD COLUMN user_image_data TEXT NOT NULL DEFAULT ''")
        if "user_image_mime" not in cols:
            conn.execute("ALTER TABLE queries ADD COLUMN user_image_mime TEXT NOT NULL DEFAULT ''")


def save_interaction(
    session_id: str,
    user_message: str,
    bot_response: str,
    active_rules: list[str],
    sources: list[dict[str, Any]],
    provider: str,
    user_image_data: str = "",
    user_image_mime: str = "",
) -> int:
    """Guarda una pregunta/respuesta (incluida captura si aplica) y devuelve su id."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO queries
                (session_id, user_message, user_image_data, user_image_mime, bot_response, active_rules, sources, provider, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_message,
                user_image_data or "",
                user_image_mime or "",
                bot_response,
                json.dumps(active_rules, ensure_ascii=False),
                json.dumps(sources, ensure_ascii=False),
                provider,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        return int(cur.lastrowid)


def get_history(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Devuelve las últimas `limit` interacciones de la sesión en orden cronológico."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM queries WHERE session_id = ? ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
            """,
            (session_id, limit),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "user_message": row["user_message"],
            "user_image_data": row["user_image_data"] or "",
            "user_image_mime": row["user_image_mime"] or "",
            "bot_response": row["bot_response"],
            "active_rules": json.loads(row["active_rules"]),
            "sources": json.loads(row["sources"]),
            "provider": row["provider"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    """Lista sesiones guardadas en SQLite ordenadas de la más reciente a la más antigua."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                q.session_id,
                MIN(q.created_at) AS created_at,
                MAX(q.created_at) AS updated_at,
                COUNT(*) AS message_count,
                (
                    SELECT q2.user_message
                    FROM queries q2
                    WHERE q2.session_id = q.session_id
                    ORDER BY q2.id ASC
                    LIMIT 1
                ) AS first_message
            FROM queries q
            GROUP BY q.session_id
            ORDER BY MAX(q.id) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row["session_id"],
            "title": ((row["first_message"] or "Conversación anterior").replace("\n", " ").strip()[:42]) or "Conversación anterior",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": int(row["message_count"] or 0),
        }
        for row in rows
    ]


def clear_history(session_id: str) -> int:
    """Borra el historial de una sesión. Devuelve el nº de filas eliminadas."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM queries WHERE session_id = ?", (session_id,))
        return cur.rowcount
