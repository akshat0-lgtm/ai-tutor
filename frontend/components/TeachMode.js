"use client";

import { useEffect, useState } from "react";
import { api, formatTs } from "@/lib/api";
import ChatBox from "./ChatBox";
import VoiceConversation from "./VoiceConversation";

const LEVELS = [
  { n: 1, name: "Like I'm 5" },
  { n: 2, name: "Beginner" },
  { n: 3, name: "Intermediate" },
  { n: 4, name: "Advanced" },
  { n: 5, name: "Expert" },
];

export default function TeachMode({ result, onRestart }) {
  const topics = result.topics;
  const [index, setIndex] = useState(0);
  const [level, setLevel] = useState(1);
  // Cache lessons per "topicIndex-level" so flipping between levels/topics
  // already visited doesn't re-trigger an LLM call.
  const [cache, setCache] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [conversationMode, setConversationMode] = useState(false);

  const cacheKey = `${index}-${level}`;
  const lesson = cache[cacheKey];

  useEffect(() => {
    if (cache[cacheKey]) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    api
      .teach(result.session_id, index, level)
      .then((res) => {
        if (!active) return;
        setCache((c) => ({ ...c, [cacheKey]: res }));
      })
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey]);

  function goToTopic(i) {
    setIndex(i);
    setLevel(1);
  }

  const topic = topics[index];

  return (
    <div>
      <div className="row-between">
        <h1 style={{ marginBottom: 4 }}>Teach mode</h1>
        <button className="btn-ghost small" onClick={onRestart}>
          New video
        </button>
      </div>

      <div className="progress-line">
        {topics.map((_, i) => (
          <div
            key={i}
            className={`dot ${i < index ? "done" : ""} ${i === index ? "current" : ""}`}
            onClick={() => goToTopic(i)}
            style={{ cursor: "pointer" }}
          />
        ))}
      </div>

      <div className="section">
        <div className="row-between">
          <h2>
            {index + 1}. {topic.topic_name}
          </h2>
          <span className="ts-pill">
            {formatTs(topic.start_ts)}–{formatTs(topic.end_ts)}
          </span>
        </div>
        <div className="row-between" style={{ marginBottom: 16 }}>
          <p className="hint" style={{ margin: 0 }}>{topic.one_line_description}</p>
          <button
            className="toggle-link"
            onClick={() => setConversationMode((v) => !v)}
            style={{ whiteSpace: "nowrap" }}
          >
            {conversationMode ? "hide conversation mode" : "talk to the tutor"}
          </button>
        </div>

        <div className="level-tabs">
          {LEVELS.map((l) => (
            <button
              key={l.n}
              className={`level-tab ${level === l.n ? "active" : ""}`}
              onClick={() => setLevel(l.n)}
            >
              {l.n}. {l.name}
            </button>
          ))}
        </div>

        {loading && (
          <div className="center" style={{ padding: "24px 0" }}>
            <div className="spinner" />
            <p className="muted">Writing this level…</p>
          </div>
        )}
        {error && <div className="error-box">{error}</div>}
        {lesson && !loading && (
          <>
            <span className="source-tag video">From the video</span>
            <div style={{ whiteSpace: "pre-wrap" }}>{lesson.explanation}</div>
            {lesson.citations?.length > 0 && (
              <div className="citations">
                {lesson.citations.map((c) => (
                  <span className="ts-pill" key={c.chunk_id}>
                    {formatTs(c.start_ts)}–{formatTs(c.end_ts)}
                  </span>
                ))}
              </div>
            )}
            {conversationMode && (
              <VoiceConversation sessionId={result.session_id} text={lesson.explanation} />
            )}
          </>
        )}

        <div className="btn-row" style={{ marginTop: 22 }}>
          <button
            className="btn-ghost"
            onClick={() => goToTopic(Math.max(0, index - 1))}
            disabled={index === 0}
          >
            ← Previous topic
          </button>
          <button
            className="btn-primary"
            onClick={() => goToTopic(Math.min(topics.length - 1, index + 1))}
            disabled={index >= topics.length - 1}
          >
            Next topic →
          </button>
        </div>
        {index >= topics.length - 1 && level >= 5 && lesson && (
          <p className="hint" style={{ marginTop: 10 }}>
            That's every level of the last topic. Keep asking questions below, or start a new video.
          </p>
        )}
      </div>

      <ChatBox
        sessionId={result.session_id}
        title="Ask a follow-up question"
        placeholder="e.g. Can you explain that part again?"
      />
    </div>
  );
}
