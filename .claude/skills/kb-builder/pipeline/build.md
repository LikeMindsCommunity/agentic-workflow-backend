# Build

Produce the KB at `outputs/{client}/kb/`: **draft from scratch** on a first run, **extend** on an update. Interactive — runs in the main conversation so the gap-question Q&A reaches the operator directly.

## Input

- The **locked scope** from `scope.md` (requirement + in scope + out of scope) and the component inventory it produced.
- The fired playbook(s) from `recognize.md` — **advice**, not a recipe to copy.
- The artifacts. **On a URL run these are the observation corpus `map-site.md` just wrote** — treat it exactly as you would any other source material, with one addition: it carries **provenance** (observed / inferred / unmapped) on every journey step, and that provenance must survive into the KB. It is what tells the downstream agent which steps were seen working and which are predictions, so never flatten it away while composing.
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
- **Present every surviving question together as one list, grouped by severity** (BLOCKING / IMPORTANT / VERIFY ASSUMPTION / NICE TO HAVE). For each: the question, one line on why it matters, and for a VERIFY ASSUMPTION the default you will apply if the operator defers. Then **end your turn and hand control back to the operator** — your message stops at the questions and you wait for a reply. While *any* question on that list is still open, do not analyze further, draft more, or continue into Phase E in the same turn. This wait-for-input rule applies to the whole list, not only the BLOCKING items: whenever you have questions for the operator, you display all of them and wait for their answers before proceeding.
- **Make artifact requests concrete and file-pointable — not abstract category names.** When a surviving item asks the operator for a reference document or export, render it in the operator's own entity terms (if the fired playbook gives a presentation format, follow it): for each doc, name it the way the operator would, say what it contains, what you already extracted, and why the gap matters — and state explicitly that they can point you at files / a folder / a wiki / a screenshot rather than typing answers. An operator can't act on "share the per-node template export," but can act on "your node docs — the sheet listing each node type's fields, defaults, and events." This is what makes a BLOCKING artifact request actionable instead of confusing.
- **A BLOCKING question halts the run until it is genuinely resolved.** "Resolved" means exactly one of: (a) the operator gives the actual answer, or (b) the operator explicitly waives it ("proceed without it" / "use your default"). A **promise to supply a missing input later is NOT a resolution** — if the operator says "I'll share the palette export" (or any artifact a BLOCKING question depends on), that input is a *pending dependency*: pause, wait for the artifact to actually arrive, and only then resume drafting with it. Never decide on the operator's behalf to proceed without a promised BLOCKING input, and never guess a BLOCKING answer.
- **The gap log records; it does not resolve.** Only three kinds of item belong in `*-gap-log.md`: ones the operator **explicitly** deferred (with their stated stance), ones no available source can answer, and residual low-severity uncertainties. Writing a still-open BLOCKING question into the gap log and proceeding is the exact failure this loop exists to prevent — the gap log is a record of asked-and-deferred or genuinely-unanswerable items, never a substitute for asking and waiting, and never a parking spot that lets the run continue past an open blocker.
- **Finalize only after the operator has responded to the list.** No BLOCKING question may remain open, and every non-blocking survivor must be either answered or assigned its stated default — but you reach that state only *after* the operator's reply, never by proceeding before they have had the chance to answer. The operator may say "use your defaults" for the non-blocking ones; that is still their input, and you wait for it.
- **Show the whole list at once; don't drip questions across turns.** Put every survivor into the single severity-grouped list rather than asking a few, proceeding, and circling back for more. What keeps the list short is the relevance gate — it should already hold only this client's genuine in-scope unknowns, never the playbook's example bank — not round-by-round rationing. BLOCKING items lead the list so the operator sees them first, but you still present the rest in the same message and wait for one reply covering all of it.
- **On an update**, ask only about the new gaps the new artifacts introduce; do not re-litigate settled first-run decisions — but still present those new gaps as one list and wait, the same way.

## E. Save

- **Enter this phase only once the gap loop's BLOCKING questions are all resolved** (each either answered or explicitly waived by the operator). If any BLOCKING item is still open — including a promised-but-not-yet-delivered input — you are still in Phase D: do not save.
- Write/update the KB files under `outputs/{client}/kb/`.
- **Bundle every referenced artifact (self-contained KB).** Scan the finished KB for any reference to a file outside `outputs/{client}/kb/` (a node-template/palette export, schema, query library, reference example). For each: copy the file into the KB directory and rewrite the reference to its bundled relative path. The KB must stand alone — its consumer is handed only this directory. If a referenced artifact can't be located or copied, that's a BLOCKING gap: surface it (don't save a KB with a dangling reference). On an update, re-run this check for any new references.
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
