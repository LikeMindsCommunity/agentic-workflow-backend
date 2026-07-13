---
name: api-agent
description: From a platform-specific Knowledge Base (KB) plus a Statement of Work / solution doc (SOW), produce an LLD/ED — a Low-Level Design / Execution Document — a structured, ordered, fully-specified, SELF-CONTAINED execution plan that a SEPARATE Runner agent later carries out. The KB's shape determines the execution surface (the skill detects it — no mode to pass): a REST API contract (endpoints, methods, schemas, status codes, auth, pagination) yields steps that are HTTP calls; a product web-flow KB (pages, navigation, UI actions, selectors, success cues) yields steps that are browser-agent actions. The skill resolves the KB + SOW into a ready-to-execute plan and writes it to the output directory (default fallback `outputs/<client>/lld/`); the Runner executes from the document ALONE and never opens the KB. This skill does NOT authenticate, hold secrets, pick the environment, or make any live call/click — it only DESIGNS the execution; the Runner executes it. Platform-agnostic: every endpoint, method, auth flow, status meaning, page, and selector comes from the KB; the SOW says WHAT workflow to run. Use when an operator points at a KB + SOW and wants the execution document a Runner will follow. Triggers: "create the LLD / execution doc from this KB + SOW", "design the {platform} API workflow", "design the browser flow from the KB", "api-agent", "produce the runbook the Runner will execute".
---

# api-agent

Turn a **platform-specific KB** + a **SOW** (the client's statement of work / solution doc, in any form) into an **LLD/ED** — a *Low-Level Design / Execution Document*: an ordered, fully-specified, ready-to-execute plan that a **separate Runner agent** later carries out as **live cURL calls** or **browser-agent actions**. **This skill designs; it never executes.**

```
   KB  (the platform's API contract) ─┐                                   ┌─ (later, separately)
                                      ├─► design ─► verify ─► LLD/ED  ───►│  a Runner agent reads
   SOW (the workflow to run)         ─┘            (the document)         └─ the LLD/ED and executes
```

The skill is a **generic engine**. It knows nothing about any API and hardcodes nothing — no endpoint, no auth flow, no status meaning. It learns the API entirely from the KB at runtime. Point it at a different KB and it designs a different platform's execution document, with no change to the skill.

**The hard boundary: this skill produces a document, full stop.** It does **not** authenticate, does **not** read or hold credential *values*, does **not** send any request, and does **not** drive a browser. All of that is the **Runner's** job, later, against the LLD/ED this skill writes. The LLD/ED names the credentials the Runner will need **by name** (never their values) and tells the Runner exactly how to use them.

**The KB's shape determines the execution surface — the skill detects it, there's no mode to pass.** A KB built by `kb-builder` is one of two shapes, and the LLD/ED follows whichever it is:
- **REST API contract** (endpoints, methods, request/response schemas, status codes, auth, pagination) → the steps are **HTTP calls**, for a cURL Runner.
- **Product web flows** (entry URLs, pages, navigation, UI actions, form fields, on-screen success cues) → the steps are **UI actions** (navigate / click / fill / assert), for a browser-agent Runner.

Same engine, same boundary, same declarative output — only *what the KB describes* and *what a "step" is* differ. It's obvious from the KB which one applies; **detect it and proceed** (only ask if a KB genuinely documents both surfaces and the SOW doesn't disambiguate).

**Self-contained — resolve the KB into the LLD, never reference it.** The LLD/ED is a **distilled, execution-focused projection of the KB**, scoped to this one workflow: it carries the *resolved* facts each step needs (the exact path/method/body schema/expected response, or the exact page/action/selector/expected state) **transcribed faithfully from the KB**. The Runner executes from **the LLD/ED alone** — it never opens the KB. Do **not** write "see KB §X"; resolve it. (This is "rewrite," not "copy the whole KB" and not "paraphrase loosely": only what the workflow needs, stated concretely, nothing invented.) A one-line provenance note — which KB + version it was derived from — is welcome for traceability; a *dependency* on the KB at run time is not.

