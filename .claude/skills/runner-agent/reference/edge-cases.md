# Reference: handle live failures (runner — cURL surface)

The failure modes a live API pipeline hits, and how to handle each **at run time**. The **LLD/ED's** specifics (which status codes mean what, the error-envelope shape, rate-limit headers, pagination style) always override the generic defaults here — and the LLD is the only authority (never open the KB). `call.sh` already handles transport retries and `429`/`5xx` backoff uniformly; this file is how *you* decide what a response **means** and what to do next.

## Triage by HTTP status

| Status | Meaning (default — the LLD overrides) | Action |
|---|---|---|
| **2xx** | success | validate body shape vs the LLD before chaining; extract; continue |
| **3xx** | redirect | follow only if the LLD/step expects it (`-L` cautiously); a redirect to a login page = session expired, re-auth |
| **400** | bad request — payload/params wrong | **don't retry.** Read the error envelope; fix only if the LLD makes the fix unambiguous, else stop and surface (likely a bad chained value or a plan/schema mismatch — a defective LLD) |
| **401** | unauthenticated | refresh token once → retry; still failing → re-auth once → retry; still failing → stop (`reference/auth.md`) |
| **403** | authenticated but forbidden | **not retryable** — missing scope/permission or wrong env. Stop, name the op |
| **404** | not found | depends: a missing resource you were about to act on may be fine (skip) or a broken chain (stop). Decide from the step's intent as the LLD states it; don't blindly continue |
| **405/415** | method/content-type not allowed | request malformed vs the LLD — this is usually a plan defect; stop and surface |
| **409** | conflict (already exists / version clash) | often the mutation already happened (idempotency) — read state and decide; don't blindly retry |
| **422** | semantic validation failed | like 400 — read the envelope, stop and surface unless the LLD makes the fix unambiguous |
| **429** | rate limited | honor `Retry-After` (or the LLD's rate headers); `call.sh` backs off. Reduce concurrency. If it persists past the cap, stop and report |
| **5xx** | server error | `call.sh` already retried with backoff + jitter; if still failing, stop — server-side. For a non-idempotent write, see "ambiguous failure" below |

## Transport-level failures (no HTTP status)
DNS failure, connection refused, TLS handshake error, **timeout**. `call.sh` retries these with backoff up to the cap. After the cap:
- Read-only / idempotent → report failure, stop the dependent chain.
- **Non-idempotent write that timed out → "ambiguous failure":** you don't know if the server applied it. **Do not auto-resend.** If the call carried an idempotency key (or keys on a unique field the LLD names), a safe resend / read-back is fine; otherwise read back state (did the resource get created?) before retrying, or stop and ask. Never double-charge / double-create.

## Token & auth (summary — full table in `reference/auth.md`)
Expiry mid-run, refresh, refresh-token rotation, clock skew, `403` scope, interactive/MFA flows that can't run unattended. Refresh proactively before expiry; reactively once on `401`.

## Rate limits & concurrency
- Respect the LLD's documented limit; prefer sequential calls unless the LLD blesses concurrency. If you parallelize iteration, cap in-flight requests and still honor `429`/`Retry-After`.
- Watch the rate-limit headers the LLD names (`X-RateLimit-Remaining`/`Reset` or its equivalents) and pace proactively, not only reacting to `429`.

## Pagination
- Use the style the LLD specifies: cursor/`next` token, offset+limit, page number, or `Link: rel="next"`. Loop until the stop signal (no cursor / empty page / `next` absent).
- **Always honor the LLD's cap** on pages/items and **log when you hit it** — never silently truncate and present partial data as complete. Carry rate-limit pacing into the loop.

## Response body problems
- **Empty body on a 2xx** that should carry data → failed expectation; don't extract from nothing. (Empty on a `204 No Content` write is normal.)
- **Non-JSON when JSON expected** (HTML error page, gateway page) → don't `jq` it blindly; capture it, report the mismatch (often a misrouted request, a WAF block, or a `5xx` HTML page).
- **Content-Type mismatch** → trust the bytes over the assumption; parse per actual type or flag.
- **Oversized / streaming / binary body** → stream to a file (`-o`), don't load into a variable or echo it; summarize. Set a max size if the LLD implies one.
- **Malformed JSON** → `jq` fails; capture raw, report; don't fabricate the parsed value.
- **Encoding** (gzip, charset) → let curl handle (`--compressed`); don't mangle.

## Data extraction & chaining
- A **required** extracted field that's missing/null → **stop the chain.** Never send the dependent call with a blank, a guess, or a stale value. Report the exact step and the `jq` path the LLD named.
- Type surprises (expected a string id, got an object/array) → validate shape before using; surface a mismatch rather than coercing.
- Multiple matches when one expected → don't pick arbitrarily; the LLD should disambiguate, else ask.

## Idempotency & state safety (mutations)
- Use idempotency keys where the LLD says the step supports them — they make a retry safe. Reuse the **same** key on resend, not a new one.
- For destructive ops (DELETE, irreversible/money-moving), confirm the **concrete target** at the moment of the call (the Phase 4 gate covers the plan; this is the per-step re-confirm).
- After a successful mutation, **verify the effect** (read back / check the returned id) before reporting done.
- **Partial pipeline failure:** stop, don't cascade. Report what succeeded (real-world effects), what's pending, the state left behind, and how to resume. Offer the LLD's compensating action if it defines one and the operator wants it.

## Environment & configuration
- Wrong base URL / wrong environment is a top cause of silent damage. Bind the LLD's symbolic `{base_url}` to the chosen environment; default non-prod; surface the target env in the plan; never invent a URL or use one the LLD didn't list.
- Guard against mixed environments in one run (token from sandbox, call to prod) — auth and target must match.

## Input & timing
- Missing required input the call needs → ask (Phase 3); don't invent it.
- Date/time/timezone params → use the LLD's exact format; be explicit about timezone; the harness has no in-process clock, so get `date` via Bash.
- Locale/number formatting in params → follow the LLD.

## Network environment
- Proxy / corporate egress, custom CA, self-signed cert in non-prod → configure curl per the operator's environment if needed; **never** disable TLS verification (`-k`) against prod, and only with explicit operator consent anywhere. Flag if a cert error blocks you rather than silently skipping verification.

## Observability discipline
- Every call appends a **redacted** line to `run.log` (method, endpoint, status, latency, retries) — secrets never in it.
- Surface what you actually did vs. what you skipped/capped. A run that quietly stopped paginating, skipped a step, or hit a cap must say so in the report. Don't present partial as complete.
