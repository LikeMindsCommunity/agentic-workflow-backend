"""In-memory session manager.

Each Session owns:
  - an AgentRunner (one ClaudeSDKClient bound to one asyncio task)
  - an ordered event log (replayable to late SSE subscribers)
  - a fan-out set of subscriber queues for live SSE delivery
"""

from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Optional  # noqa: F401
from uuid import uuid4

from .agent_runner import AgentRunner
from .schemas import SessionStatus


SESSIONS_INPUT_ROOT = Path("inputs/sessions")
SESSIONS_OUTPUT_ROOT = Path("outputs/sessions")
SESSION_TTL_SECONDS = 60 * 60 * 6  # 6h idle


class Session:
    def __init__(self, sid: str, skill: str, input_dir: Path, output_dir: Path, cwd: Optional[str] = None):
        self.id = sid
        self.skill = skill
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.cwd = cwd
        self.events: list[dict[str, Any]] = []
        self._subscribers: set[asyncio.Queue] = set()
        self.status: SessionStatus = "running"
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.updated_at = time.time()
        self.runner: AgentRunner | None = None

    async def push(self, event_type: str, data: dict[str, Any]) -> None:
        event = {"id": len(self.events), "type": event_type, "data": data}
        self.events.append(event)
        self.updated_at = time.time()

        if event_type == "turn_end":
            self.status = "idle"
        elif event_type == "turn_start":
            self.status = "running"
        elif event_type == "error":
            self.status = "error"
            self.error = data.get("message")
        elif event_type == "session_closed":
            if self.status not in ("error", "done"):
                self.status = "closed"

        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10_000)
        for event in self.events:
            q.put_nowait(event)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    def get(self, sid: str) -> Session:
        if sid not in self._sessions:
            raise KeyError(sid)
        return self._sessions[sid]

    async def create(
        self,
        skill: str,
        files: Iterable[tuple[str, bytes]],
        prompt: Optional[str],
        cwd: Optional[str] = None,
        first_message_override: Optional[str] = None,
    ) -> Session:
        sid = uuid4().hex[:16]
        input_dir = SESSIONS_INPUT_ROOT / sid
        output_dir = SESSIONS_OUTPUT_ROOT / sid / "kb"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        for name, content in files:
            safe_name = Path(name).name
            (input_dir / safe_name).write_bytes(content)

        session = Session(sid, skill, input_dir, output_dir, cwd=cwd)

        async def on_event(event_type: str, data: dict[str, Any]) -> None:
            await session.push(event_type, data)

        runner = AgentRunner(on_event=on_event, cwd=cwd)
        session.runner = runner

        if first_message_override:
            first_message = first_message_override
        else:
            first_message = self._compose_first_message(skill, input_dir, output_dir, prompt)
        runner.start(first_message)

        self._sessions[sid] = session
        return session

    @staticmethod
    def _compose_first_message(
        skill: str,
        input_dir: Path,
        output_dir: Path,
        prompt: Optional[str],
    ) -> str:
        body = (
            f"/{skill} {input_dir}\n\n"
            f"Save all output files to {output_dir} (override the default output path)."
        )
        if prompt and prompt.strip():
            body += "\n\nAdditional context from the user:\n" + prompt.strip()
        return body

    async def send_message(
        self,
        sid: str,
        text: str,
        files: Iterable[tuple[str, bytes]] = (),
    ) -> Session:
        session = self.get(sid)
        if session.status in ("closed", "error"):
            raise RuntimeError(f"Session is {session.status}")
        for name, content in files:
            safe_name = Path(name).name
            (session.input_dir / safe_name).write_bytes(content)
        if session.runner is None:
            raise RuntimeError("Session has no runner")
        await session.runner.send(text)
        return session

    async def stream(self, sid: str) -> AsyncIterator[dict[str, Any]]:
        session = self.get(sid)
        q = session.subscribe()
        try:
            while True:
                event = await q.get()
                yield event
                if event["type"] == "session_closed":
                    return
        finally:
            session.unsubscribe(q)

    async def close(self, sid: str, *, mark_done: bool = False) -> None:
        session = self._sessions.get(sid)
        if not session:
            return
        if mark_done:
            session.status = "done"
        if session.runner is not None:
            await session.runner.stop()
        self._cleanup_compare_files(session)
        # Keep the record so /result still works; cleanup happens on TTL sweep.

    @staticmethod
    def _cleanup_compare_files(session: Session) -> None:
        if session.skill not in ("find-bugs-exotel", "find-bugs") or not session.cwd:
            return
        for sub in ("generated", "expected"):
            d = Path(session.cwd) / "inputs" / "compare" / sub
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)

    async def delete(self, sid: str) -> None:
        await self.close(sid)
        session = self._sessions.pop(sid, None)
        if session is None:
            return
        self._cleanup_compare_files(session)
        for path in (session.input_dir, session.output_dir.parent):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)

    async def sweep_idle(self) -> None:
        now = time.time()
        stale = [
            sid
            for sid, s in self._sessions.items()
            if now - s.updated_at > SESSION_TTL_SECONDS
        ]
        for sid in stale:
            await self.delete(sid)
