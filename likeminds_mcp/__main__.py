"""Entrypoint: run the local MCP server over streamable HTTP.

    python -m likeminds_mcp

Clients connect at http://127.0.0.1:8787/mcp .
"""

from pathlib import Path
from dotenv import load_dotenv

# Load .env before any package module runs so env vars are set when
# config.py evaluates USE_R2 and other computed constants at import time.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .config import CLAUDE_BIN, HOST, MODEL, PORT
from .server import mcp


def main() -> None:
    print(f"[likeminds-mcp] serving on http://{HOST}:{PORT}/mcp")
    print(f"[likeminds-mcp] driving CLI: {CLAUDE_BIN}  (model: {MODEL or 'CLI default'})")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
