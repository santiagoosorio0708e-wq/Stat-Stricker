"""
langchain_pipeline.py
---------------------
Capa de orquestación con LangChain (LCEL, BaseRetriever, BaseChatModel,
BaseChatMessageHistory y ChatPromptTemplate) integrada sobre los proveedores
existentes de StatStriker (ChromaDB, EmbeddingProvider, Gemini/OpenAI/Mock y SQLite).
"""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun, CallbackManagerForRetrieverRun
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings as LangChainEmbeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import ConfigDict, Field

from backend import database
from backend.embeddings import EmbeddingProvider
from backend.llm_client import LLMClient, LLMError
from backend.vector_store import RetrievedChunk, VectorStore


class StatStrikerEmbeddings(LangChainEmbeddings):
    """Adaptador de `EmbeddingProvider` a la interfaz estándar `Embeddings` de LangChain."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._provider.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._provider.embed_query(text)


class StatStrikerChromaRetriever(BaseRetriever):
    """Retriever de LangChain respaldado por el `VectorStore` persistente en ChromaDB."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    vector_store: VectorStore
    top_k: int = 6
    match_ids: list[str] | None = None
    max_distance: float | None = None

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        chunks = self.vector_store.search(
            query,
            top_k=self.top_k,
            match_ids=self.match_ids or None,
        )
        if self.max_distance is not None and not self.match_ids:
            chunks = [c for c in chunks if c.distance <= self.max_distance]

        docs: list[Document] = []
        for chunk in chunks:
            meta = dict(chunk.metadata)
            meta.update({
                "chunk_id": chunk.id,
                "distance": chunk.distance,
                "similarity": chunk.similarity,
            })
            docs.append(Document(page_content=chunk.text, metadata=meta))
        return docs


def documents_to_chunks(docs: list[Document]) -> list[RetrievedChunk]:
    """Convierte `Document`s de LangChain de vuelta a `RetrievedChunk` para compatibilidad RAG."""
    chunks: list[RetrievedChunk] = []
    for doc in docs:
        meta = dict(doc.metadata or {})
        chunks.append(
            RetrievedChunk(
                id=str(meta.get("chunk_id", "")),
                text=doc.page_content,
                metadata=meta,
                distance=float(meta.get("distance", 0.0)),
            )
        )
    return chunks


class SQLiteChatMessageHistory(BaseChatMessageHistory):
    """Historial de conversación de LangChain respaldado por SQLite (`database.py`)."""

    def __init__(self, session_id: str, limit: int = 10) -> None:
        self.session_id = session_id
        self.limit = limit

    @property
    def messages(self) -> list[BaseMessage]:
        rows = database.get_history(self.session_id, limit=self.limit)
        msgs: list[BaseMessage] = []
        for row in rows:
            msgs.append(HumanMessage(content=str(row.get("user_message", ""))))
            msgs.append(AIMessage(content=str(row.get("bot_response", ""))))
        return msgs

    def add_messages(self, messages: list[BaseMessage]) -> None:
        # La persistencia completa (incluyendo reglas, fuentes e imágenes) se guarda en `main.py`
        return None

    def clear(self) -> None:
        database.clear_history(self.session_id)


class StatStrikerChatModel(BaseChatModel):
    """ChatModel de LangChain que envuelve a GeminiClient (Interactions API), OpenAIClient o MockClient."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: LLMClient
    image_b64: str | None = None
    image_mime_type: str | None = None
    max_output_tokens: int | None = None
    use_web_search: bool = False

    @property
    def _llm_type(self) -> str:
        return f"statstriker-{self.client.provider}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        system_parts: list[str] = []
        user_parts: list[str] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_parts.append(self._extract_text(msg.content))
            elif isinstance(msg, HumanMessage):
                user_parts.append(self._extract_text(msg.content))
            elif isinstance(msg, AIMessage):
                user_parts.append(f"Asistente previo: {self._extract_text(msg.content)}")

        system_prompt = "\n\n".join(p for p in system_parts if p).strip()
        user_prompt = "\n\n".join(p for p in user_parts if p).strip()

        answer = self.client.generate(
            system_prompt,
            user_prompt,
            image_b64=kwargs.get("image_b64", self.image_b64),
            image_mime_type=kwargs.get("image_mime_type", self.image_mime_type),
            max_output_tokens=kwargs.get("max_output_tokens", self.max_output_tokens),
            use_web_search=kwargs.get("use_web_search", self.use_web_search),
        )
        ai_msg = AIMessage(
            content=answer,
            response_metadata={
                "provider": self.client.provider,
                "model": self.client.model,
            },
        )
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    @staticmethod
    def _extract_text(content: str | list[str | dict[str, Any]]) -> str:
        if isinstance(content, str):
            return content
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)


def build_chat_chain(
    primary: LLMClient | None,
    fallback: LLMClient | None = None,
    *,
    image_b64: str | None = None,
    image_mime_type: str | None = None,
    max_output_tokens: int | None = None,
    use_web_search: bool = False,
) -> Runnable[dict[str, str], AIMessage]:
    """
    Construye un Runnable LCEL de LangChain:
        ChatPromptTemplate -> StatStrikerChatModel (con fallback automático si hay respaldo)
    """
    models: list[StatStrikerChatModel] = []
    if primary is not None:
        models.append(
            StatStrikerChatModel(
                client=primary,
                image_b64=image_b64,
                image_mime_type=image_mime_type,
                max_output_tokens=max_output_tokens,
                use_web_search=use_web_search,
            )
        )
    if fallback is not None:
        models.append(
            StatStrikerChatModel(
                client=fallback,
                image_b64=image_b64,
                image_mime_type=image_mime_type,
                max_output_tokens=max_output_tokens,
                use_web_search=use_web_search,
            )
        )
    if not models:
        raise LLMError("No hay ningún proveedor LLM configurado para LangChain.")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human", "{user_prompt}"),
    ])
    llm_runnable: Runnable[Any, AIMessage] = (
        models[0].with_fallbacks([models[1]]) if len(models) > 1 else models[0]
    )
    return prompt | llm_runnable


def build_text_extraction_chain(
    primary: LLMClient | None,
    fallback: LLMClient | None = None,
    *,
    image_b64: str | None = None,
    image_mime_type: str | None = None,
    max_output_tokens: int = 300,
) -> Runnable[dict[str, str], str]:
    """Cadena LCEL con `StrOutputParser` para extracción multimodal de boletos."""
    return build_chat_chain(
        primary,
        fallback,
        image_b64=image_b64,
        image_mime_type=image_mime_type,
        max_output_tokens=max_output_tokens,
        use_web_search=False,
    ) | StrOutputParser()


def retrieve_documents_lcel(
    vector_store: VectorStore,
    query: str,
    *,
    top_k: int,
    match_ids: list[str] | None,
    max_distance: float,
) -> list[RetrievedChunk]:
    """Ejecuta la recuperación vectorial a través de un `Runnable` de LangChain."""
    retriever = StatStrikerChromaRetriever(
        vector_store=vector_store,
        top_k=top_k,
        match_ids=match_ids or None,
        max_distance=None if match_ids else max_distance,
    )
    retrieval_runnable = retriever | RunnableLambda(documents_to_chunks)
    return retrieval_runnable.invoke(query)
