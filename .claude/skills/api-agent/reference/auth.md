# Reference: what the LLD/ED must specify about authentication & token lifecycle

This skill **designs**; it never authenticates. This file is the checklist for the **Authentication** section of the LLD/ED — everything the *Runner* needs to authenticate correctly, written down so the Runner needs nothing but this document and the credential values it sources itself. **The KB declares the scheme and the credential names; this file is the template for how to document whatever the KB declares.** Never assume a scheme the KB doesn't state, and **never read, request, store, or embed a credential value** — the LLD/ED names credentials only, using the KB's exact names.

## The credential boundary (who owns what)

- **The KB** documents *which* credentials / env vars the API needs, **by name** (e.g. `API_KEY`, `CLIENT_ID`, `CLIENT_SECRET`). That is the only authority for which credentials exist.
- **This skill / the LLD/ED** carries those **names** forward (as `<from secrets: NAME>`) and says how each attaches to a request. It does **not** hold a value, ask for one, store one, or name a secrets file/path/source. If the KB fails to name a credential the auth flow needs, that is a **KB gap to flag**, never a value to request.
- **The Runner** owns everything about values at run time: where they come from (asking the user, its own secret store, its env), loading them, and keeping them safe. The LLD/ED does not decide that for it.

## Secret-hygiene rules the LLD/ED reminds the Runner to follow (at run time)

These describe how the **Runner** must handle values when it executes. Restate them in the document as reminders, but note they are the Runner's to enforce — the LLD/ED itself carries names, never values, and names no source.

1. **Values live only wherever the Runner sources them** — never in the KB, the SOW, the chat, this LLD/ED, or any tracked file. (The LLD/ED does not pick that source; the Runner does.)
2. **Never write a secret as a command literal.** The Runner references it by shell substitution so the value is expanded at runtime and never appears in a tool input/output — e.g. after loading its own secret store, `$API_KEY` in the same compound command; a fetched token cached to a file: `-H "Authorization: Bearer $(cat run/.token)"`.
3. **Never print a secret.** No `curl -v` (it dumps `Authorization`), no `echo $TOKEN`, no pasting a response that embeds a token. The Runner's logging writes a redacted audit line, not the headers.
4. **Restrict and clean up.** Token cache files get `chmod 600`, live in the run dir, are treated as sensitive, and aren't committed.
5. **Redact in all output** — the run log, results, and any report show `***` / `<from secrets: NAME>`, never the value.

## What to document per scheme

Match the KB's declared scheme to one of these and write the matching mechanics into the LLD/ED. The KB's specifics (header names, endpoints, param names) always win over the generic shape here.

### API key (header or query)
- Header: the Runner attaches `-H "$KEY_HEADER: $API_KEY"` (header name from the KB, e.g. `X-Api-Key`). Query: append `?api_key=$API_KEY` (prefer the header form — query strings leak into logs).
- No token lifecycle. Document the failure mode: `401/403` → key wrong, disabled, or wrong environment → stop, don't retry a bad key.

### Bearer / static token
- `-H "Authorization: Bearer $TOKEN"`. Treat like an API key unless the KB says it expires.

### OAuth2 client-credentials (the common machine-to-machine flow)
- The Runner POSTs to the KB's token endpoint with `grant_type=client_credentials`, `client_id`, `client_secret` (and `scope`/`audience` if the KB requires); parses `access_token` + `expires_in`.
- Caches the token to `run/.token` (`chmod 600`) and records expiry = now + `expires_in` − a safety skew (e.g. 60s).
- **Refresh proactively** within the skew of expiry, and **reactively** on a `401` (refresh once → retry; still `401` → re-auth from scratch once → retry; still failing → stop). Document this rule in the LLD/ED.

### OAuth2 with refresh token / authorization-code
- If a refresh token is pre-provisioned (in secrets), the Runner POSTs `grant_type=refresh_token` to mint access tokens. Note **refresh-token rotation**: if the response returns a new refresh token, the Runner uses it next; a rotated secret can't be durably persisted into a committed file — flag it.
- The interactive authorization-code leg (browser login + redirect) **cannot be completed unattended.** If the KB requires it and no token is pre-provisioned, the LLD/ED must flag this as an open item: the operator must supply a token/refresh token to the Runner.

### Basic auth
- `-u "$USERNAME:$PASSWORD"` (curl keeps it out of the visible URL) or a pre-encoded `-H "Authorization: Basic $BASIC_B64"`. No lifecycle.

### Session / cookie login
- The Runner POSTs credentials to the KB's login endpoint, captures the cookie jar (`-c run/.cookies -b run/.cookies`, `chmod 600`), reuses it, and re-logs-in on session-expired (`401`/redirect-to-login per the KB).

### HMAC / request signing
- Document the KB's **exact** signing recipe: which headers/body/timestamp are signed, the algorithm, the encoding, and the required timestamp/nonce header. Clock skew breaks signatures — the Runner uses a fresh timestamp per request. If the KB's recipe is ambiguous, flag it rather than guessing — a wrong signature looks like a generic `401`.

### mTLS / client certificate
- `--cert run/client.pem --key run/client.key` (paths from secrets). If the cert/key isn't available the Runner stops and surfaces; note this in the LLD/ED.

## Auth failure modes the LLD/ED should hand the Runner

| Symptom | Likely cause | Runner action |
|---|---|---|
| `401` on first call | token expired / wrong / not sent | refresh once → retry; still `401` → re-auth once; still failing → stop, surface |
| `401` immediately after a fresh token | wrong audience/scope, clock skew, wrong env | check scope/audience/env vs KB; check clock; do **not** loop refreshing |
| `403` (authenticated) | valid creds, insufficient permission | stop — not retryable; report which op/scope is missing |
| Token endpoint `4xx` | bad client_id/secret/grant/scope | stop — fix credentials; never spin retrying bad creds |
| Signature rejected | wrong HMAC recipe or skewed clock | re-derive per KB; verify timestamp; ask if recipe unclear |
| Needs interactive login / MFA | authorization-code or MFA flow | can't run unattended — surface, operator supplies a token |

**Rate-limit the auth endpoint too:** if the token endpoint `429`s, the Runner backs off (honor `Retry-After`); document that it must not hammer it.
