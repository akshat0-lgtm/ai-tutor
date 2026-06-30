"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import ChatBox from "./ChatBox";

const LETTERS = ["A", "B", "C", "D"];

function McqQuestion({ q }) {
  const [picked, setPicked] = useState(null);

  function pick(i) {
    if (picked !== null) return;
    setPicked(i);
  }

  return (
    <div className="q-block">
      <span className={`diff ${q.difficulty}`}>{q.difficulty} · multiple choice</span>
      <p className="q-text">{q.question}</p>
      <div className="mcq-options">
        {q.options.map((opt, i) => {
          let cls = "mcq-option";
          if (picked !== null) {
            if (i === q.correct_index) cls += " correct";
            else if (i === picked) cls += " incorrect";
            else cls += " dimmed";
          }
          return (
            <button key={i} className={cls} onClick={() => pick(i)} disabled={picked !== null}>
              <span className="letter">{LETTERS[i]}</span>
              <span>{opt}</span>
            </button>
          );
        })}
      </div>
      {picked !== null && (
        <>
          <div className={`verdict ${picked === q.correct_index ? "correct" : "incorrect"}`}>
            {picked === q.correct_index ? "Correct" : "Not quite"}
          </div>
          {q.explanation && <p className="mcq-explain">{q.explanation}</p>}
        </>
      )}
    </div>
  );
}

function SubjectiveQuestion({ sessionId, topicIndex, q }) {
  const [answer, setAnswer] = useState("");
  const [grading, setGrading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function check() {
    if (!answer.trim() || grading) return;
    setGrading(true);
    setError("");
    try {
      const res = await api.grade(sessionId, topicIndex, q.question, answer.trim());
      setResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setGrading(false);
    }
  }

  return (
    <div className="q-block">
      <span className={`diff ${q.difficulty}`}>{q.difficulty} · short answer</span>
      <p className="q-text">{q.question}</p>
      <div className="chat-input-row">
        <input
          type="text"
          value={answer}
          placeholder="Your answer…"
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && check()}
          disabled={grading || !!result}
        />
        <button className="btn-primary" onClick={check} disabled={grading || !!result}>
          {grading ? "…" : "Check"}
        </button>
      </div>
      {error && <div className="error-box" style={{ marginTop: 10 }}>{error}</div>}
      {result && (
        <div>
          <div className={`verdict ${result.verdict}`}>
            {result.verdict === "correct" && "Correct"}
            {result.verdict === "partially_correct" && "Partially correct"}
            {result.verdict === "incorrect" && "Not quite"}
          </div>
          <p className="small" style={{ margin: "4px 0" }}>{result.feedback}</p>
          <div className="model-answer">
            <strong>Model answer (from the video):</strong> {result.model_answer}
          </div>
        </div>
      )}
    </div>
  );
}

export default function QuizMode({ result, onRestart }) {
  const topics = result.topics;
  const [index, setIndex] = useState(0);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setQuestions([]);
    api
      .quiz(result.session_id, index)
      .then((res) => active && setQuestions(res.questions))
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [index, result.session_id]);

  const topic = topics[index];

  return (
    <div>
      <div className="row-between">
        <h1 style={{ marginBottom: 4 }}>Quiz mode</h1>
        <button className="btn-ghost small" onClick={onRestart}>
          New video
        </button>
      </div>

      <div className="progress-line">
        {topics.map((_, i) => (
          <div key={i} className={`dot ${i < index ? "done" : ""} ${i === index ? "current" : ""}`} />
        ))}
      </div>

      <div className="section">
        <h2>
          {index + 1}. {topic.topic_name}
        </h2>
        <p className="hint" style={{ marginBottom: 16 }}>
          Easy → medium → hard. Multiple choice is graded instantly; short answer is graded against the video.
        </p>

        {loading && (
          <div className="center" style={{ padding: "24px 0" }}>
            <div className="spinner" />
            <p className="muted">Writing your questions…</p>
          </div>
        )}
        {error && <div className="error-box">{error}</div>}
        {!loading &&
          questions.map((q, i) =>
            q.format === "mcq" ? (
              <McqQuestion key={`${index}-${i}`} q={q} />
            ) : (
              <SubjectiveQuestion
                key={`${index}-${i}`}
                sessionId={result.session_id}
                topicIndex={index}
                q={q}
              />
            )
          )}

        <div className="btn-row" style={{ marginTop: 18 }}>
          <button
            className="btn-ghost"
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
            disabled={index === 0 || loading}
          >
            ← Previous topic
          </button>
          <button
            className="btn-primary"
            onClick={() => setIndex((i) => Math.min(topics.length - 1, i + 1))}
            disabled={index >= topics.length - 1 || loading}
          >
            Next topic →
          </button>
        </div>
        {index >= topics.length - 1 && !loading && (
          <p className="hint" style={{ marginTop: 10 }}>That's the last topic.</p>
        )}
      </div>

      <ChatBox
        sessionId={result.session_id}
        title="Stuck? Ask the tutor"
        placeholder="e.g. Why is my answer wrong?"
      />
    </div>
  );
}
