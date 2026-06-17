from __future__ import annotations

import anyio
from langchain_groq import ChatGroq

from .config import Settings, get_settings


def groq_configured(settings: Settings | None = None) -> bool:
    active_settings = settings or get_settings()
    return bool(active_settings.groq_api_key)


def build_chat_groq(settings: Settings | None = None) -> ChatGroq | None:
    active_settings = settings or get_settings()
    if not active_settings.groq_api_key or not active_settings.enable_llm_review:
        return None
    return ChatGroq(
        model=active_settings.groq_model,
        temperature=active_settings.groq_temperature,
        api_key=active_settings.groq_api_key,
    )


async def check_groq_connectivity(settings: Settings | None = None) -> dict[str, object]:
    active_settings = settings or get_settings()
    if not active_settings.groq_api_key:
        return {
            "configured": False,
            "status": "not_configured",
            "model": active_settings.groq_model,
        }

    llm = build_chat_groq(active_settings)
    if llm is None:
        return {
            "configured": True,
            "status": "disabled",
            "model": active_settings.groq_model,
        }

    try:
        await anyio.to_thread.run_sync(lambda: llm.invoke("Return only the word ok."))
    except Exception as exc:  # pragma: no cover - depends on external Groq availability
        return {
            "configured": True,
            "status": "error",
            "model": active_settings.groq_model,
            "detail": str(exc),
        }

    return {
        "configured": True,
        "status": "ok",
        "model": active_settings.groq_model,
    }
