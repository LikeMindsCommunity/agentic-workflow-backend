# Assemble

Compose a self-contained `{client}-kb/SKILL.md` from this client's artifacts, using the fired playbook(s) as analysis advice. The generated skill carries everything the runtime needs and doesn't reference any external playbook at runtime.

```
playbooks  ──►  kb-factory: ANALYZE + COMPOSE  ──►  {client}-kb/SKILL.md (self-contained)
```

## Input

- The client artifacts and brief.
- The fired playbook(s) from `match.md` — read them as **advice**, not as a recipe to instantiate. The playbook tells you what to pay attention to, what mistakes to avoid, what kinds of questions tend to matter for this archetype. It does **not** dictate the generated skill's structure.

## What to do

### A. Internalize the playbook's advice

Read the fired playbook(s) end to end. Treat each section as guidance, not as content to copy:

- **Recognition signals** — tell you what makes this archetype this archetype. You'll re-state recognition in the generated skill in this client's specific terms.
- **What to look for when analyzing** — domain-specific attention tips. Apply these while reading the artifacts.
- **Common pitfalls** — anti-patterns. Some will apply to this client and become critical rules in the generated skill; some won't. Decide.
- **Useful questions** — examples of gap-questions that worked. Inspire (don't copy) the gap-questions you'll embed in the generated skill.
- **Typical KB shapes that have worked** — past file lists for reference. Inform (don't dictate) the file list you'll choose for this client.
- **Skip-entirely categories** — what's typically out of scope. Apply where they fit this client.

If you find yourself transcribing playbook sections verbatim into the generated skill, stop. The user explicitly flagged that as the failure mode. The generated skill is *your* composition, informed by the playbook.

### B. Actually analyze the artifacts

Read every file. Use the playbook's attention tips to know what matters; use general intelligence to figure out the rest. The goal is to know enough about this client to write a self-contained recipe for working with their artifacts.

What to extract during analysis (varies by archetype — playbook tells you which apply):

- **Vendor-specific structural facts** — top-level container key names, field paths, fixed-value fingerprints (engine identifiers, schema constants), node/type vocabulary, event-name conventions, identifier formats.
- **Use-case shape** — what the downstream agent will produce, what gets varied per-instance, what's fixed across instances.
- **Quirks** — anything in the artifacts that the playbook didn't predict. Note each: is it client-specific (bake into generated skill) or archetype-wide (candidate playbook update)?
- **Recurring patterns** — the way components are typically composed in this client's flows / documents / whatever.

If artifacts disagree among themselves, surface to operator and resolve before composing.

### C. Compose the self-contained `{client}-kb/SKILL.md`

Write `.claude/skills/{client_name}-kb/SKILL.md`. The skill is substantial (typically 100-200 lines) and contains everything the runtime needs:

- **Frontmatter**: `name: {client_name}-kb`, `description` naming the archetype + this client's deliverable + trigger phrases.
- **Overview**: what artifacts the skill consumes, what KB it produces, where the KB lands (`outputs/{client_name}/kb/`), explicit note that on first invocation it drafts the KB from scratch and on subsequent invocations it uses the existing KB as baseline and extends.
- **Inputs section**: `inputs=<dir>` (with this client's default) and `output=<dir>` kwargs, plus the recognition signals tuned to this client's actual artifacts — vendor-specific container names, fingerprint constants, field paths, anything that lets the runtime detect "yes this is a {client}-archetype artifact" with no ambiguity.
- **Phases**: the recipe Claude composed for this client. Phase count and structure follow what the analysis revealed makes sense — typically Recognition → Inventory → Draft → Gap loop → Save, but adapt. Each phase's instructions reference this client's actual structural details ("walk `nodeflowInfo.nodes`" not "walk the node collection"; "extract every `attributes[*].staticValue` where `attributes[*].name` is `script`" not "extract embedded scripts").
- **KB file list**: the files the runtime writes to `outputs/{client}/kb/`. Sized to what this client's artifacts call for. Reference typical shapes from the playbook only for inspiration; do not include files that don't earn their keep here.
- **Critical Rules**: numbered, embedded verbatim or near-verbatim. Drawn from the playbook's common pitfalls that apply to this client + any new ones the analysis surfaced. Each rule is self-contained — the runtime reads them out of this file, not from any playbook.
- **Gap-question templates**: numbered, with `{placeholder}` slots that resolve at runtime against current artifacts. Drawn from the playbook's useful-questions examples plus questions Claude generated based on what's genuinely uncertain for this client. Each tagged BLOCKING / IMPORTANT / VERIFY ASSUMPTION / NICE TO HAVE.
- **Skip-entirely list**: what the runtime must never produce. From the playbook's skip categories that apply here + any client-specific skips Claude inferred.
- **Runtime behavior**: an explicit note describing how the runtime works — "on invocation, recognize the artifacts; if KB exists at `outputs/{client}/kb/`, use as baseline and run the inventory phase as a delta; if KB does not exist, run from scratch. Then draft/extend, run the gap loop with the operator, save."

The generated skill must be self-contained. It does not read any other playbook file at runtime. It does not import behavior by reference. Everything it needs is in its own SKILL.md.

### D. Multiple fired playbooks

If two specific playbooks fired (e.g. a flow-JSON build that also needs SOWs generated), compose one generated skill that handles both. Sections interleave naturally: recognition signals union, phases sequence the discovery for both archetypes, KB file list combines both shapes, critical rules union.

### E. Fallback playbook fired

If `match.md` routed to the fallback (no specific playbook matched), the playbook's advice is more procedural — its "what to look for" tells you to triage artifacts by kind, elicit the use case from the operator, propose a KB shape, etc. Compose a generated skill that incorporates those discovery steps as runtime phases.

Two things to do differently when the fallback was used:

- **Strong candidate-archetype flag is mandatory at end of run.** A fallback run is by definition first-of-kind. Surface the suggested archetype id + a one-line description of what the next similar client would benefit from.
- **The generated skill should explicitly include a "propose KB shape and get operator confirmation" phase early** — because Claude can't lock in the shape from analysis alone; the operator is the source of truth for the use case.

## The discipline (LOAD-BEARING)

This is what keeps cross-client learning working. Skip it and the architecture collapses into "Claude wrote a skill that happens to be like the playbook."

At every observation Claude makes while analyzing, ask: *would this apply to a different client of the same archetype?*

- **Yes** → archetype-wide. **Flag as candidate playbook update at end of run.** Do not silently bake into the per-client skill (it'd strand the learning per-client).
- **No** → client-specific. Use it in composing the generated skill or note it as something the runtime will record into the KB.
- **Unsure** → use it in the skill AND flag as a candidate. The operator decides whether to promote.

Apply each pitfall from the playbook twice while composing:

- **Once as a self-check** — am I violating any pitfall right now while writing this skill? (e.g. did I paraphrase event names? did I include a section the skip list rules out? did I describe scripting as generic JS?)
- **Once as embedded critical rules** — the runtime will enforce them every time it touches the KB.

## Don't

- **Don't transcribe playbook sections into the generated skill.** Playbooks are advice. The generated skill is your composition, in your words, tailored to this client.
- **Don't import the playbook's KB file list as-is** unless it genuinely fits this client. Trim / extend based on what artifacts demand.
- **Don't reference the playbook from the generated skill at runtime.** Self-contained means no external dereferencing.
- **Don't bake observed *values* (specific node types, event names, vocabulary lists) into the generated skill.** Those go into the KB at runtime. The skill holds the recipe for how to find and record them.
- **Don't bake archetype-wide learnings into the per-client skill.** Flag as candidates and let the playbook absorb them for next time.
- **Don't write to `outputs/{client}/kb/`.** The KB is the runtime's output, not kb-factory's.

## Before handing off — candidate-playbook flag

Scan the run:

- **Fallback fired** — automatic candidate. Surface suggested archetype id + one-line problem + why it might recur.
- **A specific playbook fired but the analysis surfaced a learning the playbook didn't carry** — surface it. One line: which playbook, what's missing, why it'd plausibly recur on a different client.
- **A pitfall came up that the playbook doesn't list** — same.
- **Two playbooks fired and the merge was non-trivial** — surface the merge logic; might warrant a combined archetype playbook.

Don't edit the library. Flag candidates with name + one-sentence problem + why it might recur.

If nothing flag-worthy came up, say so and end.

## Output

- `.claude/skills/{client_name}-kb/SKILL.md` — the self-contained, tailored, Claude-composed generated skill.
- A short list of candidate-playbook flags (zero or more lines).

No KB, no intermediate files.
