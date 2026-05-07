import { useState } from "react";
import { sendMessage } from "../lib/api.js";

export default function MessageInput({ sessionId, disabled, onSent, onError }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);

  async function send(textToSend) {
    if (!sessionId) return;
    if (!textToSend.trim() && files.length === 0) return;
    setBusy(true);
    try {
      await sendMessage(sessionId, { text: textToSend, files });
      setText("");
      setFiles([]);
      document.getElementById("msg-files").value = "";
      onSent?.();
    } catch (err) {
      onError?.(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      send(text);
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-3">
      <textarea
        className="border rounded px-3 py-2 w-full text-sm"
        rows={3}
        placeholder="Reply to the agent. ⌘/Ctrl+Enter to send."
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled || busy}
      />
      <div className="flex flex-wrap items-center gap-3">
        <input
          id="msg-files"
          type="file"
          multiple
          onChange={(e) => setFiles(Array.from(e.target.files))}
          className="text-xs"
          disabled={disabled || busy}
        />
        {files.length > 0 && (
          <span className="text-xs text-slate-500">{files.length} file(s) attached</span>
        )}
        <button
          onClick={() => send(text)}
          disabled={disabled || busy || (!text.trim() && files.length === 0)}
          className="ml-auto bg-emerald-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
        >
          {busy ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
}
