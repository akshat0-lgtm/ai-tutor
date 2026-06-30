"use client";

export default function Processing({ source }) {
  return (
    <div className="center" style={{ padding: "60px 0" }}>
      <div className="spinner" />
      <h2>Building your knowledge base…</h2>
      <p className="muted" style={{ margin: 0 }}>
        {source === "whisper"
          ? "Transcribing the audio with Whisper — this can take a minute."
          : "Fetching captions, transcribing instead if none are found."}
      </p>
      <ul className="steps" style={{ textAlign: "left", display: "inline-block", marginTop: 18 }}>
        <li>Getting the transcript</li>
        <li>Chunking it with timestamps</li>
        <li>Embedding chunks for retrieval</li>
        <li>Extracting the topics you care about</li>
      </ul>
    </div>
  );
}
