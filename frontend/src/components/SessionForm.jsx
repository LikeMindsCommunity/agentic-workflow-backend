import { useState } from "react";
import { createSession } from "../lib/api.js";

// Quick-pick suggestions; the field accepts any skill name your install has.
const SKILL_SUGGESTIONS = ["platform-kb", "generate-document", "init", "review"];

export default function SessionForm({ onCreated }) {
  const [skill, setSkill] = useState("platform-kb");
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await createSession({ skill, prompt, files });
      onCreated(session);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="bg-white rounded-lg shadow p-6 space-y-5 max-w-3xl">
      <header>
        <h2 className="text-xl font-semibold">Start a session</h2>
        <p className="text-sm text-slate-500 mt-1">
          Upload artifacts/docs and the agent will run the selected skill against them.
        </p>
      </header>

      {error && (
        <div className="bg-rose-100 border border-rose-300 text-rose-800 rounded p-3 text-sm">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium mb-1">Skill</label>
        <input
          className="border rounded px-3 py-2 w-full text-sm font-mono"
          value={skill}
          onChange={(e) => setSkill(e.target.value)}
          list="skill-suggestions"
          placeholder="my-skill"
        />
        <datalist id="skill-suggestions">
          {SKILL_SUGGESTIONS.map((s) => <option key={s} value={s} />)}
        </datalist>
        <div className="text-xs text-slate-500 mt-1 flex flex-wrap gap-1">
          {SKILL_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSkill(s)}
              className="px-2 py-0.5 bg-slate-100 hover:bg-slate-200 rounded font-mono"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Prompt (optional)</label>
        <textarea
          className="border rounded px-3 py-2 w-full text-sm"
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. This is the Acme IVR builder; focus on node types and transitions."
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Files</label>
        <input
          type="file"
          multiple
          onChange={(e) => setFiles(Array.from(e.target.files))}
          className="text-sm"
        />
        {files.length > 0 && (
          <p className="text-xs text-slate-500 mt-1">
            {files.length} file(s) — {files.map((f) => f.name).join(", ")}
          </p>
        )}
        <p className="text-xs text-slate-400 mt-1">
          Anything the skill can read: JSON, YAML, MD, PDF, DOCX, XLSX, PPTX, images.
        </p>
      </div>

      <button
        type="submit"
        disabled={busy}
        className="bg-slate-900 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
      >
        {busy ? "Starting…" : "Start session"}
      </button>
    </form>
  );
}
