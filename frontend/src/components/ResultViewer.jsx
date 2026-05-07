import { useState } from "react";
import { fetchResultJson, resultZipUrl } from "../lib/api.js";

export default function ResultViewer({ sessionId }) {
  const [files, setFiles] = useState(null);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const data = await fetchResultJson(sessionId);
      setFiles(data.files || []);
      setActive(data.files?.[0]?.path || null);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  const current = files?.find((f) => f.path === active);

  return (
    <div className="bg-white rounded-lg shadow flex flex-col h-[60vh]">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-slate-200 text-sm">
        <span className="font-semibold">Result</span>
        <button
          onClick={load}
          disabled={busy}
          className="bg-slate-200 px-3 py-1 rounded text-xs disabled:opacity-50"
        >
          {busy ? "Loading…" : files ? "Reload" : "Load files"}
        </button>
        <a
          href={resultZipUrl(sessionId)}
          target="_blank"
          rel="noreferrer"
          className="bg-sky-600 text-white px-3 py-1 rounded text-xs"
        >
          Download zip
        </a>
        {files && (
          <span className="ml-auto text-xs text-slate-500">{files.length} file(s)</span>
        )}
      </div>

      {error && (
        <div className="px-4 py-2 bg-rose-100 text-rose-800 text-sm">{error}</div>
      )}

      {!files ? (
        <div className="flex-1 grid place-items-center text-slate-400 text-sm">
          Click "Load files" once the agent has produced output.
        </div>
      ) : (
        <div className="flex-1 grid grid-cols-[14rem_1fr] overflow-hidden">
          <ul className="border-r border-slate-200 overflow-y-auto text-sm">
            {files.map((f) => (
              <li key={f.path}>
                <button
                  onClick={() => setActive(f.path)}
                  className={`w-full text-left px-3 py-2 truncate font-mono text-xs ${
                    active === f.path
                      ? "bg-slate-100 font-semibold"
                      : "hover:bg-slate-50"
                  }`}
                  title={f.path}
                >
                  {f.path}
                </button>
              </li>
            ))}
          </ul>
          <div className="overflow-y-auto p-4">
            {current ? (
              <pre className="text-xs whitespace-pre-wrap">{current.content}</pre>
            ) : (
              <div className="text-slate-400">Pick a file</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
