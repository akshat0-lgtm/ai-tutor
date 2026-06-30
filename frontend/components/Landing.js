"use client";

import { useEffect, useRef, useState } from "react";
import { api, formatDuration, looksLikeYoutubeUrl } from "@/lib/api";
import { LinkIcon, GoalIcon, CaptionIcon, ClockIcon } from "./Icons";

function PreviewCard({ status, preview, error }) {
  if (status === "idle") return null;

  if (status === "loading") {
    return (
      <div className="panel preview-card">
        <div className="preview-skeleton" />
        <div className="preview-meta">
          <span className="muted small">Loading video…</span>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="panel preview-card">
        <span className="muted small">{error || "Couldn't load that video."}</span>
      </div>
    );
  }

  return (
    <div className="panel preview-card">
      {preview.thumbnail_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="preview-thumb" src={preview.thumbnail_url} alt="" />
      ) : (
        <div className="preview-skeleton" />
      )}
      <div className="preview-meta">
        <div className="preview-title">{preview.title || "Untitled video"}</div>
        <div className="preview-sub">
          {preview.duration_seconds > 0 && (
            <span>
              <ClockIcon width={12} height={12} style={{ verticalAlign: -1 }} />{" "}
              {formatDuration(preview.duration_seconds)}
            </span>
          )}
          {preview.captions_available === true && (
            <span className="cap-badge yes">
              <CaptionIcon width={12} height={12} style={{ verticalAlign: -1 }} /> captions available
            </span>
          )}
          {preview.captions_available === false && (
            <span className="cap-badge no">
              <CaptionIcon width={12} height={12} style={{ verticalAlign: -1 }} /> no captions — will transcribe
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Landing({ onSubmit, error }) {
  const [url, setUrl] = useState("");
  const [goal, setGoal] = useState("");
  const [forceWhisper, setForceWhisper] = useState(false);

  const [previewStatus, setPreviewStatus] = useState("idle"); // idle | loading | ready | error
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const debounceRef = useRef(null);
  const lastFetchedUrl = useRef("");

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!looksLikeYoutubeUrl(url)) {
      setPreviewStatus("idle");
      setPreview(null);
      lastFetchedUrl.current = "";
      return;
    }
    if (url === lastFetchedUrl.current) return;

    setPreviewStatus("loading");
    debounceRef.current = setTimeout(async () => {
      lastFetchedUrl.current = url;
      try {
        const res = await api.preview(url);
        setPreview(res);
        setPreviewStatus("ready");
      } catch (e) {
        setPreviewError(e.message);
        setPreviewStatus("error");
      }
    }, 500);

    return () => clearTimeout(debounceRef.current);
  }, [url]);

  function submit() {
    if (!url.trim()) return;
    onSubmit({ youtube_url: url.trim(), learning_goal: goal.trim(), force_whisper: forceWhisper });
  }

  return (
    <div>
      <h1>Learn from any video</h1>
      <p className="sub">Paste a link, tell us what you want to learn, and get tutored or quizzed on it.</p>

      {error && <div className="error-box">{error}</div>}

      <div className="section">
        <div className="section-head">
          <LinkIcon className="icon" />
          <span className="label">YouTube URL</span>
        </div>
        <div className="field" style={{ marginBottom: 14 }}>
          <input
            type="url"
            placeholder="https://www.youtube.com/watch?v=…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </div>
        <PreviewCard status={previewStatus} preview={preview} error={previewError} />
      </div>

      <div className="section">
        <div className="section-head">
          <GoalIcon className="icon" />
          <span className="label">What do you want to learn?</span>
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <textarea
            rows={2}
            placeholder="e.g. I want to understand how backpropagation works"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
          <p className="hint">Optional — sharpens the topics we pull out for you.</p>
        </div>
      </div>

      <div className="section">
        <div className={`transcript-note ${forceWhisper ? "forced" : ""}`}>
          <span>
            <CaptionIcon width={14} height={14} style={{ verticalAlign: -2, marginRight: 5 }} />
            {forceWhisper
              ? "Will transcribe audio with Whisper directly"
              : "Uses captions automatically, transcribes audio if needed"}
          </span>
          <button type="button" className="toggle-link" onClick={() => setForceWhisper((v) => !v)}>
            {forceWhisper ? "use captions instead" : "force Whisper transcription"}
          </button>
        </div>
      </div>

      <button className="btn-cta" onClick={submit} disabled={!url.trim()}>
        Build my tutor
      </button>
    </div>
  );
}
