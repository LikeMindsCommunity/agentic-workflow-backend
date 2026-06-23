---
name: generate-artifact
description: From a platform-specific Knowledge Base (KB) plus a user prompt, do whichever of three jobs the KB enables — (1) generate a CONFIG: a JSON/XML/YAML/NodeFlow or any structured config a platform consumes; (2) generate CODE: an SDK integration, a function, a glue/script snippet (NOT a whole project); or (3) execute an API workflow (driven by a prompt or a supplied workflow document — prose, JSON, YAML, PDF, or DOCX): authenticate and run a pipeline of live API calls (managing tokens, chaining one response into the next request, handling retries, rate limits, pagination, and failures) when the KB documents an API's request/response surface. The skill is platform-agnostic — every platform/API-specific fact (schema, endpoints, auth scheme, rate limits, what "valid" means) comes from the KB; the prompt says what to build or what to run. Use when an operator points at a KB and asks to produce its deliverable OR run its API workflow. Triggers: "generate the config / nodeflow from this KB", "write the SDK code from the KB", "use the {client} KB to build ...", "run / execute the API workflow from the KB", "call the {platform} API to ...", "authenticate and do {pipeline} against the API".
---

# generate-artifact

Turn a **platform-specific KB** + a **user prompt** into whichever of three things the KB describes.

```
                                              ┌─ config  ─► a structured config file, verified
   KB (how this platform works) ─┐            │
                                  ├─► route ───┼─ code    ─► an SDK/code snippet, verified
   prompt (what to do)          ─┘            │
                                              └─ api     ─► a pipeline of live API calls run, with a run report
```

The skill is a **generic engine**. It knows nothing about any platform or API. It learns the platform entirely from the KB at runtime and never hardcodes a node type, a schema, an endpoint, an auth scheme, or a language. Point it at a different KB and it produces a different platform's config/code, or drives a different platform's API, with no change to the skill.

## Three use cases, one engine

Each use case has its own file. Pick one (routing, below) and follow that file.

| Use case | What it does | File |
|---|---|---|
| **config** | Generate the structured config the KB describes (JSON / XML / YAML / NodeFlow / any config a platform ingests) and verify it. Nothing is executed. | `pipeline/generate-config.md` |
| **code** | Generate the code/SDK snippet the KB describes (an integration, a function, a glue script — not a whole project) and verify it. Nothing is executed. | `pipeline/generate-code.md` |
| **api** | Authenticate and run a **pipeline of live API calls** the KB describes — manage tokens, chain responses into later requests, handle retries / rate limits / pagination / failures — and report. | `pipeline/execute-api.md` |

`config` and `code` are both **generation** and share the backbone below; only their *Generate* and *Verify* steps differ, and each file owns those. `api` is **execution** and is a different shape end-to-end.

### Choosing the use case (routing)

Decide once, up front, then follow that file:

1. **The request's verb** (in the `prompt`, or read from the `workflow` doc). *generate / build / produce / write / create* → generation (config or code). *run / execute / call / fetch / authenticate / sync / trigger / do {a sequence} against the API* → **api**. A supplied `workflow=<path>` doc is itself a strong signal for **api**. An explicit `op=config|code|api` overrides everything.
2. **config vs code.** If the deliverable is a structured config a platform ingests → **config**. If it is source the user runs/embeds (a function, an SDK integration, a glue script) → **code**. The KB's declared target usually settles it; the request can too.
3. **api vs generation.** If the KB documents a **request/response API surface** (endpoints, methods, auth, status codes) and the request asks to *act*, it's **api**. If the KB documents a **grammar/schema for an artifact** and the request asks for *a thing*, it's generation.
4. **Still ambiguous, or the KB supports several and the prompt fits more than one** → ask one quick question to pick. Never guess between "produce a file" and "make live calls" — they have very different consequences.

## Inputs

| Input | Meaning | Used by | Required |
|---|---|---|---|
| `kb=<dir>` | The platform-specific KB directory (e.g. `outputs/<client>/kb/`). The single source of truth for **how** this platform expresses things / **how** its API works. | all | **Yes** |
| `prompt` / `$ARGUMENTS` | Free text: **what** to build, or **what** workflow to run and with what inputs. | all | Yes\* |
| `workflow=<path>` | A per-run **workflow document** naming the ordered API steps to execute — supplied in any form: prose, JSON, YAML, PDF, or DOCX. The skill extracts and normalizes it into the execution plan. It is the *what to run*; the KB stays the *how*. | api | No\* |
| `output=<dir>` | Where to write the deliverable (config/code) or the run log (api). Default: `outputs/<client>/generated/` or `outputs/<client>/runs/`, where `<client>` is the parent of `kb`. | all | No |
| `op=config\|code\|api` | Force the use case instead of routing. | all | No |
| `secrets=<path>` | Where credential **values** live for api (an env file or a path the operator names). The KB declares which credentials are *needed by name*; their *values* never come from the KB or the chat. Default search: `secrets=`, then `outputs/<client>/secrets.env`, then process env vars. | api | No |
| `env=<name>` / `base_url=<url>` | Which environment to run api against (e.g. `sandbox` vs `prod`), if the KB defines more than one. **Defaults to the safest/non-prod environment the KB offers.** | api | No |
| `dry_run=true` | api plans and prints every call (redacted) but sends **no** request. | api | No |

