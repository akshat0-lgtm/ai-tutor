"""In-memory session store. One session = one video.

A session bundles the transcript, the vector store, the extracted topics, and
the running conversation history. Sessions live in a process-global dict; they
disappear on restart (acceptable for this MVP, per spec).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .vectorstore import VectorStore


@dataclass
class Session:
    session_id: str
    video_id: str
    transcript_source: str
    store: VectorStore
    topics: List[dict] = field(default_factory=list)
    # Each turn: {"question": str, "answer": str, "in_context": bool}
    history: List[dict] = field(default_factory=list)

    def add_turn(self, question: str, answer: str, in_context: bool) -> None:
        self.history.append(
            {"question": question, "answer": answer, "in_context": in_context}
        )


_SESSIONS: Dict[str, Session] = {}


def create_session(
    video_id: str, transcript_source: str, store: VectorStore, topics: List[dict]
) -> Session:
    sid = uuid.uuid4().hex[:12]
    session = Session(
        session_id=sid,
        video_id=video_id,
        transcript_source=transcript_source,
        store=store,
        topics=topics,
    )
    _SESSIONS[sid] = session
    return session


def get_session(session_id: str) -> Optional[Session]:
    return _SESSIONS.get(session_id)
