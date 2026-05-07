import { useEffect, useRef, useState, useCallback } from "react";
import { EVENT_TYPES, streamUrl } from "../lib/api.js";

// Owns the EventSource subscription and derives status + last pending question.
export function useSession(sessionId) {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("running");
  const [connected, setConnected] = useState(false);
  const esRef = useRef(null);

  const reset = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setEvents([]);
    setStatus("running");
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    const es = new EventSource(streamUrl(sessionId));
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    const onEvent = (type) => (e) => {
      let data = {};
      try { data = JSON.parse(e.data); } catch { /* ignore */ }
      const id = e.lastEventId ? Number(e.lastEventId) : Date.now() + Math.random();
      setEvents((prev) => [...prev, { id, type, data }]);

      if (type === "turn_start") setStatus("running");
      else if (type === "turn_end") setStatus("idle");
      else if (type === "error") setStatus("error");
      else if (type === "session_closed") {
        setStatus((s) => (s === "error" ? s : "done"));
        es.close();
      }
    };

    EVENT_TYPES.forEach((t) => es.addEventListener(t, onEvent(t)));

    return () => { es.close(); esRef.current = null; };
  }, [sessionId]);

  return { events, status, connected, reset };
}
