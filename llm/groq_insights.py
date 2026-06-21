from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from configs.settings import LLM, validate_required_settings


GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama3-8b-8192"


def build_airbnb_insight_prompt(summary_markdown: str) -> str:
    return f"""
You are an analytics assistant for an Airbnb Bangkok data warehouse project.

Use only the data summary below. Do not invent numbers that are not present.
Write the answer in Vietnamese.

Task:
Based on this month's Airbnb performance summary, provide 3 important insights.
For each insight, include:
1. A short title
2. Evidence from the data
3. Why it matters
4. A recommended action

Data summary:
{summary_markdown}
""".strip()


def generate_airbnb_insights(summary_markdown: str) -> str:
    missing = validate_required_settings("llm")
    if missing:
        raise ValueError(
            "Missing required LLM environment variables: " + ", ".join(missing)
        )

    model = LLM.model.strip() or DEFAULT_GROQ_MODEL
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You explain analytics results clearly, cautiously, and only "
                    "from the provided data."
                ),
            },
            {
                "role": "user",
                "content": build_airbnb_insight_prompt(summary_markdown),
            },
        ],
        "temperature": 0.2,
        "max_tokens": 900,
    }

    request = Request(
        GROQ_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {LLM.groq_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "airbnb-analytics-platform/0.1",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq API returned HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot connect to Groq API: {exc.reason}") from exc

    data = json.loads(response_body)
    return data["choices"][0]["message"]["content"].strip()
