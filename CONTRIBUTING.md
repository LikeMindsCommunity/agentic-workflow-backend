# Contributing to LikeMinds Agentic Workflow Backend

Thanks for taking the time to contribute. This document covers how to report bugs, propose features, and submit code.

---

## Reporting bugs

Open a GitHub issue and include:

- What you did
- What you expected to happen
- What actually happened
- Your OS, Python version, and Claude Code CLI version (`claude --version`)
- Relevant logs from the server output

---

## Proposing features

Open a GitHub issue describing:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you considered

For large changes, open an issue before writing code so we can discuss the approach first.

---

## Submitting code

1. Fork the repo and create a branch from `master`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes. Keep commits focused - one logical change per commit.

3. Test your changes locally:
   ```bash
   # Start the server
   venv/bin/python -m likeminds_mcp

   # Verify it connects and pipelines load
   # Run /mcp in Claude Code and check likeminds shows as connected
   ```

4. Open a pull request against `master`. Describe what you changed and why.

---

## Adding a custom skill

The easiest contribution is a new Agent Skill. Skills are plain markdown files - no Python required.

1. Create a folder under `.claude/skills/<skill-name>/`
2. Add a `SKILL.md` file with the skill's instructions
3. Add the skill to a pipeline in `.claude/pipelines.json` (or create a new pipeline)
4. Test it end to end with `@likeminds`

See the existing skills in `.claude/skills/` for reference.

---

## Code style

- Python 3.10+
- Follow the existing style in `likeminds_mcp/` - no strict linter enforced, just keep it readable
- Add the Apache 2.0 license header to any new `.py` files:
  ```python
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
  ```

---

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
