# Reference: authentication & token lifecycle (execute)

How to authenticate, manage tokens, and keep secrets safe. **The KB declares the scheme and the credential names; this file is the playbook for handling whatever the KB declares.** Never assume a scheme the KB doesn't state.

## Secret hygiene — the rules that never bend

1. **Values live only in the secrets source**, never in the KB, the prompt-as-committed, the chat, or a tracked file. Source order: `secrets=<path>` → `outputs/<client>/secrets.env` → process env vars. The secrets file must be git-ignored (verify it is; if not, add it to `.gitignore` before writing anything).
2. **Never write a secret as a command literal.** Reference it by shell substitution so the value is expanded by the shell at runtime and never appears in the tool input/output you produce:
   - from an env file: `set -a; . outputs/<client>/secrets.env; set +a` then use `$API_KEY` in the same compound command.
   - a fetched token cached to a file: `-H "Authorization: Bearer $(cat run/.token)"`.
3. **Never print a secret.** No `curl -v` (it dumps the `Authorization` header), no `echo $TOKEN`, no pasting a response that embeds the token into chat unredacted. `call.sh` writes a redacted audit line, not the headers.
4. **Restrict and clean up.** Token cache files get `chmod 600`. They live in the run dir; treat them as sensitive. Don't commit the run dir's secret files.
5. **Redact in all output** — `run.log`, `result.json`, and the final report show `***` / `<from secrets: NAME>`, never the value.

## Loading credentials

```bash
# values come from the secrets file; they are used only within this compound command
set -a; . "${SECRETS:-outputs/<client>/secrets.env}"; set +a
# now $CLIENT_ID, $CLIENT_SECRET, $API_KEY, ... are available to the curl on the next line
```
If a named credential the KB requires is absent from the source, **stop and ask** the operator to add it (name it). Do not proceed with a blank.

## Scheme catalog

Match the KB's declared scheme to one of these. The KB's specifics (header names, endpoints, param names) always win over the generic shape here.

### API key (header or query)
- Header: attach `-H "$KEY_HEADER: $API_KEY"` (header name from the KB, e.g. `X-Api-Key`, `Authorization: ApiKey ...`). Query: append `?api_key=$API_KEY` (avoid query keys if a header form exists — query strings leak into logs).
- No token lifecycle. Failure mode: `401/403` → key wrong, disabled, or wrong environment. Stop and surface; don't retry a bad key.

### Bearer / static token
- `-H "Authorization: Bearer $TOKEN"`. Treat like an API key unless the KB says it expires.

### OAuth2 client-credentials (the common machine-to-machine flow)
- POST to the KB's token endpoint with `grant_type=client_credentials`, `client_id`, `client_secret` (and `scope`/`audience` if the KB requires). Parse `access_token` and `expires_in`.
- Cache the token to `run/.token` (`chmod 600`) and record an expiry timestamp = now + `expires_in` − a safety skew (e.g. 60s) to avoid using a token that expires mid-flight.
- **Refresh proactively** when within the skew of expiry, and **reactively** on a `401` (refresh once, retry the call; if it still `401`s, re-authenticate from scratch once; if that fails, stop).

### OAuth2 with refresh token / authorization-code
- If you already hold a refresh token (from secrets), POST `grant_type=refresh_token` to mint access tokens. Handle **refresh-token rotation**: if the response returns a new refresh token, use it for the next refresh (note: you can't durably persist a rotated secret into the committed secrets file — surface to the operator if rotation needs to persist beyond the run).
- The interactive authorization-code leg (browser login + redirect) **cannot be completed unattended.** If the KB requires it and no token is pre-provisioned, stop and surface — ask the operator to supply a token/refresh token.

### Basic auth
- `-u "$USERNAME:$PASSWORD"` (curl keeps it out of the visible URL) or a pre-encoded `-H "Authorization: Basic $BASIC_B64"`. No lifecycle.

### Session / cookie login
- POST credentials to the KB's login endpoint, capture the cookie jar (`-c run/.cookies -b run/.cookies`, `chmod 600`). Reuse the jar on subsequent calls. Re-login on session-expired (`401`/redirect-to-login per the KB).

### HMAC / request signing
- Build the signature per the KB's exact recipe (which headers/body/timestamp are signed, the algorithm, the encoding). Include the required timestamp/nonce header. Clock skew breaks signatures — use a fresh timestamp per request. If the KB's recipe is ambiguous, ask rather than guess; a wrong signature looks like a generic `401`.

### mTLS / client certificate
- `--cert run/client.pem --key run/client.key` (paths from secrets). If the cert/key isn't available, stop and surface.

## Auth failure modes

| Symptom | Likely cause | Action |
|---|---|---|
| `401` on first call | token expired / wrong / not sent | refresh once → retry; still `401` → re-auth once; still failing → stop, surface |
| `401` immediately after a fresh token | wrong audience/scope, clock skew, wrong env | check scope/audience/env against KB; check system clock; do **not** loop refreshing |
| `403` (authenticated) | valid creds, insufficient permission | stop — not retryable; report which op/scope is missing |
| Token endpoint `4xx` | bad client_id/secret/grant/scope | stop — fix credentials; never spin retrying bad creds |
| Signature rejected | wrong HMAC recipe or skewed clock | re-derive per KB; verify timestamp; ask if recipe unclear |
| Needs interactive login / MFA | authorization-code or MFA flow | cannot do unattended — surface, ask operator for a token |

**Rate-limit the auth endpoint too:** if the token endpoint itself `429`s, back off (honor `Retry-After`); don't hammer it.
