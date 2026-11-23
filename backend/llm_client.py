"""
llm_client.py
-------------
Pilar 1: Consumo de un LLM mediante API RESTful.

Clientes intercambiables (variable LLM_PROVIDER):
    - gemini : Google Gemini (Interactions API, SDK google-genai)
    - openai : OpenAI Chat Completions
    - mock   : respuesta simulada para probar el flujo RAG sin API key

Las API keys se leen desde variables de entorno (ver config.py).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.config import Settings


class LLMError(RuntimeError):
    """Error controlado al invocar al proveedor LLM."""


class LLMClient(ABC):
    provider: str = "base"
    model: str = ""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str | None = None,
        image_mime_type: str | None = None,
        max_output_tokens: int | None = None,
        use_web_search: bool = False,
    ) -> str:
        """Envía el system prompt + prompt de usuario (y foto opcional) y devuelve texto."""


class GeminiClient(LLMClient):
    """Cliente para Google Gemini usando el SDK oficial `google-genai`."""

    provider = "gemini"
    _FALLBACK_MODELS = ("gemini-3.5-flash-lite", "gemini-4-hydrogen", "gemini-3.1-flash-lite")

    def __init__(self, api_key: str, model: str, max_output_tokens: int) -> None:
        from google import genai
        from google.genai import types

        http_options = types.HttpOptions(
            timeout=15000,
            retry_options=types.HttpRetryOptions(attempts=1),
        )
        self._client = genai.Client(api_key=api_key, http_options=http_options)
        # gemini-3.8-flash suele tardar >30s o devolver 503; priorizamos el modelo más ágil.
        self.model = "gemini-3.5-flash-lite" if model == "gemini-3.8-flash" else model
        self._max_tokens = max_output_tokens

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str | None = None,
        image_mime_type: str | None = None,
        max_output_tokens: int | None = None,
        use_web_search: bool = False,
    ) -> str:
        candidates = [self.model] + [m for m in self._FALLBACK_MODELS if m != self.model]
        payload_input: str | list[dict[str, str]] = (
            [
                {"type": "text", "text": user_prompt},
                {"type": "image", "data": image_b64, "mime_type": image_mime_type or "image/jpeg"},
            ]
            if image_b64
            else user_prompt
        )
        tokens = max_output_tokens or self._max_tokens
        last_exc: Exception | None = None
        for candidate in candidates:
            # Si use_web_search está activo, intentamos con google_search y si la cuota/plan
            # devuelve 429 o error de herramienta, reintentamos al instante sin tools.
            tool_modes = ([{"type": "google_search"}], None) if use_web_search and not image_b64 else (None,)
            for tools in tool_modes:
                try:
                    kwargs: dict[str, object] = {
                        "model": candidate,
                        "system_instruction": system_prompt,
                        "input": payload_input,
                        "generation_config": {"max_output_tokens": tokens},
                        "store": False,
                    }
                    if tools:
                        kwargs["tools"] = tools
                    interaction = self._client.interactions.create(**kwargs)
                    self.model = candidate
                    return (interaction.output_text or "").strip()
                except Exception as exc:
                    last_exc = exc
                    detail = str(exc).casefold()
                    if tools is not None and any(tok in detail for tok in ("429", "quota", "too_many_requests", "tool")):
                        continue
                    temporary = any(
                        token in detail
                        for token in (
                            "503", "429", "500", "502", "504",
                            "service_unavailable", "high demand", "rate limit",
                            "timed out", "timeout", "unavailable",
                        )
                    )
                    if not temporary:
                        raise LLMError(f"Error al llamar a Gemini ({candidate}): {exc}") from exc
                    break
        raise LLMError(f"Error al llamar a Gemini: {last_exc}") from last_exc


class OpenAIClient(LLMClient):
    """Cliente para OpenAI Chat Completions."""

    provider = "openai"

    def __init__(self, api_key: str, model: str, max_output_tokens: int) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=25.0, max_retries=0)
        self.model = model
        self._max_tokens = max_output_tokens

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str | None = None,
        image_mime_type: str | None = None,
        max_output_tokens: int | None = None,
        use_web_search: bool = False,
    ) -> str:
        user_content: str | list[dict[str, object]] = (
            [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_mime_type or 'image/jpeg'};base64,{image_b64}"},
                },
            ]
            if image_b64
            else user_prompt
        )
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},  # <- System Prompt dinámico
                    {"role": "user", "content": user_content},
                ],
                max_completion_tokens=max_output_tokens or self._max_tokens,
            )
        except Exception as exc:
            raise LLMError(f"Error al llamar a OpenAI: {exc}") from exc
        return (completion.choices[0].message.content or "").strip()


class MockClient(LLMClient):
    """
    Cliente simulado: no llama a ninguna API. Devuelve un resumen del contexto
    recuperado para verificar que la ingesta, la búsqueda vectorial y el
    sistema experto funcionan antes de configurar una API key real.
    """

    provider = "mock"
    model = "mock-tipster"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str | None = None,
        image_mime_type: str | None = None,
        max_output_tokens: int | None = None,
        use_web_search: bool = False,
    ) -> str:
        modules = [line[3:] for line in system_prompt.splitlines() if line.startswith("## ")]
        context = (
            user_prompt.split("<contexto>")[1].split("</contexto>")[0].strip()
            if "<contexto>" in user_prompt
            else "(sin contexto vectorial)"
        )
        preview = "\n".join(f"> {line}" for line in context.splitlines()[:12])
        img_note = f"\n**Imagen adjunta:** sí ({image_mime_type or 'image/jpeg'})\n" if image_b64 else ""
        return (
            "### 🧪 Modo simulación (LLM_PROVIDER=mock)\n"
            "No se ha llamado a ningún LLM. Así se habría construido la petición:\n\n"
            + img_note
            + "**Módulos del System Prompt inyectados:**\n"
            + "\n".join(f"- {m}" for m in modules)
            + "\n\n**Contexto recuperado de ChromaDB (extracto):**\n"
            + preview
            + "\n\n⚠️ Configura `LLM_PROVIDER=gemini` u `openai` en `.env` para obtener un análisis real."
        )


def get_llm_client(cfg: Settings) -> LLMClient:
    """Factory: crea el cliente LLM configurado o lanza un error descriptivo."""
    provider = cfg.llm_provider

    if provider == "gemini":
        if not cfg.gemini_api_key:
            raise LLMError("Falta GEMINI_API_KEY en el archivo .env (o usa LLM_PROVIDER=mock).")
        return GeminiClient(cfg.gemini_api_key, cfg.gemini_model, cfg.llm_max_output_tokens)
    if provider == "openai":
        if not cfg.openai_api_key:
            raise LLMError("Falta OPENAI_API_KEY en el archivo .env (o usa LLM_PROVIDER=mock).")
        return OpenAIClient(cfg.openai_api_key, cfg.openai_model, cfg.llm_max_output_tokens)
    if provider == "mock":
        return MockClient()

    raise LLMError(f"LLM_PROVIDER desconocido: '{provider}'. Usa gemini | openai | mock.")
