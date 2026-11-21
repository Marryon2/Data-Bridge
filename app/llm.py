from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from app.config import load_env, load_model


class LLMClient:
    """Klient JSON-mode (API zgodne z OpenAI). Gdy model wymaga klucza, a go brak => complete_json zwraca None."""

    def __init__(self, model: dict | None = None):
        load_env()
        self.model = model or load_model()
        # Pusty api_key_env = serwer bez klucza (np. własna Ollama).
        self.key_env = self.model.get("api_key_env", "MISTRAL_API_KEY")
        self.api_key = os.environ.get(self.key_env, "").strip() if self.key_env else ""

    @property
    def available(self) -> bool:
        return bool(self.model.get("endpoint")) and (not self.key_env or bool(self.api_key))

    def complete_json(self, system: str, user: str) -> dict | None:
        if not self.available:
            return None
        payload = {
            "model": self.model["name"],
            "temperature": self.model.get("temperature", 0),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        # Natywne API Ollamy (/api/chat): jedyne, które pozwala ustawić num_ctx; /v1 ucina prompt do 4096 tokenów.
        native = self.model["endpoint"].rstrip("/").endswith("/api/chat")
        if native:
            payload = {"model": payload["model"], "messages": payload["messages"], "stream": False,
                       "options": {"temperature": payload["temperature"], "num_ctx": self.model.get("num_ctx", 8192)}}
            if self.model.get("json_mode", True):
                payload["format"] = "json"
        elif self.model.get("json_mode", True):
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            self.model["endpoint"],
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
            | ({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            method="POST",
        )
        body = None
        for attempt in (1, 2):  # jedna ponowna próba: zdarzają się chwilowe błędy DNS / sieci
            try:
                with urllib.request.urlopen(request, timeout=self.model.get("timeout_s", 60)) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                print(f"LLM niedostępne (próba {attempt}): {exc}")
        if body is None:
            return None
        try:
            content = body["message"]["content"] if native else body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None
