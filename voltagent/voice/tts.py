"""Server-side TTS fallback.

The primary voice path is the browser's own Web Speech API
(`frontend/app.js`, `speechSynthesis`) — it's free, zero-latency-to-first-
audio, and needs no server round trip for playback. This module exists for
two secondary cases:
  1. Non-browser clients (e.g. testing the API directly, or a future native
     app) that need actual audio bytes back.
  2. Browsers/OS combinations with poor or missing Hindi
     `speechSynthesis` voices — gTTS's Hindi voice is more reliable than
     some platforms' built-in one.

Kept as a thin, swappable wrapper so a production deployment can drop in a
better TTS engine (e.g. a cloud TTS API) without touching callers.
"""
from __future__ import annotations

import io

from gtts import gTTS

_LANG_MAP = {"en": "en", "hi": "hi"}


def synthesize_speech(text: str, language: str) -> bytes:
    """Return MP3 bytes for `text` spoken in `language` ('en' or 'hi')."""
    lang_code = _LANG_MAP.get(language, "en")
    buffer = io.BytesIO()
    gTTS(text=text, lang=lang_code).write_to_fp(buffer)
    return buffer.getvalue()
