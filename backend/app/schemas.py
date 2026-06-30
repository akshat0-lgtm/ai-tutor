"""Pydantic request/response models for the API."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel


class PreviewRequest(BaseModel):
    youtube_url: str


class PreviewResponse(BaseModel):
    video_id: str
    title: str
    thumbnail_url: str
    duration_seconds: float
    # True/False when known; None means we couldn't determine it (e.g. a
    # transient rate-limit on the captions check) — not the same as "no captions".
    captions_available: Optional[bool] = None


class ProcessRequest(BaseModel):
    youtube_url: str
    learning_goal: str = ""
    # Default (False): try captions first, auto-fallback to Whisper on failure.
    # True: skip straight to Whisper (manual override for testing/comparison).
    force_whisper: bool = False


class Topic(BaseModel):
    topic_name: str
    start_ts: float
    end_ts: float
    one_line_description: str


class ProcessResponse(BaseModel):
    session_id: str
    video_id: str
    transcript_source: str  # which path actually succeeded: "captions" | "whisper"
    num_chunks: int
    topics: List[Topic]


class Citation(BaseModel):
    chunk_id: int
    start_ts: float
    end_ts: float
    score: float


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    in_context: bool
    answer: str
    citations: List[Citation] = []
    top_score: float = 0.0


# Five teaching difficulty levels, lazy-loaded one at a time per topic.
LEVEL_NAMES = {
    1: "Like I'm 5",
    2: "Beginner",
    3: "Intermediate",
    4: "Advanced",
    5: "Expert",
}


class TeachRequest(BaseModel):
    session_id: str
    topic_index: int
    level: int = 1  # 1-5


class TeachResponse(BaseModel):
    topic_index: int
    topic_name: str
    level: int
    level_name: str
    explanation: str
    citations: List[Citation] = []
    is_last_topic: bool = False


class QuizQuestion(BaseModel):
    difficulty: Literal["easy", "medium", "hard"]
    format: Literal["mcq", "subjective"]
    question: str
    # Populated only when format == "mcq" (4 options, graded instantly client-side).
    options: List[str] = []
    correct_index: Optional[int] = None
    explanation: str = ""


class QuizRequest(BaseModel):
    session_id: str
    topic_index: int


class QuizResponse(BaseModel):
    topic_index: int
    topic_name: str
    questions: List[QuizQuestion]
    is_last: bool = False


class GradeRequest(BaseModel):
    session_id: str
    topic_index: int
    question: str
    user_answer: str


class GradeResponse(BaseModel):
    verdict: Literal["correct", "partially_correct", "incorrect"]
    feedback: str
    model_answer: str


# ---------------------------------------------------------------------------
# Voice (conversation mode in Teach mode) — Sarvam TTS/STT
# ---------------------------------------------------------------------------
class TTSRequest(BaseModel):
    text: str


class TTSResponse(BaseModel):
    audio_base64: str
    mime_type: str = "audio/wav"


class STTResponse(BaseModel):
    transcript: str
