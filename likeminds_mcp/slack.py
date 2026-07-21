"""Slack notifications — a registration + skill-run feed posted into one conversation.

Two events reach the channel:
  • REGISTRATION — a user finishes the browser login (the OAuth /authorize handshake, or
    the standalone token page): we post the email that just registered.
  • SKILL RUN    — a run reaches a terminal state: who ran it, which skill, the session
    id, start/finish/duration, and a download link for every artifact produced.

Everything here is BEST-EFFORT and fire-and-forget. Notifications are observability, not
part of the product path: a revoked webhook, a Slack outage, or a deleted channel must
never fail a login or lose a deliverable. So every post is wrapped (`_post` swallows),
and callers dispatch through `fire()`, which runs the coroutine as a detached task so a
slow Slack API can't delay the user's own response. Failures print one line to stderr —
silent misconfiguration would look exactly like "nobody registered today".

Transport: a Slack Incoming Webhook (config.SLACK_WEBHOOK_URL) — one POST of a Block Kit
payload, with no token and no channel argument. The URL is both the credential and the
destination; the channel is fixed when the webhook is created. Note the reply is the bare
string `ok`, NOT the JSON envelope the Web API returns, so success is judged on the HTTP
status and the error text is the body itself (`no_service`, `channel_not_found`, …).
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Optional

import httpx

from . import config

# Detached notification tasks, held while in flight: asyncio keeps only a WEAK reference
# to a running task, so a task nobody holds can be garbage-collected mid-await.
_INFLIGHT: set = set()


# ─── plumbing ────────────────────────────────────────────────────────────────

def fire(coro) -> None:
    """Dispatch a notification without waiting for it (and without ever raising).

    Used on the login and run-completion paths, where the user's response must not wait
    on Slack. With Slack unconfigured the coroutine is closed rather than scheduled, so
    an off switch costs nothing and Python doesn't warn about a coroutine never awaited.
    """
    if not config.USE_SLACK:
        coro.close()
        return
    try:
        task = asyncio.ensure_future(coro)
    except RuntimeError:  # no running event loop (e.g. called at import time)
        coro.close()
        return
    _INFLIGHT.add(task)
    task.add_done_callback(_INFLIGHT.discard)


def _warn(msg: str) -> None:
    """One line to stderr. The webhook URL is a credential and some transport errors
    quote the URL they failed on, so it is redacted here rather than trusted not to
    appear — stderr ends up in container logs."""
    if config.SLACK_WEBHOOK_URL:
        msg = msg.replace(config.SLACK_WEBHOOK_URL, "<webhook-url>")
    print(f"[slack] {msg}"[:500], file=sys.stderr, flush=True)


async def _post(text: str, blocks: list) -> None:
    """Post one message to the webhook. `text` is the notification/fallback line — what a
    phone shows and what search indexes, since blocks don't supply either.

    Never raises: the failure is reported to stderr and the caller carries on. The body of
    a non-200 IS Slack's error message, so it is what gets logged."""
    if not config.USE_SLACK:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                config.SLACK_WEBHOOK_URL,
                json={"text": text, "blocks": blocks,
                      "unfurl_links": False, "unfurl_media": False},
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        if resp.status_code != 200:
            # Never echo the URL itself — it is the credential.
            _warn(f"post failed: HTTP {resp.status_code} {resp.text.strip()[:200]}")
    except Exception as e:  # noqa: BLE001 — a notification never breaks its caller
        _warn(f"post failed: {type(e).__name__}: {e}")


# ─── formatting ──────────────────────────────────────────────────────────────

def _esc(s) -> str:
    """Slack requires &, < and > to be escaped in message text."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _link(url: str, label: str) -> str:
    """A Slack link. The URL's own ampersands are escaped too — Slack unescapes them
    when it builds the anchor, and a presigned R2 URL is nothing but ampersands."""
    return f"<{str(url).replace('&', '&amp;')}|{_esc(label)}>"


def _when(epoch: Optional[float]) -> str:
    """A timestamp Slack renders in each reader's own timezone, falling back to UTC for
    clients that can't (search results, notifications, exports)."""
    if not epoch:
        return "—"
    utc = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(epoch))
    return f"<!date^{int(epoch)}^{{date_short_pretty}} {{time_secs}}|{utc}>"


