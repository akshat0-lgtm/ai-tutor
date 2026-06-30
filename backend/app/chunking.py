"""Timestamp-aware chunking.

Groups raw transcript segments into ~200-400 word chunks, preferring to break
at sentence/pause boundaries. Each chunk keeps its start/end timestamps so the
UI can cite where in the video an answer came from.
"""
from __future__ import annotations

from typing import List

TARGET_WORDS = 300
MAX_WORDS = 400
MIN_WORDS = 200

_SENTENCE_END = (".", "?", "!")


def _word_count(text: str) -> int:
    return len(text.split())


def chunk_segments(segments: List[dict]) -> List[dict]:
    """Return list of {chunk_id, chunk_text, start_ts, end_ts}."""
    chunks: List[dict] = []
    cur_texts: List[str] = []
    cur_words = 0
    cur_start: float | None = None
    cur_end = 0.0

    def flush():
        nonlocal cur_texts, cur_words, cur_start, cur_end
        if not cur_texts:
            return
        chunks.append(
            {
                "chunk_id": len(chunks),
                "chunk_text": " ".join(cur_texts).strip(),
                "start_ts": round(cur_start or 0.0, 2),
                "end_ts": round(cur_end, 2),
            }
        )
        cur_texts, cur_words, cur_start, cur_end = [], 0, None, 0.0

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue
        if cur_start is None:
            cur_start = float(seg["start"])
        cur_texts.append(text)
        cur_words += _word_count(text)
        cur_end = float(seg["start"]) + float(seg.get("duration", 0.0))

        ends_sentence = text.endswith(_SENTENCE_END)
        # Break on a sentence boundary once we're past the target, or hard-cap.
        if (cur_words >= TARGET_WORDS and ends_sentence) or cur_words >= MAX_WORDS:
            flush()

    flush()

    # Merge a too-small trailing chunk into the previous one for better context.
    if len(chunks) >= 2 and _word_count(chunks[-1]["chunk_text"]) < MIN_WORDS // 2:
        tail = chunks.pop()
        prev = chunks[-1]
        prev["chunk_text"] = f"{prev['chunk_text']} {tail['chunk_text']}".strip()
        prev["end_ts"] = tail["end_ts"]

    return chunks
