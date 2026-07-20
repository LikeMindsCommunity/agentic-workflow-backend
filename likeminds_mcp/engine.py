"""The engine: run ONE turn of a skill by spawning `claude -p` and watching its
stream-json output for a signal marker (<<<LM_ASK>>> / <<<LM_DONE>>>).

Resume-per-turn model: turn 1 uses `--session-id <uuid>`; every later turn uses
`--resume <uuid>`, so Claude Code's own on-disk session store carries the
conversation between rounds. Nothing is parked in memory between turns, which is
what makes the server leak-free, crash-resilient, and cheap while a human answers.

Signalling is done with TEXT MARKERS, not an MCP tool. A stdio MCP server is not
guaranteed to finish connecting before a `claude -p` turn begins (the init event
fires with the server "pending" and zero tools), so a signal *tool* races and is
missing on the turn. A marker the model writes into its reply has no such race, and
we harvest the deliverable from the output directory on disk regardless, so nothing
structured is lost.

Every turn passes the FULL flag set (harness, permission mode, model) — `--resume`
is not assumed to re-apply them — so continuation turns behave identically.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from . import config
from .harness import HARNESS
from .sessions import Session

# A turn may end without any marker (the model paused with a plain text summary).
# We nudge it and resume, up to this many times, before declaring failure. This
# emulates a forced tool call, which the CLI lacks.
MAX_CONTINUES = 12
NUDGE = (
    "You ended your turn without asking a question (the <<<LM_ASK>>> marker) or "
    "finishing (the <<<LM_DONE>>> marker). If the deliverable is not yet complete, "
    "keep going and finish the work — write every remaining file into the output "
    "directory. If you need something from the user to proceed, write a line with "
    "<<<LM_ASK>>> followed by the question and stop. Once every deliverable file is "
    "written into the output directory, write a line with <<<LM_DONE>>> and stop. Do "
    "not end with a plain message."
)

# stream-json lines can carry large tool payloads (a full file read, a big result);
# raise the per-line reader limit well above the 64 KiB default to avoid overruns.
_STDOUT_LIMIT = 16 * 1024 * 1024


def _write_artifacts(inputs_dir: Path, artifacts: list | None) -> list[str]:
    """Persist inline {name, content} text artifacts into the inputs dir.
    Returns the names of the files written. Binary content does not travel inline —
    it is uploaded to R2 and reaches the run via r2_keys."""
    written: list[str] = []
    for art in artifacts or []:
        if not isinstance(art, dict):
            continue
        name, content = art.get("name"), art.get("content")
        if not name or content is None:
            continue
        # A declared binary encoding would land as its own literal encoded text;
        # skip it rather than write a corrupt file.
        if art.get("encoding") not in (None, "", "utf-8", "text"):
            continue
        dest = inputs_dir / Path(name).name  # flatten; no path traversal
        try:
            dest.write_text(str(content), encoding="utf-8")
        except Exception:  # noqa: BLE001 — skip an unwritable artifact
            continue
        written.append(dest.name)
    return written


def build_first_message(
    skill: str,
    sess: Session,
    urls: list | None,
    context: str | None,
    continued: bool = False,
    seeded: list[str] | None = None,
) -> str:
    """The message that seeds the skill. Asks the model to use the named Agent Skill
    (`.claude/skills/<name>/SKILL.md`) and passes inputs=/output= so the harness can
    bind the I/O edges, plus any URLs and free-form context describing WHAT to do.

    The run mode is declared EXPLICITLY in both directions, because the spawned CLI runs
    with the project root as its cwd and can therefore see every past run's artifacts
    under `outputs/`, while several skills branch on exactly that ("a KB already exists →
    extend it", "a re-run into an existing output is an update"). Left to infer, the model
    silently resumes someone else's work. So: `continued` means the engine already copied
    that session's deliverable into the output directory — read and extend it in place.
    Otherwise this is a fresh run, and the skill's own resume branches are overridden;
    prior output found lying around is not adopted, it is asked about (see HARNESS)."""
    lines = [f"Use the {skill} skill."]
    lines.append(f"inputs={sess.inputs_dir}")
    lines.append(f"output={sess.output_dir}")
    if urls:
        lines.append("Reference URLs: " + " ".join(str(u) for u in urls))
    msg = "\n".join(lines)
    if continued:
        listing = ", ".join(seeded) if seeded else "the files already present there"
        msg += (
            "\n\nCONTINUATION: this run continues an earlier session. Its deliverable "
            f"is ALREADY in the output directory ({listing}). Read those files in full "
            "first, then continue the work by modifying and extending them in place per "
            "the instructions below. Do not start from scratch or discard existing files "
            "unless explicitly told to."
        )
    else:
        msg += (
            "\n\nFRESH RUN: this is a new session, NOT a continuation. The caller did not "
            "point at an earlier session, so nothing here is resumed work. Build from this "
            "run's inputs and the caller's instructions alone, and take the skill's "
            "from-scratch path — any branch in it that treats an existing directory as a "
            "reason to resume or extend does not apply. Earlier output you come across "
            "elsewhere in the project belongs to a different run: do not adopt or extend "
            "it, and if it looks like an earlier run of THIS same job, ask the caller "
            "whether to continue from it before using any of it."
        )
    if context:
        msg += f"\n\nContext / instructions from the caller:\n{context}"
    return msg


def build_reply_message(response: str | None, added_files: list[str]) -> str:
    """The user's answer to the open question(s), for a continuation (resume) turn.
    `added_files` are filenames the user just provided (already in the inputs dir)."""
    msg = (response or "").strip()
    if added_files:
        note = (
            "The user added these file(s) to your inputs directory: "
            + ", ".join(added_files)
            + ". Read each one in full now and use it to answer the open question "
            "before continuing."
        )
        msg = f"{msg}\n\n{note}" if msg else note
    return msg or "continue"


def _mcp_config_json() -> str:
    """The --mcp-config payload: an empty server set. We use NO MCP server for
    signalling (see module docstring), so the spawned Claude runs with no MCP servers
    at all. Combined with --strict-mcp-config so the spawned Claude never loads the
    project .mcp.json — which would otherwise make it connect back to THIS server
    (recursion) and spawn every project MCP server each turn."""
    return json.dumps({"mcpServers": {}})


def _build_argv(sess: Session, message: str, resume: bool) -> list[str]:
    """Full argv for one turn. Permission mode bypasses prompts so any tool the skill
    needs runs; no tool allowlist is imposed. --strict-mcp-config + our own
    --mcp-config keep the spawned Claude off the project's MCP servers."""
    argv = [
        config.CLAUDE_BIN, "-p", message,
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", "bypassPermissions",
        "--append-system-prompt", HARNESS,
        "--mcp-config", _mcp_config_json(),
        "--strict-mcp-config",
    ]
    if config.MODEL:
        argv += ["--model", config.MODEL]
    argv += (["--resume", sess.cc_id] if resume else ["--session-id", sess.cc_id])
    return argv


def _describe(block: dict) -> str | None:
    """A short, human-readable description of a tool call, for the live progress
    shown to the client on each poll. None = not worth surfacing."""
    name = block.get("name", "")
    inp = block.get("input") or {}
    base = lambda k: Path(str(inp.get(k, ""))).name
    if name in ("Write", "Edit"):
        return f"Writing {base('file_path')}"
    if name == "Read":
        return f"Reading {base('file_path')}"
    if name == "Bash":
        return f"Running: {str(inp.get('command', ''))[:60]}"
    if name == "WebSearch":
        return f"Web search: {str(inp.get('query', ''))[:60]}"
    if name == "WebFetch":
        return f"Fetching {str(inp.get('url', ''))[:60]}"
    if name in ("Glob", "Grep"):
        return "Searching files"
    if name == "Skill":
        return f"Using skill {inp.get('command') or inp.get('skill') or ''}".strip()
    if name.startswith("mcp__"):
        return f"Calling {name}"
    return None


def _marker_at_line_start(text: str, marker: str) -> int:
    """Index of the first occurrence of `marker` that sits at the start of a line
    (only whitespace before it on that line), or -1. Line-anchoring avoids a false
    positive when the model merely mentions the marker inside a prose sentence — the
    harness requires it on its own line."""
    for m in re.finditer(re.escape(marker), text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        if not text[line_start:m.start()].strip():
            return m.start()
    return -1


def _interpret(text: str) -> dict | None:
    """Decide the turn's signal from its accumulated assistant text. The first marker
    that appears on its own line wins (they stream in order)."""
    a = _marker_at_line_start(text, config.ASK_MARKER)
    d = _marker_at_line_start(text, config.DONE_MARKER)
    if a != -1 and (d == -1 or a < d):
        end = d if (d != -1 and d > a) else len(text)
        question = text[a + len(config.ASK_MARKER):end].strip()
        return {"kind": "ask",
                "questions": [question] if question else ["(the skill asked a question but included no text)"]}
    if d != -1:
        return {"kind": "emit"}
    return None


def _child_env(sess: Session) -> dict[str, str] | None:
    """Environment for the spawned CLI.

    Returns None to inherit the server's own environment (the .env fallback creds) —
    the default when the caller supplied no key. When the caller sent their own
    Anthropic key via the request header (BYOK), overlay it as ANTHROPIC_API_KEY for
    THIS turn only and drop any subscription/Foundry creds that would otherwise
    outrank it, so the caller's key is what authenticates and bills. The key is read
    fresh per run and never written to disk or logs; it lives only in this child
    process environment for the duration of the turn."""
    key = sess.api_key
    if not key:
        return None
    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"] = key
    for var in (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_USE_FOUNDRY",
        "ANTHROPIC_FOUNDRY_API_KEY",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
    ):
        env.pop(var, None)
    return env


async def run_turn(sess: Session, message: str, resume: bool) -> dict | None:
    """Spawn one `claude -p` turn and consume its stream to completion.

    Returns {"kind": "ask", "questions": [text]} or {"kind": "emit"} for the first
    marker seen, or None if the turn ended without either (the caller
    then nudges + resumes). Raises RuntimeError on a hard subprocess failure (nonzero
    exit with no marker), which the caller surfaces as an error.
    """
    argv = _build_argv(sess, message, resume)
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(config.PROJECT_ROOT),
        env=_child_env(sess),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=_STDOUT_LIMIT,
    )

    # Drain stderr concurrently so a large stderr can't fill its pipe and deadlock
    # the subprocess while we're busy reading stdout.
    stderr_buf: list[bytes] = []

    async def _drain_stderr() -> None:
        assert proc.stderr is not None
        async for line in proc.stderr:
            stderr_buf.append(line)

    stderr_task = asyncio.create_task(_drain_stderr())

    try:
        text_parts: list[str] = []
        result_err: str | None = None
        assert proc.stdout is not None
        async for raw in proc.stdout:
            try:
                evt = json.loads(raw.decode("utf-8", "replace"))
            except (ValueError, UnicodeDecodeError):
                continue  # not a JSON line; ignore
            etype = evt.get("type")
            if etype == "assistant":
                for block in (evt.get("message") or {}).get("content") or []:
                    btype = block.get("type")
                    if btype == "text":
                        t = block.get("text") or ""
                        text_parts.append(t)
                        first = t.strip().split("\n")[0]
                        if first and config.ASK_MARKER not in first and config.DONE_MARKER not in first:
                            sess.progress = first[:160]
                    elif btype == "tool_use":
                        desc = _describe(block)
                        if desc:
                            sess.progress = desc
            elif etype == "result":
                if evt.get("is_error") or evt.get("subtype") not in (None, "success"):
                    result_err = str(evt.get("result") or evt.get("subtype") or "unknown error")

        await proc.wait()
        await stderr_task

        signal = _interpret("\n".join(text_parts))
        if signal is not None:
            return signal

        if proc.returncode not in (0, None):
            err = (
                b"".join(stderr_buf).decode("utf-8", "replace").strip()
                or result_err
                or f"claude exited with code {proc.returncode}"
            )
            raise RuntimeError(err[:800])
        return None
    finally:
        # Guarantee the child is not orphaned on ANY exit — normal return, exception,
        # or cancellation (e.g. the per-turn timeout in _drive, or server shutdown).
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        if not stderr_task.done():
            stderr_task.cancel()
