# Assemble Skill

Compose the new `{client}-kb` skill from the fired playbooks' recipes.

## Input

- The client artifacts and brief.
- The fired playbooks from `match.md` (their `Recipe` sections, plus their `Anti-pattern` sections).

## What to do

1. **Create** `.claude/skills/{client_name}-kb/`.

2. **Generate `SKILL.md`** with:
   - YAML front matter: `name` and `description` (built from `client_name` + `target_deliverable`).
   - A short "when to use" section with trigger phrases the downstream user might type.
   - A pointer to the supporting files generated below.

3. **Generate supporting files driven by the fired recipes.** Each fired playbook's `Recipe` lists the files the generated skill should contain. Use that as the spec. Read the actual client artifacts to populate the content — the recipe says *what* each file should hold; the artifacts say *what's in it*.

4. **Merging multiple fired playbooks:**
   - Both recipes contribute a file with the same name → merge content into one file.
   - Recipes contribute disjoint files → include both.
   - Recipes conflict on file naming or numbering → follow the larger / more specific playbook's structure and rename the other's contribution to fit. State the merge decision in the gap log.

5. **Apply each playbook's `Anti-pattern` section as a self-check.** After drafting, re-read the anti-patterns and verify the output doesn't fall into them (e.g. did you accidentally summarize boilerplate? did you paraphrase event names? did you include a Skip'd UC section?). Anti-patterns encode the failure modes the recipe most often slips into — they are not optional.

6. **Fallback path: no playbook fired.** Stop. Don't try to produce a tailored skill from nothing. Surface to the operator: a one-sentence summary of what the client's artifacts looked like, and a one-line candidate-playbook flag (see below). Ask whether to (a) author a new playbook first and re-run, or (b) emit a minimal scaffold (`SKILL.md` + an empty gap log) for the operator to fill in by hand.

## Don't

- Write a `playbook_refs.md`, provenance file, or any kb-factory meta-artifact into the output. The client skill must not leak the kb-factory abstraction.
- Edit the playbook library.
- Re-introduce sections a playbook's recipe explicitly told you to skip. The skip clauses are load-bearing — they're what makes the tailored KB tighter than a one-size-fits-all KB.
- Invent content not present in the client artifacts. Flag unknowns in the generated KB's gap log; do not fabricate.

## Before handing off — candidate playbook flag

Scan the run for cases worth adding to the library:

- **No playbook fired** — the entire run is a candidate. Surface: one-sentence description of what the client's artifacts looked like, what archetype they suggest, and whether you've seen anything similar in the existing playbooks' `seen-in` lists.
- **A playbook fired but the artifacts had a substantial feature the recipe did not cover** — surface that gap. One line: which playbook, what was missing, why it'd plausibly recur on another client.
- **Two playbooks fired and the merge was non-trivial** — surface the merge logic. If it recurs, a combined archetype might be worth its own playbook.

Don't write the playbooks yourself. Flag candidates with name + one-sentence problem + why it might recur. The operator decides whether to add them.

If nothing flag-worthy came up, say so and end.

## Output

- `.claude/skills/{client_name}-kb/` — the deliverable skill folder.
- A short list of candidate-playbook flags for the operator (zero or more lines).
