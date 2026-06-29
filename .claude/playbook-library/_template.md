---
id: example-archetype
seen-in: []
fallback: false
---

# Template for new playbooks

A playbook is **analysis advice and lessons learned** for a recurring client archetype. It is NOT a recipe template the KB copies from.

When kb-builder matches this playbook against a new client, it reads the playbook as guidance, **actually analyzes that client's artifacts**, and **composes a self-contained, tailored KB under `outputs/{client}/kb/`**. The playbook informs Claude's attention and judgment during analysis. The KB is Claude's own composition for this specific client, not a slot-filled copy of this playbook.

Copy this file to `playbooks/<id>.md` and edit. Anything in `playbooks/` is read by recognize; this template lives one folder up so it's ignored.

## On vendor-agnosticism

Specific playbooks describe archetypes at a level **high enough that other vendors with the same shape would also match**. Specific vendor fingerprints (exact constants, exact top-level container key names, exact node-type lists, exact event-name conventions) do NOT belong here — they're things kb-builder captures from the actual artifacts during analysis and bakes into the KB it composes.

Examples of what DOES belong in a playbook:

- "The artifact is a JSON file with a node collection and a transition collection wiring them by ID."
- "Each node carries a stable ID and a type label."
- "Embedded scripts may live in node attributes; the host language is typically a sandboxed interpreter — extract built-ins from real script bodies, never assume Node/browser globals."

Examples of what does NOT belong:

- A particular vendor's `scriptType` value.
- The literal top-level container key name a vendor uses.
- The exact set of node types one vendor ships.
- A vendor's brand or product names.

The fallback playbook is exempt — its content is genuinely procedural since it covers no specific archetype.

## When this playbook applies (recognition signals)

Structural recognition signals — what the artifacts look like at the shape level. This block is what recognize.md tests against the artifacts to decide if this playbook fires.

- File format(s).
- Structural pairings (e.g. "nodes + transitions", "reference doc + raw source materials", "schema + data").
- Identifier conventions and how things reference each other.
- Whether embedded code blocks exist, what slots they live in, what their runtime is likely to be.
- File / sub-artifact combinations typically present together.
- What the downstream consumer is supposed to produce.

Be specific about shape. Be agnostic about vendor.

## What to look for when analyzing

The domain-specific analysis tips — what to pay attention to, what details matter, what gets missed if you're not careful. These guide kb-builder's reading of the artifacts; they don't dictate the KB's structure.

For each tip, be concrete:

- *What* to extract or enumerate (node types, event names, headings, vocabulary, styles, etc.).
- *Why it matters* — what goes wrong downstream if it's miscaptured.
- *Where it lives* in the artifacts (field paths, file kinds).

Quality tip: think about the times you've seen Claude miss a detail in this archetype's analysis. That's what belongs here.

## Common pitfalls

Anti-patterns past engagements have hit. When kb-builder composes the KB, it decides which of these apply to this client and embeds them as numbered Critical Rules. Sharper is better.

Each pitfall should be a one-line "do not X because Y" that the runtime can enforce on its own KB output.

## Useful questions to ask the operator

Gap-question phrasings that have worked. These are EXAMPLES, not prescriptions — the KB's gap-question list is Claude's composition for this client's actual unknowns, drawing inspiration here but not constrained.

Each entry: severity tag (BLOCKING / IMPORTANT / VERIFY ASSUMPTION / NICE TO HAVE) + example question phrasing with `{placeholder}` slots.

Frame this as a phrasing bank, not a checklist. The consuming skill should align scope with the operator first, then ask only the in-scope questions whose answers would change the KB and that the artifacts do not already answer. A long example list here must never become a long questionnaire at runtime.

## Typical KB shapes that have worked

Past KB file lists for clients of this archetype. Reference only — the KB's file list is sized to what *this* client's artifacts demand. Include files that don't earn their keep here, and the KB will bloat.

For each typical file: filename + one-line description of what content it holds and what to extract from artifacts to fill it.

## Skip-entirely categories

What's typically out of scope for this archetype. Things the KB should never lead the downstream agent to emit. The KB inherits these (filtered to those that apply) as a "do not produce" list.

## Notes for librarians

- Add a playbook only after seeing the archetype on 2+ engagements. One occurrence is anecdote.
- Update `seen-in:` when an existing archetype hits on a new client.
- If a playbook keeps producing "partial fit" outcomes and operators keep clarifying with the user, the recognition signals or the "what to look for" tips aren't sharp enough — rewrite, don't tolerate.
- If kb-builder's end-of-run candidate flags repeatedly suggest the same playbook update, promote it. The whole architecture's value depends on cross-client learnings flowing upward into the library.