## Inputs

| Input | Meaning | Required |
|---|---|---|
| `kb=<dir>` | The platform-specific KB directory. The single source of truth for the **API contract** — auth, endpoints, methods, schemas, status codes, pagination, rate limits, idempotency. | **Yes** |
| `sow=<path>` | The Statement of Work / solution doc — **what workflow** to design. Any form: prose, `.md`, `.txt`, JSON, YAML, **PDF**, or **DOCX**. The skill extracts and reads it. | **Yes\*** |
| `prompt` / `$ARGUMENTS` | Free-text intent and/or per-run values that refine or override the SOW. | No\* |
| `output=<dir>` | Where to write the LLD/ED. **Default fallback: `outputs/<client>/lld/`**, where `<client>` is the parent of `kb`. | No |

**The execution surface is not an input.** Whether the steps are HTTP calls or browser actions is **detected from the KB's shape** (a REST API contract → HTTP; product web flows → UI actions), not passed in. Record the detected surface in the LLD/ED so the Runner knows what kind of runner to be; only ask if a KB documents both and the SOW doesn't settle it.

\*At least one of `sow` or `prompt` must be present — there must be a workflow to design. If both are given, the SOW carries the workflow and the prompt carries values/overrides; reconcile them and **ask if they conflict**.

**The execution environment is not an input.** Which host to actually hit (sandbox / staging / prod) is a **run-time** choice the operator hands the **Runner** later — just like secrets. The skill does **not** take an `env`/`base_url`, does **not** bind a target environment into the document, and does **not** pick one. It **documents** the environments the KB defines (their names + base URLs, as reference) and **instructs the Runner to default to non-prod** (prod being an explicit run-time choice). Per-step URLs are expressed against a symbolic base the Runner binds when it picks the environment.

**Beyond these, assume nothing exists.** No sample plan, no hidden config. If you want a fact, either (a) read it from the KB, (b) take it from the SOW/prompt, or (c) ask. **Never read or embed a secret value** — the LLD/ED references credentials by name only.

## Core principles

1. **Design only — never execute.** This skill writes the LLD/ED and stops. No auth call, no live request, no browser action, no secret value touched. If the operator wants it *run*, that's the Runner's job against this document; say so and hand off the LLD/ED.
2. **Platform-agnostic, always.** Every API fact — base URLs, auth scheme, endpoints, methods, headers, request/response schemas, status meanings, pagination, rate limits, idempotency support — comes from the **KB**. The SOW/prompt supplies only *intent and per-run values* (ids, filters, payload values, which workflow). If a fact you need isn't in the KB, you do not know it: flag it, **even if the SOW appears to state it**. **Never invent an endpoint, method, status meaning, or auth flow from general knowledge — or from a mechanic the SOW inlines.**
3. **KB is *how*, the SOW is *what*.** The KB carries the API contract; the SOW carries the specific workflow, expressed using only the KB's documented operations. Even when the SOW spells out a literal URL/method/header/payload, the **KB stays authoritative** on the contract: take the SOW's intent and values, resolve the mechanics from the KB, and **surface any conflict** in the LLD/ED rather than silently following the SOW.
4. **Secrets are the Runner's concern — name them, nothing more.** The LLD/ED lists every credential the Runner will need **by the exact name the KB documents** (e.g. `<from secrets: API_KEY>`) and stops there. It does **not** hold a value, does **not** ask anyone for one, does **not** store one, and does **not** name a secrets file or source. *Where* the values come from and *who is asked for them* belongs entirely to the **Runner** at run time. This skill never reads, requests, or persists a credential value; the only authority for *which* credentials exist is the KB.
5. **Design the safety in.** The LLD/ED must mark every step read-only vs state-changing, flag destructive steps, specify the confirm-before-mutate gate the Runner must honor, **instruct the Runner to default to the non-prod environment** (prod is an explicit run-time choice — the design never binds a target environment itself), and tell the Runner where to stop on a broken chain. A plan that lets the Runner barrel a wrong/blank value into a mutation is a broken plan.
6. **Self-contained, not a reference.** Resolve every fact the Runner needs *into* the LLD/ED, transcribed faithfully from the KB and scoped to this workflow; the Runner executes from the document alone and never opens the KB. Never defer with "see the KB" — if you'd point at it, inline it instead. (Provenance note welcome; run-time dependency on the KB, no.)
7. **Ask as you go — never force a batch.** See below.

