"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import Landing from "@/components/Landing";
import Processing from "@/components/Processing";
import ModeSelect from "@/components/ModeSelect";
import TeachMode from "@/components/TeachMode";
import QuizMode from "@/components/QuizMode";

// Client-side state machine:
// landing -> processing -> modeselect -> teach | quiz
export default function Home() {
  const [stage, setStage] = useState("landing");
  const [source, setSource] = useState("captions");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleProcess(payload) {
    setError("");
    setSource(payload.force_whisper ? "whisper" : "captions");
    setStage("processing");
    try {
      const res = await api.process(payload);
      setResult(res);
      setStage("modeselect");
    } catch (e) {
      setError(e.message);
      setStage("landing");
    }
  }

  function restart() {
    setResult(null);
    setError("");
    setStage("landing");
  }

  if (stage === "processing") return <Processing source={source} />;
  if (stage === "modeselect")
    return <ModeSelect result={result} onPick={(m) => setStage(m)} onRestart={restart} />;
  if (stage === "teach") return <TeachMode result={result} onRestart={restart} />;
  if (stage === "quiz") return <QuizMode result={result} onRestart={restart} />;

  return <Landing onSubmit={handleProcess} error={error} />;
}
