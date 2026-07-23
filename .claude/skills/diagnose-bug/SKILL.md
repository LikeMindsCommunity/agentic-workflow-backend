---
name: diagnose-bug
description: Validate one or more bug reports and, for each real defect, diagnose the root cause and propose a fix as a PENDING row in the client's approval sheet (outputs/{client}/approval_sheet.md) — validate-only, never editing source or committing. Handles a single bug, a batch (with cross-fix interaction analysis), or "sheet" mode over existing rows. Use when a bug is reported and you want it triaged and a fix proposed for review. Also supports a KB target (target=kb): instead of source code, it analyses a knowledge base against a user's complaint about a deliverable it produced and proposes amendments to that KB for review — used by the kb-feedback pipeline. Triggers: "diagnose this bug", "diagnose-bug", "is this a real bug and what is the fix", "triage these bugs for {client}".
---

You are a bug diagnosis agent. Given one or more bug reports in $ARGUMENTS, do the following.

## Target: code (default) or KB

Check the run parameters / $ARGUMENTS for a `target=` selector before anything else:

- **`target=code`** (the default when no `target=` is present) — the source-code bug flow in the rest of this document (Phases A–D).
- **`target=kb`** — the **KB-feedback** flow. Skip Phases A–D entirely and follow the **[KB mode](#kb-mode--targetkb)** section at the end of this file: you analyse a knowledge base against a user's complaint about a deliverable it produced and propose amendments to the KB, rather than diagnosing source code.

Everything below this point up to the "KB mode" section is the `target=code` flow, and applies only when you were NOT sent `target=kb`.

This skill merges three jobs into one: it **validates** a report (is this a real, actionable bug?), and if valid it **diagnoses** and **proposes a fix** — handling a single bug like a focused diagnosis and multiple bugs like a batch with interaction analysis.

If $ARGUMENTS is `sheet`, skip validation and diagnosis: read all PENDING/APPROVED rows from `outputs/{client}/approval_sheet.md` and run only the batch **Interaction Analysis** (Phase C) over them.

## Scope — this skill PROPOSES fixes, it does NOT apply them

This skill only: (a) validates, (b) diagnoses, (c) writes one row with `Status = PENDING` to `outputs/{client}/approval_sheet.md` per valid bug, and (d) prints a summary. The user then reviews, flips `Status` to `APPROVED` or `REJECTED`, and runs the **apply-fixes** skill — which is the **only** step allowed to modify source files or create commits.

While this command is running you MUST NOT:
- Use `Edit`, `Write`, or `NotebookEdit` on any file other than `outputs/{client}/approval_sheet.md`.
- Run any `git` command that changes repository state (`add`, `commit`, `checkout`, `reset`, `stash`, `push`, etc.). Read-only `git status` / `git log` / `git diff` are fine for diagnosis.
- Create, rename, or delete files anywhere in the repo.
- Mark the row with any `Status` other than `PENDING` — not `APPROVED`, not `APPLIED`, not `CONFLICT`.

If you notice a trivial one-line fix while diagnosing, STILL do not apply it — write the row, stop, and let the user approve. The approval step exists even for "obvious" fixes.

## Inputs & Paths — resolve the client first
Tracking sheets live per client under `outputs/{client}/`. Resolve `{client}` before anything else:
1. `client=<name>` in $ARGUMENTS → use it.
2. `output=<dir>` in $ARGUMENTS → use that directory as the client folder directly (skip inference).
3. Otherwise infer `{client}` from context: an inputs/artifacts folder name or a client name in $ARGUMENTS or the prompt, or the parent folder of a `kb=<dir>` if one is given.
4. Still unresolved → if exactly one `outputs/*/` client directory exists, use it; otherwise ASK the user which client and STOP. Never guess.

**The approval sheet** for this run is `outputs/{client}/approval_sheet.md` — one per client, created if missing and appended to across runs (with `output=<dir>`, it is `<dir>/approval_sheet.md`). Every read and write below uses this resolved path. Everything left in $ARGUMENTS after the `client=` / `output=` / `kb=` tokens are removed is the bug report(s) or the literal `sheet` — that remainder is what Phase 0 parses.

## Phase 0 — Parse Input & Decide Mode
- If $ARGUMENTS is `sheet` → **batch mode over the existing sheet**: read all PENDING/APPROVED rows from `outputs/{client}/approval_sheet.md` and skip directly to Phase C.
- Otherwise, split $ARGUMENTS into individual bug reports. Treat it as multiple bugs when the input uses a numbering pattern (`\d+\.`), is separated into clearly distinct issues by newlines, or joins two distinct problems with "AND" (e.g. "transitions broken AND variables missing").
- **One report → single mode**: run Phase A (validate) then Phase B (diagnose) for that one bug, then Phase D.
- **Multiple reports → batch mode**: run Phase A + Phase B for each report independently, then Phase C (interaction analysis), then Phase D.

Assign sequential Bug IDs within the same date across all bugs written this run: `BUG-YYYY-MM-DD-001`, `BUG-YYYY-MM-DD-002`, etc.

## Phase A — Validate the Issue (gate)
Before proposing any fix, confirm the report describes a real, actionable bug. Do NOT skip this phase.

### A1 — Read Project Context
Read `CLAUDE.md` in the current directory. Extract:
- `## File Index` section → locate relevant files
- `## Architecture Layers` or `## Pipeline Steps` → understand the system structure
- `## Bug Patterns` section → match against known failure modes

### A2 — Search Codebase Artifacts
Extract keywords from the raw report (e.g. "transitions", "variables", "crash", "nested", "output"). Use those keywords to:

1. **Grep the codebase** for matching function names, class names, error strings, and log messages
2. **Check Bug Patterns** in CLAUDE.md — does the raw report match any known pattern? If yes, that is strong confirmation
3. **Run `git log --oneline -20`** — check if recent commits touched files related to the keywords
4. **Search for error strings** in the codebase that match words in the raw report

### A3 — Deduplicate
Read `outputs/{client}/approval_sheet.md`. If a similar bug is already tracked as an existing `BUG-XXX` with Status PENDING or APPROVED, this report is a duplicate:
- Print `⚠️ Already tracked as BUG-XXX in approval sheet` and do NOT write a second row for it. Treat it like an invalid/skip for the purpose of writing (in batch mode, continue to the next bug).

### A4 — Verdict
Decide whether the report is a **valid issue**:
- **VALID** if any of the following hold: it maps to real code/behavior that is actually wrong; it matches a known Bug Pattern; grep or a recent commit provides concrete evidence of the defect.
- **NOT VALID** if: it is a feature request, question, or general remark rather than a defect; the code already does the right thing (the report is contradicted by what you read); or it is too vague to locate anything AND no matching code, commit, or bug pattern was found.

If **NOT VALID** → print:
```
❌ Not a valid issue: <one-line reason>
Checked: <what you grepped, which bug patterns, which commits/files>
Nothing was written to outputs/{client}/approval_sheet.md.
```
Then **return** for that bug. Write nothing to `outputs/{client}/approval_sheet.md`. In single mode, stop here. In batch mode, record it under "Skipped (not a valid issue)" and continue with the remaining bugs.

If **VALID** → proceed to Phase B for that bug.

## Phase B — Diagnose & Propose Fix (per valid bug)
Run this for each bug that passed Phase A. This is a text-only proposal — do not edit any file you read here.

### B1 — Classify the Bug
Using the Architecture Layers or Pipeline Steps from CLAUDE.md, classify this bug into the layer or step most likely responsible. Do NOT use a hardcoded category list — use whatever layers THIS project has defined in CLAUDE.md.

### B2 — Locate Relevant Code AND Prompts
- Use the File Index from CLAUDE.md to locate the relevant file(s)
- For any file flagged as LARGE FILE in CLAUDE.md, grep for the specific function or class rather than reading the full file
- IF `## Prompt/Template Mapping` section exists in CLAUDE.md: also read the corresponding prompt or template file for the affected module (dual-layer analysis)
- ELSE: pure code analysis only — skip the prompt layer entirely

### B3 — Root Cause Analysis
Determine the bug layer:
- **Code bug**: Logic is wrong regardless of any template or LLM output
- **Prompt/template bug**: Instructions are missing or misleading (only applicable if Prompt/Template Mapping exists in CLAUDE.md)
- **Both**: Template produces wrong output AND code has no safeguard

Assign **Risk**:
- LOW — isolated to one function, no other layer affected
- MEDIUM — one architecture layer affected, may ripple to adjacent layer
- HIGH — multiple layers affected or shared data structure involved

Assign **Confidence**:
- LOW — hypothesis only, cannot confirm from code alone
- MEDIUM — likely root cause, has caveats or edge cases
- HIGH — root cause confirmed, fix is deterministic

### B4 — Propose Fix (text only — no file edits)
This step produces text for the `Fix Description` column only. For each affected file: provide the file path, line range, and a plain text description of what to change. No before/after code blocks. If both code and prompt/template files need changes, list both separately with their own file paths and line ranges. Respect ALL rules listed in the `## Constraints` section of CLAUDE.md.

### B5 — Write to the approval sheet
Read existing Bug IDs in `outputs/{client}/approval_sheet.md` to determine the next sequential ID. Format: `BUG-YYYY-MM-DD-NNN` (sequential per day, e.g. BUG-2026-03-25-001, BUG-2026-03-25-002).

Append one new row to the table with these columns:

| Bug ID | Reported | Bug Summary | Risk | Confidence | Root Cause | Affected Files | Fix Description | Testing Notes | Status | Reviewed By |

- Bug ID = generated sequential ID
- Reported = today's date
- Bug Summary = exact bug text from $ARGUMENTS for this bug, verbatim — do not summarize or rephrase
- Risk = LOW / MEDIUM / HIGH
- Confidence = LOW / MEDIUM / HIGH
- Root Cause = what is wrong and why (note if code, prompt, or both)
- Affected Files = file paths with line numbers, e.g. `validation_agent.py L752-792` — separate multiple files with `<br>`
- Fix Description = plain text description of the change, no code blocks
- Testing Notes = how to verify the fix works
- Status = `PENDING`
- Reviewed By = `_pending_`

Write exactly **one row per bug**. Do not split a single bug into multiple rows; do not merge distinct bugs into one row.

## Phase C — Interaction Analysis (batch only)
Skip this phase in single mode. Run it after ALL bugs in a batch have been through Phase B (or when $ARGUMENTS is `sheet`, over the existing PENDING/APPROVED rows). This analysis is **advisory only** — it reports conflicts and ordering, it does not act on them.

### Check 1 — Same File Conflict (no project knowledge needed)
- Collect all (file, line_start, line_end) tuples from every fix's Affected Files column
- Group by file path
- If two fixes target overlapping OR adjacent (≤20 lines apart) ranges in the same file → flag as CONFLICT
- Action: apply one at a time, re-run the **diagnose-bug** skill for the second after the first is applied

### Check 2 — Dependency Order (read from CLAUDE.md)
- Read `## Architecture Layers` or `## Pipeline Steps` from CLAUDE.md
- If Fix A is at an earlier layer and Fix B is at a later layer AND both touch the same data object → B depends on A
- Also check: does Fix A create a function or variable that Fix B assumes exists?
- Action: flag recommended apply order (apply A before B)

### Check 3 — Cross-Effect Risk (read from CLAUDE.md)
- Read `## File Index` from CLAUDE.md to identify files imported by many modules
- If any fix touches a high-import shared file → HIGH cross-effect risk
- If two fixes affect adjacent layers that share a data contract → flag for combined testing
- Action: flag and recommend testing all affected layers after applying

### Pre-Deploy Check (only when $ARGUMENTS is `sheet`)
Read all APPLIED rows from the last 7 days. If any PENDING fix targets code already changed by a recent APPLIED fix → flag as potentially stale.
Print: `WARNING — BUG-XXX targets code already changed by BUG-YYY applied on YYYY-MM-DD`
Recommend re-running the **diagnose-bug** skill for stale entries to get a fresh analysis.

## Phase D — Print Summary & Stop

**Single mode** — print: Bug ID assigned, classification (which layer from CLAUDE.md), risk, confidence, affected files with line numbers, and this exact line:

`Proposed fix written to outputs/{client}/approval_sheet.md with Status=PENDING. No source files were modified. Review and set Status=APPROVED, then run the apply-fixes skill.`

**Batch mode** — print:

| Bug ID | Risk | Confidence | Affected Files | Interactions |
|--------|------|------------|----------------|--------------|

Then print:
- Total bugs analyzed, written, and skipped
- Any reports skipped as **not a valid issue** (with the one-line reason) and any skipped as **duplicates** (with the existing BUG-XXX)
- Interaction warnings with specific recommendations
- Recommended apply order (dependencies first, then HIGH risk, then by confidence)
- Reminder: `Review outputs/{client}/approval_sheet.md, set Status=APPROVED on the rows you want, then run the apply-fixes skill.`

Then stop. Do not take any further action in this turn.

---

## Important Rules

1. **Validate first, always.** No fix is proposed for a report that fails Phase A. An invalid report is reported and returned — nothing is written to `outputs/{client}/approval_sheet.md`.
2. **Propose-only contract.** Only `outputs/{client}/approval_sheet.md` may be written in this skill. Every other file is read-only for the duration of the run.
3. **Status is always `PENDING`.** The human reviewer owns the transition to `APPROVED` / `REJECTED`. the **apply-fixes** skill owns the transition to `APPLIED` / `CONFLICT`.
4. **No git writes.** No staging, committing, branching, or pushing. If you discover mid-diagnosis that a fix is urgent, say so in the `Fix Description` — do not act on it.
5. **Dual-layer fixes still propose-only.** Even if both a prompt file and a code file need changes, describe both in `Fix Description` with separate file paths and line ranges — do not edit either.
6. **One row per bug.** Do not split a single bug into multiple approval rows; do not merge distinct bugs into one row. Multiple distinct bugs in one input each get their own row and their own Bug ID.
7. **Interaction analysis is advisory.** In batch mode it reports conflicts and ordering but never applies or reorders anything.

---

# KB mode — `target=kb`

Follow this section INSTEAD of Phases A–D when the run parameters contain `target=kb`. You are not diagnosing source code. You analyse a **knowledge base (KB)** against a user's complaint about a deliverable generated from it, and propose **amendments to the KB** for review. You never edit the KB here — that is apply-fixes' job. You only propose.

## Inputs (KB mode)
- **The KB** — the files staged into your `inputs=` dir (what a kb-builder run produced). If a `kb=<dir>` path is given, use that instead. Treat every file under `inputs=` as part of the KB **except**: a `feedback/` subdir, a `generated/` subdir, or an `expected/` subdir.
- **The flagged issues** — the user's complaint, verbatim, in $ARGUMENTS / context. This is WHAT went wrong with the deliverable.
- **`generated/`** (optional) — the deliverable being complained about, under `inputs=/generated/`.
- **`expected/`** (optional) — the user's corrected version of it, under `inputs=/expected/`.

Determine your **evidence mode** from which artifacts are present, and never claim more than it supports:

| Present | Mode | What you may conclude |
|---|---|---|
| generated + expected | **diff** | Everything — compare the two; each finding cites a KB rule |
| generated only | **conformance** | Where the output breaks the KB's own rules; not what it should have said instead |
| expected only | **reference-check** | Where the KB disagrees with known-good output → the KB is wrong |
| neither | **prose-only** | Only what the KB does / does not say; every finding is UNVERIFIED |

## Phase K1 — Learn what the KB already says
Read **every** KB file completely (chunk large files until fully consumed). The entire routing decision in K2 turns on whether the KB already covers each complaint, and a partial read produces confident wrong answers in the most damaging direction — a rule you failed to read looks identical to one that was never written. Note where each kind of fact lives and the KB's file / heading / vocabulary conventions; your amendments must match them.

## Phase K2 — Route each flagged issue
For each distinct issue in the complaint, trace it to its real cause and assign a **Change Type**:
- **KB-ADD** — the KB never recorded this fact. Propose the fact to add and where (file / section).
- **KB-FIX** — the KB recorded this fact but wrongly. Propose the corrected value.
- **KB_IGNORED** — the KB **already states this correctly**. The KB is not at fault; the generator ignored it. Do **NOT** propose a KB edit — restating a rule the KB already holds hides the generator bug. Record it as KB_IGNORED, citing the KB location that already covers it, so it can be escalated to a generator/source fix (a separate `target=code` run) instead.
- **ASK** — the complaint **contradicts** an existing KB rule (which may encode a deliberate house standard). Do not assume the newest opinion wins — record it and ask before changing.

Record every value the way it must be stored: a colour is the measured hex, a size is the number **with its physical unit**, a heading is the wording exactly as it appears. A value whose unit is implied will be misread later.

## Phase K3 — Write proposals to the approval sheet
Write PENDING rows to **`output=/feedback/approval_sheet.md`** (your deliverable is the `output=` dir — do NOT write under `outputs/{client}/…` in this mode, and keep it under `feedback/` so it never mixes with the KB's own files). Create the file and its `feedback/` folder if missing. One row per issue:

| Item ID | Reported | Flagged Issue | Change Type | KB Location | Proposed Amendment | Evidence Mode | Confidence | Status | Reviewed By |

- **Item ID** = `KB-YYYY-MM-DD-NNN` (sequential per day)
- **Flagged Issue** = the user's words, verbatim — do not summarise
- **Change Type** = KB-ADD / KB-FIX / KB_IGNORED / ASK
- **KB Location** = the file + section the amendment targets (for KB_IGNORED, the location that ALREADY covers it)
- **Proposed Amendment** = the exact fact/value to add or correct, **with units**; for KB_IGNORED write `KB already states this here — generator defect, no KB change`; for ASK write the question
- **Evidence Mode** = diff / conformance / reference-check / prose-only
- **Confidence** = LOW / MEDIUM / HIGH
- **Status** = `PENDING`
- **Reviewed By** = `_pending_`

## Phase K4 — Summary & stop
Print a compact table (Item ID, Change Type, KB Location, Confidence), then:
- counts by Change Type, the evidence mode you ran in, and which missing artifact would have sharpened it
- this exact line: `Proposed KB amendments written to output=/feedback/approval_sheet.md with Status=PENDING. The KB was not modified. Review, set Status=APPROVED on the rows to apply, then run apply-fixes (target=kb).`

Then stop. Do not modify the KB.

## KB-mode rules
1. **Propose-only.** The only file you write is `output=/feedback/approval_sheet.md`. The KB is read-only in this skill.
2. **KB_IGNORED is a hard guard.** If the KB already states a rule correctly, never propose restating it — route it out as a generator defect.
3. **Every amendment traces to a flagged issue.** You are not auditing the KB; a change no complaint asked for does not belong here.
4. **Conform to the KB's existing shape.** Amendments use the files, headings and vocabulary already there; never rename or re-bucket settled content.
5. **Never claim beyond your evidence mode.** In prose-only mode you have not seen the deliverable — say "the KB records no X, which would explain the complaint," not "the output used the wrong X."
