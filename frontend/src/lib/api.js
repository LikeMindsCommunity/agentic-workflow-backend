// Thin wrapper around the FastAPI Skill API.
// Set VITE_API_BASE in .env or override in the UI (persisted to localStorage).

const STORAGE_KEY = "skill-api-base";
const DEFAULT_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000";

export function getApiBase() {
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_BASE;
}

export function setApiBase(value) {
  localStorage.setItem(STORAGE_KEY, value);
}

async function ensureOk(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText}${text ? ` — ${text}` : ""}`);
  }
  return res;
}

export async function createSession({ skill, prompt, projectDir, files, generatedFile, expectedFile }) {
  const fd = new FormData();
  fd.append("skill", skill);
  if (prompt) fd.append("prompt", prompt);
  if (projectDir) fd.append("project_dir", projectDir);
  for (const f of files || []) fd.append("files", f);
  if (generatedFile) fd.append("generated_file", generatedFile);
  if (expectedFile) fd.append("expected_file", expectedFile);
  const res = await fetch(`${getApiBase()}/sessions`, { method: "POST", body: fd });
  await ensureOk(res);
  return res.json();
}

export async function fetchComparisonSheet(sessionId) {
  const res = await fetch(`${getApiBase()}/sessions/${sessionId}/comparison-sheet`);
  await ensureOk(res);
  return res.json();
}

export async function sendMessage(sessionId, { text, files }) {
  const url = `${getApiBase()}/sessions/${sessionId}/messages`;
  let res;
  if (files && files.length > 0) {
    const fd = new FormData();
    fd.append("text", text || "");
    for (const f of files) fd.append("files", f);
    res = await fetch(url, { method: "POST", body: fd });
  } else {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  }
  await ensureOk(res);
  return res.json();
}

export async function getSession(sessionId) {
  const res = await fetch(`${getApiBase()}/sessions/${sessionId}`);
  await ensureOk(res);
  return res.json();
}

export async function markDone(sessionId) {
  const res = await fetch(`${getApiBase()}/sessions/${sessionId}/done`, { method: "POST" });
  await ensureOk(res);
  return res.json();
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${getApiBase()}/sessions/${sessionId}`, { method: "DELETE" });
  if (res.status !== 204) await ensureOk(res);
}

export function resultZipUrl(sessionId) {
  return `${getApiBase()}/sessions/${sessionId}/result?format=zip`;
}

export async function fetchResultJson(sessionId) {
  const res = await fetch(`${getApiBase()}/sessions/${sessionId}/result?format=json`);
  await ensureOk(res);
  return res.json();
}

export function streamUrl(sessionId) {
  return `${getApiBase()}/sessions/${sessionId}/stream`;
}

export async function fetchSkills() {
  const res = await fetch(`${getApiBase()}/skills`);
  await ensureOk(res);
  return res.json();
}

export const EVENT_TYPES = [
  "system_init",
  "turn_start",
  "assistant_text",
  "tool_use",
  "tool_result",
  "thinking",
  "result",
  "turn_end",
  "error",
  "session_closed",
];
