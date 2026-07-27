"""LikeMinds MCP server (local).

Exposes pipelines defined in `.claude/pipelines.json` via `run_pipeline` over
local HTTP. Each pipeline is a sequence of skills driven turn-by-turn as fresh
`claude -p` subprocesses (resume-per-turn): Claude Code's own on-disk session
store carries the conversation between rounds, so nothing is parked in memory
while a human answers. The engine is skill-agnostic — it only binds the I/O
edges (inputs dir / an <<<LM_ASK>>> marker to pause for the user / an
<<<LM_DONE>>> marker to finish); each skill's own logic decides everything else.
"""
