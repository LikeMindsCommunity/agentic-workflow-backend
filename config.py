import os
from dotenv import load_dotenv
load_dotenv()

ANTHROPIC_FOUNDRY_API_KEY = os.environ.get("ANTHROPIC_FOUNDRY_API_KEY", "")
ANTHROPIC_FOUNDRY_RESOURCE = os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE", "")
MODEL = "claude-sonnet-4-5"

# Env vars injected into every SDK agent subprocess.
# Routes through Azure AI Foundry instead of direct Anthropic API.
SDK_ENV: dict[str, str] = {
    "CLAUDE_CODE_USE_FOUNDRY": "1",
    "ANTHROPIC_FOUNDRY_API_KEY": ANTHROPIC_FOUNDRY_API_KEY,
    "ANTHROPIC_FOUNDRY_RESOURCE": ANTHROPIC_FOUNDRY_RESOURCE,
}
MAX_TOKENS = 64000

BASE_DIR = os.path.dirname(__file__)
INPUT_DIR = os.path.join(BASE_DIR, "inputs")
ARTIFACTS_DIR = os.path.join(INPUT_DIR, "sample_artifacts")
DOCS_DIR = os.path.join(INPUT_DIR, "docs")
SCRAPED_DOCS_DIR = os.path.join(DOCS_DIR, "scraped")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
INPUT_CONFIG_PATH = os.path.join(INPUT_DIR, "input_config.yaml")

MAX_AREAS_PER_ROUND = 5

# ---------------------------------------------------------------------------
# MCP: Playwright stealth browser — bypasses bot detection (Cloudflare, etc.)
# Uses rebrowser-playwright under the hood for fingerprint evasion.
# Requires Xvfb on Linux (runs headed for better stealth).
# ---------------------------------------------------------------------------
PLAYWRIGHT_MCP_SERVER = {
    "playwright": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@pvinis/playwright-stealth-mcp-server"],
    }
}

PLAYWRIGHT_TOOLS = ["mcp__playwright__*"]
