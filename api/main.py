"""FastAPI app exposing Claude Code skills (e.g. /platform-kb) via HTTP + SSE.

Routes
------
POST   /sessions                 — multipart upload + skill name; spawns agent
GET    /sessions/{id}            — session state snapshot
GET    /sessions/{id}/stream     — SSE stream of agent events (live + replay)
POST   /sessions/{id}/messages   — send user reply (JSON or multipart with files)
POST   /sessions/{id}/done       — mark session done (idempotent)
GET    /sessions/{id}/result     — fetch KB output (?format=zip|json)
DELETE /sessions/{id}            — close + delete session and files
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from .schemas import MessageIn, SessionCreated, SessionState
from .sessions import SessionManager


load_dotenv()
manager = SessionManager()

# ───────────────────── skill discovery ───────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIRS = [
    PROJECT_ROOT / "commands",
    PROJECT_ROOT / ".claude" / "commands",
]


def _discover_skills() -> list[dict[str, str]]:
    """Scan skill directories and return [{name, description}, ...]."""
    seen: set[str] = set()
    skills: list[dict[str, str]] = []
    for d in SKILL_DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            name = f.stem
            if name in seen:
                continue
            seen.add(name)
            desc = ""
            text = f.read_text(errors="replace")
            m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
            if m:
                desc = m.group(1).strip()
            if not desc:
                m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                if m:
                    desc = m.group(1).strip()
            skills.append({"name": name, "description": desc})
    return skills


SKILL_REGISTRY = _discover_skills()


@asynccontextmanager
async def lifespan(app: FastAPI):
    sweeper = asyncio.create_task(_periodic_sweep())
    try:
        yield
    finally:
        sweeper.cancel()


async def _periodic_sweep() -> None:
    try:
        while True:
            await asyncio.sleep(15 * 60)
            await manager.sweep_idle()
    except asyncio.CancelledError:
        return


app = FastAPI(title="Claude Skill API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("API_CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Swagger UI (bundled with FastAPI) renders OpenAPI 3.1 `contentMediaType` arrays
# as `array<string>` with an "Add string item" button instead of a file picker.
# Downgrade the spec to 3.0.3 and rewrite binary fields to use `format: binary`.
def _rewrite_binary(schema: dict) -> None:
    if not isinstance(schema, dict):
        return
    if (
        schema.get("type") == "string"
        and schema.get("contentMediaType") == "application/octet-stream"
    ):
        schema["format"] = "binary"
        schema.pop("contentMediaType", None)
    for v in schema.values():
        if isinstance(v, dict):
            _rewrite_binary(v)
        elif isinstance(v, list):
            for item in v:
                _rewrite_binary(item)


app.openapi_version = "3.0.3"
_orig_openapi = app.openapi


def _custom_openapi():
    schema = _orig_openapi()
    schema["openapi"] = "3.0.3"
    _rewrite_binary(schema)
    return schema


app.openapi = _custom_openapi  # type: ignore[assignment]


# ───────────────────────── helpers ─────────────────────────

def _state(session) -> SessionState:
    return SessionState(
        session_id=session.id,
        status=session.status,
        skill=session.skill,
        turns=session.runner.turns if session.runner else 0,
        error=session.error,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _require_session(sid: str):
    try:
        return manager.get(sid)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found") from exc


async def _read_uploads(files: list[UploadFile] | None) -> list[tuple[str, bytes]]:
    if not files:
        return []
    out: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        out.append((f.filename or "upload.bin", content))
    return out


# ───────────────────────── routes ──────────────────────────

@app.get("/skills")
async def list_skills():
    """List all available skills with descriptions."""
    return SKILL_REGISTRY


@app.post("/sessions", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: Request,
    skill: str = Form("platform-kb"),
    prompt: Optional[str] = Form(None),
    project_dir: Optional[str] = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    generated_file: Optional[UploadFile] = File(default=None),
    expected_file: Optional[UploadFile] = File(default=None),
):
    import shutil

    session_cwd: Optional[str] = None
    final_prompt = prompt

    if skill in ("find-bugs-exotel", "find-bugs"):
        if not generated_file or not expected_file:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"{skill} requires both generated_file and expected_file",
            )
        target_dir = Path(project_dir) if project_dir else Path.cwd()
        if not target_dir.is_dir():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Project directory does not exist: {target_dir}",
            )
        session_cwd = str(target_dir)

        gen_dir = target_dir / "inputs" / "compare" / "generated"
        exp_dir = target_dir / "inputs" / "compare" / "expected"
        for d in [gen_dir, exp_dir]:
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
        (gen_dir / (generated_file.filename or "generated.json")).write_bytes(
            await generated_file.read()
        )
        (exp_dir / (expected_file.filename or "expected.json")).write_bytes(
            await expected_file.read()
        )

        compare_msg = (
            f"/{skill}\n\n"
            f"Compare the files in inputs/compare/generated/ "
            f"against inputs/compare/expected/."
        )
        if prompt and prompt.strip():
            compare_msg += "\n\nAdditional context from the user:\n" + prompt.strip()
        final_prompt = prompt
        first_msg = compare_msg
    elif project_dir:
        target_dir = Path(project_dir)
        if target_dir.is_dir():
            session_cwd = str(target_dir)
        first_msg = None
    else:
        first_msg = None

    uploads = await _read_uploads(files)
    session = await manager.create(
        skill=skill,
        files=uploads,
        prompt=final_prompt,
        cwd=session_cwd,
        first_message_override=first_msg,
    )
    base = str(request.base_url).rstrip("/")
    return SessionCreated(
        session_id=session.id,
        status=session.status,
        skill=session.skill,
        input_dir=str(session.input_dir),
        output_dir=str(session.output_dir),
        stream_url=f"{base}/sessions/{session.id}/stream",
        messages_url=f"{base}/sessions/{session.id}/messages",
        result_url=f"{base}/sessions/{session.id}/result",
    )


@app.get("/sessions/{sid}", response_model=SessionState)
async def get_session(sid: str):
    return _state(_require_session(sid))


@app.get("/sessions/{sid}/stream")
async def stream_session(sid: str, request: Request):
    session = _require_session(sid)

    async def event_generator():
        async for event in manager.stream(session.id):
            if await request.is_disconnected():
                break
            yield {
                "id": str(event["id"]),
                "event": event["type"],
                "data": json.dumps(event["data"], ensure_ascii=False),
            }

    return EventSourceResponse(event_generator(), ping=20)


@app.post("/sessions/{sid}/messages", response_model=SessionState)
async def post_message(
    sid: str,
    request: Request,
    text: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
):
    """Accepts either JSON ({text}) or multipart (text + optional files)."""
    session = _require_session(sid)

    content_type = request.headers.get("content-type", "")
    uploads: list[tuple[str, bytes]] = []
    body_text: Optional[str] = text

    if content_type.startswith("application/json"):
        body = await request.json()
        try:
            payload = MessageIn.model_validate(body)
        except Exception as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
        body_text = payload.text
    else:
        uploads = await _read_uploads(files)

    if not body_text or not body_text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "`text` is required")

    if session.status in ("closed", "error", "done"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Session is {session.status}")

    await manager.send_message(session.id, body_text, uploads)
    return _state(session)


@app.post("/sessions/{sid}/done", response_model=SessionState)
async def mark_done(sid: str):
    session = _require_session(sid)
    await manager.close(session.id, mark_done=True)
    return _state(session)


@app.get("/sessions/{sid}/result")
async def get_result(sid: str, format: str = Query("zip", pattern="^(zip|json)$")):
    session = _require_session(sid)
    output_dir: Path = session.output_dir
    if not output_dir.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Output directory not yet created")

    files = sorted(p for p in output_dir.rglob("*") if p.is_file())
    if not files:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No output files yet")

    if format == "json":
        payload = []
        for p in files:
            try:
                content = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            payload.append({"path": str(p.relative_to(output_dir)), "content": content})
        return JSONResponse({"session_id": sid, "files": payload})

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, arcname=str(p.relative_to(output_dir)))
    buf.seek(0)
    filename = f"kb-{sid}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/sessions/{sid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(sid: str):
    _require_session(sid)
    await manager.delete(sid)
    return None


def _parse_md_table(file_path: Path) -> list[dict]:
    if not file_path.exists():
        return []
    lines = file_path.read_text().splitlines()
    table_lines = [l for l in lines if "|" in l]
    if len(table_lines) < 3:
        return []
    headers = [h.strip() for h in table_lines[0].split("|") if h.strip()]
    rows = []
    for line in table_lines[2:]:
        cells = [c.strip() for c in line.split("|")]
        cells = cells[1:-1] if len(cells) >= 2 else cells
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


@app.get("/sessions/{sid}/comparison-sheet")
async def get_comparison_sheet(sid: str):
    """Return parsed comparison_sheet.md as JSON for find-bugs-exotel sessions."""
    session = _require_session(sid)
    from collections import Counter

    base = Path(session.cwd) if session.cwd else Path.cwd()
    sheet_path = base / "comparison_sheet.md"
    if not sheet_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "comparison_sheet.md not found yet")

    rows = _parse_md_table(sheet_path)
    by_category = dict(Counter(r.get("Category", "") for r in rows))
    by_risk = dict(Counter(r.get("Risk", "") for r in rows))

    return {
        "session_id": sid,
        "rows": rows,
        "summary": {
            "total": len(rows),
            "by_category": by_category,
            "by_risk": by_risk,
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "sessions": len(manager._sessions)}


def run() -> None:
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=os.environ.get("API_HOST", "0.0.0.0"),
        port=int(os.environ.get("API_PORT", "8000")),
        reload=bool(int(os.environ.get("API_RELOAD", "0"))),
    )


if __name__ == "__main__":
    run()
