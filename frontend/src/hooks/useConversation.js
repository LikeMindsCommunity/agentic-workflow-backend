import { useMemo } from "react";

// Fold the raw SSE event stream into a conversational thread.
//
// Output shape:
//   [
//     { id, role: "user",      text, ts },
//     { id, role: "assistant", parts: [
//        { kind: "text",     text },
//        { kind: "thinking", text },
//        { kind: "tool",     name, input, result, isError, toolUseId },
//      ], status: "streaming" | "complete", ts },
//     { id, role: "system", kind: "error" | "closed", text, ts },
//     ...
//   ]
//
// One assistant message per turn; tool calls and intermediate text live inside it.
// Reconstruction is pure — pass the same events, get the same thread.
export function useConversation(events) {
  return useMemo(() => buildThread(events), [events]);
}

function buildThread(events) {
  const messages = [];
  let current = null; // active assistant message
  const toolIndex = new Map(); // tool_use_id -> { msgIdx, partIdx }

  function ensureAssistant(ts) {
    if (current && current.status === "streaming") return current;
    current = {
      id: `assistant-${messages.length}`,
      role: "assistant",
      parts: [],
      status: "streaming",
      ts,
    };
    messages.push(current);
    return current;
  }

  for (const ev of events) {
    const ts = ev.id;
    const d = ev.data || {};

    switch (ev.type) {
      case "turn_start": {
        // The runner's first message is auto-built by the server (skill invocation).
        // Show it as a user-side message so the thread reads naturally.
        if (d.user_text) {
          messages.push({
            id: `user-${messages.length}`,
            role: "user",
            text: d.user_text,
            ts,
          });
        }
        // Reset the streaming-assistant pointer so the next assistant_text
        // starts a fresh message.
        current = null;
        break;
      }
      case "assistant_text": {
        const m = ensureAssistant(ts);
        m.parts.push({ kind: "text", text: d.text || "" });
        break;
      }
      case "thinking": {
        const m = ensureAssistant(ts);
        m.parts.push({ kind: "thinking", text: d.text || "" });
        break;
      }
      case "tool_use": {
        const m = ensureAssistant(ts);
        const partIdx = m.parts.length;
        m.parts.push({
          kind: "tool",
          toolUseId: d.id,
          name: d.name,
          input: d.input,
          result: null,
          isError: false,
        });
        if (d.id) toolIndex.set(d.id, { msgIdx: messages.length - 1, partIdx });
        break;
      }
      case "tool_result": {
        const ref = toolIndex.get(d.tool_use_id);
        if (ref) {
          const part = messages[ref.msgIdx].parts[ref.partIdx];
          part.result = d.output;
          part.isError = !!d.is_error;
        }
        break;
      }
      case "turn_end": {
        if (current) current.status = "complete";
        current = null;
        break;
      }
      case "error": {
        if (current) current.status = "complete";
        current = null;
        messages.push({
          id: `system-${messages.length}`,
          role: "system",
          kind: "error",
          text: d.message || "Agent error",
          ts,
        });
        break;
      }
      case "session_closed": {
        if (current) current.status = "complete";
        current = null;
        messages.push({
          id: `system-${messages.length}`,
          role: "system",
          kind: "closed",
          text: "Session closed.",
          ts,
        });
        break;
      }
      default:
        // result, system_init — silent
        break;
    }
  }

  return messages;
}
