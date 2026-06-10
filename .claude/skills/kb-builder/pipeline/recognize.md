# Recognize

Parameterize the run before any KB work: decide whether this is a **first run** or an **update**, and which archetype's advice applies.

## Input

- `inputs=<dir>` (required), optional `prompt`, `output=<dir>` (default `outputs/{client}/kb/`, where `{client}` is inferred from the inputs folder name or the prompt).
- The client artifacts directly — read the files.
- The playbook library at `.claude/kb-factory-library/playbooks/*.md` (read-only).

## Step 1 — Detect existing KB

Check `outputs/{client}/kb/` (or the `output=` override).

- **No KB present** → **first run**. Go to Step 2 to decide the archetype.
- **KB present** → **update run**. Read the existing KB files and **infer the archetype and established structure from their content** — the KB's files, vocabulary, and shape make the archetype clear. Carry the inferred archetype + structure forward and **skip matching**; go to `scope.md` (update path), then `build.md`. If you want the playbook's advice for the inferred archetype, load it from the library — but the existing KB's structure stays authoritative.

## Step 2 — Decide the archetype (first run only)

1. **List every playbook.** Walk `playbooks/*.md`. Partition into `specific` (no `fallback:` flag, or `false`) and `fallback` (`fallback: true`). Read each one's front matter and `## Artifact description` / recognition block. The library should hold exactly one fallback; if more, pick the first and warn the operator.

2. **Test specific playbooks against the artifacts.** Each playbook's recognition-signals block lists structural signals — file shape, archetype-defining pairings, how identifiers reference each other. Vendor-specific fingerprints (exact constants, exact field names, vendor brand) are deliberately *not* match conditions; they're observations the scope and build phases capture during analysis. For each specific playbook decide: **fits** / **does not fit** / **uncertain**.

3. **Decide fit yourself — don't ask the operator which archetype to use.** Weigh the recognition signals and pick the best-fitting playbook(s). If signals are mixed, use judgment (e.g. artifacts with both visual-flow JSON and SOW PDFs fire both archetypes; polished SOW PDFs with no raw sources still fit `document-from-template`). Fall through to the fallback only when nothing specific genuinely fits.

4. **Multiple specific playbooks can fire.** A folder with both visual-flow JSON exports and SOW reference PDFs hits both `nodeflow` and `document-from-template`. Carry all fired specific playbooks forward.

5. **If at least one specific playbook fires, ignore the fallback.** Specific archetypes always beat the fallback.

6. **If no specific playbook fires, use the fallback automatically.** Don't ask the operator — carry the fallback forward to `scope.md` (discovery mode). If you can see this archetype recurring on future clients, that's a hint to author a new specific playbook later, but it doesn't block this run.

7. **Library misconfiguration.** If `playbooks/` is empty, or no fallback exists and no specific playbook matches, halt with: "Library is empty or no fallback configured — at minimum a fallback playbook must exist."

Carry the fired playbook(s) forward to `scope.md` as **advice**, not a recipe to copy.

## Don't

- **Modify the playbook library.** Read-only.
- **Re-match on an update.** Infer the archetype from the existing KB's content instead.
- **Force a partial fit.** If a specific archetype doesn't genuinely fit, skip it and let the fallback catch — a wrong-archetype KB is harder to spot as wrong than an honestly discovery-driven one. Decide this yourself; don't punt it to the operator.
- **Test the fallback's recognition block against the artifacts.** The fallback fires by exclusion only.
