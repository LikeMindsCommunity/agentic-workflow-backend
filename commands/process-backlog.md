---
description: Process all APPROVED bugs from bug_backlog.md through batch-fix and into approval_sheet.md
---

You are a backlog processing agent. Read `bug_backlog.md`, collect all APPROVED bugs, and send them through the batch-fix pipeline.

## Step 1 — Read bug_backlog.md
Parse the table in `bug_backlog.md`. Filter all rows where Should Fix = `APPROVED`.

If no APPROVED rows found: print "No approved bugs in backlog. Open bug_backlog.md and mark bugs as APPROVED to process them." and stop.

## Step 2 — Collect Enriched Descriptions
For each APPROVED row, take the value from the `Enriched Description` column.

If Enriched Description = "Could not confirm from codebase — manual investigation needed":
- Skip this row
- Print: `⚠️ Skipping REF-XXX — not enough information to diagnose. Investigate manually first, then use /fix-bug directly.`

Build a numbered list of all valid enriched descriptions:
```
1. <Enriched Description from REF-001>
2. <Enriched Description from REF-002>
3. <Enriched Description from REF-003>
```

## Step 3 — Pass to /batch-fix
Run the full `/batch-fix` workflow with the numbered list from Step 2 as input.

This means:
- For each enriched description, run the full /fix-bug workflow (read CLAUDE.md, classify, locate code + prompts, root cause analysis, propose fix)
- Write a PENDING row to approval_sheet.md for each
- After all are processed, run interaction analysis across all fixes:
  - Check 1: Same file conflicts (overlapping or adjacent ≤20 lines)
  - Check 2: Dependency order (earlier layer fixes that later layer fixes depend on)
  - Check 3: Cross-effect risk (fixes touching shared data structures or adjacent pipeline layers)
- Print the interaction summary table

## Step 4 — Write Linked Bug IDs back to bug_backlog.md
After /batch-fix completes, collect the Bug IDs assigned in approval_sheet.md (e.g. BUG-2026-03-27-001, BUG-2026-03-27-002).

Map them back to the source rows:
- First APPROVED row → first Bug ID assigned
- Second APPROVED row → second Bug ID assigned
- etc.

For each processed row in bug_backlog.md, write the assigned Bug ID into the `Linked Bug ID` column.

## Step 5 — Print Summary
Print:

```
✅ Backlog processed

  Bugs sent to fix pipeline: [N]
  Bugs skipped (unconfirmed): [N]

  Created in approval_sheet.md:
    BUG-YYYY-MM-DD-001 ← REF-YYYY-MM-DD-001 (bug text)
    BUG-YYYY-MM-DD-002 ← REF-YYYY-MM-DD-002 (bug text)

  Interaction warnings: [None / list warnings]
  Recommended apply order: [if interactions found]

Next steps:
  1. Open approval_sheet.md and review the new PENDING rows
  2. Change Status to APPROVED for fixes you want to apply
  3. Run /apply-fixes to apply approved fixes and create a git commit
```
