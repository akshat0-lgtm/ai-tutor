"""FastAPI application — the API surface for the AI tutor.

Endpoints:
  GET  /                 -> liveness
  GET  /api/health       -> readiness (reports whether GROQ_API_KEY is set)
  POST /api/preview      -> lightweight video metadata for the URL preview card
  POST /api/process      -> transcript -> chunk -> embed -> topics; returns session
  POST /api/chat         -> grounded RAG answer with in/out-of-context distinction
  POST /api/teach        -> teach one topic at one of 5 difficulty levels
  POST /api/quiz         -> mostly-MCQ + subjective questions for one topic
  POST /api/quiz/grade   -> grade a subjective answer against the video context
  POST /api/tts          -> text -> speech (Sarvam), used by Teach mode's conversation mode
  POST /api/stt          -> recorded doubt audio -> transcript (Sarvam)
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import config, llm, session as session_store, voice
from .chunking import chunk_segments
from .schemas import (
    LEVEL_NAMES,
    ChatRequest,
    ChatResponse,
    Citation,
    GradeRequest,
    GradeResponse,
    PreviewRequest,
    PreviewResponse,
    ProcessRequest,
    ProcessResponse,
    QuizRequest,
    QuizResponse,
    STTResponse,
    TeachRequest,
    TeachResponse,
    TTSRequest,
    TTSResponse,
)
from .transcript import TranscriptError, fetch_video_metadata, get_transcript
from .vectorstore import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_tutor")

# The single user-facing message for any transcription/pipeline failure.
VIDEO_ERROR = "Error with the video, please try another video."

app = FastAPI(title="AI Office Hours / Tutor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",  # allow Vercel preview/prod URLs
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "ai-tutor-backend"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "groq_key_configured": bool(config.GROQ_API_KEY),
        "sarvam_key_configured": bool(config.SARVAM_API_KEY),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_session_or_404(session_id: str):
    sess = session_store.get_session(session_id)
    if sess is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found or expired. Please process a video again.",
        )
    return sess


def _retrieve(sess, query: str, k: int = 5) -> Tuple[List, float]:
    results = sess.store.search(query, k=k)
    top_score = results[0][1] if results else 0.0
    return results, top_score


def _citations(results) -> List[Citation]:
    return [
        Citation(
            chunk_id=c["chunk_id"],
            start_ts=c["start_ts"],
            end_ts=c["end_ts"],
            score=round(score, 4),
        )
        for c, score in results
    ]


# ---------------------------------------------------------------------------
# Preview: lightweight metadata shown as soon as a valid URL is pasted
# ---------------------------------------------------------------------------
@app.post("/api/preview", response_model=PreviewResponse)
def preview(req: PreviewRequest):
    try:
        meta = fetch_video_metadata(req.youtube_url)
    except TranscriptError as exc:
        logger.warning("Preview failure for %s: %s", req.youtube_url, exc)
        raise HTTPException(status_code=422, detail="Could not load that video.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected preview failure: %s", exc)
        raise HTTPException(status_code=500, detail="Could not load that video.")
    return PreviewResponse(**meta)


# ---------------------------------------------------------------------------
# Pipeline: process a video
# ---------------------------------------------------------------------------
@app.post("/api/process", response_model=ProcessResponse)
def process_video(req: ProcessRequest):
    if not config.GROQ_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Server is missing GROQ_API_KEY. Set it in backend/.env.",
        )
    try:
        # Default: captions first, automatic fallback to Whisper on failure.
        video_id, segments, source_used = get_transcript(
            req.youtube_url, force_whisper=req.force_whisper
        )
        chunks = chunk_segments(segments)
        if not chunks:
            raise TranscriptError("No content after chunking.")
        store = VectorStore(chunks)
        topics = llm.extract_topics(chunks, req.learning_goal)
        if not topics:
            raise TranscriptError("Could not extract any topics from the transcript.")
    except TranscriptError as exc:
        logger.warning("Pipeline failure for %s: %s", req.youtube_url, exc)
        raise HTTPException(status_code=422, detail=VIDEO_ERROR)
    except Exception as exc:  # noqa: BLE001 — never leak a stack trace to the user
        logger.exception("Unexpected pipeline failure: %s", exc)
        raise HTTPException(status_code=500, detail=VIDEO_ERROR)

    sess = session_store.create_session(video_id, source_used, store, topics)
    return ProcessResponse(
        session_id=sess.session_id,
        video_id=video_id,
        transcript_source=source_used,
        num_chunks=len(chunks),
        topics=topics,
    )


# ---------------------------------------------------------------------------
# Chat (persistent box, used in both modes)
# ---------------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    sess = _get_session_or_404(req.session_id)
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Empty message.")

    try:
        # Resolve pronouns/references against recent turns before retrieving.
        search_query = llm.rewrite_query(sess.history, message)
        results, top_score = _retrieve(sess, search_query, k=5)

        below_threshold = top_score < config.SIMILARITY_THRESHOLD
        grounded = {"in_context": False, "answer": ""}
        if not below_threshold:
            grounded = llm.answer_from_context(message, results, sess.history)

        in_context = grounded["in_context"] and not below_threshold
        if in_context:
            answer = grounded["answer"]
            citations = _citations(results)
        else:
            # Out of context: answer from general knowledge, clearly labeled.
            answer = llm.general_knowledge_answer(message, sess.history)
            citations = []
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chat failure: %s", exc)
        raise HTTPException(status_code=500, detail="Something went wrong answering that. Please try again.")

    sess.add_turn(message, answer, in_context)
    return ChatResponse(
        in_context=in_context, answer=answer, citations=citations, top_score=round(top_score, 4)
    )


# ---------------------------------------------------------------------------
# Teach mode
# ---------------------------------------------------------------------------
@app.post("/api/teach", response_model=TeachResponse)
def teach(req: TeachRequest):
    sess = _get_session_or_404(req.session_id)
    if req.topic_index < 0 or req.topic_index >= len(sess.topics):
        raise HTTPException(status_code=400, detail="Invalid topic index.")
    if req.level < 1 or req.level > 5:
        raise HTTPException(status_code=400, detail="level must be 1-5.")
    topic = sess.topics[req.topic_index]
    level_name = LEVEL_NAMES[req.level]

    try:
        query = f"{topic['topic_name']} {topic.get('one_line_description', '')}"
        results, _ = _retrieve(sess, query, k=6)
        explanation = llm.teach_topic_at_level(topic, results, req.level, level_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Teach failure: %s", exc)
        raise HTTPException(status_code=500, detail="Could not generate the lesson. Please try again.")

    return TeachResponse(
        topic_index=req.topic_index,
        topic_name=topic["topic_name"],
        level=req.level,
        level_name=level_name,
        explanation=explanation,
        citations=_citations(results),
        is_last_topic=req.topic_index == len(sess.topics) - 1,
    )


# ---------------------------------------------------------------------------
# Quiz mode
# ---------------------------------------------------------------------------
@app.post("/api/quiz", response_model=QuizResponse)
def quiz(req: QuizRequest):
    sess = _get_session_or_404(req.session_id)
    if req.topic_index < 0 or req.topic_index >= len(sess.topics):
        raise HTTPException(status_code=400, detail="Invalid topic index.")
    topic = sess.topics[req.topic_index]

    try:
        query = f"{topic['topic_name']} {topic.get('one_line_description', '')}"
        results, _ = _retrieve(sess, query, k=6)
        questions = llm.generate_quiz(topic, results)
        if not questions:
            raise RuntimeError("No questions generated.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Quiz failure: %s", exc)
        raise HTTPException(status_code=500, detail="Could not generate the quiz. Please try again.")

    return QuizResponse(
        topic_index=req.topic_index,
        topic_name=topic["topic_name"],
        questions=questions,
        is_last=req.topic_index == len(sess.topics) - 1,
    )


@app.post("/api/quiz/grade", response_model=GradeResponse)
def grade(req: GradeRequest):
    sess = _get_session_or_404(req.session_id)
    if req.topic_index < 0 or req.topic_index >= len(sess.topics):
        raise HTTPException(status_code=400, detail="Invalid topic index.")
    topic = sess.topics[req.topic_index]

    try:
        query = f"{topic['topic_name']} {req.question}"
        results, _ = _retrieve(sess, query, k=6)
        result = llm.grade_answer(req.question, req.user_answer, results)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Grade failure: %s", exc)
        raise HTTPException(status_code=500, detail="Could not grade that answer. Please try again.")

    return GradeResponse(**result)


# ---------------------------------------------------------------------------
# Voice — conversation mode in Teach mode (Sarvam TTS/STT)
# ---------------------------------------------------------------------------
@app.post("/api/tts", response_model=TTSResponse)
def text_to_speech(req: TTSRequest):
    if not config.SARVAM_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Voice isn't set up yet. Add SARVAM_API_KEY in backend/.env to enable it.",
        )
    try:
        audio_b64 = voice.text_to_speech(req.text)
    except voice.VoiceError as exc:
        logger.warning("TTS failure: %s", exc)
        raise HTTPException(status_code=502, detail="Could not generate speech for that. Please try again.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected TTS failure: %s", exc)
        raise HTTPException(status_code=500, detail="Could not generate speech for that. Please try again.")
    return TTSResponse(audio_base64=audio_b64, mime_type="audio/wav")


@app.post("/api/stt", response_model=STTResponse)
async def speech_to_text(file: UploadFile = File(...)):
    if not config.SARVAM_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Voice isn't set up yet. Add SARVAM_API_KEY in backend/.env to enable it.",
        )
    try:
        audio_bytes = await file.read()
        transcript = voice.speech_to_text(audio_bytes, file.filename or "doubt.webm", file.content_type or "audio/webm")
    except voice.VoiceError as exc:
        logger.warning("STT failure: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected STT failure: %s", exc)
        raise HTTPException(status_code=500, detail="Could not transcribe that. Please try again.")
    return STTResponse(transcript=transcript)
