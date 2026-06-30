"""Sarvam AI voice integration — text-to-speech and speech-to-text.

Both are plain REST calls (not the WebSocket streaming STT API): for a single
"ask one doubt" interaction, push-to-talk record-then-transcribe is far
simpler and just as good as true real-time streaming, with much less to break.

API reference: https://docs.sarvam.ai/api-reference-docs
"""
from __future__ import annotations

import httpx

from . import config

SARVAM_BASE = "https://api.sarvam.ai"
_TIMEOUT = httpx.Timeout(30.0, read=60.0)


class VoiceError(Exception):
    """Raised when a Sarvam TTS/STT call fails."""


def text_to_speech(text: str) -> str:
    """Returns base64-encoded WAV audio for the given text."""
    config.require_sarvam_key()
    if not text.strip():
        raise VoiceError("No text to speak.")

    # Sarvam caps input length per call; truncate defensively (callers already
    # keep teach/answer text short, this just guards against edge cases).
    payload_text = text.strip()[:2400]

    try:
        resp = httpx.post(
            f"{SARVAM_BASE}/text-to-speech",
            headers={
                "api-subscription-key": config.SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "text": payload_text,
                "target_language_code": config.SARVAM_TTS_LANGUAGE,
                "model": config.SARVAM_TTS_MODEL,
                "speaker": config.SARVAM_TTS_SPEAKER,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise VoiceError(f"Sarvam TTS failed: {exc.response.status_code} {exc.response.text}") from exc
    except Exception as exc:  # noqa: BLE001
        raise VoiceError(f"Sarvam TTS request failed: {exc}") from exc

    data = resp.json()
    audios = data.get("audios") or []
    if not audios:
        raise VoiceError("Sarvam TTS returned no audio.")
    return audios[0]


def speech_to_text(audio_bytes: bytes, filename: str, content_type: str) -> str:
    """Transcribes a recorded audio clip (webm/wav/etc.) to text."""
    config.require_sarvam_key()
    if not audio_bytes:
        raise VoiceError("No audio received.")

    try:
        resp = httpx.post(
            f"{SARVAM_BASE}/speech-to-text",
            headers={"api-subscription-key": config.SARVAM_API_KEY},
            data={
                "model": config.SARVAM_STT_MODEL,
                "language_code": config.SARVAM_STT_LANGUAGE,
            },
            files={"file": (filename, audio_bytes, content_type or "audio/webm")},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise VoiceError(f"Sarvam STT failed: {exc.response.status_code} {exc.response.text}") from exc
    except Exception as exc:  # noqa: BLE001
        raise VoiceError(f"Sarvam STT request failed: {exc}") from exc

    transcript = (resp.json().get("transcript") or "").strip()
    if not transcript:
        raise VoiceError("Could not make out any speech in that recording.")
    return transcript
