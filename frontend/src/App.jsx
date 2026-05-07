import { useEffect, useState } from "react";
import { getApiBase, setApiBase } from "./lib/api.js";
import SessionForm from "./components/SessionForm.jsx";
import SessionView from "./components/SessionView.jsx";

export default function App() {
  const [base, setBase] = useState(getApiBase());
  const [session, setSession] = useState(null);

  useEffect(() => { setApiBase(base); }, [base]);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-4">
          <h1 className="text-lg font-semibold tracking-tight">
            Skill API <span className="text-slate-400 font-normal">· Console</span>
          </h1>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <label className="text-slate-500">API base</label>
            <input
              className="border rounded px-2 py-1 w-72 font-mono text-xs"
              value={base}
              onChange={(e) => setBase(e.target.value)}
              spellCheck={false}
            />
            {session && (
              <button
                onClick={() => setSession(null)}
                className="bg-slate-200 px-3 py-1 rounded text-xs"
              >
                ← New session
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-6">
        {!session ? (
          <SessionForm onCreated={setSession} />
        ) : (
          <SessionView session={session} onClosed={() => setSession(null)} />
        )}
      </main>

      <footer className="text-center text-xs text-slate-400 py-4">
        Claude Agent SDK · FastAPI · SSE
      </footer>
    </div>
  );
}
