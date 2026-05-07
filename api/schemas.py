from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# Status reflects the agent loop, independent of any skill semantics:
#   running  — agent is producing output (tool calls, text, …)
#   idle     — agent finished its turn; the user can speak next
#   done     — explicitly closed (Mark done) or runner exited cleanly
#   error    — runner raised
#   closed   — session deleted
SessionStatus = Literal["running", "idle", "done", "error", "closed"]


class SessionCreated(BaseModel):
    session_id: str
    status: SessionStatus
    skill: str
    input_dir: str
    output_dir: str
    stream_url: str
    messages_url: str
    result_url: str


class SessionState(BaseModel):
    session_id: str
    status: SessionStatus
    skill: str
    turns: int
    error: Optional[str] = None
    created_at: float
    updated_at: float


class MessageIn(BaseModel):
    text: str = Field(..., description="User reply forwarded to the running agent.")


class Event(BaseModel):
    id: int
    type: str
    data: Any
