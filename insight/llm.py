"""Pembungkus async untuk llm.py di root repo (yang SINKRON). llm.py root tidak diubah.

Kunci API dibaca oleh llm.py root dari environment/.env; modul ini tidak pernah mencatatnya ke log.
"""
from __future__ import annotations

import asyncio
import importlib
import os

LLM_TIMEOUT_SECONDS = 60.0
MAX_TOKENS = 1500


class LLMUnavailable(Exception):
    pass


def _chat_sync(system: str, user: str, max_tokens: int) -> str:
    root_llm = importlib.import_module("llm")   # llm.py di root repo (memanggil load_dotenv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LLMUnavailable("ANTHROPIC_API_KEY tidak tersedia")
    return root_llm.chat([{"role": "user", "content": user}], system=system, max_tokens=max_tokens)


def available() -> bool:
    """True bila kunci API tersedia (llm.py root memuat .env saat diimpor). Tidak memanggil jaringan."""
    try:
        importlib.import_module("llm")
    except Exception:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


async def complete(system: str, user: str, *, max_tokens: int = MAX_TOKENS,
                   timeout: float = LLM_TIMEOUT_SECONDS) -> str:
    """Panggil LLM tanpa memblokir event loop. Lempar exception bila gagal/timeout."""
    return await asyncio.wait_for(asyncio.to_thread(_chat_sync, system, user, max_tokens), timeout)
