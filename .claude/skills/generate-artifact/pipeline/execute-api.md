# Use case: api — execute a live API pipeline

Authenticate and run a **live pipeline of API calls** the KB describes, driven by the user's request — a `prompt` and/or a supplied **workflow document** (`workflow=<path>`, in any form: prose, JSON, YAML, PDF, or DOCX) — manage tokens, chain each response into later requests, validate as you go, and report. Obey the shared principles, asking-questions discipline, and **Execution safety** rules in `SKILL.md`.

Companion files:
- `reference/auth.md` — auth-scheme catalog, token lifecycle, secret hygiene.
- `reference/edge-cases.md` — the exhaustive failure/edge-case catalog. Phase 6 references it by name; read it before running.
- `reference/call.sh` — the robust single-call helper you copy into the run dir and invoke per step.

Run the phases in order. Questions and the confirm-before-mutate gate apply throughout.

## 0. Set up the run
- Pick `<client>` (parent of `kb`), make a run dir `outputs/<client>/runs/<runid>/` where `<runid>` is a timestamp (`date +%Y%m%d-%H%M%S` via Bash — the harness has no in-process clock). `output=<dir>` overrides.
- Copy `reference/call.sh` into the run dir and `chmod +x` it. Every call goes through it (uniform retry/backoff/redaction/status-capture).
- Create `run.log` (redacted, append-only audit trail) and `result.json` (final structured result) in the run dir.

## 1. Learn the API from the KB
Read the **entire** KB. The KB is the only authority for the API. Extract and write down (a short internal spec):
- **Base URL(s) and environments.** Which hosts exist (prod / sandbox / staging / region). If more than one, note which is non-prod — you will default there (see Phase 2).
- **Auth scheme.** How the API authenticates (API key, Bearer, OAuth2 client-credentials / refresh, Basic, HMAC signing, session login, mTLS, custom header). Which credentials it needs **by name**, the token endpoint and token lifetime if any, and how the credential is attached to each request. Hand this to `reference/auth.md`.
- **Operations (endpoints).** For each: method, path, path/query params, required headers, request body schema, and the **expected success status** + response schema. Note which are **read-only** vs **state-changing** (POST/PUT/PATCH/DELETE, or anything the KB marks mutating/destructive).
- **Conventions.** Content-type, date/encoding formats, pagination style (cursor / offset / page / `Link` header), rate limits + the rate-limit/`Retry-After` headers, idempotency-key support, error envelope shape (where the error code/message lives), and any required ordering between calls.
- **What a good response looks like** — so Phase 6 can validate before chaining.

If the KB doesn't document something you need (an endpoint, the auth flow, a status meaning), **say the KB is missing it** — do not fill the gap from general knowledge or guess a URL.

## 2. Resolve environment and credentials
- **Environment:** use `env=` / `base_url=` if given; else default to the **safest non-prod** environment the KB offers; else the only one. Whatever you pick, it goes into the Phase 4 confirmation in plain sight. Running against prod is always an explicit, surfaced choice.
- **Credentials:** the KB says *which* credentials are needed by name; their **values** come only from the secrets source — `secrets=<path>` if given, else `outputs/<client>/secrets.env`, else process env vars. Follow `reference/auth.md` for loading them safely.
- **If a required credential is missing**, stop and ask the operator to add it to the secrets file — name it exactly as the KB calls it, and say which source you read (the `secrets=` path / `outputs/<client>/secrets.env` / env var) so they know where to put it. If several are missing, list them all at once (this is the Phase 3c preflight, not one-at-a-time discovery). **Never** accept a secret pasted into chat as something to write into a committed file, and never echo it. If the operator pastes one anyway, use it for the run but tell them to move it to the secrets file and not commit it. Never fabricate a credential value or proceed with a blank one.

## 3. Parse the request and build the execution plan

The **request** — what to run this run — arrives as a free-text `prompt` and/or a supplied **workflow document** (`workflow=<path>`), and may be in any form. Ingest it first, then normalize it into an ordered plan. The request is the **what / sequence**; the KB stays the **how** (auth, endpoints, schemas, conventions).

**3a. Ingest the request (any format).** Read whatever was supplied and reduce it to plain, ordered intent:
- **Prose / natural language** (the `prompt`, a `.txt` / `.md` doc) → read it directly.
- **JSON / YAML** → parse it; if it already enumerates steps (op + inputs + chaining), honor that **sequence and the inputs it specifies** directly rather than re-deriving the order — but still resolve each step's **mechanics** (endpoint, method, headers, body schema) from the KB, never from a URL/method the doc may inline. If the doc's mechanics conflict with the KB, the **KB wins** — surface the conflict, don't silently follow the doc.
- **PDF** → extract its text with the `pdf` skill; **DOCX** → extract with the `docx` skill; then read the extracted text as prose.
- If **both** a `prompt` and a `workflow` doc are given, the doc carries the steps and the prompt carries values / overrides; reconcile them, and **ask if they conflict**. If neither is present, stop and ask — there is nothing to run.

**3b. Build the ordered plan.** Turn the ingested intent into an ordered list of steps, **each mapped to a documented KB operation**. For each step record:
- **op** (which KB endpoint), **method**, **inputs** (literal values from the request, or `← step N.field` when chained from an earlier response), and whether it is **read-only or state-changing**.
- **extract**: which field(s) of the response feed later steps (the JSONPath/`jq` path), and whether each is **required** (a missing required value breaks the chain → stop).
- **iteration/pagination**: does this step loop (over a collection from a prior step, or over pages)? What's the stop condition and a sane cap?
- **idempotency**: for state-changing steps, can it carry an idempotency key (KB-supported)? Is it safe to retry?
- **preconditions/guards**: anything that must be true first (e.g. "only DELETE if status==inactive").

