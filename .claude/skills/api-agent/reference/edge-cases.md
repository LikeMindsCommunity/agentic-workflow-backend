# Reference: edge-case handling the LLD/ED must hand the Runner

This skill **designs**; it never executes. This file is the catalog of failure modes a live API pipeline hits, written as **what the LLD/ED must tell the Runner to do** for each. The KB's specifics (which status codes mean what, the error-envelope shape, rate-limit headers, pagination style) always override the generic defaults here. The LLD/ED states the **retry/backoff policy** declaratively in its Execution-policy section (which conditions are retryable, attempts, backoff shape, honor `Retry-After`) — the Runner *implements* that however it likes; the per-step "error handling" notes below are how the *Runner* decides what a response **means** and what to do next. The skill ships no script to do this.

Encode the relevant entries below into each step's error-handling note (Phase 3), and the cross-cutting ones into the **Safety gates** section (Phase 5).

## Triage by HTTP status — document the Runner's action per step

| Status | Meaning (default — KB overrides) | Runner action to specify |
|---|---|---|
| **2xx** | success | validate body shape vs KB before chaining; extract; continue |
| **3xx** | redirect | follow only if the KB/endpoint expects it (`-L` cautiously); a redirect to a login page = session expired → re-auth |
| **400** | bad request — payload/params wrong | **don't retry.** Read the error envelope; fix only if unambiguous, else stop and surface (likely a bad chained value or KB-schema mismatch) |
| **401** | unauthenticated | refresh token once → retry; still failing → re-auth once → retry; still failing → stop (`reference/auth.md`) |
| **403** | authenticated but forbidden | **not retryable** — missing scope/permission or wrong env. Stop, name the op |
| **404** | not found | depends: a missing resource you were about to act on may be fine (skip) or a broken chain (stop). Decide from the step's intent; don't blindly continue |
| **405/415** | method/content-type not allowed | request malformed vs KB — fix method/`Content-Type`, or stop |
| **409** | conflict (already exists / version clash) | often the mutation already happened (idempotency) — read state and decide; don't blindly retry |
| **422** | semantic validation failed | like 400 — read the envelope, fix or stop; not blindly retryable |
| **429** | rate limited | honor `Retry-After` (or the KB's rate headers); back off per the retry policy; reduce concurrency; if it persists past the cap, stop and report |
| **5xx** | server error | retry with backoff + jitter per the retry policy; if still failing, stop — server-side. For a non-idempotent write, see "ambiguous failure" below |

## Transport-level failures (no HTTP status)
DNS failure, connection refused, TLS handshake error, **timeout**. The retry policy retries these with backoff up to the cap. After the cap, the LLD/ED must tell the Runner:
- Read-only / idempotent → report failure, stop the dependent chain.
- **Non-idempotent write that timed out → "ambiguous failure":** the Runner doesn't know if the server applied it. **Do not auto-resend.** If the call carried an idempotency key, a safe resend is fine; otherwise read back state (did the resource get created?) before retrying, or stop and ask. Never double-charge / double-create.

## Token & auth (summary — full table in `reference/auth.md`)
Expiry mid-run, refresh, refresh-token rotation, clock skew, `403` scope, interactive/MFA flows that can't run unattended. The LLD/ED specifies: refresh proactively before expiry; reactively once on `401`.

## Rate limits & concurrency
- The LLD/ED states the KB's documented limit and prefers sequential calls unless the KB blesses concurrency. If iteration is parallelized, cap in-flight requests and still honor `429`/`Retry-After`.
- Tell the Runner to watch rate-limit headers (`X-RateLimit-Remaining`/`Reset` or the KB's names) and pace proactively, not only react to `429`.

## Pagination
- Specify the style from the KB: cursor/`next` token, offset+limit, page number, or `Link: rel="next"`. The Runner loops until the stop signal (no cursor / empty page / `next` absent).
- **Always specify a cap** on pages/items with a sane bound and require the Runner to **log when it hits the cap** — never silently truncate and present partial data as complete. Carry rate-limit pacing into the loop.

## Response body problems
- **Empty body on a 2xx** that should carry data → treat as a failed expectation; don't extract from nothing. (Empty on `204 No Content` write is normal.)
- **Non-JSON when JSON expected** (HTML error page, gateway page) → don't `jq` it blindly; capture it, report the mismatch (often a misrouted request, a WAF block, or a `5xx` HTML page).
- **Content-Type mismatch** → trust the bytes over the assumption; parse per actual type or flag.
- **Oversized / streaming / binary body** → stream to a file (`-o`), don't load into a variable or echo it; summarize. Set a max size if the KB implies one.
- **Malformed JSON** → `jq` fails; capture raw, report; don't fabricate the parsed value.
- **Encoding** (gzip, charset) → let curl handle (`--compressed`); don't mangle.

## Data extraction & chaining
- A **required** extracted field that's missing/null → **the Runner stops the chain.** Never send the dependent call with a blank, a guess, or a stale value. Report the exact step and path. (Design the chain so this is checkable: name the required field and its `jq` path per step.)
- Type surprises (expected a string id, got an object/array) → validate shape before using; surface a mismatch rather than coercing.
- Multiple matches when one expected → don't pick arbitrarily; the KB/SOW should disambiguate, else the Runner asks.

## Idempotency & state safety (mutations)
- Prefer idempotency keys where the KB supports them — they make a retry safe. The Runner reuses the same key on resend, not a new one. Specify this per state-changing step.
- For destructive ops (DELETE, irreversible change), the LLD/ED requires the Runner to confirm the concrete target at the moment of the call.
- After a successful mutation, the Runner **verifies the effect** (read back / check returned id) before reporting done.
- **Partial pipeline failure:** stop, don't cascade. The Runner reports what succeeded (real-world effects), what's pending, the state left behind, and how to resume. Offer a KB-defined compensating action if one exists and the operator wants it.

## Environment & configuration
- Wrong base URL / wrong environment is a top cause of silent damage. The LLD/ED **lists the KB's environments without binding one** (step URLs use a symbolic base the Runner resolves), instructs the Runner to **default to non-prod**, and never invents a URL. The operator picks the actual environment with the Runner at run time.
- Guard against mixed environments in one run (token from sandbox, call to prod) — auth and target must match.

## Input & timing
- Missing required input the call needs → the LLD/ED records it as an open item for the Runner; don't invent it into the document.
- Date/time/timezone params → specify the KB's exact format and be explicit about timezone; the Runner gets `date` from the shell (no in-process clock).
- Locale/number formatting in params → follow the KB.

## Network environment
- Proxy / corporate egress, custom CA, self-signed cert in non-prod → the Runner configures curl per the operator's environment if needed; **never** disable TLS verification (`-k`) against prod, and only with explicit operator consent anywhere. Flag if a cert error would block the Runner.

## Observability discipline (require it in the LLD/ED)
- Every call appends a **redacted** line to the run log (method, endpoint, status, latency, retries) — secrets never in it.
- The Runner must surface what it actually did vs. what it skipped/capped. A run that quietly stopped paginating, or skipped a step, must say so. Don't present partial as complete.
