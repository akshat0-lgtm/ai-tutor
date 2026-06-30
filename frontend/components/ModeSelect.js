"use client";

import { formatTs } from "@/lib/api";
import { BookIcon, PencilIcon } from "./Icons";

export default function ModeSelect({ result, onPick, onRestart }) {
  return (
    <div>
      <div className="row-between">
        <h1 style={{ marginBottom: 4 }}>Ready to go</h1>
        <button className="btn-ghost small" onClick={onRestart}>
          New video
        </button>
      </div>
      <p className="sub" style={{ marginBottom: 24 }}>
        Built from {result.transcript_source === "whisper" ? "a Whisper transcript" : "the video's captions"} ·{" "}
        {result.topics.length} topics found.
      </p>

      <div className="section" style={{ marginBottom: 30 }}>
        <div className="section-head">
          <span className="label">Do you already know this topic?</span>
        </div>
        <div className="choice-row">
          <div className="choice" onClick={() => onPick("teach")}>
            <BookIcon className="icon" width={26} height={26} />
            <div className="title">No — teach me</div>
            <div className="desc">Five levels of depth per topic, with real examples</div>
          </div>
          <div className="choice" onClick={() => onPick("quiz")}>
            <PencilIcon className="icon" width={26} height={26} />
            <div className="title">Yes — quiz me</div>
            <div className="desc">Mostly multiple choice, easy → medium → hard</div>
          </div>
        </div>
      </div>

      <div className="section">
        <div className="section-head">
          <span className="label">What we'll cover</span>
        </div>
        {result.topics.map((t, i) => (
          <div className="topic" key={i}>
            <div className="row-between">
              <span className="name">
                {i + 1}. {t.topic_name}
              </span>
              <span className="ts-pill">
                {formatTs(t.start_ts)}–{formatTs(t.end_ts)}
              </span>
            </div>
            <div className="meta">{t.one_line_description}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
