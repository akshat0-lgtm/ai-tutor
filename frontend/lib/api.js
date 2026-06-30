// Thin client for the FastAPI backend. All calls go through request() so error
// handling and the base URL live in one place.

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request(path, body) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new Error("Could not reach the server. Is the backend running?");
  }

  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* non-JSON response */
  }

  if (!res.ok) {
    const detail = (data && data.detail) || "Something went wrong. Please try again.";
    throw new Error(detail);
  }
  return data;
}

async function requestFormData(path, formData) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { method: "POST", body: formData });
  } catch (e) {
    throw new Error("Could not reach the server. Is the backend running?");
  }

  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* non-JSON response */
  }

  if (!res.ok) {
    const detail = (data && data.detail) || "Something went wrong. Please try again.";
    throw new Error(detail);
  }
  return data;
}

export const api = {
  preview: (youtube_url) => request("/api/preview", { youtube_url }),
  process: (payload) => request("/api/process", payload),
  chat: (session_id, message) => request("/api/chat", { session_id, message }),
  teach: (session_id, topic_index, level) =>
    request("/api/teach", { session_id, topic_index, level }),
  quiz: (session_id, topic_index) =>
    request("/api/quiz", { session_id, topic_index }),
  grade: (session_id, topic_index, question, user_answer) =>
    request("/api/quiz/grade", { session_id, topic_index, question, user_answer }),
  tts: (text) => request("/api/tts", { text }),
  stt: (blob) => {
    const formData = new FormData();
    formData.append("file", blob, "doubt.webm");
    return requestFormData("/api/stt", formData);
  },
};

// Decodes a base64 WAV string into a playable object URL. Caller is
// responsible for revoking it (URL.revokeObjectURL) once done playing.
export function audioUrlFromBase64(base64, mimeType = "audio/wav") {
  const bytes = atob(base64);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  const blob = new Blob([arr], { type: mimeType });
  return URL.createObjectURL(blob);
}

export function formatTs(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function formatDuration(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

// Extracts an 11-char YouTube video id from common URL shapes, used to decide
// when the input looks like a real link worth previewing.
export function looksLikeYoutubeUrl(url) {
  return /(?:v=|\/shorts\/|\/embed\/|youtu\.be\/)([0-9A-Za-z_-]{11})/.test(url || "");
}