**3c. Preflight — resolve every required input, prompt for whatever's missing.** Before executing, walk the whole plan *and* the auth scheme and enumerate every input each step needs: credentials (by the KB's name), path/query params, body fields the KB marks required, and the target environment. Tag each with its **source** — a literal from the request, `← step N.field` (chained), `<from secrets: NAME>`, a stated KB/convention default, or **MISSING**. For everything still **MISSING** with no documented default, **ask the operator now, in one consolidated, tightly-scoped prompt**: name each missing item and say where it goes (a credential → the secrets file, by name; a value → inline). Do not start the pipeline until they're supplied. This is the one place a grouped ask is correct — these are the genuine blockers, not speculative questions. Never substitute a blank, a guess, or a silent default for a required input.

**If the request names an operation the KB doesn't document, say the KB is missing it — don't invent an endpoint, method, or payload to make it fit.** Resolve other unknowns the usual way: KB convention or obvious default → take it and state it; real fork or a value only the operator has → ask now. **Missing required input for a call is a blocker — ask, don't invent.**

## 4. Confirm the plan (gate before any state change)
Present the plan as a compact, ordered list: per step the method, endpoint, resolved inputs (secrets shown as `<from secrets: NAME>`, never values), what gets extracted, and the **target environment**. Mark read-only vs state-changing clearly. Show any required input still unresolved as **MISSING** and clear it via the Phase 3c prompt **before** sending anything — never send a blank or guessed value in its place.

- **All read-only** → you may proceed without a gate (still show the plan).
- **Any state-changing step** → **wait for the operator's go** before sending the first one. For destructive steps (DELETE / irreversible), confirm again at that step with the concrete target (the actual id/payload), not just the plan.
- `dry_run=true` → print the full plan and the exact (redacted) calls you *would* make, send nothing, stop here.
- If the operator durably authorized autonomous execution for this run, you may skip the interactive go but still print the plan and still pause before anything **destructive**.

## 5. Authenticate
Acquire the credential/token per `reference/auth.md`: run the auth/token call (through `call.sh`), cache the token in the run dir with `chmod 600` (e.g. `run/.token`), record its expiry, and from here attach it to each request via shell substitution so the value never appears as a literal. Verify auth succeeded (a probe/whoami call if the KB offers one, else trust the token endpoint's 2xx) before doing real work. Handle the auth failure modes in `reference/auth.md` (bad creds, clock skew, scope, MFA/interactive — which you can't complete unattended, so surface it).

## 6. Run the pipeline
Execute steps in planned order. For each step:

1. **Build the request** — URL from base+path, params, headers (incl. auth via substitution), body from a file (`-d @body.json`) so payloads aren't inlined. Never inline secrets.
2. **Send via `call.sh`**, which captures status + headers + body to files and applies transport retry/backoff. Example:
   `BODY_FILE=run/s3.body HDR_FILE=run/s3.hdr LOG_FILE=run/run.log run/call.sh POST "$URL" -H "Authorization: Bearer $(cat run/.token)" -H 'Content-Type: application/json' -d @run/s3.body.json` (here `run/` = the run dir from Phase 0; response bodies can themselves echo secrets, so redact them before printing).
3. **Validate the response** against the KB's expectation for this op: is the status the expected success code? Does the body match the expected shape / error envelope? Use `jq` to parse (check `jq` is installed; if not, install or parse minimally). 
4. **Apply edge-case handling** from `reference/edge-cases.md` for whatever you got: `401` (refresh token once, then re-auth, then fail), `403`, `429`/rate-limit (honor `Retry-After`), `5xx` (already retried by `call.sh`), `4xx` business errors (read the error envelope, decide stop/skip/ask), non-JSON/empty/oversized body, pagination, timeouts.
5. **Extract and chain.** Pull the planned fields with `jq`. **If a required field is absent or null, stop** — record where, report, and do not send the dependent call with a blank/guessed value.
6. **Iterate** if the step loops (next page until no cursor / `Link`; or per-item over a collection), respecting the cap and rate limits.
7. **Record** a redacted line to `run.log`: step, method, endpoint, status, latency, what was extracted (values redacted if sensitive), retry count.

On a **state-changing** step: send only after the Phase 4 gate (and the per-step destructive confirm). After it returns, **confirm the effect** where the KB allows (read back the resource / check the returned id) before treating it as done.

**Partial failure:** if a step fails unrecoverably mid-pipeline, **stop by default** — do not barrel on through dependent steps. Report exactly what completed, what didn't, and the state left behind. If the KB defines a compensating/rollback action and the operator wants it, offer to run it. Resume guidance goes in the report.

## 7. Report and persist
Write `result.json` (final structured outputs the operator asked for, plus per-step status) and finalize `run.log`. Then give a short report:
- **What ran** — the ordered steps with status (✓/✗/skipped) and the key result of each.
- **The outcome** — the final answer/result the request asked for (e.g. created ids, fetched data summary).
- **What changed** — every state-changing call that actually succeeded (so the operator knows the real-world effect), and against which **environment**.
- **What failed / is open** — failures with the (redacted) error, anything skipped, any value the chain couldn't resolve, and **how to resume** (which step to restart from; whether already-completed mutations are idempotent).
- **Assumptions** you took (defaults, env choice) so they can correct them.

Never print a secret. Redact tokens/keys/credential values everywhere — chat, `run.log`, `result.json`.

## Re-runs / resume
A run dir is the record of what happened. To resume after a failure, read the prior `run.log`/`result.json`, skip steps already completed **whose effects you can confirm are durable** (re-read the resource or rely on a recorded idempotency key), and restart from the first unconfirmed step. Never blindly replay a non-idempotent mutation on resume — verify whether it already took effect first.
