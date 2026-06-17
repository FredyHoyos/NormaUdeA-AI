from __future__ import annotations

import json
import logging
import os
import re
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
        if self.provider in {"none", "local"}:
            return LLMResponse(text="{}", raw=None)
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
