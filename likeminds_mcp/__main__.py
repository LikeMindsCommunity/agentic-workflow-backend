"""Entrypoint: run the local MCP server over streamable HTTP.

    python -m likeminds_mcp

Clients connect at http://127.0.0.1:8787/mcp .
"""

from .config import HOST, PORT
from .server import mcp


def main() -> None:
    print(f"[likeminds-mcp] serving on http://{HOST}:{PORT}/mcp")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
