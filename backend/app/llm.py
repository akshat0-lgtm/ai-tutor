"""All Groq LLM interactions: topic extraction, query rewriting, RAG answers,
general-knowledge answers, teaching, quiz generation, and grading.

Every "must be grounded" call asks the model for JSON so we can branch on an
explicit `in_context` flag instead of parsing prose.
"""
from __future__ import annotations

import json
from typing import List, Optional, Tuple

from groq import Groq

from . import config


def _client() -> Groq:
    config.require_groq_key()
    return Groq(api_key=config.GROQ_API_KEY)


def _fmt_ts(seconds: float) -> str:
    seconds = int(seconds or 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def build_timestamped_transcript(chunks: List[dict], budget_chars: int = 14000) -> str:
    """Render chunks as '[mm:ss] text'. If over budget, evenly downsample chunks
    so we keep coverage across the whole video timeline."""
    selected = chunks
    if chunks:
        total = sum(len(c["chunk_text"]) for c in chunks)
        if total > budget_chars:
            keep = max(1, int(len(chunks) * budget_chars / total))
            step = max(1, len(chunks) // keep)
            selected = chunks[::step]
    return "\n".join(f"[{_fmt_ts(c['start_ts'])}] {c['chunk_text']}" for c in selected)


def _chat_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    resp = _client().chat.completions.create(
        model=config.GROQ_LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def _chat_text(system: str, user: str, max_tokens: int = 900) -> str:
    resp = _client().chat.completions.create(
        model=config.GROQ_LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# Topic extraction (one call per video)
# ---------------------------------------------------------------------------
def extract_topics(chunks: List[dict], learning_goal: str) -> List[dict]:
    transcript = build_timestamped_transcript(chunks)
    goal = learning_goal.strip() or "(no specific goal stated — cover the video's main ideas)"
    system = (
        "You are a curriculum designer. Given a timestamped video transcript and "
        "what the learner wants to learn, produce an ordered list of the key topics "
        "actually taught in the video. Bias the selection and ordering toward the "
        "learner's stated goal, but only include topics that are genuinely present "
        "in the transcript. Return 3 to 8 topics."
    )
    user = (
        f"LEARNER'S GOAL:\n{goal}\n\n"
        f"TRANSCRIPT (each line prefixed with its [mm:ss] start time):\n{transcript}\n\n"
        "Return JSON of the exact form:\n"
        '{"topics": [{"topic_name": str, "start_ts": number (seconds), '
        '"end_ts": number (seconds), "one_line_description": str}]}\n'
        "start_ts/end_ts are seconds (e.g. 95 for 01:35) bounding where the topic "
        "is discussed. Order topics by their appearance / logical teaching order."
    )
    data = _chat_json(system, user, max_tokens=1800)
    topics = data.get("topics") or []
    cleaned: List[dict] = []
    for t in topics:
        if not isinstance(t, dict) or not t.get("topic_name"):
            continue
        cleaned.append(
            {
                "topic_name": str(t.get("topic_name", "")).strip(),
                "start_ts": float(t.get("start_ts", 0) or 0),
                "end_ts": float(t.get("end_ts", 0) or 0),
                "one_line_description": str(t.get("one_line_description", "")).strip(),
            }
        )
    return cleaned


# ---------------------------------------------------------------------------
# Follow-up query rewriting (resolve pronouns before retrieval)
# ---------------------------------------------------------------------------
def rewrite_query(history: List[dict], message: str) -> str:
    if not history:
        return message
    recent = history[-2:]
    convo = "\n".join(f"Q: {h['question']}\nA: {h['answer'][:300]}" for h in recent)
    system = (
        "Rewrite the user's latest message into a standalone search query by "
        "resolving pronouns and references using the recent conversation. Output "
        "ONLY the rewritten query text, nothing else. If it is already standalone, "
        "return it unchanged."
    )
    user = f"RECENT CONVERSATION:\n{convo}\n\nLATEST MESSAGE:\n{message}\n\nStandalone query:"
    try:
        rewritten = _chat_text(system, user, max_tokens=80)
        return rewritten or message
    except Exception:  # noqa: BLE001 — never let rewriting break the flow
        return message


# ---------------------------------------------------------------------------
# RAG answer (grounded in retrieved chunks)
# ---------------------------------------------------------------------------
def _format_context(retrieved: List[Tuple[dict, float]]) -> str:
    blocks = []
    for chunk, score in retrieved:
        blocks.append(
            f"[chunk {chunk['chunk_id']} | {_fmt_ts(chunk['start_ts'])}-"
            f"{_fmt_ts(chunk['end_ts'])}]\n{chunk['chunk_text']}"
        )
    return "\n\n".join(blocks)


def _format_history(history: List[dict], n: int = 5) -> str:
    if not history:
        return "(no prior conversation)"
    recent = history[-n:]
    return "\n".join(f"User: {h['question']}\nTutor: {h['answer'][:400]}" for h in recent)


def answer_from_context(
    question: str, retrieved: List[Tuple[dict, float]], history: List[dict]
) -> dict:
    context = _format_context(retrieved)
    system = (
        "You are a tutor answering ONLY from the provided video transcript context. "
        "Do not use outside knowledge. Decide whether the context actually answers "
        "the question. Respond in JSON: "
        '{"in_context": true|false, "answer": str}. '
        "If the context does not contain the answer, set in_context to false and let "
        "answer be a brief note that the video does not cover this. Keep answers "
        "concise and clear, suitable for a learner."
    )
    user = (
        f"CONVERSATION SO FAR:\n{_format_history(history)}\n\n"
        f"VIDEO CONTEXT CHUNKS:\n{context}\n\n"
        f"QUESTION:\n{question}"
    )
    data = _chat_json(system, user, max_tokens=900)
    return {
        "in_context": bool(data.get("in_context", False)),
        "answer": str(data.get("answer", "")).strip(),
    }


def general_knowledge_answer(question: str, history: List[dict]) -> str:
    system = (
        "You are a helpful tutor. The user's question was NOT covered by the video. "
        "Answer from your general knowledge, clearly and concisely. Do not claim it "
        "came from the video."
    )
    user = f"CONVERSATION SO FAR:\n{_format_history(history)}\n\nQUESTION:\n{question}"
    return _chat_text(system, user, max_tokens=700)


# ---------------------------------------------------------------------------
# Teach mode — five difficulty levels per topic, each with real-world examples
# ---------------------------------------------------------------------------
LEVEL_GUIDANCE = {
    1: (
        "Like I'm 5. No jargon at all. Use a simple, playful everyday analogy "
        "(toys, animals, food, games). Keep sentences short."
    ),
    2: (
        "Beginner. Plain language; introduce any necessary term with a one-line "
        "definition the moment you use it. Use a relatable everyday example."
    ),
    3: (
        "Intermediate. Assume the reader already knows the basics. Use correct "
        "terminology and explain the mechanism/how it actually works. Use a "
        "practical, real-world example (a workplace or technology scenario)."
    ),
    4: (
        "Advanced. Assume a strong foundation. Discuss nuance, edge cases, and "
        "tradeoffs. Use a real-world example from industry or research that "
        "shows the concept applied in a non-trivial way."
    ),
    5: (
        "Expert. Precise and technical. Discuss subtleties, limitations, and "
        "connections to adjacent concepts. Use a sophisticated real-world "
        "example or case study that demonstrates mastery-level application."
    ),
}


def teach_topic_at_level(
    topic: dict, retrieved: List[Tuple[dict, float]], level: int, level_name: str
) -> str:
    context = _format_context(retrieved)
    guidance = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE[1])
    system = (
        "You are a patient tutor teaching ONE topic using ONLY the provided video "
        "transcript context. Do not invent facts beyond the context, but you may "
        "invent illustrative real-world examples/analogies that are consistent "
        "with it. Write a tight, well-structured explanation (a couple of short "
        "paragraphs) at the requested difficulty level, and ALWAYS include at "
        "least one concrete real-world example appropriate to that level. End "
        "with a one-sentence recap. Hard limit: 300-350 words total, no exceptions."
    )
    user = (
        f"TOPIC: {topic['topic_name']}\n"
        f"DESCRIPTION: {topic.get('one_line_description', '')}\n\n"
        f"DIFFICULTY LEVEL {level} of 5 — {level_name}\n"
        f"LEVEL GUIDANCE: {guidance}\n\n"
        f"VIDEO CONTEXT CHUNKS:\n{context}\n\n"
        "Teach this topic now, at exactly this difficulty level, with a real-world example. "
        "Stay within 300-350 words."
    )
    return _chat_text(system, user, max_tokens=550)


# ---------------------------------------------------------------------------
# Quiz mode — mostly multiple-choice, ~30% subjective (the hard tier)
# ---------------------------------------------------------------------------
# Easy + medium are MCQ (instant client-side grading); hard is subjective
# short-answer (LLM-graded). That's a 2:1 ratio (~67/30 split) per topic,
# matching the "mostly objective, some subjective" rule of thumb while
# keeping the format-per-difficulty mapping simple and predictable.
_QUESTION_FORMAT = {"easy": "mcq", "medium": "mcq", "hard": "subjective"}


def generate_quiz(topic: dict, retrieved: List[Tuple[dict, float]]) -> List[dict]:
    context = _format_context(retrieved)
    system = (
        "You are a quiz writer. Using ONLY the provided video transcript context, "
        "write exactly three questions about the topic, one per difficulty in "
        "this order: easy, medium, hard.\n"
        "- The EASY and MEDIUM questions must be multiple-choice with exactly 4 "
        "options, exactly one correct, plus a one-sentence explanation of why "
        "that option is correct (grounded in the context).\n"
        "- The HARD question must be a short-answer (subjective) question, not "
        "multiple-choice.\n"
        "All questions must be answerable from the context. Return JSON:\n"
        '{"questions": ['
        '{"difficulty": "easy", "format": "mcq", "question": str, '
        '"options": [str, str, str, str], "correct_index": int, "explanation": str}, '
        '{"difficulty": "medium", "format": "mcq", "question": str, '
        '"options": [str, str, str, str], "correct_index": int, "explanation": str}, '
        '{"difficulty": "hard", "format": "subjective", "question": str}'
        "]}"
    )
    user = (
        f"TOPIC: {topic['topic_name']}\n"
        f"DESCRIPTION: {topic.get('one_line_description', '')}\n\n"
        f"VIDEO CONTEXT CHUNKS:\n{context}\n\nWrite the three questions."
    )
    data = _chat_json(system, user, max_tokens=900)
    questions = data.get("questions") or []
    order = {"easy": 0, "medium": 1, "hard": 2}
    cleaned: List[dict] = []
    for q in questions:
        if not isinstance(q, dict) or not q.get("question"):
            continue
        difficulty = q.get("difficulty", "easy")
        if difficulty not in _QUESTION_FORMAT:
            difficulty = "easy"
        fmt = q.get("format") or _QUESTION_FORMAT[difficulty]
        item = {
            "difficulty": difficulty,
            "format": fmt,
            "question": str(q.get("question", "")).strip(),
            "options": [],
            "correct_index": None,
            "explanation": "",
        }
        if fmt == "mcq":
            options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
            correct_index = q.get("correct_index")
            if len(options) == 4 and isinstance(correct_index, int) and 0 <= correct_index < 4:
                item["options"] = options
                item["correct_index"] = correct_index
                item["explanation"] = str(q.get("explanation", "")).strip()
            else:
                # Malformed MCQ payload — fall back to subjective so the quiz
                # doesn't silently lose a question.
                item["format"] = "subjective"
        cleaned.append(item)
    cleaned.sort(key=lambda q: order.get(q["difficulty"], 0))
    return cleaned


def grade_answer(
    question: str, user_answer: str, retrieved: List[Tuple[dict, float]]
) -> dict:
    context = _format_context(retrieved)
    system = (
        "You are grading a learner's short answer against the video transcript "
        "context ONLY (not your own outside knowledge). Be encouraging but honest. "
        "Return JSON: "
        '{"verdict": "correct|partially_correct|incorrect", "feedback": str, '
        '"model_answer": str}. model_answer is the ideal answer drawn from the context.'
    )
    user = (
        f"VIDEO CONTEXT CHUNKS:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        f"LEARNER'S ANSWER: {user_answer}\n\nGrade it."
    )
    data = _chat_json(system, user, max_tokens=600)
    verdict = data.get("verdict", "partially_correct")
    if verdict not in ("correct", "partially_correct", "incorrect"):
        verdict = "partially_correct"
    return {
        "verdict": verdict,
        "feedback": str(data.get("feedback", "")).strip(),
        "model_answer": str(data.get("model_answer", "")).strip(),
    }
