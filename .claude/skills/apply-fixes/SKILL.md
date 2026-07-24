---
name: apply-fixes
description: Apply every APPROVED fix from a client's approval sheet (outputs/{client}/approval_sheet.md) to the source code — read each approved row, verify the code still matches the documented root cause, make the change, mark the row APPLIED, and create one git commit for all of them. The only step permitted to modify source files or commit. Use after a reviewer has marked rows APPROVED (following diagnose-bug or process-comparison). Also supports a KB target (target=kb): apply approved KB amendments into a knowledge base in place — editing the KB files and logging the round, with no git commit — as the final step of the kb-feedback pipeline. Triggers: "apply the approved fixes", "apply-fixes", "apply the fixes in {client}'s approval sheet".
---

# Apply Approved Fixes

You are applying approved bug fixes from `outputs/{client}/approval_sheet.md`. Follow this exact process:

## Target: code (default) or KB

Check the run parameters / $ARGUMENTS for a `target=` selector before anything else:

- **`target=code`** (the default when no `target=` is present) — apply source-code fixes and commit, exactly as described in the rest of this document.
- **`target=kb`** — apply approved **KB amendments** into a knowledge base in place. Skip the code steps and the git commit below and follow the **[KB mode](#kb-mode--targetkb)** section at the end of this file.

Everything below up to the "KB mode" section is the `target=code` flow, and applies only when you were NOT sent `target=kb`.

## Inputs & Paths — resolve the client first
The approval sheet is stored per client at `outputs/{client}/approval_sheet.md`. Resolve `{client}` before reading it:
1. `client=<name>` in $ARGUMENTS → use it.
2. `output=<dir>` in $ARGUMENTS → the approval sheet is `<dir>/approval_sheet.md` (skip inference).
3. Otherwise infer `{client}` from context: an inputs/artifacts folder name or a client name in $ARGUMENTS or the prompt, or the parent folder of a `kb=<dir>` if one is given.
4. Still unresolved → if exactly one `outputs/*/` client directory exists, use it; otherwise ASK the user which client and STOP. Never guess.

Every step below reads and updates this resolved `outputs/{client}/approval_sheet.md`.

## Step 1: Read the Approval Sheet
Read `outputs/{client}/approval_sheet.md`. Parse the table rows.

## Step 2: Find APPROVED Entries
Find all rows with Status = `APPROVED`. If none found, inform the user and stop.

## Step 3: For Each APPROVED Row (in order)
For each approved fix:

1. **Announce**: Print the Bug ID and summary you are about to apply
2. **Read affected files**: Use the "Affected Files" column to find exactly which files and line ranges to read
3. **Verify current state**: Confirm the code at those lines matches what the root cause describes. If the code has already changed, SKIP this entry.
4. **Apply the fix**: Make the changes described in "Fix Description" at the locations specified in "Affected Files"
5. **Verify**: Re-read the modified lines to confirm correctness
6. **Update the sheet**: Change the row's Status from `APPROVED` to `APPLIED` and add the date

## Step 4: Create a Git Commit
Stage all modified files (both code changes and the updated `outputs/{client}/approval_sheet.md`).
Create a single commit with the message format:
```
fix: apply approved bug fixes {BUG-IDs}

Applied fixes:
- BUG-YYYY-MM-DD-N: {summary}
- BUG-YYYY-MM-DD-N: {summary}
```

## Step 5: Summary Report
Print:
- Number of fixes applied
- Number of fixes skipped (with reasons)
- List of files modified
- The git commit hash

## Important Rules
- NEVER apply a fix with Status other than APPROVED
- Before applying any fix, read the `## Constraints` section of CLAUDE.md and follow all rules listed there
- If a fix conflicts with current code state, SKIP it and mark Status as `CONFLICT`
- Create ONE commit for all applied fixes, not separate commits per fix

---

# KB mode — `target=kb`

Follow this section INSTEAD of the code steps above when the run parameters contain `target=kb`. You apply approved **KB amendments** into a knowledge base **in place**: edit the KB files, log the round, and — unlike code mode — make **no git commit**. Persistence is the file write itself; the harness merges your `output=` dir back into the KB's own bucket.

## Inputs & Paths (KB mode)
- **The approval sheet** — `inputs=/feedback/approval_sheet.md`, written by diagnose-bug in KB mode and threaded in. It lists the proposed amendments and their Status.
- **The KB** — the files staged into your `inputs=` dir (everything except the `feedback/`, `generated/` and `expected/` subdirs). Each KB file sits at some path relative to `inputs=`; you write the amended version to the **same relative path** under `output=`.
- **Write everything into `output=`**: amended KB files at their original relative paths, the updated sheet at `output=/feedback/approval_sheet.md`, and the gap log at `output=/feedback/kb_gap_log.md`. The harness merges `output=` back into the KB bucket, so writing only the files you changed updates the KB in place.

## Step K1 — Read the sheet and select what to apply
Read `inputs=/feedback/approval_sheet.md`. Only rows whose **Change Type** is `KB-ADD` or `KB-FIX` are applicable — `KB_IGNORED` and `ASK` rows are never applied here (see K4).

Decide the approved set:
- If any applicable rows already have **Status = APPROVED** (a reviewer pre-approved them on the sheet), apply exactly those.
- Otherwise (rows are still PENDING and nothing is approved), get approval before changing anything: **present the proposed amendments and ask which to apply.** List each as `Item ID — Change Type — KB Location — Proposed Amendment`, and ask the user to reply `all`, a list of Item IDs, or `none`. Treat the reply as the approved set (`all` = every applicable row, a list = those IDs, `none` = apply nothing and stop). Never apply an amendment the user did not approve.

## Step K2 — Apply each approved amendment to the KB
For each approved row, in sheet order:
1. **Announce** the Item ID and the KB Location it targets.
2. **Open the target KB file** at `inputs=/<relative path>` and locate the exact section named in KB Location.
3. **Verify** the KB still matches what the row assumes — for a KB-FIX the wrong value is still present; for a KB-ADD the fact is still absent. If it no longer matches, SKIP the row and mark it `CONFLICT`.
4. **Make the change** — add the fact or correct the value exactly as written in Proposed Amendment, **with its units**. Conform to the file's existing headings, table shapes and vocabulary; never rename or re-bucket settled content.
5. **Write the amended file** to `output=/<same relative path>`. Write only files you actually changed.

## Step K3 — Log the round
Append an entry to `output=/feedback/kb_gap_log.md` (create it if missing) — the KB's memory of what feedback changed it:

```
## <today's date> — feedback round
- KB-YYYY-MM-DD-NNN (KB-ADD): <one line — what was added, to which file/section>
- KB-YYYY-MM-DD-NNN (KB-FIX): <one line — what was corrected>
```

## Step K4 — Update the sheet, report, and STOP
Write the updated sheet to `output=/feedback/approval_sheet.md` with each row's Status set to its outcome:
- applied rows → `APPLIED` (add today's date)
- rows skipped for a stale / mismatched KB → `CONFLICT`
- `KB_IGNORED` rows → `ESCALATED` (generator defects — recommend a `target=code` diagnose-bug run on the generator; do NOT edit the KB for them)
- `ASK` rows → leave `PENDING` (they need the user's decision first)

Then print a summary: which KB files changed, counts by outcome, the escalated (KB_IGNORED) items, and this exact line: `KB amended in place and written back to its bucket. No git commit was made (the KB is not tracked in git).`

## KB-mode rules
1. **No git.** Never stage, commit, branch, or push in KB mode — the KB lives outside git; the file write IS the persistence.
2. **Only KB-ADD / KB-FIX are applied.** KB_IGNORED is a generator defect (escalate, never "fix" in the KB); ASK needs a human decision first.
3. **Approve before you write.** If nothing is pre-approved, ask, and apply only what the user approves. Never auto-apply PENDING rows.
4. **Amendment text is authoritative, units included.** Write the value exactly as the approved row states it; do not round or reinterpret.
5. **Conform to the KB's shape.** Edit within the existing files and sections; do not restructure the KB to fit a new fact.
