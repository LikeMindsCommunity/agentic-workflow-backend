# Match Playbooks

Decide which playbooks in the library apply to this client. Each playbook is analysis advice for a client archetype; **multiple specific playbooks can fire** when the client spans archetypes (e.g. a flow-JSON build that also needs an SOW generated alongside it). If no specific playbook fires, the **fallback playbook** fires instead — kb-factory always produces a tailored skill, even for first-of-kind clients.

## Input

- The client artifacts directly. No pre-digested descriptor — just read the files.
- `client_name` and `target_deliverable`.
- All `.md` files under `.claude/kb-factory-library/playbooks/`.

## Playbook flavors

Playbooks have a `fallback:` flag in their front matter:

- **Specific playbooks** (`fallback: false` or absent) — describe an archetype with structural recognition signals. The matcher tests them against the artifacts.
- **Fallback playbook(s)** (`fallback: true`) — fire only by exclusion when no specific playbook matched. The matcher does not signal-test these against the artifacts.

The library should contain exactly one fallback playbook. More than one is a library configuration error — warn the operator and pick the first.

## What to do

1. **List every playbook.** Walk `kb-factory-library/playbooks/*.md`. Partition into `specific` (no fallback flag) and `fallback` (flag true). For each playbook in either group, read the front matter and the `## Artifact description` block.

2. **Test specific playbooks against the artifacts.** The `When this playbook applies (recognition signals)` block lists structural recognition signals — file shape, archetype-defining pairings (e.g. node+transition collections; reference doc + raw sources), how identifiers reference each other. Vendor-specific fingerprints (exact constants, exact field names, vendor brand) are deliberately *not* there; they're observations kb-factory captures from real artifacts during analysis, not match conditions.

   For each specific playbook, decide fit:
   - **Fits** — recognition signals match. Carry the playbook forward to assemble (it'll consult the playbook's advice while composing the generated skill).
   - **Does not fit** — signals clearly miss. Skip.
   - **Uncertain** — some signals match, some don't; or the inputs span the archetype only partially.

3. **On uncertain fit, ask the user** with the specific archetype context. Phrase the question in terms of what you saw and what's missing — not a generic "what do you want?". Example:
   > The artifacts include polished SOW PDFs but no raw MOMs or transcripts — the `document-from-template` archetype expects both. Is the downstream agent supposed to generate new SOWs from MOMs you'll provide later, or just emit one-off SOWs from prompts?

4. **Multiple specific playbooks can fire.** A client whose folder has both visual-flow JSON exports *and* SOW reference PDFs hits both `nodeflow` and `document-from-template`. Carry all fired specific playbooks forward; assemble consults all of them when composing the generated skill.

5. **If at least one specific playbook fires, ignore the fallback.** Specific archetypes always beat the fallback. The fallback exists for first-of-kind clients, not as a complement to archetype playbooks.

6. **If no specific playbook fires, surface the situation to the operator before firing the fallback.** Wording:
   > No archetype-specific playbook matched this client's artifacts. Options:
   > (a) **Proceed with the fallback playbook** — kb-factory will triage the artifacts, ask you about the use-case, propose a KB shape for confirmation, then build the tailored KB.
   > (b) **Pause and author a new specific playbook first**, then re-run — recommended if you can already see this archetype recurring on future clients.
   >
   > Which do you want?

   On (a): carry the fallback playbook forward to assemble.
   On (b): halt this run cleanly; the operator authors the new playbook and re-invokes kb-factory.

7. **Library misconfiguration.** If `playbooks/` contains zero entries, or zero fallback playbooks AND zero specific playbooks match, halt with: "Library is empty or no fallback configured — at minimum a fallback playbook must exist." Don't try to do anything else.

## Don't

- **Modify the playbook library.** Read-only.
- **Force a fit on a specific playbook.** If artifacts genuinely don't match a specific archetype, fall back to the fallback playbook (with operator confirmation) — don't shoehorn into the nearest specific one. A wrong-archetype tailored KB is harder to spot as wrong than a fallback KB that was honest about being discovery-driven.
- **Fire the fallback alongside specific playbooks.** The fallback is exclusion-only.
- **Test the fallback's `Artifact description` against the artifacts.** The fallback fires by exclusion, not by signal-matching. Its artifact-description block exists for the template's sake only.
- **Batch every uncertainty into one giant question at the end.** Ask as fit-uncertainty surfaces, naturally.
- **Treat "partial fit" as full fit.** Partial fit produces a tailored skill that's wrong in ways the operator can't easily spot. Either ask, or skip and let the fallback catch.

## Edge cases

- **Empty library** — halt with library-misconfigured error (see step 7).
- **Multiple fallbacks in library** — pick the first; warn the operator that the library has more than one fallback (this is a config bug).
- **Two specific playbooks fire with overlapping advice** — fine. Carry both; assemble consults both while composing the generated skill.
- **A specific playbook fires but its `seen-in` list is short (1 entry)** — still use it, but lower confidence; an extra clarifying question is appropriate.
- **Specific playbook is uncertain AND fallback is available** — surface the uncertainty first ("the artifacts partially match archetype X — confirm or skip?"). If the operator skips the specific playbook, fall through to the fallback flow in step 6.
