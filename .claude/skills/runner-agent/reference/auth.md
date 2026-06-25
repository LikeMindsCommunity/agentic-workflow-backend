# Reference: authenticate live (runner — cURL surface)

How to authenticate, manage tokens, and keep secrets safe **at run time**. **The LLD/ED declares the scheme and the credential names; this file is the playbook for handling whatever the LLD declares.** Never assume a scheme the LLD doesn't state, and never open the KB to "check" — the LLD is self-contained and is the only authority. If the LLD's auth section is missing something the scheme clearly needs (a token endpoint, a signing recipe), that is a **defective LLD to surface** — not a gap to fill from general knowledge.

## The credential boundary (who owns what)

- **The LLD/ED** names *which* credentials are needed (`<from secrets: NAME>`) and how each attaches to a request. It carries **names only** — never a value, never a source.
- **The Runner** (you) owns everything about values at run time: where they come from, loading them, keeping them safe — and you **never write a value back into the LLD**.

## Secret hygiene — the rules that never bend

1. **Values live only in the secret source** the Runner reads — never in the LLD, the chat, or a tracked file. Source order: `secrets=<path>` → `outputs/<client>/secrets.env` → a `*-creds.json` the operator names → process env vars → **ask the operator**. Any secrets file must be git-ignored (verify; if not, add it to `.gitignore` before anything else).
2. **Never write a secret as a command literal.** Reference it by shell substitution so the value is expanded by the shell at run time and never appears in the tool input/output you produce:
   - from an env file: `set -a; . outputs/<client>/secrets.env; set +a` then use `$API_KEY` in the **same** compound command.
   - from a JSON creds file: `KEY=$(jq -r .key_id creds.json)` in the same compound command — don't echo the result.
   - a fetched token cached to a file: `-H "Authorization: Bearer $(cat run/.token)"`.
3. **Never print a secret.** No `curl -v` (it dumps the `Authorization` header), no `echo $TOKEN`, no pasting a response that embeds the token into chat unredacted. `call.sh` writes a **redacted** audit line, not the headers.
4. **Restrict and clean up.** Token/cookie cache files get `chmod 600`, live in the run dir, are treated as sensitive, and are never committed.
5. **Redact in all output** — `run.log`, `result.json`, and the report show `***` / `<from secrets: NAME>`, never the value.

## Loading credentials

```bash
# env-file form — values used only within this compound command
set -a; . "${SECRETS:-outputs/<client>/secrets.env}"; set +a
# now $CLIENT_ID, $CLIENT_SECRET, $API_KEY, ... are available to the curl on the next line
```
If a named credential the LLD requires is absent from the source, **stop and ask** the operator to add it — name it exactly as the LLD calls it, and say which source you read (the `secrets=` path / `outputs/<client>/secrets.env` / the JSON file / env var) so they know where to put it. List **every** missing credential at once. Never proceed with a blank, and never fabricate a value.

## Scheme catalog

Match the LLD's declared scheme to one of these. The LLD's specifics (header names, endpoints, param names) always win over the generic shape here.

### API key (header or query)
- Header: attach `-H "$KEY_HEADER: $API_KEY"` (header name from the LLD, e.g. `X-Api-Key`). Query: append `?api_key=$API_KEY` only if the LLD says so (query keys leak into logs — prefer the header form).
- No token lifecycle. Failure mode: `401/403` → key wrong, disabled, or wrong environment. Stop and surface; don't retry a bad key.

### Bearer / static token
- `-H "Authorization: Bearer $TOKEN"`. Treat like an API key unless the LLD says it expires.

### OAuth2 client-credentials (the common machine-to-machine flow)
- POST to the LLD's token endpoint with `grant_type=client_credentials`, `client_id`, `client_secret` (and `scope`/`audience` if the LLD requires). Parse `access_token` and `expires_in`.
- Cache the token to `run/.token` (`chmod 600`) and record expiry = now + `expires_in` − a safety skew (e.g. 60s).
- **Refresh proactively** within the skew of expiry, and **reactively** on a `401` (refresh once → retry; still `401` → re-auth from scratch once → retry; still failing → stop).

### OAuth2 with refresh token / authorization-code
- Hold a refresh token (from secrets) → POST `grant_type=refresh_token` to mint access tokens. Handle **refresh-token rotation**: if the response returns a new refresh token, use it next; a rotated secret can't be durably persisted — surface it if rotation must outlive the run.
- The interactive authorization-code leg (browser login + redirect) **cannot run unattended.** If the LLD flags it and no token is pre-provisioned, stop and surface — the operator must supply a token/refresh token.

### Basic auth
- `-u "$USERNAME:$PASSWORD"` (curl keeps it out of the visible URL) or a pre-encoded `-H "Authorization: Basic $BASIC_B64"`. No lifecycle. The scheme word must be exactly what the LLD states (e.g. `Basic`, capital B).

### Session / cookie login
- POST credentials to the LLD's login endpoint, capture the cookie jar (`-c run/.cookies -b run/.cookies`, `chmod 600`). Reuse the jar on subsequent calls. Re-login on session-expired (`401`/redirect-to-login per the LLD).

### HMAC / request signing
- Build the signature per the LLD's **exact** recipe (which headers/body/timestamp are signed, the algorithm, the encoding) and include the required timestamp/nonce header. Clock skew breaks signatures — use a fresh timestamp per request. If the LLD's recipe is ambiguous, **stop and surface** (a defective LLD); a wrong signature looks like a generic `401`.

### mTLS / client certificate
- `--cert run/client.pem --key run/client.key` (paths from secrets). If the cert/key isn't available, stop and surface.

## Auth failure modes

| Symptom | Likely cause | Action |
|---|---|---|
| `401` on first call | token expired / wrong / not sent | refresh once → retry; still `401` → re-auth once; still failing → stop, surface |
| `401` immediately after a fresh token | wrong audience/scope, clock skew, wrong env | check scope/audience/env vs the LLD; check the system clock; do **not** loop refreshing |
| `403` (authenticated) | valid creds, insufficient permission | stop — not retryable; report which op/scope is missing |
| Token endpoint `4xx` | bad client_id/secret/grant/scope | stop — fix credentials; never spin retrying bad creds |
| Signature rejected | wrong HMAC recipe or skewed clock | re-derive per the LLD; verify timestamp; surface if the recipe is unclear |
| Needs interactive login / MFA | authorization-code or MFA flow | cannot do unattended — surface, operator supplies a token |

**Rate-limit the auth endpoint too:** if the token endpoint itself `429`s, back off (honor `Retry-After`); don't hammer it.
