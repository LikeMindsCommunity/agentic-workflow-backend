#!/usr/bin/env bash
# call.sh — one robust API call for the generate-artifact `execute` operation.
#
# The execute pipeline copies this into the run dir and invokes it once per step so that
# retries/backoff/redaction/status-capture are handled uniformly in ONE place, while the
# model keeps ownership of planning, chaining, conditionals, and pagination.
#
# SECRETS NEVER APPEAR HERE AS LITERALS. Pass auth at the call site via shell substitution,
# e.g.  -H "Authorization: Bearer $(cat run/.token)"  or  -u "$USER:$PASS"  after sourcing
# the secrets file. This script writes only a REDACTED audit line — never the headers.
#
# Usage:   call.sh METHOD URL [extra curl args...]
# Env knobs (all optional):
#   MAX_RETRIES  retry attempts for transport errors / 429 / 5xx     (default 4)
#   TIMEOUT      per-attempt --max-time seconds                       (default 30)
#   CONNECT_TO   --connect-timeout seconds                            (default 10)
#   RETRY_BASE   base seconds for exponential backoff                 (default 1)
#   BODY_FILE    where the response body is written      (default ${RUN_DIR:-.}/last.body)
#   HDR_FILE     where response headers are written      (default ${RUN_DIR:-.}/last.hdr)
#   LOG_FILE     append a redacted audit line per attempt (default: none)
#   FOLLOW       set to 1 to follow redirects (-L)                    (default 0)
#
# Output:  prints the final HTTP status code to stdout.
# Exit:    0 if a response was received (any status — caller decides what the status means);
#          1 if the call never completed at the transport level after all retries.

set -uo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: call.sh METHOD URL [curl args...]" >&2
  exit 2
fi

METHOD="$1"; URL="$2"; shift 2

MAX_RETRIES="${MAX_RETRIES:-4}"
TIMEOUT="${TIMEOUT:-30}"
CONNECT_TO="${CONNECT_TO:-10}"
RETRY_BASE="${RETRY_BASE:-1}"
BODY_FILE="${BODY_FILE:-${RUN_DIR:-.}/last.body}"
HDR_FILE="${HDR_FILE:-${RUN_DIR:-.}/last.hdr}"
FOLLOW="${FOLLOW:-0}"

follow_flag=""
[ "$FOLLOW" = "1" ] && follow_flag="-L"

attempt=0
while : ; do
  attempt=$((attempt + 1))

  # -sS: quiet but show real errors. NEVER add -v (it would dump the Authorization header).
  if code=$(curl -sS $follow_flag -X "$METHOD" "$URL" \
        --connect-timeout "$CONNECT_TO" --max-time "$TIMEOUT" \
        -D "$HDR_FILE" -o "$BODY_FILE" -w '%{http_code}' "$@" 2>"$BODY_FILE.err"); then
    curl_ok=1
  else
    curl_ok=0
  fi

  if [ -n "${LOG_FILE:-}" ]; then
    # redacted: method, url, status, attempt — no headers, no payload, no secrets
    printf '%s %s -> %s (attempt %s/%s)\n' \
      "$METHOD" "$URL" "${code:-TRANSPORT_ERR}" "$attempt" "$((MAX_RETRIES + 1))" >>"$LOG_FILE"
  fi

  retryable=0
  if [ "$curl_ok" -ne 1 ] || [ -z "${code:-}" ]; then
    retryable=1                       # transport error: timeout / DNS / TLS / refused
  else
    case "$code" in
      429|5[0-9][0-9]) retryable=1 ;; # rate limited or server error
      *) echo "$code"; exit 0 ;;      # 2xx/3xx/4xx(non-429): hand back, caller decides
    esac
  fi

  if [ "$attempt" -gt "$MAX_RETRIES" ]; then
    if [ "$curl_ok" -ne 1 ] || [ -z "${code:-}" ]; then
      echo "${code:-000}"; exit 1     # never completed at transport level
    fi
    echo "$code"; exit 0              # exhausted retries on 429/5xx — hand status back
  fi

  # Backoff: honor Retry-After (seconds) if the server sent one, else exponential + jitter.
  # case-insensitive without gawk's IGNORECASE (BSD awk on macOS lacks it)
  retry_after=$(awk 'tolower($1) ~ /^retry-after:/ {print $2}' "$HDR_FILE" 2>/dev/null | tr -d '\r' | head -1)
  if printf '%s' "${retry_after:-}" | grep -Eq '^[0-9]+$'; then
    sleep_s="$retry_after"
  else
    sleep_s=$(awk -v b="$RETRY_BASE" -v a="$attempt" -v r="$RANDOM" \
      'BEGIN{ printf "%.2f", b * (2 ^ (a - 1)) + (r % 1000) / 1000 }')
  fi
  sleep "$sleep_s"
done
