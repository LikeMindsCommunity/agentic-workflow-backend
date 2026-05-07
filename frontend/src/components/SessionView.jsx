import { useState } from "react";
import { useSession } from "../hooks/useSession.js";
import { useConversation } from "../hooks/useConversation.js";
import { deleteSession, markDone } from "../lib/api.js";
import StatusPill from "./StatusPill.jsx";
import Conversation from "./Conversation.jsx";
import EventFeed from "./EventFeed.jsx";
import MessageInput from "./MessageInput.jsx";
import ResultViewer from "./ResultViewer.jsx";

export default function SessionView({ session, onClosed }) {
  const { events, status, connected } = useSession(session.session_id);
  const messages = useConversation(events);
  const [tab, setTab] = useState("chat");
  const [error, setError] = useState(null);

  const inputDisabled = status === "done" || status === "error" || status === "closed";

  async function onMarkDone() {
    try { await markDone(session.session_id); } catch (e) { setError(String(e.message || e)); }
  }
  async function onDelete() {
    if (!confirm("Delete this session and all uploaded/generated files?")) return;
    try {
      await deleteSession(session.session_id);
      onClosed();
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  return (
    <div className="space-y-4">
      <header className="bg-white rounded-lg shadow p-4 flex flex-wrap items-center gap-3 text-sm">
        <StatusPill status={status} connected={connected} />
        <span className="font-mono text-xs text-slate-500">{session.session_id}</span>
        <span className="text-slate-500">
          skill: <span className="font-mono">{session.skill}</span>
        </span>
        <span className="text-slate-500 hidden md:inline">
          in: <span className="font-mono text-xs">{session.input_dir}</span>
        </span>
        <span className="text-slate-500 hidden md:inline">
          out: <span className="font-mono text-xs">{session.output_dir}</span>
        </span>
        <div className="ml-auto flex gap-2">
          <button onClick={onMarkDone} className="bg-slate-200 px-3 py-1 rounded text-xs">
            Mark done
          </button>
          <button onClick={onDelete} className="bg-rose-100 text-rose-800 px-3 py-1 rounded text-xs">
            Delete
          </button>
        </div>
      </header>

      {error && (
        <div className="bg-rose-100 border border-rose-300 text-rose-800 rounded p-3 text-sm">
          {error}
        </div>
      )}

      <div className="flex gap-2 text-sm">
        {[
          { key: "chat",   label: "Chat" },
          { key: "result", label: "Result" },
          { key: "debug",  label: "Debug" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-1 rounded ${
              tab === t.key ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "chat"   && <Conversation messages={messages} />}
      {tab === "result" && <ResultViewer sessionId={session.session_id} />}
      {tab === "debug"  && <EventFeed events={events} />}

      <MessageInput
        sessionId={session.session_id}
        disabled={inputDisabled}
        onError={(msg) => setError(msg)}
      />
    </div>
  );
}
