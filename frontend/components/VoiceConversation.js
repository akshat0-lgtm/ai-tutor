"use client";

import { useEffect, useRef, useState } from "react";
import { api, audioUrlFromBase64 } from "@/lib/api";

// Push-to-talk conversation: "Speak to me" reads the current explanation
// aloud (Sarvam TTS); once it's done, "Got a doubt?" records a question
// (Sarvam STT), answers it via the existing RAG chat endpoint, and speaks
// the answer back. Record-then-transcribe rather than true streaming —
// simpler and plenty responsive for a single follow-up question at a time.
const STATE = {
  IDLE: "idle",
  SPEAKING: "speaking",
  RECORDING: "recording",
  TRANSCRIBING: "transcribing",
  THINKING: "thinking",
  ANSWERING: "answering",
};

export default function VoiceConversation({ sessionId, text }) {
  const [state, setState] = useState(STATE.IDLE);
  const [error, setError] = useState("");
  const [doubtTranscript, setDoubtTranscript] = useState("");
  const [answer, setAnswer] = useState(null); // { text, in_context }
  const [hasSpokenLesson, setHasSpokenLesson] = useState(false);

  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);

  // Reset the conversation whenever the underlying lesson text changes
  // (new topic or new difficulty level).
  useEffect(() => {
    setState(STATE.IDLE);
    setError("");
    setDoubtTranscript("");
    setAnswer(null);
    setHasSpokenLesson(false);
    stopPlayback();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  useEffect(() => stopEverything, []); // cleanup on unmount

  function stopPlayback() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
  }

  function stopEverything() {
    stopPlayback();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
  }

  async function speak(textToSpeak, nextStateAfter) {
    setError("");
    try {
      const res = await api.tts(textToSpeak);
      const url = audioUrlFromBase64(res.audio_base64, res.mime_type);
      audioUrlRef.current = url;
      const audioEl = new Audio(url);
      audioRef.current = audioEl;
      audioEl.onended = () => {
        setState(nextStateAfter);
      };
      audioEl.onerror = () => {
        setError("Could not play that audio.");
        setState(STATE.IDLE);
      };
      await audioEl.play();
    } catch (e) {
      setError(e.message);
      setState(STATE.IDLE);
    }
  }

  async function handleSpeakLesson() {
    setState(STATE.SPEAKING);
    setHasSpokenLesson(true);
    await speak(text, STATE.IDLE);
  }

  async function startRecording() {
    setError("");
    setDoubtTranscript("");
    setAnswer(null);
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      setError("Voice recording isn't supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = handleRecordingStop;
      mediaRecorderRef.current = recorder;
      recorder.start();
      setState(STATE.RECORDING);
    } catch (e) {
      setError("Microphone access was denied or unavailable.");
      setState(STATE.IDLE);
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
  }

  async function handleRecordingStop() {
    setState(STATE.TRANSCRIBING);
    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    try {
      const sttRes = await api.stt(blob);
      setDoubtTranscript(sttRes.transcript);
      setState(STATE.THINKING);
      const chatRes = await api.chat(sessionId, sttRes.transcript);
      setAnswer({ text: chatRes.answer, in_context: chatRes.in_context });
      setState(STATE.ANSWERING);
      await speak(chatRes.answer, STATE.IDLE);
    } catch (e) {
      setError(e.message);
      setState(STATE.IDLE);
    }
  }

  const busy = [STATE.SPEAKING, STATE.TRANSCRIBING, STATE.THINKING, STATE.ANSWERING].includes(state);

  return (
    <div className="panel" style={{ marginTop: 18 }}>
      {error && <div className="error-box" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="btn-row">
        <button className="btn-primary" onClick={handleSpeakLesson} disabled={busy || state === STATE.RECORDING}>
          {state === STATE.SPEAKING ? "Speaking…" : hasSpokenLesson ? "Speak again" : "Speak to me"}
        </button>

        {state === STATE.RECORDING ? (
          <button className="btn-ghost" style={{ color: "var(--danger)", borderColor: "var(--danger)" }} onClick={stopRecording}>
            ● Stop recording
          </button>
        ) : (
          <button className="btn-ghost" onClick={startRecording} disabled={busy}>
            Got a doubt? Ask by voice
          </button>
        )}
      </div>

      {state === STATE.TRANSCRIBING && <p className="hint" style={{ marginTop: 10 }}>Listening back…</p>}
      {state === STATE.THINKING && <p className="hint" style={{ marginTop: 10 }}>Thinking…</p>}

      {doubtTranscript && (
        <div className="chat-log" style={{ marginTop: 14 }}>
          <div className="bubble user">{doubtTranscript}</div>
          {answer && (
            <div className={`bubble tutor ${answer.in_context ? "src-video" : "src-general"}`}>
              <span className={`source-tag ${answer.in_context ? "video" : "general"}`}>
                {answer.in_context ? "From the video" : "General knowledge"}
              </span>
              <div>{answer.text}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
