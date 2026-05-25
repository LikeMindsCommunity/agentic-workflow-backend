---
id: example-archetype
seen-in: []
---

# Template for new playbooks.

Copy to `playbooks/<id>.md` and edit. Anything in `playbooks/` is matched against; this template lives one folder up so it's ignored.

A playbook encodes one **client archetype** — a kind of artifact + use case we've seen recur — and a **recipe** for what the generated `{client}-kb` skill should contain when this archetype applies.

## Artifact description

What the client's artifacts look like, and how to recognize this archetype. Be specific:

- File shapes — top-level keys, expected structure, file extensions.
- Fixed-value fingerprints — a constant string, a versioned naming pattern, a schema field that's always the same.
- Combinations — what kinds of files are typically present together (e.g. source materials + reference deliverables, multiple JSON exports, etc.).
- Use case — what the downstream agent is supposed to produce from these artifacts.

The match step reads this block to decide whether this playbook fires on a new client. Write it sharply: if a future operator could read it and not be sure whether a given client's folder fits, the description isn't sharp enough.

## Recipe

What the generated `{client}-kb/` skill should contain. Concrete, file-by-file. Each entry: filename and what content goes in it, described in its own words — what the file holds, why it matters for this archetype.

Also state **what to skip** — kinds of content that another archetype might generate but that don't apply here. The skip list is what makes the tailored KB tighter than a generic one. Without it, the recipe is just a longer way of saying "do everything."

## Anti-pattern (optional)

Common failure modes the recipe is likely to fall into. The sharper, the better — each anti-pattern should describe a specific wrong move the assemble step might make and why it's wrong. The assemble step re-reads these as a self-check after drafting.

## Notes for librarians

- Add a playbook only after seeing the archetype on 2+ engagements. One occurrence is anecdote.
- Update `seen-in:` when an existing archetype hits on a new client.
- If a playbook keeps producing "partial fit" results and operators keep having to clarify with the user, the artifact description isn't sharp enough — rewrite, don't tolerate.
