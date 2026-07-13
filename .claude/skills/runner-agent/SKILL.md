---
name: runner-agent
description: Execute an LLD/ED — the Low-Level Design / Execution Document that api-agent produced — as a live run, carrying it out exactly as written from the document ALONE. The LLD/ED's recorded execution surface decides what a step is: an HTTP-call plan runs as live cURL requests (authenticate, manage the token lifecycle, chain each response into the next request, handle retries, rate limits, pagination, idempotency, partial-failure); a browser-flow plan runs as live browser-agent actions (sign-in, navigate / click / fill / assert, waits, capture). The Runner owns the run-time reality the design deliberately left open: it PICKS the environment (defaults to non-prod; prod/live is an explicit choice), SOURCES its own credential values by the names the LLD lists (asking the operator / reading its own secret store — never from the document), honors the LLD's execution policy and safety gates (confirm before any state change, double-confirm destructive, stop on a broken chain), and writes a redacted run record (run dir + run.log + result.json). It reads the LLD/ED and nothing else — never the KB, never the SOW — and never redesigns the plan or invents a missing mechanic; a defective or incomplete LLD is surfaced, not patched. Platform-agnostic: every endpoint, method, auth flow, status meaning, page, and selector comes from the LLD. Use when an operator points at an LLD/ED and wants it run. Triggers: "run / execute this LLD", "execute the execution document", "runner-agent", "run the {platform} workflow from the LLD", "carry out the runbook the api-agent produced".
---

# runner-agent

Execute an **LLD/ED** — the *Low-Level Design / Execution Document* that **api-agent** produced — as a **live run**: carry it out exactly as written, **from the document alone**, as live **cURL calls** or live **browser-agent actions**. **This skill executes; it never designs.**

```
   LLD/ED ──► read the document ──► resolve env + secrets ──► confirm ──► EXECUTE (live) ──► run record
  (the plan)   (alone — not the KB)   (Runner's run-time job)   (gate)    cURL / browser     run.log + result.json
```

This is the **execution counterpart** of `api-agent`. api-agent reads a KB + SOW and **writes** the LLD/ED, touching nothing live. runner-agent reads that LLD/ED and **runs** it. The two never overlap: the design says *what* to do and *where the choices are*; the Runner decides *how* and *which*, and makes the live calls.

The skill is a **generic engine**. It knows nothing about any API or product and hardcodes nothing — no endpoint, no auth flow, no status meaning, no page, no selector. It learns the entire run from the **LLD/ED** at run time. Point it at a different LLD and it runs a different platform's workflow, with no change to the skill.

