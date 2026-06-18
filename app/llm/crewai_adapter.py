from __future__ import annotations

import logging

from app.config.settings import Settings

logger = logging.getLogger(__name__)


def build_crewai_llm(settings: Settings):
    from crewai import LLM as CrewLLM

    provider = settings.llm_provider.lower().strip()

    if provider == "auto":
        provider = _resolve_for_crewai(settings)

    if provider == "openai":
        kwargs = {"model": settings.openai_model}
        if settings.openai_api_key:
            kwargs["api_key"] = settings.openai_api_key
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return CrewLLM(**kwargs)

    if provider == "gemini":
        kwargs = {"model": settings.gemini_model, "provider": "google"}
        if settings.gemini_api_key:
            kwargs["api_key"] = settings.gemini_api_key
        return CrewLLM(**kwargs)

    if provider in ("ollama", "local"):
        model_name = f"ollama/{settings.ollama_model}"
        kwargs = {"model": model_name, "base_url": settings.ollama_base_url}
        return CrewLLM(**kwargs)

    logger.warning("No se pudo crear CrewAI LLM para provider=%s. Usando fallback None.", provider)
    return None


def _resolve_for_crewai(settings: Settings) -> str:
    if settings.openai_api_key or settings.openai_base_url:
        return "openai"
    if settings.gemini_api_key:
        return "gemini"
    try:
        import urllib.request
        import json

        req = urllib.request.Request(
            f"{settings.ollama_base_url}/api/tags",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode())
            if data.get("models"):
                return "ollama"
    except Exception:
        pass
    return "openai"