## Asking questions

Ask **only** when the answer would **materially change the LLD/ED** AND it is **not already answered by the KB or the SOW/prompt**.

- If a reasonable default exists (a KB convention or an obvious choice), **take it, state the assumption in the document, and keep going.**
- Ask **one or a few tightly-scoped questions at a time**, in the flow of the work — never a wall of speculative questions.
- **Missing *required* design inputs are the one case where a consolidated ask is right** — e.g. the SOW names an operation the KB doesn't document, or a required call parameter has no value and no default. Surface them together, once, naming each. (You do **not** ask for credential *values* — those are the Runner's concern; you only note which credentials the Runner will need.)
- Never ask the operator for API knowledge that belongs in the KB. If the KB is missing it, say the KB is missing it.

You run **in the main conversation**, so asking mid-flow just works.

## Pipeline

Run the phases in order. Companion references are **the skill's own authoring guidance** — checklists of what a good LLD/ED must *specify*. They are **not** shipped to the Runner; nothing in `reference/` is copied into the output. The LLD/ED is **declarative**: it lays down endpoints, request bodies, expected responses, and execution *policy* (timeouts, retries, redaction) as **instructions** — *how* to execute (which tool, which language, how to implement a retry) is the Runner's to figure out. This skill ships no scripts.

- `reference/auth.md` — (**API-contract KB**) what the LLD/ED must specify about **authentication & token lifecycle**, per scheme.
- `reference/edge-cases.md` — (**API-contract KB**) what failure/edge-case handling and execution policy the LLD/ED must specify (status triage, pagination, retries, idempotency, partial-failure).
- `reference/browser.md` — (**web-flow KB**) what the LLD/ED must specify for a browser-agent Runner (entry/login, per-step UI actions + locators, waits, assertions, and UI-flow failure handling).

### 1. Learn the platform from the KB (and detect the surface)
Read the **entire** KB. The KB is the only authority. **First, detect the surface** from what the KB documents — a REST API contract, or product web flows — then extract accordingly. (It's obvious from the content; only ask if the KB clearly covers both and the SOW doesn't settle which the workflow uses.)

**Either way:**
- **Environments.** Which targets exist (prod / sandbox / staging / region) and which is non-prod — base URLs for an API, site origins for a web product. Document them all as **reference options for the Runner**; the LLD/ED never picks or binds one (the operator tells the Runner which to hit at run time) and instructs the Runner to default to non-prod.
- **What "success" looks like** at each step — so the LLD/ED can tell the Runner what to validate before chaining.

**If the KB is a REST API contract** (steps will be HTTP calls):
- **Auth scheme.** How the API authenticates (API key, Bearer, OAuth2 client-credentials / refresh, Basic, HMAC, session login, mTLS, custom header), **which credentials / env vars it needs — by the exact name the KB documents** (you carry only the names forward, never values, never a source), the token endpoint + lifetime if any, and how the credential attaches to each request. → `reference/auth.md`.
- **Operations (endpoints).** For each: method, path, path/query params, required headers, request body schema, **expected success status** + response schema. Mark **read-only** vs **state-changing** (POST/PUT/PATCH/DELETE, or anything the KB marks mutating/destructive).
- **Conventions.** Content-type, date/encoding formats, pagination style (cursor / offset / page / `Link`), rate limits + headers, idempotency-key support, error-envelope shape, any required ordering between calls.

