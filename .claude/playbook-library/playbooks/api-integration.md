---
id: api-integration
seen-in: [razorpay-api, tmdb-api, pubnub-api, getstream-api]
fallback: false
---

# Playbook: api-integration

Analysis advice and lessons learned for clients whose artifacts are **the reference documentation for an HTTP API** — a set of endpoints with auth, request/response shapes, and conventions. The downstream consumers (`code-agent` and `api-agent`) use the resulting KB for either of two families of job against this API:

- **Integration** — **write integration code** (an SDK call, a function, a glue script), or **execute a live pipeline of calls** that accomplishes a goal (authenticate, chain one response into the next request, handle retries / rate limits / pagination / failures, and report). Occasionally it emits a **config** the API ingests (a webhook subscription, a collection export).
- **API testing** — **generate a test suite** (contract/schema, functional/scenario, negative/boundary, auth, regression) or **execute a live test run** that exercises endpoints, **asserts** each response against the documented contract, and reports pass/fail. Testing is integration's mirror image: integration makes the API *do work*; testing *verifies the API behaves*, and it leans hardest on the API's negative space (errors, constraints, invalid states) plus explicit assertions and test data.

The consuming skill uses this playbook as guidance while analyzing the artifacts; the KB that gets generated is Claude's composition for *this* API, not a copy of this file. The same KB serves both families — the operator's prompt at consume time picks which; testing simply activates the assertion-oracle and test-data parts of the KB that integration can leave implicit.

**This archetype's distinctive stakes: the KB drives LIVE calls.** Unlike the artifact-emission archetypes (where a wrong fact yields a malformed file you can re-generate), a wrong fact here can fire a real request against a real service — double-charge a card, mutate prod, leak a secret, or chain a blank value forward. Completeness and fidelity are therefore not cosmetic; they are a safety contract. For the **testing** family the stakes invert but don't lessen: the KB is the **oracle** the assertions trust, so a wrong expected-status, a stale enum, or a missing error code becomes a false pass or a false failure — a test that is confidently wrong is worse than no test. Either way, capture the surface the consumer needs to act **correctly and safely**, not merely to describe the API.

## When this playbook applies (recognition signals)

Structural signals at the archetype level — vendor-agnostic by design. Specific vendor fingerprints (the exact base host, the exact auth header name, the exact error-field path, the exact status-code meanings) are NOT match conditions; they're captured from the actual artifacts during analysis.

- **The artifacts are API reference material**, in one or both forms:
  - **Prose reference** — Markdown / HTML / PDF pages describing endpoints, usually one file (or section) per resource, plus an intro/auth page and an index.
  - **A machine spec** — an OpenAPI/Swagger document (JSON or YAML), a Postman collection, a GraphQL SDL, a `.proto`/gRPC definition, RAML, or API Blueprint. (Several corpora are *generated from* such a spec and ship it alongside — that spec is gold; see "Close the gap first".)
- **They describe a request/response HTTP(S) surface.** Each operation carries a **method** (GET/POST/PUT/PATCH/DELETE, or a GraphQL/RPC operation) and a **path/endpoint**, with parameters, an example request, an example response, and status codes.
- **There is an authentication / authorization section** naming credentials and a scheme — API key (header or query), Bearer / static token, OAuth2 (client-credentials or refresh), Basic, JWT (often a server-signed vs client token split), HMAC / request signing, session/cookie login, or mTLS — together with one or more **base URLs / hosts**.
- **There is usually a conventions layer** — pagination, rate limits, error format, versioning, date/encoding rules — even if thin.
- **The downstream intent is to CALL the service, write code against it, or test it**, not to emit a self-contained artifact the platform renders.

If the artifacts don't match these signals, the playbook doesn't apply:

- A **node-and-transition graph** the consumer *emits and the platform imports* is `nodeflow`, even though it's JSON. The tell: that JSON is a *flow the consumer produces*; an API spec is a *description of an external service the consumer calls*. (An OpenAPI/Postman/GraphQL file is structured JSON/YAML too — but it documents endpoints + verbs + auth + request/response schemas, not a graph of nodes wired by transitions.)
- A **polished branded document to reproduce** (SOW/BRD/PRD) is `document-from-template`.
- A pure **prose brief with no endpoint/auth surface** is not this archetype; let the fallback catch it.

