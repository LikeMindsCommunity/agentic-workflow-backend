"""
LikeMinds Layer 1 - Knowledge Base Builder

Entry point. Delegates to orchestrator.main().
"""
import sys

import anyio
from claude_agent_sdk import query, ClaudeAgentOptions

try:
    import claude_agent_sdk  # noqa: F401
except ImportError:
    print("\n  [ERROR] claude-agent-sdk not installed.")
    print("  Run: pip install claude-agent-sdk\n")
    sys.exit(1)

from orchestrator import main

# async def main():
#     async for message in query(
#         prompt="hello",
#         options=ClaudeAgentOptions(
#             model="claude-sonnet-4-5",
#         ),
#     ):
#         print(message)

if __name__ == "__main__":
    anyio.run(main)
