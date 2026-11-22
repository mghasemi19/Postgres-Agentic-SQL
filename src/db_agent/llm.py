from __future__ import annotations

from langchain_openai import ChatOpenAI

from .config import Settings


def build_llm(settings: Settings) -> ChatOpenAI:
    kwargs: dict[str, object] = {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
        "temperature": settings.llm_temperature,
        "timeout": 60,
        "max_retries": 2,
    }
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return ChatOpenAI(**kwargs)