A mixed folder fires more than one playbook: API docs *plus* a node-flow export hits both `api-integration` and `nodeflow`; carry both forward.

## The analyst's real job: close the docs-to-runnable gap

**API reference docs describe the happy path of a platform you don't control — they are not a runnable contract.** Two distinct gaps separate "documented" from "the consumer can call this correctly and safely," and both must be closed. This is doubly true for the **testing** family: a test asserts against the *full* behavioral contract — how the API succeeds *and* how it fails — so the negative space the docs gloss (error bodies, field constraints, invalid transitions, auth failures) is not an edge case to defer but the primary material.

1. **Coverage gap — the docs cover a slice of the API.** A doc set (or a scraped/generated subset) routinely documents only some endpoints, mentions others by name without detail, and silently omits the rest. Some "endpoints" in the prose have **no REST surface at all** (they happen in a hosted UI or SDK widget) — fabricating one is worse than flagging it. Enumerate exactly what is documented in depth, list what is referenced-but-not-detailed, and never present the documented slice as the whole API.

2. **Depth / fidelity gap — each documented endpoint shows one happy-path example.** That single 200 example reveals the fields it populated and nothing about error responses, the **real success-discriminator** (how you tell success from failure on the wire), the full enum sets, defaults, field constraints, nullability, rate-limit behavior, pagination caps, idempotency scope, or the exact auth-signing recipe. These are invisible or partial in the docs, and they are exactly what makes a call *runnable and safe* rather than merely *describable*.

The operating rule that keeps this honest: **for every must-elicit category below, the row must resolve to an artifact request and/or a tagged question.** A category with no closing mechanism is a silent cap — and because this KB drives live calls, a silent cap doesn't just produce a malformed artifact, it fires a wrong request. (B = BLOCKING, I = IMPORTANT, V = VERIFY ASSUMPTION; tags map to the question bank below.)

Map the KB onto what the consumer's execution path actually extracts, so it can lift facts directly: **base URL(s) + which environment is non-prod; the auth scheme + credential names + token lifecycle + how each credential attaches; per-operation method / path / params / headers / request body schema / success status / response schema / read-only-vs-state-changing; conventions (content-type, encoding, pagination, rate limits + headers, idempotency, error envelope, required ordering); and what a *good* response looks like so each response can be validated before it is chained forward.** For testing, that same response contract doubles as the **assertion oracle** (assert status + schema + key fields against it), and three more things become first-class: the **negative contract** (which invalid input yields which error), **test data / fixtures** (sandbox accounts, test cards/tokens, seedable entities), and **isolation** (idempotent setup/teardown, which resources are safe to create and destroy).

### What the docs CAN reveal — mine these exhaustively

Extraction technique. In every case: **capture exhaustively what the docs show, AND log where they show only a happy-path slice** so the gap carries to the artifact-request / question round.

- **The full operation inventory the docs detail** — for each: method, path template (with `{path_params}` marked), every documented query/path param and required header, the request body schema, the example request, the example response, and the documented success status. Mirror the docs' own resource grouping (file-per-resource is common). Treat this set as a **floor**, not the whole API.
- **The auth section verbatim** — the scheme, the **credential names** (never values), where each attaches (header / query / path segment / body / signature param), any token/grant endpoint, stated token lifetime/TTL, scope/permission model, and any server-vs-client credential split. Quote header/param names exactly — they are wire-exact strings.
- **The conventions section** — pagination style and params, stated rate limits and their headers, the error-envelope shape, content-type, versioning, date/amount/encoding formats. Capture the global request/response envelope once.
- **Every example response body** — pull the field names, types, and especially the **shape that signals success vs failure** (a status field, an `entity`/type discriminator, a positional success flag, a top-level `success` boolean). Note which fields appear only conditionally (enriched/expanded/append).
- **Any embedded chains** — where a doc shows an id from one response used as a path/body param in another (`create X` → `act on X.id`), record the dependency; it seeds the workflows file.
- **Cross-corpus consistency** — a convention stated on one page may not hold on another; flag discrepancies rather than generalizing one page's rule.