**If the KB documents product web flows** (steps will be UI actions): → `reference/browser.md`.
- **Entry & session.** The entry/landing URL, whether a login is required and how it's performed (the login page, which fields, which credential **names** — never values), and how session is carried (cookie/logged-in state).
- **Flows & screens.** The pages/screens the workflow traverses, the **navigation** between them, and for each step the **UI action** (navigate / click / fill / select / upload / assert), the **target element** (the locator/selector or stable accessible name the KB provides), and any input fields + their values.
- **Success & failure cues.** The on-screen state that confirms a step worked (a toast, a URL change, a visible element), and the cues that mean it failed.

If the KB doesn't document something you need (an endpoint, the auth flow, a page, a selector), **say the KB is missing it** — do not fill the gap from general knowledge or guess a URL/selector.

### 2. Read the SOW and fix the workflow
Ingest the SOW in whatever form it arrives — prose/`.md`/`.txt` read directly; JSON/YAML parsed (if it already enumerates steps, honor that sequence and inputs, but still resolve each step's mechanics from the KB); **PDF** via the `pdf` skill; **DOCX** via the `docx` skill — and reduce it to plain, ordered intent. Reconcile with what the KB documents:
- One clear workflow → proceed.
- KB supports several paths and the SOW is ambiguous → ask one quick question.
- SOW names an operation the KB doesn't document → say so plainly; don't invent an endpoint/method/payload to make it fit.

### 3. Build the ordered execution plan
Turn the workflow into an ordered list of steps, **each mapped to a documented KB operation/flow**. For each step record everything the Runner will need — *resolved from the KB into the step itself* (no "see KB").

**If the surface is a REST API — each step is an HTTP call:**
- **op** (which KB endpoint), **method**, **inputs** (literal values from the SOW/prompt, or `← step N.field` when chained from an earlier response), and whether it is **read-only or state-changing** (and **destructive** if so).
- **request shape**: the **path** (expressed against a symbolic base, e.g. `{base_url}/v1/...`, that the Runner binds when it picks the environment — never a hardcoded host), path/query params, required headers, and the request body **schema/template** (values filled from the SOW/prompt; credentials shown only as `<from secrets: NAME>` using the KB's exact name — never a value, never a source).
- **expected response**: the success status and the response shape the Runner should validate before chaining.
- **extract**: which response field(s) feed later steps (JSONPath/`jq` path), and whether each is **required** (a missing required value breaks the chain → the Runner must stop).
- **iteration/pagination**: does this step loop (over a collection, or over pages)? Stop condition and a sane cap.
- **idempotency**: for state-changing steps, can it carry an idempotency key (KB-supported)? Is a retry safe?
- **preconditions/guards**: anything that must be true first (e.g. "only DELETE if status==inactive").
- **error handling**: per-step guidance from `reference/edge-cases.md` (what each non-2xx means here and whether the Runner should retry / skip / stop / ask).

**If the surface is product web flows — each step is a UI action:**
- **action** (navigate / click / fill / select / upload / assert), the **target element** (the locator/selector or stable accessible name from the KB), and **inputs** (literal values, or `← step N.<captured>` when chained), and whether the action **changes state** (submits/creates/deletes) vs merely reads/navigates.
- **page/precondition**: which screen the Runner must be on first, and any guard ("only proceed if logged in / if the row exists").
- **expected result**: the on-screen state that confirms success (URL change, a visible element/toast, field value) — what the Runner asserts before moving on.
- **capture**: any on-screen value to read for later steps, and whether it is **required** (missing → stop the chain).
- **iteration**: does this step repeat (over a list/table on the page)? Stop condition and a sane cap.
- **waits & failure cues**: what to wait for, and the cues that mean failure (error banner, element-not-found, navigation timeout) → `reference/browser.md`.

**Preflight the design.** Walk the whole plan *and* the auth scheme and tag every input with its **source** — a literal from the SOW, `← step N.field`, `<from secrets: NAME>`, a KB/convention default, or **MISSING**.
- **Credentials are never MISSING and never asked here.** Every credential the auth scheme or a request needs is tagged `<from secrets: NAME>` (the KB's exact name) and treated as **resolved-by-the-Runner** — the design is complete without its value. Do not ask the operator for a secret value, do not chase a missing one, do not name where it lives. If the KB doesn't document a credential the auth flow clearly requires, that's a *KB gap* — flag it as "the KB doesn't name the credential for X," not a request for the value.
- **Only non-secret design inputs can block.** A required call parameter (an id, a filter) with no value and no documented default is the one thing that may still be **MISSING**. For those, ask the operator now (one consolidated, tightly-scoped prompt), or record them in the LLD/ED as inputs the Runner must be given. **Never** blank-fill or guess a required input into the document.

### 4. Verify the design
Before writing, check the plan against the KB:
- Every step maps to a **real** KB operation with the **right method, path, and required params/headers**.
- Every chained `← step N.field` is actually produced by step N's documented response.
- The auth section matches the KB's declared scheme and names the right credentials.
- Read-only vs state-changing vs destructive flags are correct; the confirm-before-mutate gate is present, and the document lists the KB's environments without binding one, instructing the Runner to default to non-prod.
- Pagination, rate-limit, and idempotency notes match the KB's conventions.

Fix anything that fails. Surface anything you can't resolve in the document with the reason — **never ship an LLD/ED with an unverified or invented step.**

### 5. Write the LLD/ED and report
Write the LLD/ED to `output` (default `outputs/<client>/lld/`). Make it **self-contained — complete enough that the Runner needs nothing but this document and the credential values + environment it gets at run time** (the LLD names the credentials and lists the environments; it carries neither values nor a bound target). Every fact is **resolved from the KB into the document**, never referenced. Recommended structure (Markdown is the default; emit JSON/YAML instead if the operator/Runner expects a machine-readable plan — the *content* below is what matters, not the syntax):

1. **Goal & summary** — what this workflow accomplishes (from the SOW), in a sentence or two.
2. **Execution surface** — HTTP calls (cURL Runner) or browser actions (browser-agent Runner), as **detected from the KB**. State which, so the Runner knows what kind of runner to be; do **not** prescribe the implementation (no script, no specific tool) — the Runner picks how to execute.
3. **Environments (reference)** — list the environments the KB documents (each name + its base URL) as the **options the Runner chooses from**. Do **not** bind a target or hardcode a host; step URLs use a symbolic base (`{base_url}`) the Runner resolves once it picks an environment. Instruct the Runner to **default to non-prod** — targeting prod is an explicit run-time choice the operator makes with the Runner, not here.
4. **Authentication / sign-in** — the credentials needed **by the KB's exact name** (`<from secrets: NAME>`) and how each is used, with the Runner responsible for obtaining their values (asking the user, reading its own secret store) — never a value, never a secrets file/path/source. *`curl`*: the auth scheme, token lifecycle (endpoint, lifetime, refresh rule), and how the credential attaches to each request (from `reference/auth.md`). *`browser`*: the login flow (page, fields, the credential names to type) and how logged-in session is carried/verified (from `reference/browser.md`).
5. **Execution plan** — the ordered steps from Phase 3, each fully specified and **resolved** (no "see KB"). *`curl`*: op, method, symbolic-base URL, params/headers, request body template, expected status + response shape, what to extract and whether required, iteration/pagination, idempotency, guards, per-step error handling. *`browser`*: action, target element/locator, inputs, the page/precondition, the expected on-screen result to assert, what to capture and whether required, iteration, and waits/failure cues.
6. **Execution policy (non-functional instructions)** — the behavioral rules the Runner must honor, stated **declaratively** (not as code). *`curl`*: per-request timeout, retry/backoff policy (which conditions are retryable — transport errors, `429`, `5xx` — attempts, backoff shape, honor `Retry-After`), rate-limit pacing, pagination caps, redaction (never log credentials/`Authorization`), concurrency limit. *`browser`*: per-action wait/timeout, retry on transient flake (element-not-yet-visible, navigation timeout), pacing, and redaction (never log typed secret values). *What* the policy is, is the design's job; *how* to implement it is the Runner's.
7. **Safety gates** — which steps are read-only vs state-changing vs destructive; the confirm-before-mutate rule the Runner must honor; the stop-on-broken-chain rule; partial-failure handling.
8. **Final outputs** — exactly what the Runner should return when done (ids created, data fetched, etc.).
9. **Open items / assumptions** — any MISSING input the Runner must be supplied, any KB gap, any assumption you took.

Either way, the document stays **declarative and self-contained** — every step resolved from the KB, no "see KB," and it never ships a script or dictates the Runner's tooling.

Then a short report: **what** LLD/ED you produced and **where**, the **key design choices/assumptions** (the execution surface detected, the environments documented), and any **open items** the Runner will need (MISSING inputs, KB gaps, and that it must choose the execution environment + supply secrets at run time). On a re-run into an existing `output`, treat it as an **update** — apply only what the new SOW/prompt changes and keep a tiny `manifest.json` (what was designed, from which KB + SOW, key assumptions, open items) beside it.

## Deliverable
An **LLD/ED** — a Low-Level Design / Execution Document (Markdown by default, or JSON/YAML if a machine-readable plan is wanted) — fully specifying an ordered API/UI execution for a separate Runner agent. It is **declarative**: endpoints, request bodies, expected responses, and execution policy (timeouts, retries, redaction) as instructions — never a script or a dictated toolchain. Validity is "every step maps to a real KB operation/flow with correct mechanics, every chain resolves, auth and safety and execution policy are specified, the document is self-contained, and nothing is invented." **No live call is ever made by this skill, and it ships no executable.**

## Never do this
- **Never execute, and never ship an executable.** No auth call, no live request, no browser action. This skill writes a **document** and hands off — it ships no scripts and dictates no tooling; *how* to execute is the Runner's to decide.
- **Never make the Runner depend on the KB.** Resolve every needed fact into the LLD/ED; never write "see the KB" or leave a step pointing at it. The Runner executes from the document alone. (A provenance note naming the KB is fine; a run-time dependency is not.)
- **Never touch a secret value, and never own secret resolution.** The LLD/ED names credentials only, using the KB's exact names (`<from secrets: NAME>`). This skill never reads, embeds, prints, asks for, or stores a value, and never names a secrets file/path/source — obtaining values (and asking the user) is the **Runner's** job. A credential the KB doesn't name is a KB gap to flag, not a value to request.
- Never invent an endpoint, method, status meaning, auth flow, or base URL to make the plan fit. If the KB lacks it, say so. **Never bind the document to a concrete environment or hardcode a host** — list the KB's environments as options, use a symbolic base in step URLs, and instruct the Runner to default to non-prod (the operator picks the environment with the Runner at run time).
- Never chain a field a step's documented response doesn't actually produce; never blank-fill a MISSING required input into the document.
- Never dump a forced wall of clarifying questions. Ask narrowly, when it matters, as you go.

## Folder layout
```
.claude/skills/api-agent/
├── SKILL.md                 ← this file (router + LLD/ED design pipeline)
└── reference/               ← the skill's OWN authoring guidance (never shipped to the Runner)
    ├── auth.md              ← (curl) what the LLD/ED must specify about auth + token lifecycle, per scheme
    ├── edge-cases.md        ← (curl) what failure/edge-case handling + execution policy the LLD/ED must specify
    └── browser.md          ← (browser) what the LLD/ED must specify for a browser-agent Runner

outputs/<client>/
├── kb/    ← the KB (input — produced by kb-builder)
└── lld/   ← the LLD/ED document is written here (+ manifest.json), unless output= overrides
```
