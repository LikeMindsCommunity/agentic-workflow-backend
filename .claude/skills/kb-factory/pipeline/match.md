# Match Playbooks

Decide which playbooks in the library apply to this client. Each playbook is a client-archetype recipe; **multiple can fire** when the client spans archetypes (e.g. an IVR build that also needs a SOW generated alongside it).

## Input

- The client artifacts directly. No pre-digested descriptor — just read the files.
- `client_name` and `target_deliverable`.
- All `.md` files under `.claude/kb-factory-library/playbooks/`.

## What to do

1. **List every playbook.** Walk `kb-factory-library/playbooks/*.md`. For each, read the front matter and the `## Artifact description` block. That block lists recognition signals — file shape, fixed-value fingerprints, naming conventions, what the artifact is for.

2. **Compare each playbook's description against the actual client artifacts.** Look at the inputs directly — file names, top-level structure of JSON/XML/YAML, presence of branded PDFs/DOCX, presence of conversational sources like MOMs or transcripts. Decide fit per playbook:
   - **Fits** — recognition signals match. Carry the playbook's `Recipe` forward to assemble.
   - **Does not fit** — signals clearly miss. Skip.
   - **Uncertain** — some signals match, some don't; or the inputs span the archetype only partially.

3. **On uncertain fit, ask the user** with the specific archetype context. Phrase the question in terms of what you saw and what's missing — not a generic "what do you want?". Example:
   > The artifacts include polished SOW PDFs but no raw MOMs or transcripts — the `document-from-template` archetype expects both. Is the downstream agent supposed to generate new SOWs from MOMs you'll provide later, or just emit one-off SOWs from prompts?

4. **Multiple playbooks can fire.** A client whose folder has both NodeFlow JSON exports *and* SOW reference PDFs hits both `nodeflow` and `document-from-template`. Carry all fired playbooks' recipes forward; assemble will merge them.

5. **If no playbook fires**, surface the no-fit to the operator with a one-sentence summary of what the artifacts looked like. Don't try to assemble a tailored skill from nothing — flag the client as a candidate for a new archetype and let the operator decide whether to author a playbook before re-running.

## Don't

- Modify the playbook library. Read-only.
- Force a fit. If artifacts genuinely don't match any archetype, fall back and flag a candidate playbook — don't shoehorn into the nearest one. A wrong-archetype tailored KB is harder to spot as wrong than a generic one.
- Batch every uncertainty into one giant question at the end. Ask as fit-uncertainty surfaces, naturally.
- Treat "partial fit" as full fit. Partial fit produces a tailored skill that's wrong in ways the operator can't easily spot. Either ask, or skip.

## Edge cases

- **Empty library** — every run surfaces no-fit. At least one playbook must exist in the library for kb-factory to produce tailored output.
- **Two playbooks fire on overlapping recipes** — fine. Carry both; assemble handles file-level merging.
- **A playbook fires but its `seen-in` list is short (1 entry)** — still use it, but lower confidence; an extra clarifying question is appropriate.
