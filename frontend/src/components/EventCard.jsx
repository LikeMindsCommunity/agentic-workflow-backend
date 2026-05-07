const STYLES = {
  assistant_text:  "border-emerald-500 bg-emerald-50",
  tool_use:        "border-sky-500 bg-sky-50",
  tool_result:     "border-amber-500 bg-amber-50",
  thinking:        "border-fuchsia-400 bg-fuchsia-50 text-slate-500",
  turn_start:      "border-slate-400 bg-slate-100",
  turn_end:        "border-indigo-500 bg-indigo-50",
  error:           "border-rose-500 bg-rose-50 text-rose-800",
  session_closed:  "border-slate-500 bg-slate-100 italic text-slate-500",
  result:          "border-slate-300 bg-white text-slate-500",
  system_init:     "border-slate-200 bg-white text-slate-400",
};

function Body({ type, data }) {
  switch (type) {
    case "assistant_text":
      return <pre className="whitespace-pre-wrap">{data.text}</pre>;
    case "tool_use":
      return (
        <div>
          <div className="font-mono text-xs text-sky-700">→ {data.name}</div>
          <pre className="text-xs mt-1 text-slate-600">
            {typeof data.input === "string" ? data.input : JSON.stringify(data.input, null, 2)}
          </pre>
        </div>
      );
    case "tool_result":
      return (
        <div>
          <div className="font-mono text-xs text-amber-700">← {data.is_error ? "error" : "output"}</div>
          <pre className="text-xs mt-1 text-slate-600">{data.output}</pre>
        </div>
      );
    case "thinking":
      return <pre className="text-xs italic">{data.text}</pre>;
    case "turn_start":
      return (
        <div className="text-sm">
          <span className="font-semibold">turn {data.turn} →</span>{" "}
          <span className="font-mono text-xs text-slate-600">
            {(data.user_text || "").slice(0, 240)}
          </span>
        </div>
      );
    case "turn_end":
      return (
        <div>
          <div className="font-semibold">turn {data.turn} — agent awaiting input.</div>
          {data.pending_question && (
            <pre className="mt-2 text-xs whitespace-pre-wrap">{data.pending_question}</pre>
          )}
        </div>
      );
    case "error":
      return <div>{data.message}</div>;
    case "result":
      return (
        <div className="text-xs">
          turns: {data.turns ?? "—"} · cost:{" "}
          {typeof data.cost_usd === "number" ? `$${data.cost_usd.toFixed(4)}` : "—"}
        </div>
      );
    case "session_closed":
      return <div>session closed</div>;
    case "system_init":
      return <div>session ready</div>;
    default:
      return <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>;
  }
}

export default function EventCard({ event }) {
  const style = STYLES[event.type] || "border-slate-300 bg-white";
  return (
    <div className={`border-l-4 px-3 py-2 rounded ${style}`}>
      <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
        {event.type}
      </div>
      <Body type={event.type} data={event.data || {}} />
    </div>
  );
}
