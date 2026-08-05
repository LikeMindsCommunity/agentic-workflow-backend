# Copyright 2026 LikeMinds
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Entrypoint: run the local MCP server over streamable HTTP.

    python -m likeminds_mcp

Clients connect at http://127.0.0.1:8787/mcp .
"""

from pathlib import Path
from dotenv import load_dotenv

# Load .env before any package module runs so env vars are set when
# config.py evaluates its computed constants at import time.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .config import CLAUDE_BIN, HOST, MODEL, PORT
from .server import mcp


def main() -> None:
    print(f"[likeminds-mcp] serving on http://{HOST}:{PORT}/mcp")
    print(f"[likeminds-mcp] driving CLI: {CLAUDE_BIN}  (model: {MODEL or 'CLI default'})")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
