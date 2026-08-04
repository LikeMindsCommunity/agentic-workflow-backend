---
name: kb-builder
description: Generate and maintain a per-client knowledge base (KB) directly from a client's raw artifacts, drawing on a hand-curated playbook library of archetype advice. Here "client" means the FIRM whose knowledge the KB encodes and whose team will use it — never a company that firm's documents happen to be addressed to; a KB is named after the team that owns it, not after a deal. One skill owns the KB's whole lifecycle — first run drafts it from scratch; later runs extend it as new artifacts arrive — and runs the operator gap-question Q&A interactively in the main conversation. It classifies every input first: finished deliverables and product docs build the KB, while per-deal briefs (MOMs, call transcripts, email threads) are set aside and never ingested, because one deal's requirements must not become the team's standard scope. Artifacts are the usual input, but they are not the only one: given a `url=` instead, the skill ACQUIRES its own material by driving a real browser over the live site and mapping the user journeys in scope, then builds a web-flow KB from what it observed — the KB the `browser-agent` skill later executes against. Use when an operator provides client artifacts, or a website URL, and wants the KB built or updated. Triggers: "build the KB for {client}", "update {client}'s KB", "generate a KB from these artifacts", "extend the {client} KB with this new material", "set up a document generator for {client}", "onboard {client} from these artifacts", "map this website into a KB", "build a KB from this URL so we can automate it in the browser".
---

# kb-builder

Turns a client's raw material into a per-client KB at `outputs/{client}/kb/`, and maintains that KB over time. One skill, the whole lifecycle.

It branches on exactly one thing: **does a KB already exist at `outputs/{client}/kb/`?**

- **No KB yet (first run):** decide the archetype from the material, inventory it, align scope with the operator, draft the KB, run the scope-gated gap loop, save.
- **KB exists (update run):** read the existing KB as the authoritative structural baseline (the archetype is inferred from its content), confirm scope is unchanged, analyze only the new material as a delta, fold new facts in, run the gap loop on just the new gaps, save.

```
                          ┌─ no KB     → draft from scratch ─┐
 material ─► kb-builder ──┤                                  ├─► outputs/{client}/kb/
            (+ playbooks) └─ KB exists → extend as a delta  ─┘
```

**Where the material comes from is a second, independent axis.** Usually the operator hands over artifacts and the skill reads them. But some knowledge exists only in a running system, so when the operator gives a **`url=`**, kb-builder **acquires its own material**: it drives a real browser over the live site, walks the journeys the scope locked, and records what it observes — then builds the KB from that. Both axes compose freely; a URL run can be a first run or an update, and a run may carry both a `url=` and supporting artifacts.

```
artifacts=<dir>  ─┐
                  ├─► (same recognize → scope → build pipeline) ─► outputs/{client}/kb/
url=<origin>     ─┘   URL runs insert a live mapping phase first
```

The product of a URL run is a **web-flow KB** — screens, journeys, locators, cues, interventions — which is what the **`browser-agent`** skill executes against, given that KB plus a SOW.

