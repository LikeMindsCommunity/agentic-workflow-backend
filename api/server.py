import os
import shutil
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)

PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", os.getcwd()))
SKILLS_DIR = Path(__file__).resolve().parent.parent / "commands"

app = FastAPI(title="Find-Bugs-Exotel API", version="0.3.0")


def load_skill(skill_name: str) -> str:
    skill_path = SKILLS_DIR / f"{skill_name}.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill file not found: {skill_path}")
    content = skill_path.read_text()
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].strip()
    return content


def parse_md_table(file_path: Path) -> list[dict]:
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


@app.post("/upload")
async def upload_files(
    generated: UploadFile = File(...),
    expected: UploadFile = File(...),
):
    gen_dir = PROJECT_DIR / "inputs" / "compare" / "generated"
    exp_dir = PROJECT_DIR / "inputs" / "compare" / "expected"

    for d in [gen_dir, exp_dir]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    gen_path = gen_dir / generated.filename
    exp_path = exp_dir / expected.filename

    gen_path.write_bytes(await generated.read())
    exp_path.write_bytes(await expected.read())

    return {
        "generated": generated.filename,
        "expected": expected.filename,
        "message": "Files uploaded successfully",
    }


@app.post("/find-bugs-exotel")
async def find_bugs_exotel():
    gen_dir = PROJECT_DIR / "inputs" / "compare" / "generated"
    exp_dir = PROJECT_DIR / "inputs" / "compare" / "expected"

    if not gen_dir.exists() or not any(gen_dir.iterdir()):
        raise HTTPException(400, "No generated file found. Upload files first via POST /upload.")
    if not exp_dir.exists() or not any(exp_dir.iterdir()):
        raise HTTPException(400, "No expected file found. Upload files first via POST /upload.")

    try:
        system_prompt = load_skill("find-bugs-exotel")
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))

    user_prompt = (
        "Compare the Exotel IVR JSON in inputs/compare/generated/ "
        "against inputs/compare/expected/. "
        "Read CLAUDE.md first for the file index and project context. "
        "Follow every step in your instructions."
    )

    result_text = ""
    input_tokens = 0
    output_tokens = 0

    try:
        async for message in query(
            prompt=user_prompt,
            options=ClaudeAgentOptions(
                system_prompt=system_prompt,
                cwd=str(PROJECT_DIR),
                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                permission_mode="bypassPermissions",
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result_text = block.text
            elif isinstance(message, ResultMessage):
                input_tokens = getattr(message, "input_tokens", 0) or 0
                output_tokens = getattr(message, "output_tokens", 0) or 0
    except Exception as e:
        raise HTTPException(500, f"Agent error: {type(e).__name__}: {e}")

    sheet_path = PROJECT_DIR / "comparison_sheet.md"
    rows = parse_md_table(sheet_path)

    by_category = dict(Counter(r.get("Category", "") for r in rows))
    by_risk = dict(Counter(r.get("Risk", "") for r in rows))

    return {
        "status": "complete",
        "rows": rows,
        "summary": {
            "total": len(rows),
            "by_category": by_category,
            "by_risk": by_risk,
        },
        "agent_stats": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }


@app.get("/comparison-sheet")
async def get_comparison_sheet():
    sheet_path = PROJECT_DIR / "comparison_sheet.md"

    if not sheet_path.exists():
        raise HTTPException(404, "comparison_sheet.md not found. Run /find-bugs-exotel first.")

    rows = parse_md_table(sheet_path)

    by_category = dict(Counter(r.get("Category", "") for r in rows))
    by_risk = dict(Counter(r.get("Risk", "") for r in rows))

    return {
        "rows": rows,
        "summary": {
            "total": len(rows),
            "by_category": by_category,
            "by_risk": by_risk,
        },
    }
