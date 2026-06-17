from __future__ import annotations

import json
import logging
import os
import re
from urllib import error, request
from dataclasses import dataclass

from app.config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    raw: object | None = None


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = settings.llm_provider.lower().strip()

    def complete(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        if self.provider == "auto":
            self.provider = self._resolve_auto_provider()
        if self.provider == "none":
            return LLMResponse(text="{}", raw=None)
        if self.provider in {"local", "ollama"}:
            return self._complete_ollama(prompt, system_prompt)
        if self.provider == "openai":
            return self._complete_openai(prompt, system_prompt)
        if self.provider == "gemini":
            return self._complete_gemini(prompt, system_prompt)
        raise ValueError(f"Proveedor LLM no soportado: {self.provider}")

    def complete_json(self, prompt: str, system_prompt: str = "") -> dict:
        response = self.complete(prompt=prompt, system_prompt=system_prompt)
        return self._extract_json(response.text)

    def _complete_openai(self, prompt: str, system_prompt: str) -> LLMResponse:
        from openai import OpenAI

        api_key = self.settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY no configurada")

        client = OpenAI(api_key=api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        completion = client.chat.completions.create(
            model=self.settings.openai_model,
            messages=messages,
            temperature=self.settings.temperature,
        )
        text = completion.choices[0].message.content or ""
        return LLMResponse(text=text, raw=completion)

    def _complete_gemini(self, prompt: str, system_prompt: str) -> LLMResponse:
        import google.generativeai as genai

        api_key = self.settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no configurada")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=self.settings.gemini_model,
            system_instruction=system_prompt or None,
        )
        response = model.generate_content(prompt)
        text = getattr(response, "text", "") or ""
        return LLMResponse(text=text, raw=response)

    def _complete_ollama(self, prompt: str, system_prompt: str) -> LLMResponse:
        base_url = self.settings.ollama_base_url.rstrip("/")
        url = f"{base_url}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.settings.temperature},
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.settings.ollama_timeout_seconds) as response:
                raw_bytes = response.read()
        except error.URLError as exc:
            raise ValueError(
                "No se pudo conectar con Ollama. Verifica que Ollama este corriendo y revisa OLLAMA_BASE_URL."
            ) from exc

        raw_text = raw_bytes.decode("utf-8", errors="replace")
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Respuesta invalida del servidor Ollama") from exc

        message = data.get("message") or {}
        text = message.get("content") or data.get("response") or ""
        return LLMResponse(text=text, raw=data)

    def _resolve_auto_provider(self) -> str:
        if self._configure_ollama_model_from_installed():
            logger.info("LLM auto: usando proveedor ollama con modelo %s", self.settings.ollama_model)
            return "ollama"

        if self.settings.openai_api_key or os.getenv("OPENAI_API_KEY"):
            logger.info("LLM auto: usando proveedor openai")
            return "openai"

        if self.settings.gemini_api_key or os.getenv("GEMINI_API_KEY"):
            logger.info("LLM auto: usando proveedor gemini")
            return "gemini"

        logger.warning("LLM auto: no se detecto proveedor disponible, activando modo none")
        return "none"

    def _configure_ollama_model_from_installed(self) -> bool:
        installed = self._get_ollama_installed_models()
        if not installed:
            return False

        candidates = [
            item.strip()
            for item in (self.settings.ollama_model_candidates or "").split(",")
            if item.strip()
        ]

        if self.settings.ollama_model in installed:
            return True

        for candidate in candidates:
            if candidate in installed:
                self.settings.ollama_model = candidate
                return True

        self.settings.ollama_model = sorted(installed)[0]
        return True

    def _get_ollama_installed_models(self) -> set[str]:
        base_url = self.settings.ollama_base_url.rstrip("/")
        url = f"{base_url}/api/tags"
        req = request.Request(url=url, method="GET")
        try:
            with request.urlopen(req, timeout=min(self.settings.ollama_timeout_seconds, 8)) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except Exception:
            return set()

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return set()

        models = payload.get("models") or []
        names = {str(model.get("name", "")).strip() for model in models if isinstance(model, dict)}
        return {name for name in names if name}

    def _extract_json(self, text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                return {"raw_text": text}
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {"raw_text": text}