**The hard boundary — execute from the document, own the run-time reality, never redesign.**
- **The LLD/ED is the only source of truth.** The Runner reads the document and **nothing else** — never the KB, never the SOW. The LLD is self-contained by construction (api-agent resolved every fact into it); if a step says "see the KB," or a mechanic a step needs is missing, that is a **defective LLD** — stop and surface it, do **not** open the KB and do **not** fill the gap from general knowledge.
- **The Runner owns what the design left open: the environment and the secret values.** It **picks the environment** (binds the LLD's symbolic `{base_url}`; defaults to non-prod; prod/live is an explicit, surfaced choice) and **sources its own credential values** by the exact names the LLD lists — asking the operator or reading its own secret store. Values never come from the LLD (it carries names only) and never get written back into it.
- **Never redesign and never invent.** Run the plan as written. The Runner does not re-derive the order, swap an endpoint, change a payload schema, or "fix" the plan from API knowledge. If the LLD is wrong, incomplete, or its mechanics conflict with what the platform returns, **stop and report** — a broken plan is the designer's to fix (re-run api-agent), not the Runner's to silently patch.

## Inputs

| Input | Meaning | Required |
|---|---|---|
| `lld=<path>` | The **LLD/ED** to execute (the document api-agent wrote, e.g. `outputs/<client>/lld/<workflow>-lld.md`). The single source of truth for the whole run — surface, environments, auth, steps, policy, gates. Markdown, JSON, or YAML. | **Yes** |
| `env=` / `mode=` / `base_url=` | Which environment to bind for this run. If omitted, default to the LLD's **non-prod** environment. Targeting prod/live is always explicit and surfaced. | No |
| `secrets=<path>` | Where the Runner reads credential **values** (an env file or a JSON creds file). Resolution order if omitted: `secrets=` → `outputs/<client>/secrets.env` → a `*-creds.json` the operator names → process env vars → **ask the operator**. | No |
| `output=<dir>` | Where the run record goes. **Default: `outputs/<client>/runs/<runid>/`**, where `<client>` is derived from the LLD path and `<runid>` is a timestamp. | No |
| `dry_run=true` | Print the full plan and the exact (redacted) calls/actions it *would* make, send/click nothing, stop. | No |
| `prompt` / `$ARGUMENTS` | Per-run **values** for inputs the LLD flagged MISSING/open, an explicit go-ahead, or a durable authorization for autonomous execution. Never a place to redefine the plan's mechanics. | No |

**The execution surface is not an input.** Whether steps are HTTP calls or browser actions is **read from the LLD/ED** (api-agent recorded it). Only inspect the step shapes to confirm if the field is somehow absent; never override it.

**Beyond these, assume nothing exists.** Every fact about *what to do* comes from the LLD. Every *value* (secrets) and the *environment* come from the operator/secret store at run time. If you want anything else, ask. **Never read a secret value out of the LLD (it has none), and never write one into it.**

## Core principles

1. **Execute only — never design, never invent.** Run the LLD as written. No re-deriving the plan, no swapping an endpoint/payload, no "fixing" it from general API knowledge. If the plan is wrong or incomplete, **stop and surface** — re-running api-agent is how a plan gets fixed, not a silent patch here.
2. **The LLD/ED is the only authority — never the KB.** Read the document alone. It is self-contained by construction; a "see the KB" pointer or a missing mechanic is a **defective LLD to flag**, not a reason to open the KB. Never carry a fact from a previous run or from training.
3. **Own the run-time reality the design left open — the environment and the secret values.** Pick the environment (bind `{base_url}`; default non-prod; prod/live is explicit and surfaced in the confirmation). Source every credential **value** yourself by the LLD's exact name; the LLD carries names only and never receives a value back.
4. **Honor the safety gates.** Confirm before any **state-changing** step; **double-confirm destructive** steps at the moment of the call with the concrete target; **stop on a broken chain** (a required extracted/captured value that's missing → do not proceed with a blank or guess); on partial failure, **stop — don't cascade**.
5. **Honor the execution policy as written.** Timeouts, retry/backoff, `Retry-After`, rate-limit pacing, pagination caps, redaction, concurrency — exactly as the LLD declares them. *What* the policy is comes from the document; *how* to implement it is yours.
6. **Redacted, faithful observability.** The run dir is the record. Redact every secret everywhere (chat, `run.log`, `result.json`). Report what actually ran vs. what was skipped/capped — **never present partial as complete**.
7. **Ask only for genuine blockers — never for design facts.** A MISSING required input the LLD flagged, or a credential value not in the secret source, are the only things to ask about (one consolidated ask). API/UI mechanics are never asked — they live in the LLD; if the LLD lacks one, that's an LLD gap to surface, not a question for the operator.

## Asking questions

Ask **only** when the answer is a genuine run-time blocker AND it is **not already in the LLD/ED**.

- **Missing required inputs and missing credential values are the one case where a consolidated ask is right** — surface them together, once, before executing: name each MISSING non-secret input the LLD flagged (and where the value goes), and name each credential absent from the secret source (by the LLD's exact name, saying which source you read so the operator knows where to put it).
- **Never ask the operator for design facts** — endpoints, methods, schemas, selectors, status meanings. Those are the LLD's job. If the LLD is missing one, say *the LLD is missing it* (and that api-agent must be re-run); don't ask the operator to supply API knowledge.
- The environment is the operator's run-time choice — confirm it (especially prod/live), but default to non-prod and keep moving.

You run **in the main conversation**, so asking mid-flow just works.

## Pipeline

Run the phases in order. The confirm-before-mutate gate and the questions discipline apply throughout. Companion references are the Runner's **own execution how-to**:

- `reference/auth.md` — (cURL) how to authenticate live: load secrets safely, mint/cache/refresh tokens, attach the credential per scheme, handle auth failures.
- `reference/edge-cases.md` — (cURL) how to handle live failures: status triage, transport/ambiguous-write, retries, rate limits, pagination, extraction/chaining, idempotency, partial-failure.
- `reference/browser.md` — (browser) how to drive the UI live: sign-in/session, per-step act → wait → assert → capture, and UI failure recovery.
- `reference/call.sh` — the robust single-call helper the Runner copies into the run dir and invokes per HTTP step (uniform retry/backoff/redaction/status-capture).

### 0. Set up the run
- Derive `<client>` from the LLD path (e.g. `outputs/<client>/lld/...` → `<client>`). Make a run dir `outputs/<client>/runs/<runid>/`, where `<runid>` is a timestamp from `date +%Y%m%d-%H%M%S` via Bash (the harness has no in-process clock). `output=<dir>` overrides.
- Create `run.log` (redacted, append-only audit trail) and `result.json` (final structured result) in the run dir.
- **cURL surface:** copy `reference/call.sh` into the run dir and `chmod +x` it — every HTTP call goes through it.
- **Browser surface:** prepare the run dir for evidence (screenshots/DOM snapshots, secrets masked) per the LLD's redaction policy.

### 1. Read the LLD/ED (the only input)
Read the **entire** LLD/ED. It is the only authority — **do not open the KB or the SOW.** It is the document **api-agent** wrote, and follows its section structure (1 Goal & summary · 2 Execution surface · 3 Environments · 4 Authentication/sign-in · 5 Execution plan · 6 Execution policy · 7 Safety gates · 8 Final outputs · 9 Open items). Map each section to what you need below; don't assume a fixed heading — read by meaning, since an older LLD may label a section differently. Extract:
- **Execution surface** — cURL (HTTP) or browser, as the LLD records it (api-agent's §2; an older LLD may call this "Runner mode"). This decides what a "step" is for the rest of the run.
- **Environments offered** — the names + base URLs/origins the LLD lists as options, and which it marks non-prod (your default).
- **Auth / sign-in** — the scheme and the credential **names** (cURL: scheme, token lifecycle, how the credential attaches; browser: the login page/fields and how session is carried).
- **The ordered steps** — each with its fully-resolved mechanics (cURL: op, method, symbolic-base path, params/headers, body template, expected status + response shape, what to extract and whether required, iteration/pagination, idempotency, guards, per-step error handling. browser: action, target locator, inputs, page/precondition, expected on-screen result, what to capture and whether required, waits/failure cues).
- **Execution policy** — timeouts, retry/backoff, rate-limit pacing, pagination caps, redaction, concurrency.
- **Safety gates** — which steps are read-only / state-changing / destructive; the confirm-before-mutate rule; the stop-on-broken-chain rule; partial-failure handling.
- **Final outputs** — exactly what to return when done.
- **Open items** — the MISSING inputs the LLD says the Runner must be supplied, and any KB gaps it flagged.

If the LLD points at the KB, or a step is missing a mechanic it needs, **stop and surface it as a defective LLD** — do not open the KB and do not invent the mechanic.

### 2. Resolve the environment
Bind the symbolic `{base_url}`/origin every step uses:
- Use `env=` / `mode=` / `base_url=` if given; else default to the LLD's **non-prod** environment; else its only one.
- Whatever you pick goes into the Phase 4 confirmation **in plain sight**. Targeting **prod/live is always an explicit, surfaced choice** — never the silent default.
- Guard against mixed environments (a token minted against sandbox but a call sent to prod): auth and target must match.

### 3. Resolve credentials and preflight inputs
- **Credentials:** the LLD names *which* credentials are needed; their **values** come only from the secret source (`secrets=` → `outputs/<client>/secrets.env` → a named `*-creds.json` → process env). Load them safely per `reference/auth.md` — never inline a value, never echo one.
- **Preflight:** walk the whole plan *and* the auth scheme and tag every input with its **source** — a literal from the LLD, `← step N.field` (chained), `<from secrets: NAME>`, or **MISSING**.
- **One consolidated ask for the genuine blockers:** every credential absent from the secret source (name it exactly as the LLD calls it, say which source you read), and every required non-secret input the LLD flagged as open with no value supplied via `prompt`. Name each and where it goes. **Do not start until they're supplied; never blank-fill, guess, or fabricate a value.**

### 4. Confirm the plan (gate before any state change)
Present the plan as a compact, ordered list: per step the method + endpoint (or action + target), resolved inputs (secrets shown as `<from secrets: NAME>`, never values), what gets extracted/captured, and the **target environment**. Mark read-only vs state-changing vs destructive clearly.
- **All read-only** → you may proceed without a gate (still show the plan).
- **Any state-changing step** → **wait for the operator's go** before the first one. For **destructive** steps (DELETE / irreversible / money-moving), confirm **again** at that step with the concrete target (the actual id/payload), not just the plan.
- `dry_run=true` → print the full plan and the exact (redacted) calls/actions you *would* make, do nothing, stop here.
- If the operator durably authorized autonomous execution for this run, you may skip the interactive go but **still** print the plan and **still** pause before anything destructive.

### 5. Authenticate / sign in
- **cURL:** acquire the credential/token per the LLD's auth section + `reference/auth.md` (run the token call through `call.sh`, cache the token `chmod 600` in the run dir, record expiry, attach it via shell substitution so it never appears as a literal). Verify auth succeeded before real work. Interactive/MFA legs can't run unattended — surface and stop.
- **Browser:** perform the sign-in per the LLD + `reference/browser.md` (navigate the login page, fill the credential fields by name, submit, confirm the logged-in cue). MFA/CAPTCHA/emailed-code → can't run unattended — surface and stop.

### 6. Execute (live)
Run steps in the LLD's order.

**cURL — per step:**
1. **Build the request** — URL from `{base_url}`+path, params, headers (auth via substitution), body from a file (`-d @body.json`) so payloads aren't inlined. Never inline a secret.
2. **Send via `call.sh`** (captures status + headers + body to files; applies transport retry/backoff).
3. **Validate** the response against the LLD's expectation for this step (expected status; body shape / error envelope). Use `jq` to parse.
4. **Apply edge-case handling** from `reference/edge-cases.md` for whatever you got (`401` refresh-then-reauth, `403`, `429`/`Retry-After`, `5xx`, business `4xx`, non-JSON/empty/oversized, pagination, timeouts).
5. **Extract and chain.** Pull the planned fields with `jq`. **If a required field is absent/null, stop** — record where, report, never chain a blank/guess.
6. **Iterate/paginate** if the step loops, respecting the LLD's cap and rate limits; **log when you hit a cap**.
7. **Record** a redacted line to `run.log` (step, method, endpoint, status, latency, retries).

**Browser — per step:** act → **wait** for the LLD's success cue → **assert** the expected on-screen state before moving on → **capture** any required value (missing → stop). Recover from transient flake (element-not-yet-visible, navigation timeout) per the policy; a missing page/element or failed assertion is terminal for that step — stop, don't cascade. Redact typed secrets in any log/screenshot.

**State-changing steps** run only after the Phase 4 gate (and the per-step destructive confirm). After one returns, **confirm the effect** where possible (read back the resource / check the returned id / verify the record appears) before treating it as done — a UI submit with no idempotency key especially must be verified, not blindly re-submitted.

**Partial failure:** if a step fails unrecoverably mid-run, **stop by default** — do not barrel through dependent steps. Report what completed, what didn't, and the state left behind. If the LLD defines a compensating/rollback action and the operator wants it, offer to run it.

### 7. Report and persist
Write `result.json` (the LLD's Final-outputs, plus per-step status) and finalize `run.log`. Then a short report:
- **What ran** — the ordered steps with status (✓/✗/skipped) and the key result of each.
- **The outcome** — the final answer the LLD asked for (created ids, fetched data summary, the `short_url`, etc.).
- **What changed** — every state-changing call/action that actually succeeded, and against which **environment** (so the operator knows the real-world effect).
- **What failed / is open** — failures with the (redacted) error, anything skipped or capped, any chain that couldn't resolve, anything the LLD flagged as **not run** (don't fake it), and **how to resume**.
- **Assumptions** taken (the environment chosen, any default) so they can correct them.

Never print a secret. Redact tokens/keys/values everywhere — chat, `run.log`, `result.json`.

### Re-runs / resume
A run dir is the record of what happened. To resume after a failure, read the prior `run.log`/`result.json`, **skip steps already completed whose effects you can confirm are durable** (re-read the resource, or rely on a recorded idempotency key / a unique-field read-back), and restart from the first unconfirmed step. **Never blindly replay a non-idempotent mutation on resume** — verify whether it already took effect first.

## Deliverable
A **completed live run of the LLD/ED** plus its **run record** — a run dir containing `run.log` (redacted audit trail), `result.json` (the Final-outputs + per-step status), the per-step response/evidence files, and a short report. Success is "every step ran as the LLD specified (or stopped safely with a clear reason), every state change was gated and confirmed, every secret stayed redacted, and the reported outcome matches what actually happened." The Runner makes the live calls/clicks; it never edits the LLD and never opens the KB.

## Never do this
- **Never redesign or invent.** No re-deriving the plan, no swapping an endpoint/method/payload, no inventing a mechanic the LLD lacks. A wrong or incomplete LLD is surfaced (re-run api-agent), never silently patched.
- **Never open the KB or the SOW.** The LLD/ED is self-contained and is the only authority. A "see the KB" pointer in the LLD is a defect to flag, not an instruction to follow.
- **Never touch a secret unsafely.** Values come only from the secret source, are referenced by shell substitution, are never inlined/echoed/printed, are redacted in all output, and are **never written back into the LLD**. A credential the LLD doesn't name is an LLD gap to flag, not a value to invent.
- **Never bind prod silently.** Default to non-prod; targeting prod/live is an explicit, surfaced choice in the confirmation. Never hardcode a host the LLD didn't list.
- **Never blow past a safety gate.** No state change without the confirm; no destructive op without the per-step concrete-target re-confirm; stop on a broken chain; stop (don't cascade) on partial failure.
- **Never present partial as complete.** A run that stopped paginating, skipped a step, hit a cap, or left a step "not run" (per the LLD) must say so in the report.
- Never dump a forced wall of questions. Ask narrowly, only for genuine run-time blockers (a MISSING input, a missing credential value), once.

## Folder layout
```
.claude/skills/runner-agent/
├── SKILL.md                 ← this file (router + live-execution pipeline)
└── reference/               ← the Runner's OWN execution how-to
    ├── auth.md              ← (cURL) authenticate live: secrets, token lifecycle, per-scheme attach, failures
    ├── edge-cases.md        ← (cURL) handle live failures: status triage, retries, pagination, idempotency, partial-failure
    ├── browser.md           ← (browser) drive the UI live: sign-in, act→wait→assert→capture, failure recovery
    └── call.sh              ← the robust single-call helper, copied into each run dir

outputs/<client>/
├── lld/    ← the LLD/ED (input — produced by api-agent)
└── runs/   ← one run dir per execution: <runid>/{call.sh, run.log, result.json, per-step bodies/evidence}
```
