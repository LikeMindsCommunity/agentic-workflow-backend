"""The per-session browser: one long-lived Chromium the SERVER owns, spoken to over CDP.

This is the one process in the design deliberately allowed to outlive a turn.

Everywhere else the server is turn-scoped on purpose — nothing is parked between
turns, which is what makes it leak-free and crash-resilient (see sessions.py). The
browser cannot follow that rule and still work. `browser-agent` pauses to ask the
operator for an OTP, and a pause ends the turn; when the whole browser stack was a
stdio child of that turn it died with it, so the resume restarted the login, the site
issued a fresh code, and the code the operator had just sent was already dead. The
interaction the skill is built around could never complete.

Why the anchor is Chromium itself and not a long-lived MCP driver: v1 of this module
kept a persistent `playwright-mcp --port` process and replayed its `Mcp-Session-Id`
from a per-turn stdio bridge. That put the cross-turn state in ANOTHER PROCESS'S
session table, and the driver's streamable-HTTP session manager destroys sessions
nondeterministically — `404 Session not found` after real turns, with no DELETE ever
sent (BROWSER_SESSION_FINDINGS.md §5; v1 is preserved in the git stash). It also
forced three wire-level workarounds (local initialize replay, SSE frame selection,
jsonrpc normalization) just to keep the handshake legal.

v2 moves the anchor down a level. The only long-lived process is Chromium
(`--remote-debugging-port`); every turn gets a brand-new, disposable stdio
`playwright-mcp --cdp-endpoint` that attaches to it, acts, and dies with the turn.
Each turn performs a complete, legal MCP handshake with its own private driver, so
there is no MCP session that outlives a turn — nothing a session manager can lose.
Measured (host, pinned 0.0.78): repeated SIGKILL-and-reattach cycles keep tabs,
cookies, and IN-MEMORY page state intact — the OTP-equivalent, since a login page
waiting at its code prompt is exactly in-memory state.

Profile hygiene: v0 passed `--isolated` so no run could inherit a previous run's
cookies. Launching Chromium ourselves needs an on-disk `--user-data-dir`; the
equivalent guarantee is a fresh temp dir per session, wiped by `sessions.reap_browser`
on every terminal path (purge covers done / error / turn timeout / reply timeout).

sessions.py must not import this module (it imports config, which sessions also
imports, and reaping must work even where no browser ever ran) — so the reap lives in
sessions.py itself, operating only on the handles this module leaves on the Session.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from . import config, sessions

# Fetch spec for the fallback path only; the image installs this globally at build time
# so `playwright-mcp` is normally already on PATH and nothing is fetched at run time.
BROWSER_MCP_SPEC = "@playwright/mcp@0.0.78"

# Where the per-turn driver writes screenshots and traces. Deliberately under outputs/
# — bind-mounted to the host — and NOT in the sandbox, which is invisible to the
# operator and discarded with the run. A headless browser the operator cannot see is
# only usable if what it saw lands somewhere they can open DURING the run, because the
# whole point of pausing is asking about a screen they must be able to look at.
BROWSER_EVIDENCE_ROOT = config.PROJECT_ROOT / "outputs" / "browser"

# How long to wait for Chromium to open its CDP port.
_START_TIMEOUT = float(os.environ.get("LIKEMINDS_BROWSER_START_TIMEOUT", "90"))


def _free_port() -> int:
    """Ask the OS for an unused port. Bound to loopback only."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _driver_cmd() -> list[str] | None:
    """The per-turn stdio driver's base command, or None if no driver is resolvable."""
    installed = shutil.which("playwright-mcp")
    if installed:
        return [installed]
    if shutil.which("npx"):
        return ["npx", "-y", BROWSER_MCP_SPEC]
    return None


