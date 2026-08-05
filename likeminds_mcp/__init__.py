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

"""LikeMinds MCP server (local).

Exposes pipelines defined in `.claude/pipelines.json` via `run_pipeline` over
local HTTP. Each pipeline is a sequence of skills driven turn-by-turn as fresh
`claude -p` subprocesses (resume-per-turn): Claude Code's own on-disk session
store carries the conversation between rounds, so nothing is parked in memory
while a human answers. The engine is skill-agnostic — it only binds the I/O
edges (inputs dir / an <<<LM_ASK>>> marker to pause for the user / an
<<<LM_DONE>>> marker to finish); each skill's own logic decides everything else.
"""
