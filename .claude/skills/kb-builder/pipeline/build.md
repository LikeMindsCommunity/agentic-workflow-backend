# Build

Produce the KB at `outputs/{client}/kb/`: **draft from scratch** on a first run, **extend** on an update. Interactive — runs in the main conversation so the gap-question Q&A reaches the operator directly.

## Input

- The **locked scope** from `scope.md` (requirement + in scope + out of scope) and the component inventory it produced.
- The fired playbook(s) from `recognize.md` — **advice**, not a recipe to copy.
- The artifacts.
- On an update: the existing KB (the archetype + structure are inferred from its content).

## A. Internalize the playbook's advice

Read the fired playbook(s) end to end. Treat each section as guidance:

- **Recognition signals** — what makes this archetype this archetype.
- **What to look for when analyzing** — domain-specific attention tips; apply while reading artifacts.
- **Common pitfalls** — anti-patterns; some become critical rules for this client.
- **Useful questions** — gap-question phrasings that worked before; inspire (don't copy) the gap-questions you ask.
- **Typical KB shapes** — past file lists for reference; inform (don't dictate) the file list you choose.
- **Skip-entirely categories** — what's typically out of scope.

Don't transcribe playbook sections into the KB. The KB is *this client's* extracted facts, composed by analyzing real artifacts and informed by the playbook.

## B. Deep-extract the in-scope components

The scope phase mapped the artifacts' anatomy and locked what is in scope. Now extract the full detail of the in-scope components only; do not deep-mine anything scoped out.

- **First run** — re-read the in-scope parts of every artifact closely. Use the playbook's attention tips; use general intelligence for the rest. Extract:
  - **Structural facts** — top-level container key names, field paths, fixed-value fingerprints (engine identifiers, schema constants), node/type vocabulary, event-name conventions, identifier formats.
  - **Per-instance vs fixed** — what varies per downstream instance vs what is constant across them.
  - **Quirks and recurring patterns** — how the in-scope components are typically composed in this client's artifacts.
- **Update** — extract from **only the new artifacts**. Diff against the existing KB: which node types / headings / vocabulary / sections / patterns are genuinely new? The existing KB's content is the frame (its files and shape define the established structure); you are finding **deltas** to fold in, not re-deriving the whole thing.
- If artifacts disagree among themselves, surface to the operator and resolve before composing.

## C. Draft or extend the KB

- **File list** — first run: choose the KB files this client's artifacts demand, informed by the playbook's typical shapes; include only files that earn their keep. Update: reuse the existing KB's file list (the files already present in `outputs/{client}/kb/`); add a new file only if a genuinely new category appears, and flag it to the operator.
- **Write the real observed values** into the KB files — verbatim, not paraphrased.
- **Anti-drift (update, LOAD-BEARING):** the existing KB's structure is authoritative. Conform new facts to the established containers / field paths / file shape as seen in the existing KB files. Do not reshape, rename, or re-bucket settled content. If a new artifact's shape can't fit the existing KB's structure, **stop and surface it to the operator** — it may be a genuinely new structure warranting a deliberate shape change, not a silent reshape.
- **Apply every critical rule while writing** — verbatim values, no internal-meta leak into recorded content, no out-of-scope categories from the skip list.

## D. Gap loop (interactive, scope-gated)

After drafting, surface the open questions to the operator and **wait for answers before you finalize**. This step is mandatory whenever any question survives the relevance gate. Do not self-resolve every gap into a "safe assumption" and save; the gate trims the list to what is worth the operator's attention, it does not let you skip the ask.

- **Relevance gate.** Drop a candidate question only if one of these is true: it is out of the locked scope, the artifacts already answer it, or its answer could not change the KB in any way. Everything else survives and gets asked. "I could assume a safe default" is NOT a reason to drop a question: surface it as a VERIFY ASSUMPTION with the default you would use, and let the operator confirm or correct it.
- **The playbook's useful-questions are phrasing inspiration, not a checklist.** Generate questions from *this* client's genuine, in-scope unknowns; borrow phrasing only where it fits. Do not enumerate the playbook list.
- **Present the survivors explicitly, grouped by severity** (BLOCKING / IMPORTANT / VERIFY ASSUMPTION / NICE TO HAVE). For each: the question, one line on why it matters, and for a VERIFY ASSUMPTION the default you will apply if the operator defers. Then stop and wait for the operator.
- **Finalize only after the operator responds.** BLOCKING questions must be answered before you save; never guess one. For the rest, the operator may answer or say "use your default", and you record their choice. Only items the operator explicitly defers, or that no source can answer, go to the gap log with a stated stance. The gap log is a fallback for deferred items, not a substitute for asking.
- **Ask in small rounds, not one giant batch.** Lead with BLOCKING; once those are resolved, raise the rest. Keep each round short.
- **On an update**, ask only about the new gaps the new artifacts introduce; do not re-litigate settled first-run decisions.

## E. Save

- Write/update the KB files under `outputs/{client}/kb/`.
- The KB's own files and content carry the archetype and structure; a future update infers them by reading the KB.
- Extend, never clobber: an update folds new facts into existing files; it must not drop settled content.

## Fallback playbook fired (first run only)

The fallback's advice is procedural: triage artifacts by kind, elicit the use case from the operator, propose a KB shape. Most of this belongs in the scope phase (`scope.md`): because the shape cannot be locked from analysis alone, scope.md proposes the KB file list and gets the operator's confirmation before drafting. Build then proceeds through Phases B to E as usual.

## Multiple specific playbooks fired

Compose one KB that serves both archetypes: union the structural facts, sequence the analysis for each, combine the file lists, union the critical rules. The KB's content reflects both archetypes.

## Don't

- **Don't ask before scoping.** Scope is locked in `scope.md` before build runs. An unscoped gap loop is what produces the flood of irrelevant questions.
- **Don't enumerate the playbook's example questions.** They are a phrasing bank. Ask only this client's genuine, in-scope unknowns whose answers change the KB.
- **Don't ask what the artifacts already answer**, and don't ask one giant batch of every severity at once.
- **Don't transcribe playbook sections into the KB.** Playbooks are advice; the KB is this client's extracted facts.
- **Don't paraphrase observed values** (node types, event names, vocabulary). Record them as they appear.
- **Don't reshape an existing KB on update.** Extend within the recorded structure; surface genuine new shapes instead of forcing them.
- **Don't leak internal meta into the KB** (archetype/playbook names, KB filenames, section codes, constraint IDs) in recorded content. The KB content alone conveys the archetype to downstream consumers and to future update runs.

## Output

- `outputs/{client}/kb/` — KB drafted or extended.
