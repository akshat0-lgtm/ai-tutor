"""Transcript acquisition.

Two paths, both producing the same shape: a list of
{"text": str, "start": float, "duration": float} segments.

1. captions  -> youtube-transcript-api (existing YouTube captions)
2. whisper   -> yt-dlp pulls bestaudio, Groq Whisper transcribes it

Default behavior is automatic: try captions first, and only fall back to
Whisper if captions fail. If both fail, TranscriptError propagates, which the
API layer turns into the user-facing
"Error with the video, please try another video." message.
"""
from __future__ import annotations

import os
import re
import tempfile
from typing import List, Optional

from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

from . import config


class TranscriptError(Exception):
    """Raised when we cannot obtain a usable transcript by any means."""


_YOUTUBE_ID_PATTERNS = [
    r"(?:v=|/shorts/|/embed/|youtu\.be/)([0-9A-Za-z_-]{11})",
    r"^([0-9A-Za-z_-]{11})$",  # bare id
]


def extract_video_id(url: str) -> str:
    url = (url or "").strip()
    for pattern in _YOUTUBE_ID_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    raise TranscriptError("Could not parse a YouTube video id from the URL.")


# ---------------------------------------------------------------------------
# Path 1: existing captions
# ---------------------------------------------------------------------------
def fetch_captions(video_id: str) -> List[dict]:
    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        raw = fetched.to_raw_data()
    except (NoTranscriptFound, TranscriptsDisabled):
        # No English; try any available transcript as a last resort.
        try:
            listing = api.list(video_id)
            transcript = next(iter(listing))
            raw = transcript.fetch().to_raw_data()
        except Exception as exc:  # noqa: BLE001
            raise TranscriptError(f"No captions available: {exc}") from exc
    except VideoUnavailable as exc:
        raise TranscriptError(f"Video unavailable: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise TranscriptError(f"Caption fetch failed: {exc}") from exc

    segments = [
        {
            "text": (item.get("text") or "").strip(),
            "start": float(item.get("start", 0.0)),
            "duration": float(item.get("duration", 0.0)),
        }
        for item in raw
        if (item.get("text") or "").strip()
    ]
    if not segments:
        raise TranscriptError("Captions were empty.")
    return segments


# ---------------------------------------------------------------------------
# Path 2: yt-dlp audio -> Groq Whisper
# ---------------------------------------------------------------------------
# YouTube increasingly serves a "Sign in to confirm you're not a bot" wall to
# yt-dlp's default web client. Forcing the android client sidesteps it without
# needing cookies/auth — a well-known yt-dlp workaround.
_YDL_BOT_CHECK_BYPASS = {"extractor_args": {"youtube": {"player_client": ["android"]}}}


def _download_audio(video_id: str, out_dir: str) -> str:
    """Download audio with yt-dlp. No ffmpeg post-processing so this works on
    hosts without ffmpeg (e.g. Render's native Python runtime).

    Prefer a true audio-only stream (smallest possible file). The android
    client (needed to bypass YouTube's bot-check) sometimes exposes only a
    single combined video+audio format per video — in that case pick the
    LOWEST quality one, since we only need the audio for transcription and
    that minimizes the chance of tripping Groq's free-tier upload size cap.
    """
    import yt_dlp

    out_tmpl = os.path.join(out_dir, "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/worst[ext=mp4]/worst",
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        **_YDL_BOT_CHECK_BYPASS,
    }
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    for fname in os.listdir(out_dir):
        if fname.startswith(video_id):
            return os.path.join(out_dir, fname)
    raise TranscriptError("Audio download produced no file.")


def transcribe_with_whisper(video_id: str) -> List[dict]:
    config.require_groq_key()
    client = Groq(api_key=config.GROQ_API_KEY)

    with tempfile.TemporaryDirectory(prefix="ai_tutor_audio_") as tmp:
        try:
            audio_path = _download_audio(video_id, tmp)
        except Exception as exc:  # noqa: BLE001
            raise TranscriptError(f"Audio download failed: {exc}") from exc

        # Groq Whisper has an upload size limit (~25-40MB). Guard early.
        size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if size_mb > 24:
            raise TranscriptError(
                f"Audio too large for free Whisper tier ({size_mb:.0f}MB). "
                "Try a shorter video or use existing captions."
            )

        try:
            with open(audio_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    file=(os.path.basename(audio_path), f.read()),
                    model=config.GROQ_WHISPER_MODEL,
                    response_format="verbose_json",  # gives segment timestamps
                    timestamp_granularities=["segment"],
                )
        except Exception as exc:  # noqa: BLE001
            raise TranscriptError(f"Whisper transcription failed: {exc}") from exc

    segments_raw = getattr(result, "segments", None) or []
    segments: List[dict] = []
    for seg in segments_raw:
        # SDK returns dicts for segments.
        text = (seg.get("text") if isinstance(seg, dict) else getattr(seg, "text", "")) or ""
        start = seg.get("start") if isinstance(seg, dict) else getattr(seg, "start", 0.0)
        end = seg.get("end") if isinstance(seg, dict) else getattr(seg, "end", 0.0)
        text = text.strip()
        if not text:
            continue
        start = float(start or 0.0)
        end = float(end or start)
        segments.append({"text": text, "start": start, "duration": max(0.0, end - start)})

    if not segments:
        # Fall back to the flat text if no segment timestamps came back.
        full = (getattr(result, "text", "") or "").strip()
        if not full:
            raise TranscriptError("Whisper returned no text.")
        segments = [{"text": full, "start": 0.0, "duration": 0.0}]
    return segments


def get_transcript(url: str, force_whisper: bool = False) -> tuple[str, List[dict], str]:
    """Return (video_id, segments, source_used).

    Default: try captions first; on any failure, automatically fall back to
    Whisper. If force_whisper is set, skip straight to Whisper (useful for
    testing/comparison). Raises TranscriptError only if every attempted path
    fails.
    """
    video_id = extract_video_id(url)

    if force_whisper:
        return video_id, transcribe_with_whisper(video_id), "whisper"

    try:
        return video_id, fetch_captions(video_id), "captions"
    except TranscriptError as captions_exc:
        try:
            return video_id, transcribe_with_whisper(video_id), "whisper"
        except TranscriptError as whisper_exc:
            raise TranscriptError(
                f"Captions failed ({captions_exc}); Whisper fallback also "
                f"failed ({whisper_exc})"
            ) from whisper_exc


# ---------------------------------------------------------------------------
# Video preview metadata (title/thumbnail/duration/caption availability)
# ---------------------------------------------------------------------------
def captions_available(video_id: str) -> Optional[bool]:
    """True/False when we can tell for sure; None when the check itself failed
    (e.g. transient IP rate-limiting) — callers should treat None as 'unknown',
    not as 'no captions'."""
    try:
        api = YouTubeTranscriptApi()
        next(iter(api.list(video_id)))
        return True
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable, StopIteration):
        return False
    except (IpBlocked, RequestBlocked):
        return None
    except Exception:  # noqa: BLE001
        return None


def fetch_video_metadata(url: str) -> dict:
    """Lightweight, no-download lookup for the URL preview card."""
    import yt_dlp

    video_id = extract_video_id(url)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        **_YDL_BOT_CHECK_BYPASS,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
    except Exception as exc:  # noqa: BLE001
        raise TranscriptError(f"Could not load video info: {exc}") from exc

    thumbnails = info.get("thumbnails") or []
    thumbnail_url = info.get("thumbnail") or (thumbnails[-1]["url"] if thumbnails else "")

    return {
        "video_id": video_id,
        "title": info.get("title") or "",
        "thumbnail_url": thumbnail_url,
        "duration_seconds": float(info.get("duration") or 0),
        "captions_available": captions_available(video_id),
    }
