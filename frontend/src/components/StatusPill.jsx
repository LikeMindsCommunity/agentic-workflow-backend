const COLORS = {
  idle:    "bg-emerald-200 text-emerald-900",
  running: "bg-amber-200 text-amber-900",
  done:    "bg-sky-200 text-sky-900",
  error:   "bg-rose-200 text-rose-900",
  closed:  "bg-slate-300 text-slate-800",
};

const LABEL = {
  idle:    "your turn",
  running: "agent thinking",
  done:    "done",
  error:   "error",
  closed:  "closed",
};

export default function StatusPill({ status, connected }) {
  const cls = COLORS[status] || "bg-slate-200";
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`px-2 py-1 rounded text-xs font-semibold ${cls}`}>
        {LABEL[status] || status}
      </span>
      {connected !== undefined && (
        <span
          title={connected ? "SSE connected" : "SSE disconnected"}
          className={`inline-block w-2 h-2 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-400"}`}
        />
      )}
    </span>
  );
}
