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
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Envía el system prompt + prompt de usuario y devuelve el texto generado."""


class GeminiClient(LLMClient):
    """Cliente para Google Gemini usando el SDK oficial `google-genai`."""

    provider = "gemini"

    def __init__(self, api_key: str, model: str, max_output_tokens: int) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self._max_tokens = max_output_tokens

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            interaction = self._client.interactions.create(
                model=self.model,
                system_instruction=system_prompt,  # <- System Prompt dinámico
                input=user_prompt,
                generation_config={"max_output_tokens": self._max_tokens},
                store=False,  # no necesitamos estado en servidor: el historial vive en SQLite
            )
        except Exception as exc:  # errores de red, cuota, clave inválida...
            raise LLMError(f"Error al llamar a Gemini: {exc}") from exc
        return (interaction.output_text or "").strip()


class OpenAIClient(LLMClient):
    """Cliente para OpenAI Chat Completions."""

    provider = "openai"

    def __init__(self, api_key: str, model: str, max_output_tokens: int) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.model = model
        self._max_tokens = max_output_tokens

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},  # <- System Prompt dinámico
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=self._max_tokens,
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

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        modules = [line[3:] for line in system_prompt.splitlines() if line.startswith("## ")]
        context = user_prompt.split("<contexto>")[1].split("</contexto>")[0].strip()
        preview = "\n".join(f"> {line}" for line in context.splitlines()[:12])
        return (
            "### 🧪 Modo simulación (LLM_PROVIDER=mock)\n"
            "No se ha llamado a ningún LLM. Así se habría construido la petición:\n\n"
            "**Módulos del System Prompt inyectados:**\n"
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
