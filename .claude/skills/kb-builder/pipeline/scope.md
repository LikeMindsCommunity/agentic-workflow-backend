# Scope

Define and lock what KB to build, before any drafting. This is the first analytical phase: understand the artifacts, derive the requirement from the operator's prompt, and settle scope. Everything downstream (extraction, drafting, the gap loop) obeys the scope locked here.

Runs in the main conversation, so any scoping question reaches the operator directly.

## Input

- `inputs=<dir>` (the artifacts), optional `prompt`, and the fired playbook(s) from `recognize.md` (advice, not a recipe).
- On an update: the existing KB, whose content already encodes the established scope and structure.

## Step 1: Read the prompt for intent

Read the operator's `prompt` and extract the stated requirement:

- **What the downstream agent must produce** (the deliverable: a SOW DOCX, a NodeFlow JSON, and so on).
- **What it is for**, plus any focus, priorities, constraints, or exclusions the operator already gave.
- Bank everything the prompt settles; do not re-ask it later.

If there is no prompt, note that scope must come from the artifacts plus a focused Q&A in Step 4.

## Step 2: Map the artifacts' anatomy

**On a URL run there are no artifacts to inventory yet — the material does not exist until the browser goes and gets it.** So this phase inverts: instead of reading what you were given and deciding what to keep, you decide **what to go and look at**. Produce a **journey list** in place of a component inventory:

- Read the `sow=` (and prompt) for the **tasks to automate**, and reduce them to named, ordered journeys — "sign in", "find an order by reference", "update its delivery date", "download the invoice".
- For each journey, note the **role** it needs and any **precondition** (an existing record to act on, a populated list).
- Mark journeys the SOW implies but does not state — an unstated sign-in is still a journey that must be mapped.
- Everything not on this list is **out of scope for mapping**. This is the phase's most important output: an unbounded site walk has no completion condition, and the journey list is what supplies one.
- The list is a boundary, not a blindfold. When the live site later surfaces something whose relevance to a journey is genuinely unclear — an approval queue a submit might route through, a settings page that could gate a field — `map-site.md` asks the operator rather than silently exploring or silently skipping. Scope changes mid-walk are made **with** the operator, never inferred.

Take one quick reconnaissance look at the entry URL if it helps you name the journeys sensibly, but do not start walking them — that is `map-site.md`, after the scope is locked. If the SOW is missing or names no concrete tasks, **ask for the journey list before browsing anything**; it is the one input this phase cannot default.


Read every artifact in a broad pass (shape and composition, not deep extraction yet). For each one:

- Identify its kind and enumerate its components, sections, and pieces (a document's section spine; a flow JSON's node, transition, and script layers; a schema's entities; and so on).
- Classify its role: target deliverable to mimic, source material to extract from, reference example, or noise.
- Note structural variants across artifacts (for example several document profiles built on one template) and which pieces recur vs appear once.

Produce a short **component inventory**: the menu of pieces the KB could capture. Only the in-scope ones get deep-extracted later, in `build.md`.

## Step 3: Draft a scope hypothesis

From prompt intent plus anatomy, write a candidate scope in three parts:

- **Requirement**: one line stating what the KB enables the downstream agent to produce.
- **In scope**: the components the KB must capture to serve that requirement.
- **Out of scope / noise**: components and categories the KB will deliberately exclude (the playbook's skip-entirely categories, plus anything the requirement does not need). Filter aggressively; the smallest KB that fully serves the requirement wins.

## Step 4: Confirm or ask (prompt-aware)

Decide whether the scope is already settled:

- **Prompt plus artifacts fully determine the scope**: state the scope hypothesis to the operator for a one-line confirm, then proceed. Do not manufacture questions.
- **Material ambiguity remains**: run a focused Q&A on only the decisions that change the KB's shape (which variant or profile to cover, output format, what to treat as out of scope, and the like). Apply the relevance gate: never ask what the prompt or artifacts already answer, and never dump a checklist. Filter the noise; ask only what pins down the requirement.

This is the high-level, shape-determining round. Detailed content gaps are not asked here; they surface later, while drafting, in `build.md`'s gap loop.

## Step 5: Lock the scope

Record the final scope (requirement + in scope + out of scope). It is the gate for the rest of the run: `build.md` deep-extracts only in-scope components, drafts within this shape, and the gap loop drops any question that does not bear on it. The requirement and overview naturally seed `00-overview.md` (legitimate KB content, not a meta file).

## On an update

A KB already exists, so the scope is largely set by its content. Do not re-run a full scoping conversation:

- Infer the established scope from the existing KB.
- Map only the **new** artifacts' anatomy (Step 2) and check whether they fit that scope.
- If they fit, confirm in one line ("scope unchanged; new material adds X") and proceed.
- If they push beyond the established scope (a genuinely new component or profile), surface that to the operator as a scope decision before drafting. Do not silently widen or reshape.

## Don't

- **Don't deep-extract here.** This phase maps shape and settles scope; `build.md` does the full extraction of in-scope components.
- **Don't ask what the prompt or artifacts already answer.** Bank settled context; ask only residual, shape-changing ambiguities.
- **Don't carry noise into scope** just because it sits in the artifacts. If a component does not serve the requirement, mark it out of scope.

## Output

- A locked scope (requirement + in scope + out of scope), carried forward to `build.md`.
