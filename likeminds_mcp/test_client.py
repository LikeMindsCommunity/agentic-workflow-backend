"""Interactive test client for the local likeminds MCP server.

Drives run_skill end-to-end from the terminal: invoke any skill, see its questions,
type answers, repeat until the deliverable is emitted. No Claude Code needed.

Usage (server must already be running on :8787):

    .venv/bin/python -m likeminds_mcp.test_client list
    .venv/bin/python -m likeminds_mcp.test_client run kb-builder path/to/artifact.json [more ...]
    .venv/bin/python -m likeminds_mcp.test_client run config-agent --context "Build the X config" --url https://docs...

On 'need_input' it prints the questions and reads your reply from stdin.
Type your answer and press Enter; type 'done' to stop and finish.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import timedelta
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:8787/mcp"
# A skill turn (read + research + draft) can take minutes; wait generously.
TOOL_TIMEOUT = timedelta(minutes=10)


def _parse(res):
    return json.loads(res.content[0].text)


async def list_skills():
    async with streamablehttp_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            out = _parse(await s.call_tool("list_skills", {}))
            for sk in out["skills"]:
                print(f"  {sk['name']:<28} {sk['description'][:80]}")


async def run(skill: str, files: list[str], context: str | None, urls: list[str],
              client: str | None = None, workspace_id: str | None = None):
    artifacts = []
    for f in files:
        p = Path(f)
        if not p.is_file():
            print(f"! not a file: {f}", file=sys.stderr)
            sys.exit(1)
        artifacts.append({"name": p.name, "content": p.read_text(encoding="utf-8")})

    async with streamablehttp_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()

            print(f">>> run_skill(skill={skill!r}, artifacts={len(artifacts)}) — this can take minutes…")
            payload = {"skill": skill, "artifacts": artifacts}
            if client:
                payload["client"] = client
            if workspace_id:
                payload["workspace_id"] = workspace_id
            if context:
                payload["context"] = context
            if urls:
                payload["urls"] = urls
            out = _parse(await s.call_tool("run_skill", payload, read_timeout_seconds=TOOL_TIMEOUT))

            # Poll/relay loop: keep calling until a terminal status.
            while True:
                status = out.get("status")
                if status == "need_input":
                    print("\n" + "=" * 60)
                    print("QUESTIONS FROM THE SKILL:")
                    for i, q in enumerate(out["questions"], 1):
                        print(f"  {i}. {q}")
                    print("=" * 60)
                    reply = input("Your reply (or 'done'): ").strip()
                    print(">>> continuing — this can take minutes…")
                    args = {"session_id": out["session_id"], "response": reply}
                elif status == "running":
                    print(f"    … {out.get('progress', '')}  (files: {out.get('files_written', 0)})")
                    args = {"session_id": out["session_id"]}
                else:
                    break
                out = _parse(await s.call_tool("run_skill", args, read_timeout_seconds=TOOL_TIMEOUT))

            print("\n" + "=" * 60)
            print("FINAL RESULT:")
            print(json.dumps(out, indent=2))
            if out.get("status") == "done":
                cl, ws = out.get("client"), out.get("workspace_id")
                print(f"\nWorkspace : {cl}/{ws}")
                print(f"KB (persistent): outputs/{cl}/{ws}/kb/")
                print(f"Download  : {out.get('download_url')}")
                print(f"Reuse client={cl!r} workspace_id={ws!r} in a new run to extend this KB.")


def main():
    ap = argparse.ArgumentParser(prog="likeminds_mcp.test_client")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    rp = sub.add_parser("run")
    rp.add_argument("skill")
    rp.add_argument("files", nargs="*", help="artifact files to send as inputs")
    rp.add_argument("--context", default=None)
    rp.add_argument("--url", action="append", dest="urls", default=[])
    rp.add_argument("--client", default=None, help="tenant label (durable)")
    rp.add_argument("--workspace-id", dest="workspace_id", default=None,
                    help="durable project id; reuse to extend the same KB")
    args = ap.parse_args()

    if args.cmd == "list":
        asyncio.run(list_skills())
    else:
        asyncio.run(run(args.skill, args.files, args.context, args.urls,
                        args.client, args.workspace_id))


if __name__ == "__main__":
    main()
