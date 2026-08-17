# Copyright 2026 LikeMinds
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""PostHog usage analytics.

The server runs on each user's own machine, so the project key is baked into this
file rather than read from .env — a fresh clone has no .env value to read, and it
would never be set. A PostHog project key is write-only (it can create events, it
cannot read any data back), which is exactly why it is safe to ship in public source.

Identity is the user's email, resolved ONCE at startup by `require_email()`. There is
no queue and no background worker: `capture()` fires one HTTP POST on a daemon thread
and forgets it. The thread matters — everything else in this server shares a single
asyncio event loop, so a blocking POST would stall every running pipeline behind it.

Sending is best-effort by design. A failed request is dropped silently; analytics
never surfaces an error to a caller and never fails a run.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import urllib.request

# Write-only PostHog project key ("phc_..."). Empty disables analytics entirely,
# including the startup email requirement — a fork that has not set its own key
# still runs.
POSTHOG_KEY = "phc_nfq24fLj4u44zuYkauJCcHhsi6EJiWWsatidAgSpcZBx"
POSTHOG_HOST = "https://us.i.posthog.com"

_REQUEST_TIMEOUT = 5

# Resolved once by require_email() at startup. Empty means "do not send".
_email = ""


class EmailNotConfigured(RuntimeError):
    """Neither source yielded a usable email — the server refuses to start."""


_HELP = """Could not determine your email address, which this server needs to start.

Fix either one:

  1. Configure git (applies to every project on this machine):

       git config --global user.email "you@example.com"

  2. Or set it in .env at the project root:

       LIKEMINDS_USER_EMAIL=you@example.com

Running in Docker? Use option 2 — the container has no git identity of its own.

This email identifies your usage in LikeMinds' analytics. See the Telemetry
section of README.md for exactly what is sent."""


def _git_email() -> str:
    """`git config --get user.email`, or "" if git is missing or has no identity set.

    Reads the global config too, so this works whether or not the server was started
    from inside a repository.
    """
    try:
        done = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip()


def require_email() -> str:
    """Resolve the user's email and remember it, or raise EmailNotConfigured.

    LIKEMINDS_USER_EMAIL is checked BEFORE git: setting it is a deliberate act, and a
    machine's git identity is often not the address the user wants reported. Falling
    back to git is what makes the common case zero-setup.
    """
    global _email
    if not POSTHOG_KEY:
        return ""
    email = (os.environ.get("LIKEMINDS_USER_EMAIL") or "").strip() or _git_email()
    if "@" not in email:
        raise EmailNotConfigured(_HELP)
    _email = email
    return email


def capture(event: str, **properties) -> None:
    """Send one event. Returns immediately; never raises."""
    if not _email:
        return
    payload = json.dumps(
        {
            "api_key": POSTHOG_KEY,
            "event": event,
            "distinct_id": _email,
            # $set puts the address on the PostHog person profile, so people are
            # listed by email rather than by a bare distinct_id.
            "properties": {**properties, "$set": {"email": _email}},
        }
    ).encode("utf-8")
    threading.Thread(target=_post, args=(payload,), daemon=True).start()


def _post(payload: bytes) -> None:
    req = urllib.request.Request(
        f"{POSTHOG_HOST}/i/v0/e",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT).close()
    except Exception:  # noqa: BLE001 — a dropped event must never reach the caller
        pass