def _chromium_path() -> str | None:
    """Resolve the Chromium binary WE launch (the driver only attaches, never launches).

    Ladder: explicit override → the Chromium the image already ships for PDF rendering
    (one browser in the image instead of two) → anything on PATH → dev-host fallbacks
    (Playwright's own builds, then the desktop Chrome) so the server is runnable on a
    bare macOS checkout without extra setup.
    """
    override = os.environ.get("LIKEMINDS_CHROMIUM")
    if override and Path(override).exists():
        return override
    if Path("/usr/bin/chromium").exists():
        return "/usr/bin/chromium"
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    if sys.platform == "darwin":
        cache = Path.home() / "Library" / "Caches" / "ms-playwright"
        for binary in sorted(cache.glob("chromium-*/chrome-mac*/*.app/Contents/MacOS/*"),
                             reverse=True):
            if binary.is_file() and os.access(binary, os.X_OK):
                return str(binary)
        desktop = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if desktop.exists():
            return str(desktop)
    return None


def _cdp_alive(cdp_url: str, timeout: float = 2.0) -> bool:
    """One probe of Chromium's CDP endpoint. Sync — callers wrap in a thread."""
    try:
        with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001 — any failure means "not reachable"
        return False


def _turn_entry(driver: list[str], cdp_url: str, evidence: Path) -> dict:
    """The MCP server entry handed to ONE turn: a disposable stdio playwright-mcp that
    attaches to the session's Chromium over CDP. It launches no browser of its own, so
    none of the launch flags (--headless, --no-sandbox, --isolated, --executable-path)
    apply; it may die as violently as the turn likes — the browser does not."""
    return {
        "command": driver[0],
        "args": driver[1:] + ["--cdp-endpoint", cdp_url, "--output-dir", str(evidence)],
    }


async def ensure(sess) -> dict | None:
    """Start this session's Chromium if it has none, and return the MCP server entry to
    hand the turn. None if no driver or no Chromium is resolvable, which the skills
    report as a missing surface rather than faking.

    Idempotent: later turns in the same session probe the running Chromium and reuse
    it, which is the entire point — the pause→ask→resume loop lands every turn in the
    SAME live browser, tabs and in-flight logins intact.
    """
    driver = _driver_cmd()
    if driver is None:
        return None

    evidence = BROWSER_EVIDENCE_ROOT / sess.id
    evidence.mkdir(parents=True, exist_ok=True)

    proc = getattr(sess, "browser_proc", None)
    if proc is not None and sess.browser_cdp:
        if proc.poll() is None and await asyncio.to_thread(_cdp_alive, sess.browser_cdp):
            return _turn_entry(driver, sess.browser_cdp, evidence)
        sessions.reap_browser(sess)  # died or unreachable between turns → rebuild

    chromium = _chromium_path()
    if chromium is None:
        return None

    port = _free_port()
    profile = tempfile.mkdtemp(prefix=f"lm-browser-{sess.id[:8]}-")
    proc = subprocess.Popen(
        [
            chromium,
            "--headless",                 # no display anywhere this runs
            "--no-sandbox",               # Chromium's sandbox needs privileges the container lacks
            "--disable-dev-shm-usage",    # container /dev/shm is tiny; without this tabs crash
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        cwd=str(config.PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # its own process group: reap kills the WHOLE tree
    )
    cdp_url = f"http://127.0.0.1:{port}"

    # Handles go on the record BEFORE the readiness wait so every failure path from
    # here — including purge racing a slow startup — reaps the process and the profile.
    sess.browser_proc = proc
    sess.browser_profile_dir = profile
    sess.browser_cdp = cdp_url

    loop = asyncio.get_running_loop()
    deadline = loop.time() + _START_TIMEOUT
    while loop.time() < deadline:
        if proc.poll() is not None:
            break  # Chromium exited during startup
        if await asyncio.to_thread(_cdp_alive, cdp_url):
            return _turn_entry(driver, cdp_url, evidence)
        await asyncio.sleep(0.5)

    sessions.reap_browser(sess)
    return None
