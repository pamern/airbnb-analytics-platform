"""Resilient Groq client with key rotation, shared cooldowns, and model fallback."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from groq import Groq, RateLimitError

from configs.settings import LLM

logger = logging.getLogger(__name__)

_POOL_LOCK = threading.Lock()
_POOL_COOLDOWNS: dict[str, float] = {}
_POOL_CURRENT_KEY_IDX = 0


def strip_json_fences(text: str) -> str:
    """Remove markdown code fences around a JSON response."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


class GroqKeyPoolClient:
    """Groq Chat Completions client with process-wide key cooldown state."""

    def __init__(self) -> None:
        keys_str = LLM.groq_api_keys or LLM.groq_api_key
        if not keys_str:
            raise ValueError("Missing GROQ_API_KEY or GROQ_API_KEYS in settings.")

        self.keys = [key.strip() for key in keys_str.split(",") if key.strip()]
        self.model = LLM.model
        self.fallback_models = [
            model.strip()
            for model in LLM.fallback_models.split(",")
            if model.strip()
        ]
        self.max_tokens = max(LLM.max_tokens, 2500)
        self.temperature = LLM.temperature
        self.cooldown_seconds = LLM.cooldown_seconds

        with _POOL_LOCK:
            for key in self.keys:
                _POOL_COOLDOWNS.setdefault(key, 0.0)

    def _next_valid_key(self) -> str:
        """Return the next key that is not cooling down."""
        global _POOL_CURRENT_KEY_IDX

        with _POOL_LOCK:
            now = time.time()
            for _ in range(len(self.keys)):
                key = self.keys[_POOL_CURRENT_KEY_IDX % len(self.keys)]
                _POOL_CURRENT_KEY_IDX = (_POOL_CURRENT_KEY_IDX + 1) % len(self.keys)
                if now >= _POOL_COOLDOWNS.get(key, 0.0):
                    return key

            earliest_unlock = min(_POOL_COOLDOWNS[key] for key in self.keys)

        wait_time = earliest_unlock - time.time()
        if wait_time > 0:
            logger.warning("All keys in cooldown. Waiting %.1fs...", wait_time)
            time.sleep(wait_time)
        return self._next_valid_key()

    def _cooldown_key(self, key: str) -> None:
        with _POOL_LOCK:
            _POOL_COOLDOWNS[key] = time.time() + self.cooldown_seconds

    def _call_groq(self, key: str, model: str, prompt: str) -> str:
        client = Groq(api_key=key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": "Please output the analysis in JSON format based on the context.",
                },
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    def chat_json(self, prompt: str) -> dict[str, Any]:
        """Call Groq and parse a JSON object response."""
        models_to_try = [self.model] + self.fallback_models

        for model in models_to_try:
            for _ in range(len(self.keys)):
                key = self._next_valid_key()
                try:
                    raw_response = self._call_groq(key, model, prompt)
                    return json.loads(strip_json_fences(raw_response))
                except RateLimitError:
                    logger.warning(
                        "[RateLimit] Model %s. Key goes on %ss cooldown.",
                        model,
                        self.cooldown_seconds,
                    )
                    self._cooldown_key(key)
                    continue
                except json.JSONDecodeError as exc:
                    logger.error("[JSON Error] Failed to parse output from %s: %s", model, exc)
                    break
                except Exception as exc:
                    logger.error("[API Error] Calling Groq with model %s failed: %s", model, exc)
                    continue

        raise RuntimeError("All keys and fallback models failed.")