The gap-question Q&A runs **in the main conversation**, so the interactive back-and-forth with the operator just works (a sub-agent couldn't pause to ask).

## Why one skill works without a frozen recipe

kb-builder is the single producer and maintainer of the KB — there is no generated per-client skill that freezes this client's recipe so updates can replay a known structure. So **something else must be the structural source of truth on updates** — and that is the **KB itself**. Its files, vocabulary, and structure already encode the archetype and the established shape. An update run reads the existing KB, infers the archetype and structure directly from that content, and conforms new facts to it, without re-matching. That, plus the anti-drift rule, keeps the KB consistent run-over-run.

One trade-off to accept consciously: kb-builder consults the playbooks on every run, so playbook improvements reach update runs too (rather than being frozen at first-run time). Usually a feature; the KB-as-source-of-truth rule keeps it from reshaping settled structure.

## Inputs

- `inputs=<dir>` — the artifacts folder: reference deliverables, product/spec/process docs, samples, code. **Required unless `url=` is given** (a URL run acquires its own material). See the artifact-role gate below — a folder may also contain per-deal briefs, and those are set aside rather than ingested.
- `url=<origin>` — a **live website to map** instead of (or alongside) an artifacts folder. Switches on the `web-flow` archetype and the live mapping phase. **One of `inputs=` or `url=` is required.** A site URL supplied any other way counts the same: a `Reference URLs:` line, or one named in the prompt/context as the site to map. What triggers this mode is a **site to drive**, not a particular argument spelling — but a URL that is plainly a *document to read* (a PDF, a doc link, a spec page) is an artifact, not a mapping target; if which one is meant is genuinely unclear, ask.
- `sow=<path>` — on a URL run, the statement of work naming the **journeys to automate**. Used *only* to scope which flows get mapped — see the scoping-vs-ingestion note below. Any form: prose, `.md`, JSON/YAML, PDF, DOCX.
- `client=<slug>` — the **firm this KB belongs to**. Names the KB path. Accepts `customer` as a legacy alias. If not given, infer it (see below).
- `prompt` — optional free-text describing the use case or any important context.
- `output=<dir>` — where the KB is written. Defaults to `outputs/{client}/kb/`.

### A SOW on a URL run scopes the mapping; it is never ingested

Rule 3 below still holds without exception: a per-deal document does not become KB content. On a URL run the SOW plays a **different role** — it answers "which journeys do I walk?", nothing more. What lands in the KB is what the **site** does: its screens, locators, cues, and interventions. Those are durable product facts that stay true for the next SOW against the same site, which is exactly why the KB is worth building once and reusing.

The line to hold: *"the SOW says which flows to map; the site says how they work, and only the latter is recorded."* Record a requirement the SOW states about the deal — volumes, deadlines, which records to touch, what to do with the results — and you have contaminated a reusable site KB with one engagement's scope.

### Classify every input before you read it for content

Each file plays one of three roles, and they are not interchangeable:

| Role | What it is | What happens to it |
|---|---|---|
| **reference / knowledge** | A finished deliverable the team has issued, or a product / spec / process doc explaining their offering. | Built into the KB — this is the material. |
| **brief** | A MOM, call transcript, email thread, or scoping note describing **one deal**: attendees, decisions, action items, one buyer's requirements. | **Set aside. Never enters the KB.** |
| **operator instruction** | A note about what to build. | Read as guidance, not recorded as a fact. |

**Set every brief aside, and say so in one line.** A brief is a *generate-time* input that arrives per deal, exactly like the recipient it describes. Fold one into the KB and that recipient's requirements start reading as the team's **standard** scope, so every future artifact silently inherits them — a contamination nothing downstream checks for. From a reference document the KB learns the substance; from a brief it learns nothing it should keep. Do not cite one, do not let it inform a single KB fact, not even "harmlessly" or as an illustration.

Operators hand over briefs constantly — they usually have a live deal in hand and it is the first file they reach for. Don't argue and don't discard: set it aside, mention it once, and point out that it is what the downstream generator takes.

**Where an archetype needs a finished deliverable and the inputs hold none, that is a halt, however many files there are.** Ten transcripts are zero reference documents, and "there was only one file, so it must be the reference" is the trap. Ask for a real one rather than building from briefs.

### Who `{client}` is

**`{client}` is the firm whose knowledge this KB encodes — the team that will use it — not any company its documents get addressed to.** The distinction matters because the artifacts are usually *about* the second kind of company: a transcript of Acme scoping an IVR for Contoso is Contoso-heavy on every page, but the KB it feeds belongs to **Acme**. `outputs/contoso/kb/` would be wrong — a KB per deal is a KB that never gets reused.

So when inferring the slug from `client`, else the inputs folder name, else the prompt: the firm is the one whose **product, format, and delivery practice** the artifacts reveal, not the one being sold to. If those two readings disagree, or the folder is named after the buyer, **ask** — do not guess. A KB filed under the wrong name is invisible to the next run, which then builds a second KB for the same team.

## Pipeline

Execute in order. Phase 2b runs **only on a URL run**; an artifacts-only run goes straight from scope to build.

1. **`pipeline/recognize.md`** — detect whether a KB already exists. On a first run, the LLM decides which archetype(s) apply by matching the playbook library against the artifacts (it never asks the operator). On an update, it infers the archetype and structure from the existing KB's own content (no re-match). **A `url=` settles the archetype on its own** — the material is a live site, so `web-flow` fires without matching; still match the artifacts if any were also supplied, since a run can be both.
2. **`pipeline/scope.md`** — understand the material's anatomy, derive the requirement from the operator's prompt, and **lock the scope** (requirement + in scope + out of scope). Ask only when the prompt and material leave real ambiguity. Everything downstream obeys this scope. **On a URL run this phase decides which journeys get walked**, from the SOW/prompt — so it must run *before* any browsing. Unbounded mapping has no completion condition; scope is what gives it one.
3. **`pipeline/map-site.md`** *(URL runs only)* — drive a real browser over the live site, walk the in-scope journeys, and record screens, locators, cues, interventions and provenance into a working observation corpus. Pauses to ask whenever it meets a login wall, a step-up challenge, or a state-changing control. This phase **produces the material** that phase 4 then treats exactly as it treats any other artifacts.
4. **`pipeline/build.md`** — deep-extract the in-scope components, draft or extend the KB conforming to the established structure, run the scope-gated gap loop, then save.

## The playbook library

Archetype advice lives in `.claude/playbook-library/playbooks/*.md` (**read-only**). Each playbook holds recognition signals, what-to-look-for tips, common pitfalls, useful gap-questions, typical KB shapes, and skip-entirely categories. Playbooks are **advice, not recipes** — kb-builder composes the actual KB by analyzing this client's real artifacts, *informed* by the playbook.

Current playbooks: `nodeflow`, `document-from-template`, `api-integration`, `web-flow`, `fallback` (the exclusion-only fallback for first-of-kind clients).

`web-flow` is the archetype for **live sites driven through their UI** — it fires on a `url=` run, and also on artifacts that stand in for a site (HAR captures, codegen scripts or existing browser tests, session recordings, click-path runbooks). Those proxies are worth asking for on any URL run: a team's own test suite names the exact automation attributes its engineers rely on, which is the most durable locator source that exists.

## Critical rules

1. **On update, the existing KB's structure is authoritative — extend it, don't reshape it.** New facts conform to the established containers / field paths / file shape. No renaming or re-bucketing of settled content.
2. **Scope first, then ask only what matters, but do ask.** The scope phase (`scope.md`) locks the requirement and what's in/out of scope before drafting, asking only when the prompt and artifacts leave ambiguity. In the gap loop, drop only questions that are out of scope, already answered by the artifacts, or that can't change the KB; **present every survivor to the operator and wait for answers before finalizing.** A safe default is not a reason to skip a question: surface it as a VERIFY ASSUMPTION with your proposed default. Never self-resolve all gaps into assumptions and save, and never guess a BLOCKING answer. **Whenever you have questions for the operator, display all of them as one severity-grouped list (BLOCKING first) and wait for the operator's input before proceeding** — don't drip them out across turns or proceed on the non-blocking ones without a reply; the relevance gate, not round-by-round rationing, is what keeps the list short, so don't pad it with the playbook's example questions. **A BLOCKING question halts the run** until the operator actually answers or explicitly waives it; a promise to supply a missing input later (e.g. "I'll share the palette export") does **not** count as resolved — pause and wait for that input to arrive. The gap log only **records** items the operator explicitly deferred or that no source can answer; it is never where an open BLOCKING question goes so the run can proceed. (This is about missing artifact *content*, not archetype selection.)
3. **Briefs are set aside, never ingested.** Classify every input before reading it for content (see the artifact-role gate above). A MOM, transcript, email thread, or scoping note describes one deal and teaches the KB nothing it should keep; absorbing one makes that recipient's requirements read as house standard in every artifact the KB ever produces. Set it aside, say so in one line, and point the operator at the downstream generator, which is what a brief is actually for.
4. **Record observed values verbatim** — node types, event names, headings, vocabulary as they appear in the artifacts. Don't paraphrase.
5. **If artifacts disagree among themselves, surface to the operator and resolve before saving.**
6. **If new artifacts reveal a shape the existing KB can't account for, surface it** to the operator (it may be a genuinely new structure) rather than forcing it into the old shape.
7. **Leak no internal meta into the KB.** No archetype/playbook names, KB filenames, section codes, or constraint IDs in recorded content. The KB's content alone conveys the archetype and structure, both to downstream deliverables and to a future update run.
8. **Decide the archetype yourself — never ask the operator which to use.** Pick the applicable playbook(s) from the artifacts; if nothing specific fits, use the fallback automatically.
9. **Never name another firm, and don't recite your internals.** Every operator sees only their own work: no other client's name, KB, artifacts, or generated skills may appear in anything you say or write — not as an example, not as a comparison, not "the way another client does it". Ask gap-questions in the operator's own vocabulary; the machinery here (archetypes, playbooks, pipeline phases, severity tiers) is for you, not for them.
10. **The KB must be self-contained — bundle every file it references.** If any KB file points to a supporting artifact (a node-template / palette export, a schema file, a query/template library, a reference example the generator must read), **copy that artifact into `outputs/{client}/kb/` and reference it by its bundled relative path.** Never reference an external, working-directory, or absolute path that can move or be missing when the KB is consumed — a downstream consumer (e.g. `config-agent`, `code-agent`, `api-agent`, or `document-generator`) is handed only the KB directory, so a referenced-but-absent file is a dangling dependency that breaks generation. At save time, scan the KB for references to anything outside the directory; bundle each one. If a referenced artifact can't be located or copied, treat it as a BLOCKING gap and surface it — never save a KB with a dangling reference.

   **A reference deliverable is one of those files, not merely a source you read.** Where the KB encodes a document format measured from a finished deliverable, that deliverable is still needed at generate time — it is the base document the DOCX path clones (styles, theme, header images, footer, margins, all inherited in one line that no style description can reproduce) and the target the PDF path diffs its output against page by page. Copy the canonical one into the KB alongside the extracted assets and record its bundled relative path. A KB that names the operator's original input path works only on the machine it was built on.

11. **On a URL run you are acting on a live system, so read-only is the default and mutations need an explicit go-ahead.** Navigating, opening, filtering and reading are free; submitting, creating, editing, deleting, sending or paying is not, and permission is granted **per action, not once per run**. Map a form's fields and stop at its button — everything past an unfired submit is recorded as *inferred*, never as observed. Prefer a non-prod origin, ask before mapping a third party's site, and **never attempt to solve or bypass a CAPTCHA, bot check, or rate limit** — record it as a finding and surface it. Record credential **names** only, never values, and never let a real customer record, identifier, or any PII you see while mapping reach the KB: capture the shape, redact the instance.

12. **On a URL run, mark provenance on every journey step — observed, inferred, or unmapped.** This is load-bearing, not bookkeeping: it is what tells `browser-agent` which steps are trustworthy and which need a human watching the first live run. An unmarked gap becomes an agent improvising on someone's production account, which is the exact failure this architecture exists to prevent. Never present an inferred step as observed, and never let a partially-walked journey read as complete.

## Folder layout

```
.claude/
├── skills/
│   └── kb-builder/
│       ├── SKILL.md
│       └── pipeline/
│           ├── recognize.md
│           ├── scope.md
│           ├── map-site.md    ← URL runs only: drive the browser, observe the site
│           └── build.md
└── playbook-library/
    └── playbooks/        ← shared archetype advice (read-only)

outputs/
└── {client}/
    └── kb/               ← the KB this skill produces and maintains
```

## Output

- `outputs/{client}/kb/` — the KB (first run: drafted; later runs: extended).

On a URL run the KB is a **web-flow KB**: screens and their URL patterns, the journeys walked, durable locators with fallbacks, verbatim success and failure cues, waits, the state-changing action inventory, the interventions a human must clear, and an explicit record of what went unmapped. That KB plus a SOW is what **`browser-agent`** executes.
