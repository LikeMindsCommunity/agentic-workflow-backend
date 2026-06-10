# Build

Produce the KB at `outputs/{client}/kb/`: **draft from scratch** on a first run, **extend** on an update. Interactive — runs in the main conversation so the gap-question Q&A reaches the operator directly.

## Input

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

## B. Analyze the artifacts

- **First run** — read every artifact. Use the playbook's attention tips; use general intelligence for the rest. Extract:
  - **Structural facts** — top-level container key names, field paths, fixed-value fingerprints (engine identifiers, schema constants), node/type vocabulary, event-name conventions, identifier formats.
  - **Use-case shape** — what downstream agents will produce from this KB, what varies per-instance, what's fixed.
  - **Quirks and recurring patterns** — how components are typically composed in this client's artifacts.
- **Update** — read **only the new artifacts**. Diff against the existing KB: which node types / headings / vocabulary / sections / patterns are genuinely new? The existing KB's content is the frame (its files and shape define the established structure); you are finding **deltas** to fold in, not re-deriving the whole thing.
- If artifacts disagree among themselves, surface to the operator and resolve before composing.

## C. Align scope with the operator (before drafting)

You now understand the artifacts. Before drafting, and before asking any detailed questions, pin down what this KB is actually for, so every later question is relevant.

- **State your understanding back to the operator, briefly:** the deliverable the downstream agent will produce, the archetype you decided, and the scope you intend for the KB (what it will cover, and what you are deliberately leaving out per the skip-entirely categories).
- **Ask a small set of scope-framing questions about focus, not detail.** For example: what matters most for their use case, anything in the artifacts to ignore or treat as out of scope, any priorities or constraints that should shape the KB. Keep this to a few high-level questions, not the detailed gap list.
- **Lock the scope** from the operator's answers. This locked scope is the filter for the gap loop (Phase E): any later question that does not bear on it is dropped before you ask it.
- **On an update**, the scope is already set by the existing KB. Do not re-run a full scoping conversation; confirm in one line that the scope is unchanged and note what the new artifacts add.

## D. Draft or extend the KB

- **File list** — first run: choose the KB files this client's artifacts demand, informed by the playbook's typical shapes; include only files that earn their keep. Update: reuse the existing KB's file list (the files already present in `outputs/{client}/kb/`); add a new file only if a genuinely new category appears, and flag it to the operator.
- **Write the real observed values** into the KB files — verbatim, not paraphrased.
- **Anti-drift (update, LOAD-BEARING):** the existing KB's structure is authoritative. Conform new facts to the established containers / field paths / file shape as seen in the existing KB files. Do not reshape, rename, or re-bucket settled content. If a new artifact's shape can't fit the existing KB's structure, **stop and surface it to the operator** — it may be a genuinely new structure warranting a deliberate shape change, not a silent reshape.
- **Apply every critical rule while writing** — verbatim values, no internal-meta leak into recorded content, no out-of-scope categories from the skip list.

## E. Gap loop (interactive, scope-gated)

After drafting, surface the open questions to the operator and **wait for answers before you finalize**. This step is mandatory whenever any question survives the relevance gate. Do not self-resolve every gap into a "safe assumption" and save; the gate trims the list to what is worth the operator's attention, it does not let you skip the ask.

- **Relevance gate.** Drop a candidate question only if one of these is true: it is out of the locked scope, the artifacts already answer it, or its answer could not change the KB in any way. Everything else survives and gets asked. "I could assume a safe default" is NOT a reason to drop a question: surface it as a VERIFY ASSUMPTION with the default you would use, and let the operator confirm or correct it.
- **The playbook's useful-questions are phrasing inspiration, not a checklist.** Generate questions from *this* client's genuine, in-scope unknowns; borrow phrasing only where it fits. Do not enumerate the playbook list.
- **Present the survivors explicitly, grouped by severity** (BLOCKING / IMPORTANT / VERIFY ASSUMPTION / NICE TO HAVE). For each: the question, one line on why it matters, and for a VERIFY ASSUMPTION the default you will apply if the operator defers. Then stop and wait for the operator.
- **Finalize only after the operator responds.** BLOCKING questions must be answered before you save; never guess one. For the rest, the operator may answer or say "use your default", and you record their choice. Only items the operator explicitly defers, or that no source can answer, go to the gap log with a stated stance. The gap log is a fallback for deferred items, not a substitute for asking.
- **Ask in small rounds, not one giant batch.** Lead with BLOCKING; once those are resolved, raise the rest. Keep each round short.
- **On an update**, ask only about the new gaps the new artifacts introduce; do not re-litigate settled first-run decisions.

## F. Save

- Write/update the KB files under `outputs/{client}/kb/`.
- The KB's own files and content carry the archetype and structure; a future update infers them by reading the KB.
- Extend, never clobber: an update folds new facts into existing files; it must not drop settled content.

## Fallback playbook fired (first run only)

The fallback's advice is procedural: triage artifacts by kind, elicit the use case from the operator, propose a KB shape. Fold this into Phase C (scope alignment): because the shape cannot be locked from analysis alone, **propose the KB file list and get the operator's confirmation before drafting**. Then proceed through Phases D to F.

## Multiple specific playbooks fired

Compose one KB that serves both archetypes: union the structural facts, sequence the analysis for each, combine the file lists, union the critical rules. The KB's content reflects both archetypes.

## Don't

- **Don't ask before scoping.** Align scope first (Phase C). An unscoped gap loop is what produces the flood of irrelevant questions.
- **Don't enumerate the playbook's example questions.** They are a phrasing bank. Ask only this client's genuine, in-scope unknowns whose answers change the KB.
- **Don't ask what the artifacts already answer**, and don't ask one giant batch of every severity at once.
- **Don't transcribe playbook sections into the KB.** Playbooks are advice; the KB is this client's extracted facts.
- **Don't paraphrase observed values** (node types, event names, vocabulary). Record them as they appear.
- **Don't reshape an existing KB on update.** Extend within the recorded structure; surface genuine new shapes instead of forcing them.
- **Don't leak internal meta into the KB** (archetype/playbook names, KB filenames, section codes, constraint IDs) in recorded content. The KB content alone conveys the archetype to downstream consumers and to future update runs.

## Output

- `outputs/{client}/kb/` — KB drafted or extended.
