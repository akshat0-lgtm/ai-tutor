"use client";

import { useRef, useState } from "react";
import { api, formatTs } from "@/lib/api";

// Renders a single tutor answer with a STRUCTURAL source distinction:
// in-context answers get a green "From the video" tag + timestamp citations;
// out-of-context answers get an explicit "not covered" line and an amber
// "General knowledge" tag. This is the honesty requirement made visible.
function TutorAnswer({ msg }) {
  if (msg.in_context) {
    return (
      <div className="bubble tutor src-video">
        <span className="source-tag video">From the video</span>
        <div>{msg.answer}</div>
        {msg.citations && msg.citations.length > 0 && (
          <div className="citations">
            {msg.citations.map((c) => (
              <span className="ts-pill" key={c.chunk_id}>
                {formatTs(c.start_ts)}–{formatTs(c.end_ts)}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="bubble tutor src-general">
      <div className="notcovered">Not covered in the video — answering from general knowledge:</div>
      <span className="source-tag general">General knowledge</span>
      <div>{msg.answer}</div>
    </div>
  );
}

export default function ChatBox({ sessionId, title = "Ask a question", placeholder }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const logRef = useRef(null);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setError("");
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);
    try {
      const res = await api.chat(sessionId, text);
      setMessages((m) => [
        ...m,
        {
          role: "tutor",
          answer: res.answer,
          in_context: res.in_context,
          citations: res.citations,
        },
      ]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setTimeout(() => logRef.current?.scrollTo(0, logRef.current.scrollHeight), 50);
    }
  }

  return (
    <div className="section">
      <h2>{title}</h2>
      <p className="hint" style={{ marginBottom: 14 }}>
        Answers are clearly labeled as coming from the video or from general knowledge.
      </p>

      {messages.length > 0 && (
        <div className="chat-log" ref={logRef}>
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div className="bubble user" key={i}>
                {m.text}
              </div>
            ) : (
              <TutorAnswer msg={m} key={i} />
            )
          )}
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      <div className="chat-input-row">
        <input
          type="text"
          value={input}
          placeholder={placeholder || "Type your question…"}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={loading}
        />
        <button className="btn-primary" onClick={send} disabled={loading}>
          {loading ? "…" : "Ask"}
        </button>
      </div>
    </div>
  );
}