def _ttl() -> str:
    """How long a posted download link stays valid, in human terms. The links are R2
    presigned URLs, and a posted message cannot re-sign itself the way a polling client
    can — so the message has to say when they die rather than leave a dead link looking
    live."""
    secs = config.R2_URL_EXPIRY
    if secs >= 86400:
        return f"{secs // 86400}d"
    if secs >= 3600:
        return f"{secs // 3600}h"
    return f"{max(1, secs // 60)}m"


def _duration(start: Optional[float], end: Optional[float]) -> str:
    if not start or not end or end < start:
        return "—"
    secs = int(end - start)
    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s" if m else f"{s}s"


def _fields(pairs: list[tuple[str, str]]) -> dict:
    """A two-column section. Slack caps a section at 10 fields, so the caller's list is
    truncated rather than rejected by the API."""
    return {
        "type": "section",
        "fields": [{"type": "mrkdwn", "text": f"*{k}*\n{v}"} for k, v in pairs[:10]],
    }


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:2900]}}


# ─── events ──────────────────────────────────────────────────────────────────

async def notify_registration(
    email: str, user_id: str, is_new: bool, via: str = "oauth"
) -> None:
    """A user completed the browser login.

    Only a REGISTRATION posts. `is_new` is false for a returning sign-in — the same page
    and the same code path, but routine, and posting every re-login would bury the
    registrations the channel exists to surface."""
    if not config.USE_SLACK or not is_new:
        return
    how = "OAuth (MCP client)" if via == "oauth" else "Access token (manual config)"
    await _post(
        f"New user registered: {email}",
        [
            _section(f":tada: *New user registered* — `{_esc(email)}`"),
            _fields([
                ("Email", _esc(email)),
                ("Connected via", how),
                ("User ID", f"`{_esc(user_id)}`"),
                ("When", _when(time.time())),
            ]),
        ],
    )


async def notify_skill_run(
    *,
    status: str,
    skill: str,
    session_id: str,
    result_id: str = "",
    email: Optional[str] = None,
    tenant: Optional[str] = None,
    started_at: Optional[float] = None,
    finished_at: Optional[float] = None,
    files: Optional[list] = None,
    download_urls: Optional[dict] = None,
    registered_skills: Optional[list] = None,
    error: Optional[str] = None,
) -> None:
    """A skill run reached a terminal state — `done` or `error`. Both post: a failed run
    is the one you most want to see land in the channel."""
    if not config.USE_SLACK:
        return

    ok = status == "done"
    who = email or (f"anonymous (tenant `{_esc(tenant)}`)" if tenant else "anonymous")
    headline = "Skill run complete" if ok else "Skill run failed"
    blocks = [
        _section(f"{':white_check_mark:' if ok else ':x:'} *{headline}* — `{_esc(skill)}`"),
        _fields([
            ("User", _esc(who)),
            ("Skill", f"`{_esc(skill)}`"),
            ("Session ID", f"`{_esc(session_id)}`"),
            ("Duration", _duration(started_at, finished_at)),
            ("Started", _when(started_at)),
            ("Finished", _when(finished_at)),
        ]),
    ]

    if not ok:
        blocks.append(_section(f"*Error*\n```{_esc(error or 'unknown error')[:1500]}```"))
    elif registered_skills:
        # A compile run installs skills instead of producing a downloadable deliverable.
        names = ", ".join(f"`{_esc(n)}`" for n in registered_skills)
        blocks.append(_section(f"*Registered skill(s)*\n{names}"))
    elif download_urls:
        lines, shown = [], 0
        for name, url in download_urls.items():
            line = f"• {_link(url, name)}"
            if sum(len(x) + 1 for x in lines) + len(line) > 2700:
                break
            lines.append(line)
            shown += 1
        more = len(download_urls) - shown
        if more > 0:
            lines.append(f"…and {more} more file(s) in `outputs/mcp/{_esc(result_id)}/`")
        blocks.append(_section(
            f"*Artifacts ({len(download_urls)})* — links expire in {_ttl()}\n"
            + "\n".join(lines)
        ))
    else:
        # No links to give — either R2 is not configured, or the upload failed. Name the
        # files and point at the on-server copy, which an operator can still fetch off the
        # host by hand; that is the only route left that works.
        names = "\n".join(f"• `{_esc(n)}`" for n in (files or [])[:20]) or "_none_"
        more = len(files or []) - 20
        if more > 0:
            names += f"\n…and {more} more"
        blocks.append(_section(
            f":warning: *Artifacts ({len(files or [])})* — no download links available. "
            f"On the server at `outputs/mcp/{_esc(result_id)}/`\n{names}"
        ))

    await _post(f"{headline}: {skill} — {who}", blocks)
