"""The two engine signal tools, exposed to the server-side Claude as in-process
SDK MCP tools.

The model treats `ask_user` and `emit_result` as ordinary tools. The engine
treats them specially: `ask_user` is the pause signal, `emit_result` is the
finish signal (see engine_sdk.run_until_signal, which reads the tool-use blocks
off the stream). The handlers here only need to return a benign acknowledgement
so the SDK turn can complete cleanly.
"""

from __future__ import annotations

from claude_agent_sdk import create_sdk_mcp_server, tool


@tool(
    "ask_user",
    "Relay the skill's gap block to the client VERBATIM. Pass the entire block as "
    "a single string in `questions`, exactly as the skill formats it for an "
    "interactive user — do not reformat into objects, and do not add, drop, or "
    "invent items.",
    {"questions": list},
)
async def ask_user(args):
    # The engine reads `questions` directly from the tool-use block; we just
    # acknowledge and instruct the model to stop until the reply arrives.
    return {
        "content": [
            {
                "type": "text",
                "text": "Questions delivered to the user. Stop now and wait — "
                "their reply will arrive as the next message. Do not take "
                "further action.",
            }
        ]
    }


@tool(
    "emit_result",
    "Call when the deliverable is complete AND all final files have been fully "
    "written into the output/ directory. The engine collects the actual file "
    "contents from output/ — do NOT inline content here. Pass `files` only as a "
    "short manifest: the list of filenames you wrote (e.g. {name: '00-overview.md'}).",
    {"files": list},
)
async def emit_result(args):
    return {
        "content": [
            {"type": "text", "text": "Deliverable received. The session is complete."}
        ]
    }


def build_signals_server():
    """Create the in-process MCP server holding the two signal tools.

    Tools become callable as `mcp__signals__ask_user` / `mcp__signals__emit_result`.
    """
    return create_sdk_mcp_server(
        name="signals", version="1.0.0", tools=[ask_user, emit_result]
    )
