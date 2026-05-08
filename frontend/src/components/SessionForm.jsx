import { useEffect, useState } from "react";
import { createSession, fetchSkills } from "../lib/api.js";

const COMPARE_SKILLS = ["find-bugs-exotel", "find-bugs"];

export default function SessionForm({ onCreated }) {
  const [skills, setSkills] = useState([]);
  const [skill, setSkill] = useState("platform-kb");
  const [prompt, setPrompt] = useState("");
  const [projectDir, setProjectDir] = useState("");
  const [files, setFiles] = useState([]);
  const [generatedFile, setGeneratedFile] = useState(null);
  const [expectedFile, setExpectedFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const isCompareSkill = COMPARE_SKILLS.includes(skill);

  useEffect(() => {
    fetchSkills()
      .then((list) => {
        setSkills(list);
        if (list.length > 0 && !list.find((s) => s.name === skill)) {
          setSkill(list[0].name);
        }
      })
      .catch(() => setSkills([]));
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    if (isCompareSkill && (!generatedFile || !expectedFile)) {
      setError("Please upload both a generated file and an expected file.");
      setBusy(false);
      return;
    }

    if (isCompareSkill && !projectDir.trim()) {
      setError("Please provide the project directory path.");
      setBusy(false);
      return;
    }

    try {
      const session = await createSession({
        skill,
        prompt,
        projectDir: isCompareSkill ? projectDir : "",
        files: isCompareSkill ? [] : files,
        generatedFile: isCompareSkill ? generatedFile : null,
        expectedFile: isCompareSkill ? expectedFile : null,
      });
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
        <select
          className="border rounded px-3 py-2 w-full text-sm font-mono bg-white"
          value={skill}
          onChange={(e) => setSkill(e.target.value)}
        >
          {skills.length === 0 && <option value={skill}>{skill}</option>}
          {skills.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name}
              {s.description ? ` — ${s.description.slice(0, 80)}` : ""}
            </option>
          ))}
        </select>
        {skills.length === 0 && (
          <p className="text-xs text-slate-400 mt-1">
            Could not load skills from API. Type a skill name manually.
          </p>
        )}
      </div>

      {isCompareSkill && (
        <div>
          <label className="block text-sm font-medium mb-1">
            Project Directory
            <span className="text-rose-500 ml-0.5">*</span>
          </label>
          <input
            className="border rounded px-3 py-2 w-full text-sm font-mono"
            value={projectDir}
            onChange={(e) => setProjectDir(e.target.value)}
            placeholder="e.g. /home/user/projects/my-ivr-project"
          />
          <p className="text-xs text-slate-400 mt-1">
            Absolute path to the project containing CLAUDE.md and source files. The agent will run in this directory.
          </p>
        </div>
      )}

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

      {isCompareSkill ? (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">
              Generated File
              <span className="text-rose-500 ml-0.5">*</span>
            </label>
            <input
              type="file"
              onChange={(e) => setGeneratedFile(e.target.files[0] || null)}
              className="text-sm"
            />
            {generatedFile && (
              <p className="text-xs text-slate-500 mt-1">{generatedFile.name}</p>
            )}
            <p className="text-xs text-slate-400 mt-1">
              The IVR JSON your system generated (stored in inputs/compare/generated/)
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Expected File
              <span className="text-rose-500 ml-0.5">*</span>
            </label>
            <input
              type="file"
              onChange={(e) => setExpectedFile(e.target.files[0] || null)}
              className="text-sm"
            />
            {expectedFile && (
              <p className="text-xs text-slate-500 mt-1">{expectedFile.name}</p>
            )}
            <p className="text-xs text-slate-400 mt-1">
              The reference/correct IVR JSON to compare against (stored in inputs/compare/expected/)
            </p>
          </div>
        </div>
      ) : (
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
      )}

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
