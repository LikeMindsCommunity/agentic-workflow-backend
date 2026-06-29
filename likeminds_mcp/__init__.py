"""LikeMinds MCP server (local MVP).

Exposes the skills in `.claude/commands/` behind a single `run_skill` dispatch
tool over local HTTP, so a Claude Code client can invoke a skill and handle its
runtime questions through pause/resume round-trips — without ever seeing the
skill prompt. The skill runs server-side via the Claude Agent SDK.

This is the local-test MVP of the Confidential Multi-Skill MCP Platform LLD:
no OAuth, no Redis, no multi-tenancy, single in-process session store.
"""
