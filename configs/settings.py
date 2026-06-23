# -*- coding: utf-8 -*-
"""Đọc biến môi trường và gom cấu hình runtime của project."""

from dataclasses import dataclass
from os import getenv
from typing import Literal

from dotenv import load_dotenv

from configs.paths import ENV_FILE


load_dotenv(dotenv_path=ENV_FILE, override=False)


def _get_int(name: str, default: int) -> int:
    """Đọc biến integer từ môi trường, nếu sai định dạng thì dùng default."""
    value = getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppSettings:
    """Cấu hình chung của project."""

    project_name: str
    environment: str


@dataclass(frozen=True)
class MotherDuckSettings:
    """Cấu hình kết nối MotherDuck."""

    token: str
    database: str
    schema: str


@dataclass(frozen=True)
class LLMSettings:
    """Cấu hình dịch vụ LLM."""

    groq_api_key: str
    model: str
    groq_api_keys: str = ""
    fallback_models: str = ""
    max_tokens: int = 4096
    temperature: float = 0.1
    cooldown_seconds: int = 60


@dataclass(frozen=True)
class StreamlitSettings:
    """Cấu hình Streamlit dashboard."""

    server_port: int


@dataclass(frozen=True)
class ObjectStorageSettings:
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    region: str
    prefix: str


ServiceName = Literal["motherduck", "llm", "streamlit"]


APP = AppSettings(
    project_name=getenv("PROJECT_NAME", "airbnb-analytics-platform"),
    environment=getenv("ENVIRONMENT", "development"),
)

MOTHERDUCK = MotherDuckSettings(
    token=getenv("MOTHERDUCK_TOKEN", ""),
    database=getenv("MOTHERDUCK_DATABASE", "airbnb_analytics"),
    schema=getenv("MOTHERDUCK_SCHEMA", "bronze"),
)

LLM = LLMSettings(
    groq_api_key=getenv("GROQ_API_KEY", ""),
    model=getenv("LLM_MODEL", ""),
    groq_api_keys=getenv("GROQ_API_KEYS", ""),
    fallback_models=getenv("LLM_FALLBACK_MODELS", "llama-3.3-70b-versatile,mixtral-8x7b-32768,gemma2-9b-it"),
    max_tokens=_get_int("LLM_MAX_TOKENS", 4096),
    temperature=float(getenv("LLM_TEMPERATURE", "0.1")),
    cooldown_seconds=_get_int("LLM_COOLDOWN_SECONDS", 60),
)


STREAMLIT = StreamlitSettings(
    server_port=_get_int("STREAMLIT_SERVER_PORT", 8501),
)

OBJECT_STORAGE = ObjectStorageSettings(
    endpoint_url=getenv("OBJECT_STORAGE_ENDPOINT_URL", getenv("R2_ENDPOINT_URL", "")),
    access_key_id=getenv("OBJECT_STORAGE_ACCESS_KEY_ID", getenv("R2_ACCESS_KEY_ID", "")),
    secret_access_key=getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", getenv("R2_SECRET_ACCESS_KEY", "")),
    bucket_name=getenv("OBJECT_STORAGE_BUCKET_NAME", getenv("R2_BUCKET_NAME", "")),
    region=getenv("OBJECT_STORAGE_REGION", "auto"),
    prefix=getenv("OBJECT_STORAGE_PREFIX", "airbnb-models").strip("/"),
)

def validate_required_settings(service: ServiceName | None = None) -> list[str]:
    """Kiểm tra các biến bắt buộc trước khi kết nối service thật.

    Hàm này không được gọi ở import time để project vẫn chạy được khi chưa có secret.
    Trả về danh sách tên biến đang thiếu; danh sách rỗng nghĩa là hợp lệ.
    """
    required_by_service: dict[ServiceName, dict[str, str]] = {
        "motherduck": {
            "MOTHERDUCK_TOKEN": MOTHERDUCK.token,
            "MOTHERDUCK_DATABASE": MOTHERDUCK.database,
            "MOTHERDUCK_SCHEMA": MOTHERDUCK.schema,
        },
        "llm": {
            "GROQ_API_KEY": LLM.groq_api_key,
            "LLM_MODEL": LLM.model,
        },
        "streamlit": {
            "STREAMLIT_SERVER_PORT": str(STREAMLIT.server_port),
        },
    }

    services: tuple[ServiceName, ...]
    if service is None:
        services = tuple(required_by_service)
    else:
        services = (service,)

    missing: list[str] = []
    for service_name in services:
        missing.extend(
            name
            for name, value in required_by_service[service_name].items()
            if value.strip() == ""
        )
    return missing