### What the docs CANNOT reliably reveal — elicit every row

Walk this table for every api-integration client. For each row, decide whether the docs actually settle it; if not, close it via the **How to close it** column.

| Knowledge category | What the docs show | What's missing — and must be elicited | How to close it |
|---|---|---|---|
| **Credentials & their source** | the credential *names* and the scheme | which credentials *this* integration needs, their scopes/permissions, the **sandbox-vs-prod key distinction**, and that VALUES live only in the secrets source — never the KB, the chat, or a committed file | → operator + secrets file · Q-B |
| **Environment & safe default** | a base URL, maybe a "test mode" note | which host is **non-prod (the safe default to run against)**, any regional hosts, auxiliary hosts (token / image / data-plane / upload), and where the version sits in the path | → operator / docs · Q-B |
| **Auth signing / token recipe** | "signed with HMAC", "use a Bearer token", "JWT" | the **exact, runnable recipe**: for HMAC/custom — what is signed, in what order, the encoding, the timestamp/nonce header; for OAuth2 — token endpoint, grant type, scope/audience, lifetime, refresh/rotation; for JWT — the claim set, the server-vs-client split, and header quirks (e.g. a custom auth-type header, or that no `Bearer` prefix is sent) | → auth/signing reference or a known-good call · Q-B |
| **Success-discriminator & error envelope** | one happy-path `2xx` example | **how to tell success from failure on the wire** — HTTP status alone, a top-level `success` flag, a positional array flag, or an internal status code *distinct from the HTTP status*; where the error code/message live; the error-code catalog | → error reference + a known-good *error* response · Q-I |
| **Endpoint coverage** | the endpoints this doc page included | the operations referenced-but-not-detailed, and which "operations" have **no REST surface** (UI/SDK-only) so the consumer never fabricates one | → full spec (OpenAPI/Postman) · Q-I |
| **Per-field schema depth** | the fields a happy-path example populated | every request/response field with its type, **required/optional, default, enum set, constraints (length/range/regex), and nullability**, plus which response fields are present only conditionally | → spec · Q-I |
| **State-change classification** | the HTTP method | which ops actually change state vs read, which are **destructive/irreversible** (need the confirm-gate and a per-step destructive confirm), and whether method alone is a reliable signal here | → operator / docs · Q-B |
| **Idempotency & retry safety** | maybe an idempotency mention on a couple of ops | which ops accept an **idempotency key** (which header/param), which are safe to auto-retry, and what a resend after an *ambiguous* failure (timeout on a write) must do | → docs / operator · Q-I |
| **Rate limits & quotas** | "be reasonable" / a 429 mention | the concrete limit, the **rate-limit headers** and `Retry-After`, whether it's per-key/per-endpoint/per-account, and burst behavior | → rate-limit docs · Q-I |
| **Pagination exacts** | one list example | the style (cursor / offset / page / `Link` header / timetoken), the **stop condition**, the page-size default **and cap**, and the resume token's exact field name | → spec / known-good call · Q-I |
| **Required ordering & chains** | endpoints in isolation | the canonical multi-step **pipelines**, the **chain map** (which response field feeds which later request), preconditions/guards, resource **state machines** (legal transitions), and any **stateful handshake** (an initial call that returns a resume token used by the next) | → workflow/SME docs · Q-I |
| **Webhooks / events** (if in scope) | maybe a list of event names | the full event catalog, **each payload schema**, and the **signature-verification recipe** (header, algorithm, exactly what bytes are signed, the secret's name, raw-body-vs-reserialized) | → webhook docs · Q-I |
| **Versioning & deprecation** | the version in the path | which version to target, which endpoints are deprecated, and any breaking-change notes between versions | → docs · Q-V |
| **Encoding & value formats** | values as rendered | date/time/timezone format, amount/currency conventions (minor units, zero-/three-decimal rules), number/locale formatting, content-type and compression | → docs / known-good call · Q-V |
| **Expected-behavior matrix** (testing) | one happy-path success per op | the full **positive / negative / boundary** behavior — valid input → status + schema, each invalid input → which error code, illegal state-machine transitions → what the API does, auth-failure → which status — and how strict the assertion bar is (status only vs full schema vs exact field values) | → error reference + SME · Q-I |
| **Test data, fixtures & isolation** (testing) | example values, often dummy/redacted | the real **sandbox test accounts / cards / tokens**, seedable entities, which resources are safe to create / mutate / **destroy** in a run, and the setup/teardown that keeps tests isolated and repeatable | → sandbox/test-data docs + operator · Q-I |

### When a known-good captured call is available, validate the docs against it

Docs describe the API **above the wire** — they show a cleaned-up example, not the bytes the server actually returns. The signature failure of this archetype: the generated code (or the live pipeline) matches every documented field, yet breaks on the real response because the wire shape differs — a logical error rode an HTTP `200`, the cursor field had a different name, the error envelope nested the code one level deeper, the success flag was at array index 0.

So whenever the operator can share even **one** real captured call — a Postman/Insomnia run, a HAR export, a `curl` transcript, a recorded webhook delivery — make it ground truth and **diff every doc claim against it**:

- For each response the docs describe, compare the **actual key-set, the success-discriminator, and the error envelope** against what the capture shows. Where they differ, **the capture wins** — record the real shape.
- Capture a real **error** response too, not just a success: the error path is where docs are thinnest and where the consumer's validate-before-chaining step depends most on exact field paths.
- For HMAC/signed schemes, a captured request with its signature header lets you **reconstruct and verify the signing recipe** instead of guessing canonicalization — a wrong recipe looks like a generic `401`.
- Bake this into the KB as a generator/execution verify note: validate each response against the recorded success-discriminator and envelope before extracting from it.

A captured call is an **analysis and verification input**, like a known-good flow in nodeflow — read to confirm the docs, never shipped as the contract.

## Close the gap first: artifacts to request

Before — or alongside — the gap-question round, ask whether the operator can share any of these. **One good machine spec collapses dozens of questions and is far more reliable than reverse-inferring a schema from prose examples.**

**A. Machine specs — the authoritative surface:**

- **The OpenAPI/Swagger spec, Postman collection, GraphQL SDL, or `.proto`.** *This is the single highest-value artifact; it is most of a deep KB by itself* — paths, methods, params with types/required/defaults/enums, request/response schemas, auth schemes, servers. If the prose docs were generated from one, ask for the source spec.
- **A known-good captured call** (success *and* error) — to validate the spec/docs against the wire (above).
- **An SDK reference**, if code-gen targets a specific SDK — the client's method signatures and the call surface (not its source).

**B. Operational references the spec will NOT contain — just as load-bearing:**

What makes a call *safe and runnable* rather than merely *well-formed* rarely lives in the spec:

- **The error-code / status reference** — the catalog of error codes, where they sit in the envelope, and the success-vs-failure discriminator (especially any `200`-with-logical-error case).
- **The rate-limit & quota doc** — concrete limits, the headers, `Retry-After`, retry guidance.
- **The auth/signing guide** — the exact recipe for HMAC/custom signing, the OAuth token endpoint + scopes + lifetime, the JWT claim set, the sandbox-vs-prod key story.
- **The webhook/event reference** (if events are in scope) — event catalog, payload schemas, signature-verification recipe.
- **The workflow / "common integrations" guide** — the canonical call sequences and state machines the team actually runs.

**C. Credentials and environment — operator-only, and never in the KB:**

- **Which credentials are needed, by name**, their scopes, and **the safe (non-prod) environment** to default to. The KB records the credential *names* and where they attach; the **values come only from the secrets source at runtime** (`secrets=<path>` → `outputs/<client>/secrets.env` → process env). Never write a credential value into the KB, and never accept one pasted in chat as something to commit.

Record every referenced-but-undocumented endpoint / enum / error code as **known-but-unconfirmed** (named, no fabricated schema) until a spec or the SME confirms it. A *promise* to send the spec is a pending **BLOCKING** dependency — wait for it; don't draft around it and silently cap the surface.

When you receive a big spec (the OpenAPI/Postman file is the usual one), the consumer may need to read it at generation/execution time — so **bundle it into the KB directory and reference the bundled copy**, never the path it arrived on (per the skill's self-contained-KB rule). The **secrets file is the exception: never bundle it** — only its credential names.

### Presenting the request to the operator

Operators recognize "your API docs" and "a Postman export", not "the per-operation response-envelope schema." Render the ask in **their** terms: one line per thing you actually need, in plain language, as **one checklist** — and make the affordance explicit: **they can point you at files / a folder / a wiki / a Postman export / a screenshot — they don't have to type the answers.** Fill every row from *this* client's real surface; drop any row the docs already settled.

| What I'm asking for | What it contains | What I already have | Why I need it |
|---|---|---|---|
| **The API spec** (OpenAPI / Postman / GraphQL) | every endpoint with params, types, defaults, enums, and request/response schemas | the `{N}` endpoints your docs detail | to cover the whole surface with real types — not just the slice the docs walked |
| **A real captured call** (one success, one error) | the actual wire shape: success-discriminator, error envelope, cursor field | one happy-path example per endpoint | so generated code / live calls match the bytes the server returns, not the cleaned-up doc |
| **Error / status reference** | the error-code catalog and how success vs failure reads on the wire | `{observed_status_codes}` | so each response is validated correctly before its value is chained forward |
| **Auth & signing details** | the exact signing recipe / token endpoint + scopes + lifetime, and sandbox-vs-prod keys | the scheme is `{observed_scheme}`; credentials `{observed_cred_names}` | so authentication actually succeeds and the run targets the safe environment |
| **Rate-limit & webhook docs** | the real limits + headers; the event catalog + signature recipe | `{observed_rate_note}` / `{observed_events}` | so the pipeline paces itself and webhook payloads verify |
| **Credentials (by name) + which environment** | which keys/tokens to use and whether to run against sandbox or prod | the names the docs reference | so I can run — values go in your secrets file, never the KB or chat |

Close with the out: *"Hand these over however they exist — a docs link, an exported spec, a Postman collection, a screenshot — and I'll read and bundle them (except secret values, which stay in your secrets file). If one genuinely doesn't exist, tell me and I'll proceed on what the docs attest and log the gap."* Keep the severity tags so the operator sees which asks actually halt the build (credentials/environment and the signing recipe are BLOCKING for live execution; the rest IMPORTANT).

## Questions to ask the operator

Ask in **two tiers**. *First*, request the artifacts above — they answer most of this by construction. *Then* interview on what no spec contains. This is a phrasing bank, not a checklist: align scope first (is the deliverable code, live execution, or both? which resources are in play?), then ask only the in-scope unknowns whose answers would change the KB. Fill the `{...}` placeholders from your analysis. Every row in the table above resolves to one of these.

**BLOCKING — the KB cannot drive a correct/safe call without these**

- **Deliverable & scope.** "Should this KB drive **integration** (write code / run a pipeline that accomplishes a goal), **API testing** (generate a test suite / run live tests that assert and report), or both? If testing, which kinds — contract/schema, functional/scenario, negative/boundary, auth, regression? And which resources/operations are in scope — all of `{observed_resources}`, or a subset?"
- **Credentials & environment (for live execution).** "Which credentials does a run need — `{observed_cred_names}` — and what scopes? Is there a **sandbox/test** environment I should default to vs **prod**, and what are their base URLs? I'll record the credential *names*; their values must go in your secrets file, never the KB or chat."
- **Auth signing / token exacts.** "The docs say auth is `{observed_scheme}`. For the consumer to authenticate, I need the runnable specifics: `{for HMAC: exactly what's signed and in what order, the encoding, the timestamp/nonce header}` / `{for OAuth: the token endpoint, grant type, scope/audience, token lifetime, refresh handling}` / `{for JWT: the claim set, and the server-vs-client token split}`. Can you share the signing/auth guide or one captured signed request?"
- **State-change & destructive ops.** "Which of `{observed_ops}` actually change state, and which are **destructive/irreversible**? The consumer confirms before any mutation and double-confirms before anything destructive — so anything misclassified either fires without a gate or stalls a safe read."

**IMPORTANT — conventions the docs under-reveal**

- **Success-discriminator & errors.** "How does a response signal success vs failure — HTTP status alone, a `success` flag, a positional array element, or an internal status code separate from the HTTP code? Where do the error code and message live, and is there a full error-code catalog? Can a `2xx` still be a logical error?"
- **Endpoint coverage.** "The docs detail `{observed_ops}` and mention `{referenced_but_thin}` without full schemas. Can you share the full spec so I capture the rest — and are any of these **UI-/SDK-only** with no REST endpoint, so I never fabricate one?"
- **Field schemas, enums, defaults, constraints.** "For `{key_ops}`, what is the complete request/response schema — every field's type, required/optional, default, allowed enum values, constraints, and nullability? Examples only show the fields a happy path populated."
- **Idempotency & retries.** "Which write ops accept an idempotency key (and via which header/param), which are safe to auto-retry, and what should a resend do after a *timeout* on a write where I can't tell if it applied?"
- **Rate limits.** "What are the real rate limits, which response headers report remaining/reset, and is `Retry-After` honored? Per key, per endpoint, or per account?"
- **Pagination.** "List endpoints use `{observed_pagination}`. What's the exact style, the stop condition, the default page size and its **cap**, and the resume-token field name? I'll always cap and log truncation."
- **Workflows & chains.** "What are the canonical multi-step sequences (e.g. `{create → act → read-back}`), which response field feeds which later request, what preconditions guard each step, and are there resource state machines or a **stateful handshake** (an initial call returning a token the next call must resume from)?"
- **Webhooks/events** (if in scope). "What's the full event catalog, each payload schema, and the exact signature-verification recipe — which header, which algorithm, what bytes are signed (raw body?), and which secret?"
- **Expected-behavior matrix** (testing). "For the endpoints under test, what's the expected behavior beyond the happy path — which invalid inputs should return which error codes, what are the boundary values for `{constrained_fields}`, which state-machine transitions are illegal (e.g. `{example_illegal_transition}`), and what should an unauthenticated/under-scoped call return? And how strict should assertions be: status only, or full response-schema validation?"
- **Test data, fixtures & isolation** (testing). "Is there sandbox test data — test accounts, test cards/tokens, seedable entities — and which resources are safe to **create, mutate, and destroy** in a run? What setup/teardown keeps tests isolated and repeatable, and which environment may destructive test scenarios run against (never prod unless you say so)?"
- **Rare/odd op.** For an operation seen in only one place: "I saw `{op}` documented only in `{file}` — current and supported, or legacy/deprecated?"

**VERIFY ASSUMPTION — state the default, let them correct**

- **Environment default.** "I'll default live runs to `{sandbox_base_url}` (the non-prod host) and treat prod as an explicit, surfaced choice — confirm?"
- **Version.** "I'll target API version `{observed_version}` from the path — still the right one, or is a newer version preferred?"
- **Encoding/format.** "I'll use `{observed_date_format}` for dates and `{observed_amount_convention}` for amounts (e.g. minor units), per the examples — confirm these hold across endpoints?"
- **Retry policy.** "I'll auto-retry only idempotent reads and writes carrying an idempotency key, honor `Retry-After` on `429`, and stop a non-idempotent write on an ambiguous failure rather than resend — confirm this matches your expectations?"

## Common pitfalls

When composing the KB's Critical Rules, draw from these (the ones that apply + new ones the analysis surfaces). Each is a one-line "do not X because Y" the runtime can enforce on its own output.

- **Do not present the documented endpoints as the whole API.** Docs/specs are a slice; enumerate what's detailed, flag what's referenced-but-thin, and never fabricate the rest.
- **Do not invent an endpoint, field, param, status meaning, or auth flow** to make a request fit. If the docs lack it, record it as a gap — a fabricated fact here fires a wrong live call, not just a bad file.
- **Do not capture only the happy-path `2xx` example.** Record the error responses, the error envelope, and the **success-discriminator** — the consumer validates every response before chaining, and a logical error can ride a `200`.
- **Do not conflate the HTTP status with the API's internal status code.** Some APIs return `200` with a body-level failure flag, or carry their own numeric code distinct from the HTTP code; capture both and which one is authoritative.
- **Do not put credential VALUES in the KB.** Record credential *names* and where they attach; values come only from the secrets source at runtime. Never bundle the secrets file. (Security-critical: this KB drives live, authenticated calls.)
- **Do not leave the auth signing recipe vague.** "HMAC-SHA256 with the secret" or "send a JWT" is not runnable — capture the exact canonicalization / claim set / header conventions, or mark it BLOCKING. A wrong recipe surfaces as an opaque `401`.
- **Do not omit the read-only / mutating / destructive classification per op.** The consumer gates on it; an unclassified `POST` is sent without the confirmation it needed, and a safe `GET` may stall behind a needless gate.
- **Do not default to prod or invent a base URL.** Record sandbox and prod hosts and mark which is the safe default; running against prod is an explicit, surfaced choice.
- **Do not omit pagination caps or rate-limit/`Retry-After` handling.** The consumer loops; a missing cap silently truncates results or hammers the API into a `429` storm.
- **Do not omit idempotency-key support where it exists** — it is what makes a write safe to retry; without it the consumer must stop on ambiguous failures and can't safely resume.
- **Do not fabricate enums, defaults, constraints, or nullability the docs don't state.** Record them as gaps; a guessed enum or a wrong "required" makes generated code emit an invalid request.
- **Do not paraphrase paths, param names, header names, or path-embedded key segments.** They are exact wire strings (a custom auth-type header, a key embedded as a path segment, a signature query param) — quote them verbatim everywhere.
- **Do not model a realtime / long-poll / stateful API as plain request/response.** If subscribe/stream works by an initial handshake returning a resume token used by the next call, or responses are positional arrays with a success flag, capture that sequence and shape — it is invisible in a single endpoint description.
- **Do not skip validating the docs against a known-good captured call when one exists.** The wire shape (success-discriminator, error envelope, cursor field, signature) routinely differs from the cleaned-up doc example; the capture wins.
- **(Testing) Do not let assertions trust an unverified expected-value.** The KB is the test oracle; an expected-status or enum the docs only imply, not attest, produces confident false passes/failures — mark unverified expectations as such and don't assert on them.
- **(Testing) Do not run destructive or state-changing test scenarios against prod.** Negative and lifecycle tests create, mutate, and delete real resources — pin them to sandbox/test data and the safe environment, and isolate with setup/teardown.
- **(Testing) Do not test only the happy path.** The negative contract — invalid-input → error, boundary values, illegal state transitions, auth failures, rate-limit behavior — is the *point* of testing; the constraints/error catalog is its oracle, so capture it rather than defer it.
- **Do not include the platform's internal dashboard/admin click-paths, pricing, or marketing pages.** They are not the API surface and tempt the generator toward facts the runtime can't act on.
- **Do not hardcode vendor fingerprints into this playbook.** Base hosts, exact header/field names, status-code meanings, error-envelope paths, the credential list — all vary by vendor; they belong in the KB as observed values, not here.

## Typical KB shapes that have worked

Past clients of this archetype have settled around these files. Reference only — the file list is sized to what *this* API's surface and the chosen deliverable (code / live execution / config) demand. A small read-only API needs far fewer files than a payments API with webhooks and multi-step pipelines.

- `00-overview.md` — What the API does and the deliverable(s) the KB enables (code snippet / live pipeline / config). Glossary. **Environments & base URLs** (prod / sandbox / regional / auxiliary hosts; version-in-path; **which host is the safe non-prod default**). The global request/response envelope, content-type and encoding defaults, and the **success-discriminator** (how success vs failure reads on the wire).
- `01-authentication.md` — The auth scheme (matched to a catalog shape), the **credential names needed (by name, never values)** and where each attaches (header / query / path / body / signature), the server-vs-client token split if any, the token/grant endpoint + lifetime + refresh/rotation, the **exact signing recipe** for HMAC/custom schemes, and the scope/permission model. States plainly that values come from the secrets source at runtime.
- `02-operations.md` (or `02-operations/` split per resource for large APIs) — The operation catalog. One entry per endpoint: name/operationId, method, path template (path params marked), query/path params (type / required / default / enum / constraints), required headers, request body schema (type / required / default / enum / constraints / nullability), **success status**, response schema (key fields, which are nullable, which feed later calls), **classification: read-only / mutating / destructive**, **idempotency support**, and pagination applicability. Universal request/response fields documented once. The index lists every operation and flags referenced-but-undetailed ones.
- `03-conventions.md` — Pagination (style + params + default + **cap** + stop condition), rate limits (limits + headers + `Retry-After` + scope), the error model (envelope shape, where the code/message live, an HTTP-status-to-meaning table with this API's overrides, and any `2xx`-logical-error cases), retry/idempotency conventions, and date / time / amount / currency / encoding formats.
- `04-workflows.md` — Canonical multi-step pipelines: each as an ordered call sequence with a **chain map** (response field → next request input), preconditions/guards, resource **state machines** (legal transitions), any **stateful handshake** (initial call → resume token), and per-step safety notes (which steps mutate / are destructive). This is what lets the consumer run a real pipeline rather than one-off calls.
- `05-webhooks.md` — *(only if events are in scope)* The event catalog, each payload schema, the **signature-verification recipe** (header, algorithm, exactly-what-is-signed, secret name), and delivery/retry semantics.
- `06-test-scenarios.md` — *(only when testing is in scope)* The test plan as the consumer will generate or run it: per scenario, the call sequence, the **inputs** (valid, invalid, and boundary), and the **assertions** (expected status, expected error code, the response schema to validate, specific field expectations, headers/latency where relevant). Covers positive, negative, boundary, **auth-failure**, and **illegal-state-transition** cases, plus the **test data / fixtures** (sandbox accounts, test cards/tokens, seedable entities) and the **setup/teardown** that isolates and repeats a run. The constraints file is this file's negative-test oracle.
- `07-input-checklist.md` — Per-run inputs the prompt/operator must supply before a call, pipeline, or test run (ids, query values, body fields, target environment, and — when testing — which fixtures/test accounts to seed), tiered by criticality, plus the **credential-name → secret-key mapping** (names only) and which environment a run targets.
- `08-constraints.md` — Numbered "what makes a call invalid or unsafe": required-but-easily-missed fields, mutating/destructive ops that need confirmation, the prod-vs-sandbox guardrail, pagination/rate-limit caps, idempotency-on-retry rules, the validate-against-the-success-discriminator rule, and the secret-hygiene rule (values never in KB/chat/logs). When testing is in scope, this file doubles as the **negative-test oracle** — each "invalid" rule is a test case whose expected outcome is the documented error.
- `09-gap-log.md` — Documented-but-thin areas (incomplete error catalog, missing enums, undocumented defaults/constraints/nullability), endpoints referenced-but-not-detailed, pending artifacts (the spec, the error reference, the webhook catalog, a captured call, sandbox test data), and any credential whose name/scope/environment is still unconfirmed.

## Skip-entirely categories

What's typically out of scope. The KB should never emit:

- **Visual-flow / node-graph composition rules** — that's `nodeflow`; this KB describes calling an external service, not emitting a graph.
- **Branded-document visual style** — that's `document-from-template`.
- The platform's **dashboard/admin UI walkthroughs, click-paths, pricing, and marketing content** — not the callable surface.
- **SDK source internals** — capture an SDK's call signatures only when code-gen targets that SDK; never its implementation.
- **Operations with no REST/API surface** (hosted-UI or SDK-widget-only flows) — note them as out-of-band so the generator never fabricates an endpoint; do not document them as callable.
- **Credential values, secrets files, and full data-model/entity catalogs** beyond what the in-scope operations actually reference.
- **Full load / performance / chaos test harnesses** — functional, contract, negative, and auth testing are in scope; a load rig's tuning (concurrency ramps, soak profiles, latency SLOs) is its own concern. Capture it only if the operator asks, and never run it against prod.

The deliverable is integration code, a live API run, or a test suite/run — keep the KB to the callable, authenticatable, chainable, **assertable** surface, and nothing that tempts the consumer to act on a surface the runtime doesn't expose.

