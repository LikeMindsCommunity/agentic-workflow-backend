import { useEffect, useMemo, useRef, useState } from "react";
import EventCard from "./EventCard.jsx";

const ALL = "all";
const FILTERS = [
  { key: ALL, label: "All" },
  { key: "assistant_text", label: "Assistant" },
  { key: "tool_use,tool_result", label: "Tools" },
  { key: "turn_start,turn_end", label: "Turns" },
  { key: "thinking", label: "Thinking" },
  { key: "error,session_closed", label: "Errors" },
];

export default function EventFeed({ events }) {
  const [filter, setFilter] = useState(ALL);
  const [stickToBottom, setStickToBottom] = useState(true);
  const ref = useRef(null);

  const visible = useMemo(() => {
    if (filter === ALL) return events;
    const allowed = new Set(filter.split(","));
    return events.filter((e) => allowed.has(e.type));
  }, [events, filter]);

  useEffect(() => {
    if (!ref.current || !stickToBottom) return;
    ref.current.scrollTop = ref.current.scrollHeight;
  }, [visible, stickToBottom]);

  function onScroll() {
    if (!ref.current) return;
    const el = ref.current;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
    setStickToBottom(atBottom);
  }

  return (
    <div className="bg-white rounded-lg shadow flex flex-col h-[60vh]">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-200 text-xs">
        <span className="text-slate-500">Filter:</span>
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-2 py-1 rounded ${
              filter === f.key
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }`}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-slate-400">
          {visible.length} / {events.length} events
        </span>
      </div>

      <div ref={ref} onScroll={onScroll} className="flex-1 overflow-y-auto p-4 space-y-2 text-sm">
        {visible.length === 0 && (
          <div className="text-slate-400 italic">Waiting for events…</div>
        )}
        {visible.map((ev) => (
          <EventCard key={ev.id} event={ev} />
        ))}
      </div>
    </div>
  );
}
