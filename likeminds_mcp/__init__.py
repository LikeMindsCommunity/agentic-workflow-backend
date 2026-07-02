"""LikeMinds MCP server (local).

Exposes every skill in `.claude/` behind a single `run_skill` dispatch tool over
local HTTP, so a Claude Code client can invoke any skill and handle its runtime
questions through pause/resume round-trips — without ever seeing the skill prompt.

Each turn runs server-side as a fresh `claude -p` subprocess (resume-per-turn):
Claude Code's own on-disk session store carries the conversation between rounds, so
nothing is parked in memory while a human answers. The engine is skill-agnostic —
it only binds the I/O edges (inputs dir / an <<<LM_ASK>>> marker to pause for the
user / an <<<LM_DONE>>> marker to finish); the skill's own logic decides everything
else.
"""
