# Reference: edge-case catalog (execute)

The failure modes a live API pipeline hits, and how to handle each. The KB's specifics (which status codes mean what, the error-envelope shape, rate-limit headers, pagination style) always override the generic defaults here. `call.sh` already handles transport retries and `429`/`5xx` backoff uniformly; this file is how *you* decide what a response means and what to do next.

## Triage by HTTP status

| Status | Meaning (default — KB overrides) | Action |
|---|---|---|
| **2xx** | success | validate body shape vs KB before chaining; extract; continue |
| **3xx** | redirect | follow only if the KB/endpoint expects it (`-L` cautiously); a redirect to a login page = session expired, re-auth |
| **400** | bad request — your payload/params are wrong | **don't retry.** Read the error envelope, fix the request if the fix is unambiguous, else stop and surface (likely a bad chained value or a KB-schema mismatch) |
| **401** | unauthenticated | refresh token once → retry; still failing → re-auth once → retry; still failing → stop (`reference/auth.md`) |
| **403** | authenticated but forbidden | **not retryable** — missing scope/permission or wrong env. Stop, name the op |
| **404** | not found | depends: a missing resource you were about to act on may be fine (skip) or a broken chain (stop). Decide from the step's intent; don't blindly continue |
| **405/415** | method/content-type not allowed | request is malformed vs KB — fix method/`Content-Type`, or stop |
| **409** | conflict (already exists / version clash) | often means the mutation already happened (idempotency) — read state and decide; don't blindly retry |
| **422** | semantic validation failed | like 400 — read the envelope, fix or stop; not blindly retryable |
| **429** | rate limited | honor `Retry-After` (or the KB's rate headers); `call.sh` backs off. Reduce concurrency. If it persists past the cap, stop and report |
| **5xx** | server error | `call.sh` already retried with exponential backoff + jitter; if still failing, stop — server-side, not yours to fix. For a non-idempotent write, see "ambiguous failure" below |

## Transport-level failures (no HTTP status)
DNS failure, connection refused, TLS handshake error, **timeout**. `call.sh` retries these with backoff up to the cap. After the cap:
- Read-only / idempotent → report failure, stop the dependent chain.
- **Non-idempotent write that timed out → "ambiguous failure":** you don't know if the server applied it. **Do not auto-resend.** If the call carried an idempotency key, a safe resend is fine. Otherwise, read back state (did the resource get created?) before retrying, or stop and ask. Never double-charge / double-create.

## Token & auth (summary — full table in `reference/auth.md`)
Expiry mid-run, refresh, refresh-token rotation, clock skew, `403` scope, interactive/MFA flows that can't run unattended. Refresh proactively before expiry; reactively once on `401`.

## Rate limits & concurrency
- Respect the KB's documented limit; prefer sequential calls unless the KB blesses concurrency. If you parallelize iteration, cap in-flight requests and still honor `429`/`Retry-After`.
- Watch rate-limit headers (`X-RateLimit-Remaining`/`Reset` or the KB's names) and pace proactively rather than only reacting to `429`.

## Pagination
- Detect the style from the KB: cursor/`next` token, offset+limit, page number, or `Link: rel="next"`. Loop until the stop signal (no cursor / empty page / `next` absent).
- **Always cap** the number of pages/items with a sane bound and **log when you hit the cap** — never silently truncate and present partial data as complete. Carry rate-limit pacing into the loop.

## Response body problems
- **Empty body on a 2xx** that should carry data → treat as a failed expectation; don't extract from nothing. (Empty on a `204 No Content` write is normal.)
- **Non-JSON when JSON expected** (HTML error page, plain text, gateway page) → don't `jq` it blindly; capture it, report the mismatch (often a misrouted request, a WAF block, or a `5xx` HTML page).
- **Content-Type mismatch** → trust the bytes over the assumption; parse per actual type or flag.
- **Oversized / streaming / binary body** → stream to a file (`-o`), don't load into a variable or echo it; summarize. Set a max size if the KB implies one.
- **Malformed JSON** → `jq` will fail; capture raw, report; don't fabricate the parsed value.
- **Encoding** (gzip, charset) → let curl handle (`--compressed`) if needed; don't mangle.

## Data extraction & chaining
- A **required** extracted field that's missing/null → **stop the chain.** Never send the dependent call with a blank, a guess, or a stale value. Report the exact step and path.
- Type surprises (expected a string id, got an object/array) → validate shape before using; surface a mismatch rather than coercing silently.
- Multiple matches when one expected → don't pick arbitrarily; the KB/prompt should disambiguate, else ask.

## Idempotency & state safety (mutations)
- Prefer idempotency keys where the KB supports them — they make a retry safe. Reuse the same key on resend, not a new one.
- For destructive ops (DELETE, irreversible state change), confirm the concrete target at the moment of the call (`reference/auth.md` is about creds; the confirm gate is in `pipeline/execute-api.md` Phase 4).
- After a successful mutation, **verify the effect** (read back / check returned id) before reporting done.
- **Partial pipeline failure:** stop, don't cascade. Report what succeeded (real-world effects), what's pending, the state left behind, and how to resume. Offer a KB-defined compensating action if one exists and the operator wants it.

## Environment & configuration
- Wrong base URL / wrong environment is a top cause of silent damage. Default non-prod; surface the target env in the plan; never invent a URL.
- Mixed environments in one run (token from sandbox, call to prod) → guard against it; auth and target must match.

## Input & timing
- Missing required input the call needs → ask; don't invent.
- Date/time/timezone params → use the KB's exact format; be explicit about timezone; the harness has no in-process clock, so get `date` via Bash.
- Locale/number formatting in params → follow the KB.

## Network environment
- Proxy / corporate egress, custom CA, self-signed cert in non-prod → configure curl per the operator's environment if needed; **never** disable TLS verification (`-k`) against prod, and only with explicit operator consent anywhere. Flag if a cert error blocks you rather than silently skipping verification.

## Observability discipline
- Every call appends a **redacted** line to `run.log` (method, endpoint, status, latency, retries) — secrets never in it.
- Surface what you actually did vs. what you skipped/capped. A run that quietly stopped paginating, or skipped a step, must say so in the report. Don't present partial as complete.
