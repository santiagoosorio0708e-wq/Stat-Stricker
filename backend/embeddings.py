"""
embeddings.py
-------------
Capa de abstracción para generar embeddings.

Se usa el MISMO proveedor en la ingesta (`ingest.py`) y en la consulta
(`main.py`) para que los vectores vivan en el mismo espacio semántico.

Proveedores soportados (variable EMBEDDING_PROVIDER):
    - local  : all-MiniLM-L6-v2 vía ONNX (incluido en ChromaDB, sin API key)
    - gemini : gemini-embedding-001 (requiere GEMINI_API_KEY)
    - openai : text-embedding-3-small (requiere OPENAI_API_KEY)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.config import Settings


class EmbeddingProvider(ABC):
    """Interfaz común para cualquier generador de embeddings."""

    #: Identificador que se guarda en los metadatos de la colección vectorial.
    name: str = "base"

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Vectoriza fragmentos de conocimiento (fase de ingesta)."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Vectoriza la consulta del usuario (fase de recuperación)."""


class LocalEmbeddings(EmbeddingProvider):
    """Modelo local all-MiniLM-L6-v2 (se descarga una sola vez, ~80 MB)."""

    def __init__(self) -> None:
        from chromadb.utils import embedding_functions

        self._fn = embedding_functions.DefaultEmbeddingFunction()
        self.name = "local:all-MiniLM-L6-v2"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vec] for vec in self._fn(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class GeminiEmbeddings(EmbeddingProvider):
    """Embeddings de Google Gemini con task_type específico para RAG."""

    def __init__(self, api_key: str, model: str) -> None:
        from google import genai
        from google.genai import types

        self._client = genai.Client(api_key=api_key)
        self._types = types
        self._model = model
        self.name = f"gemini:{model}"

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=texts,
            config=self._types.EmbedContentConfig(task_type=task_type),
        )
        return [list(e.values) for e in response.embeddings]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


class OpenAIEmbeddings(EmbeddingProvider):
    """Embeddings de OpenAI."""

    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self.name = f"openai:{model}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embedding_provider(cfg: Settings) -> EmbeddingProvider:
    """Factory: construye el proveedor de embeddings configurado."""
    provider = cfg.embedding_provider

    if provider == "local":
        return LocalEmbeddings()
    if provider == "gemini":
        if not cfg.gemini_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=gemini requiere la variable GEMINI_API_KEY.")
        return GeminiEmbeddings(cfg.gemini_api_key, cfg.gemini_embedding_model)
    if provider == "openai":
        if not cfg.openai_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai requiere la variable OPENAI_API_KEY.")
        return OpenAIEmbeddings(cfg.openai_api_key, cfg.openai_embedding_model)

    raise RuntimeError(f"EMBEDDING_PROVIDER desconocido: '{provider}'. Usa local | gemini | openai.")
