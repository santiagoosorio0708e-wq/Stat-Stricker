"""
vector_store.py
---------------
Pilar 3: Búsqueda Semántica con ChromaDB (persistente en disco).

Los embeddings se calculan explícitamente con `EmbeddingProvider` y se
pasan a Chroma, de modo que el flujo RAG es transparente:
    texto -> embedding -> búsqueda por similitud coseno -> fragmentos.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

from backend.embeddings import EmbeddingProvider


@dataclass
class RetrievedChunk:
    """Fragmento de conocimiento recuperado de la base vectorial."""

    id: str
    text: str
    metadata: dict[str, Any]
    distance: float

    @property
    def similarity(self) -> float:
        """Similitud aproximada 0..1 a partir de la distancia coseno (0..2)."""
        return max(0.0, 1.0 - self.distance / 2.0)

    def to_source(self) -> dict[str, Any]:
        """Representación ligera para el frontend / historial."""
        return {
            "id": self.id,
            "match_id": self.metadata.get("match_id", ""),
            "match": f"{self.metadata.get('home_team', '?')} vs {self.metadata.get('away_team', '?')}",
            "category": self.metadata.get("category", ""),
            "similarity": round(self.similarity, 3),
        }


class VectorStore:
    """Envoltorio de alto nivel sobre una colección de ChromaDB."""

    def __init__(self, path: Path, collection_name: str, embedder: EmbeddingProvider) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection_name = collection_name
        self._embedder = embedder
        self._collection = self._get_or_create()

    # ------------------------------------------------------------------ #
    # Gestión de la colección
    # ------------------------------------------------------------------ #
    def _get_or_create(self):
        return self._client.get_or_create_collection(
            name=self._collection_name,
            # Similitud coseno + proveedor de embeddings usado (para detectar incompatibilidades)
            metadata={"hnsw:space": "cosine", "embedding_provider": self._embedder.name},
            embedding_function=None,  # los embeddings los calculamos nosotros
        )

    def reset(self) -> None:
        """Elimina y recrea la colección (útil al cambiar de proveedor de embeddings)."""
        try:
            self._client.delete_collection(self._collection_name)
        except Exception:  # la colección no existía
            pass
        self._collection = self._get_or_create()

    def count(self) -> int:
        return self._collection.count()

    def check_compatibility(self) -> None:
        """Lanza un error claro si la colección se creó con otro proveedor de embeddings."""
        stored = (self._collection.metadata or {}).get("embedding_provider")
        if stored and stored != self._embedder.name and self.count() > 0:
            raise RuntimeError(
                f"La base vectorial fue creada con '{stored}' pero el proveedor actual es "
                f"'{self._embedder.name}'. Ejecuta: python -m backend.ingest --reset"
            )

    # ------------------------------------------------------------------ #
    # Escritura
    # ------------------------------------------------------------------ #
    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        """Vectoriza y guarda (o actualiza) los fragmentos."""
        embeddings = self._embedder.embed_documents(documents)
        self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    # ------------------------------------------------------------------ #
    # Lectura
    # ------------------------------------------------------------------ #
    def search(
        self,
        query: str,
        top_k: int = 6,
        match_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        """
        Búsqueda semántica:
          1. Convierte la consulta en embedding.
          2. Busca los `top_k` vecinos más cercanos (coseno).
          3. Si el sistema experto detectó equipos, filtra por esos partidos.
        """
        total = self.count()
        if total == 0:
            return []

        query_embedding = self._embedder.embed_query(query)

        where: dict[str, Any] | None = None
        if match_ids:
            where = {"match_id": {"$in": match_ids}} if len(match_ids) > 1 else {"match_id": match_ids[0]}

        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, min(top_k, total)),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[RetrievedChunk] = []
        for i, chunk_id in enumerate(result["ids"][0]):
            chunks.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=result["documents"][0][i],
                    metadata=dict(result["metadatas"][0][i] or {}),
                    distance=float(result["distances"][0][i]),
                )
            )
        return chunks

    def list_matches(self) -> list[dict[str, Any]]:
        """Catálogo de partidos ingeridos (a partir de los fragmentos 'overview')."""
        if self.count() == 0:
            return []
        data = self._collection.get(where={"category": "overview"}, include=["metadatas"])
        matches = []
        for meta in data["metadatas"]:
            meta = dict(meta or {})
            matches.append(
                {
                    "match_id": meta.get("match_id", ""),
                    "home_team": meta.get("home_team", ""),
                    "away_team": meta.get("away_team", ""),
                    "competition": meta.get("competition", ""),
                    "date": meta.get("date", ""),
                    "aliases": [a for a in str(meta.get("aliases", "")).split("|") if a],
                }
            )
        return sorted(matches, key=lambda m: m["date"])
