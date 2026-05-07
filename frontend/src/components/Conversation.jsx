import { useEffect, useRef, useState } from "react";

function ToolPart({ part }) {
  const [open, setOpen] = useState(false);
  const summary = (
    <button
      onClick={() => setOpen((v) => !v)}
      className="text-left flex items-center gap-2 text-xs text-slate-600 hover:text-slate-900"
    >
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${
        part.result == null ? "bg-amber-400 animate-pulse" :
        part.isError ? "bg-rose-500" : "bg-emerald-500"
      }`} />
      <span className="font-mono text-[11px]">{part.name}</span>
      <span className="text-slate-400">
        {part.result == null ? "running…" : part.isError ? "error" : "done"}
      </span>
      <span className="text-slate-400">{open ? "▾" : "▸"}</span>
    </button>
  );

  return (
    <div className="border border-slate-200 rounded bg-slate-50 px-3 py-2">
      {summary}
      {open && (
        <div className="mt-2 space-y-2">
          <div>
            <div className="text-[10px] uppercase text-slate-500 mb-1">input</div>
            <pre className="text-xs text-slate-700 bg-white border border-slate-200 rounded p-2 max-h-48 overflow-auto">
              {typeof part.input === "string"
                ? part.input
                : JSON.stringify(part.input, null, 2)}
            </pre>
          </div>
          {part.result != null && (
            <div>
              <div className={`text-[10px] uppercase mb-1 ${part.isError ? "text-rose-600" : "text-slate-500"}`}>
                {part.isError ? "error" : "output"}
              </div>
              <pre className={`text-xs bg-white border rounded p-2 max-h-48 overflow-auto ${
                part.isError ? "border-rose-300 text-rose-800" : "border-slate-200 text-slate-700"
              }`}>
                {part.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ThinkingPart({ part }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-fuchsia-200 rounded bg-fuchsia-50 px-3 py-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-xs text-fuchsia-700 hover:text-fuchsia-900 flex items-center gap-1"
      >
        thinking <span className="text-fuchsia-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <pre className="text-xs italic text-slate-600 mt-2 whitespace-pre-wrap">
          {part.text}
        </pre>
      )}
    </div>
  );
}

function AssistantMessage({ msg }) {
  const isStreaming = msg.status === "streaming";
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-slate-900 text-white grid place-items-center text-xs font-semibold shrink-0">
        A
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        {msg.parts.length === 0 && isStreaming && (
          <div className="text-slate-400 text-sm italic">…</div>
        )}
        {msg.parts.map((p, i) => {
          if (p.kind === "text") {
            return (
              <div key={i} className="text-sm whitespace-pre-wrap leading-relaxed">
                {p.text}
              </div>
            );
          }
          if (p.kind === "thinking") return <ThinkingPart key={i} part={p} />;
          if (p.kind === "tool")     return <ToolPart key={i} part={p} />;
          return null;
        })}
        {isStreaming && (
          <div className="text-[10px] text-amber-700 uppercase tracking-wider">
            streaming…
          </div>
        )}
      </div>
    </div>
  );
}

function UserMessage({ msg }) {
  return (
    <div className="flex gap-3 justify-end">
      <div className="max-w-[80%] bg-emerald-600 text-white rounded-2xl rounded-br-sm px-4 py-2 text-sm whitespace-pre-wrap">
        {msg.text}
      </div>
      <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 grid place-items-center text-xs font-semibold shrink-0">
        U
      </div>
    </div>
  );
}

function SystemMessage({ msg }) {
  const isErr = msg.kind === "error";
  return (
    <div className={`text-xs text-center py-1 ${isErr ? "text-rose-700" : "text-slate-400"}`}>
      {msg.text}
    </div>
  );
}

export default function Conversation({ messages }) {
  const ref = useRef(null);
  const [stick, setStick] = useState(true);

  useEffect(() => {
    if (ref.current && stick) ref.current.scrollTop = ref.current.scrollHeight;
  }, [messages, stick]);

  function onScroll() {
    if (!ref.current) return;
    const el = ref.current;
    setStick(el.scrollHeight - el.scrollTop - el.clientHeight < 32);
  }

  return (
    <div
      ref={ref}
      onScroll={onScroll}
      className="bg-white rounded-lg shadow p-6 h-[60vh] overflow-y-auto space-y-5"
    >
      {messages.length === 0 && (
        <div className="text-slate-400 italic text-sm text-center pt-8">
          Waiting for the agent…
        </div>
      )}
      {messages.map((m) => {
        if (m.role === "user")      return <UserMessage      key={m.id} msg={m} />;
        if (m.role === "assistant") return <AssistantMessage key={m.id} msg={m} />;
        return <SystemMessage key={m.id} msg={m} />;
      })}
    </div>
  );
}