**Beyond these, assume nothing exists.** No sample artifacts, no reference deliverables, no hidden config. If you want one, either (a) read it from the KB, (b) take it from the request (the `prompt` and/or the `workflow` doc), or (c) ask.

\*For `api`, the run is driven by the **request** — at least one of `prompt` or `workflow=<path>` must be present (both may be combined: the doc carries the steps, the prompt carries values/overrides). For `config`/`code`, `prompt` is required as before.

## Core principles (all use cases)

1. **Platform-agnostic, always.** Every platform/API-specific fact — schemas, field names, node/event types, endpoints, methods, auth scheme, status-code meanings, rate limits, naming rules, defaults, what counts as valid — comes from the KB. The **request** (the `prompt` and/or the `workflow` doc) supplies only *intent and per-run values* (which op to run, ids, filters, payload values) — **never platform facts**. If a fact you need isn't in the KB, you do not know it: ask or flag it, **even if the request appears to state it**. **Never invent platform facts (an endpoint, method, status meaning, or auth flow) from general knowledge — or from a mechanic a request inlines.**
2. **KB is *how*, the request is *what*.** The KB carries the platform's grammar / API contract; the request (prompt and/or workflow doc) carries the specific thing to build or run, expressed using only the KB's constructs. Even when a workflow doc spells out mechanics (a literal URL, method, header, or payload), the KB stays authoritative on the contract: take the doc's *intent and values*, resolve the *mechanics* from the KB, and **surface any conflict** rather than silently following the doc.
3. **Verify before you trust.** config/code: derive validity checks from the KB and run them (each file's Verify step). api: check every response against the KB's expected status/shape before chaining it forward. A config that is 95% right is broken; a pipeline that chains a wrong/blank value forward is worse.
4. **Ask as you go — never force a batch.** See below.
5. **Secrets are sacred (api).** Credential values never appear in the chat, in a command's literal text, in the run log, or in any committed file. See `reference/auth.md`.
6. **Side effects need consent (api).** Read-only calls run freely; anything that **changes state** (typically POST/PUT/PATCH/DELETE, or anything the KB marks mutating/destructive) is **planned and confirmed before it is sent**. See "Execution safety" below.

## Asking questions

Ask the user a question **whenever you actually need to, at the moment you need to** — not as one big upfront questionnaire, and not a long checklist at the end. Most forced batch questions turn out irrelevant; do not generate them.

- Ask only when the answer would **materially change the deliverable or the calls you'll make** AND it is **not already answered by the KB or the request** (the prompt and/or the workflow doc).
- If a reasonable default exists (in the KB's conventions, or an obvious choice), **take it, state the assumption, and keep going**. Reserve real questions for genuine blockers, true forks where guessing wrong is costly, or **anything that would send a state-changing request you're unsure about**.
- Ask **one or a few tightly-scoped questions at a time**, in the flow of the work, then continue.
- **Missing *required* inputs are the one case where a consolidated ask is right.** When you've identified genuine blockers you can't resolve — a credential the KB requires but the secrets source lacks, or a required call parameter with no value and no default — surface them **together, once, before you act**, naming each and where it goes (a credential → the secrets file by that name; a value → inline). That isn't the forbidden wall of speculative questions; it's the blockers you already know you have. Never invent or blank-fill a required input to avoid asking.
- Never ask the user to supply platform knowledge that belongs in the KB — if the KB is missing it, say the KB is missing it.

You run **in the main conversation**, so asking mid-flow just works. Use that.

## Shared generation backbone (config & code)

`generate-config.md` and `generate-code.md` both follow these steps. Each file overrides only **Generate** and **Verify** with its type-specific rules — do not duplicate the backbone there.

1. **Learn the platform from the KB.** Read the **entire** KB. Determine, from its content alone: what deliverable it enables and in what form (which config format, or which code/SDK + language) — an explicit KB declaration of its target governs; the grammar to obey (schema, field/symbol catalog, node/event types, vocabulary, naming conventions, required vs optional parts, and any reference structures — alias→JSON maps, templates, canonical examples — to be used faithfully, not approximated); and **what "valid" means** for this platform (the checks the file's Verify step will run).
2. **Understand the request and fix the deliverable.** Parse the prompt: what to build and the specific content. Reconcile with what the KB can produce. One clear deliverable → proceed. KB supports several and the prompt is ambiguous → ask one quick question. Prompt asks for something the KB doesn't cover → say so plainly; don't fabricate platform facts.
3. **Plan the deliverable.** Form an internal, platform-neutral spec of what's being built, mapped onto the KB's constructs. Missing specific → take a KB-supported default and state it, or ask if it's a real fork. The deliverable is the artifact, not the plan.
4. **Generate.** → defined per use case (`generate-config.md` / `generate-code.md`).
5. **Verify and repair.** → defined per use case. Loop generate↔verify until clean or genuinely stuck; surface anything unresolved with the reason — never silently ship a failing check.
6. **Deliver.** Write the artifact to `output` (default `outputs/<client>/generated/`). Then a short report: what was produced and where, the key assumptions you made, any open questions or checks you couldn't satisfy, and (if useful) how to verify it on the platform. On a re-run into an existing `output`, treat it as an **update**: apply only what the new prompt changes, keep a tiny `manifest.json` (what was built, from which KB, key assumptions, open items) beside it.

## Execution safety (api only)

The non-negotiables when you make live calls. Full handling lives in `pipeline/execute-api.md` and `reference/edge-cases.md`; the rules that must never be skipped:

- **Confirm before you mutate.** Before the **first** state-changing call (and before any destructive one), show the plan — method, endpoint, the resolved payload, the target **environment** — and wait for a go. `dry_run=true` forces plan-only. Read-only GETs need no confirmation.
- **Default to the safe environment.** If the KB exposes sandbox/staging *and* prod, default to the non-prod one. Running against prod is an explicit, stated choice — surface the target env in the confirmation.
- **Never leak secrets.** Tokens, keys, and credential values are read from the secrets source at call time via shell substitution, never typed as literals, never printed (no `curl -v`), and **redacted** in the run log.
- **Make retries safe.** Only auto-retry calls that are safe to repeat (idempotent reads, or writes carrying an idempotency key the KB supports). Never blindly re-fire a non-idempotent mutation after an ambiguous failure — verify state or ask.
- **Stop on a broken chain.** If a required value isn't in a response (the next call depends on it), do **not** fabricate or send a blank — stop, report where, and surface it.

## Pipelines

Pick the use case (routing, above), then run that file in order. The asking-questions and safety rules apply throughout, not just at one gate.

- **config** → `pipeline/generate-config.md` (+ the shared backbone above)
- **code** → `pipeline/generate-code.md` (+ the shared backbone above)
- **api** → `pipeline/execute-api.md` (which uses `reference/auth.md`, `reference/edge-cases.md`, and the `reference/call.sh` helper template)

## Never do this

- Never hardcode a platform fact in the skill, or carry one over from a previous run / general knowledge. The KB is the only authority.
- Never invent a field, node type, event, endpoint, method, status-code meaning, or auth flow to make something fit. If the KB lacks it, say so.
- **config/code:** never emit a generator program or scaffold a project — the deliverable is the artifact itself. Never emit a fixed-per-type constant just because documentation lists it as an "option"; use the value attested in a known-good example or flag it.
- **api:** never put a secret value in a command literal, a log, or a file. Never fire a state-changing call without confirmation (unless the operator durably authorized it for this run). Never invent a base URL or default to prod. Never chain a missing/blank extracted value forward. Never auto-retry a non-idempotent write after an ambiguous result.
- Never dump a forced wall of clarifying questions. Ask narrowly, when it matters, as you go.

## Folder layout

```
.claude/skills/generate-artifact/
├── SKILL.md                 ← this router + shared engine (incl. the generation backbone)
├── pipeline/
│   ├── generate-config.md   ← use case: config  (Generate + Verify for configs)
│   ├── generate-code.md     ← use case: code    (Generate + Verify for code)
│   └── execute-api.md       ← use case: api     (live API pipeline)
└── reference/
    ├── auth.md              ← auth-scheme catalog + token lifecycle + secret hygiene
    ├── edge-cases.md        ← exhaustive failure/edge-case handling for api
    └── call.sh              ← robust single-call helper (retry/backoff/redaction) the api use case copies into the run dir

outputs/<client>/
├── kb/         ← the KB (input — produced by kb-builder)
├── secrets.env ← credential VALUES for api (git-ignored; never committed) — optional default location
├── generated/  ← config/code write the deliverable here (+ manifest.json)
└── runs/       ← api writes a redacted run log + result here, one dir per run
```
