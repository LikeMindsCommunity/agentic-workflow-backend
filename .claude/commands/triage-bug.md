---
description: Enrich a vague bug report using codebase artifacts and add it to the bug backlog for review
---

You are a bug triage agent. Given the vague or unclear bug report in $ARGUMENTS, do the following:

## Step 1 — Read Project Context
Read `CLAUDE.md` in the current directory. Extract:
- `## File Index` section → locate relevant files
- `## Architecture Layers` or `## Pipeline Steps` → understand the system structure
- `## Bug Patterns` section → match against known failure modes

## Step 2 — Search Codebase Artifacts
Extract keywords from the raw report (e.g. "transitions", "variables", "crash", "nested", "output").
Use those keywords to:

1. **Grep the codebase** for matching function names, class names, error strings, and log messages
2. **Check Bug Patterns** in CLAUDE.md — does the raw report match any known pattern? If yes, use that pattern's description as a strong hint
3. **Run `git log --oneline -20`** — check if recent commits touched files related to the keywords
4. **Search for error strings** in the codebase that match words in the raw report

## Step 3 — Enrich the Description
Using everything found in Step 2, build a specific and actionable bug description:
- Name the exact file and function where the issue likely lives
- Describe what the wrong behavior is and why it happens
- Reference the specific artifact that confirmed it (grep match, git commit, bug pattern)

If nothing was found in Step 2:
- Enriched Description = "Could not confirm from codebase — manual investigation needed"
- Evidence = "No matching code patterns, commits, or bug patterns found"

## Step 4 — Detect Multiple Bugs
If the raw report contains two distinct issues (e.g. "transitions broken AND variables missing"), create TWO separate rows in bug_backlog.md — one per issue. Each gets its own Ref ID.

## Step 5 — Deduplicate
Read `bug_backlog.md` and `approval_sheet.md`.
Check if a similar bug already exists:
- Similar Enriched Description to an existing backlog row → flag: `⚠️ Similar to REF-XXX already in backlog`
- Similar description already in approval_sheet.md → flag: `⚠️ Already tracked as BUG-XXX in approval sheet`
Still write the new row — just include the warning in the Evidence column.

## Step 6 — Write to bug_backlog.md
Read existing Ref IDs to determine the next sequential ID.
Format: `REF-YYYY-MM-DD-NNN` (sequential per day)

Append a new row to the table in `bug_backlog.md`:

| Ref ID | Reported | Raw Report | Enriched Description | Affected Area | Evidence | Should Fix | Reviewed By | Linked Bug ID |

- Ref ID = generated sequential ID
- Reported = today's date
- Raw Report = exact original input from $ARGUMENTS, unedited
- Enriched Description = specific actionable description from Step 3
- Affected Area = module name, file name, or pipeline step (e.g. "Step 5 — AddTransitions", "validation_agent.py", "Celery worker layer")
- Evidence = what confirmed the enrichment: grep match with file:line, git commit hash, or bug pattern name
- Should Fix = `PENDING_REVIEW`
- Reviewed By = `_pending_`
- Linked Bug ID = _(empty — filled later by /process-backlog)_

## Step 7 — Print Summary
Print:
- Ref ID assigned
- Raw Report (as received)
- Enriched Description
- Affected Area
- Evidence
- Any duplication warnings
- Reminder: "Open bug_backlog.md and change Should Fix to APPROVED or REJECTED. Then run /process-backlog to send approved bugs into the fix pipeline."
