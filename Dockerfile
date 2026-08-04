# likeminds_mcp — MCP server that drives the Claude Code CLI (resume-per-turn).
#
# The image bundles the three things the server needs at runtime:
#   1. Python + the server's deps (mcp, python-dotenv)
#   2. the `claude` CLI — the server spawns `claude -p …` as a subprocess every turn
#   3. a headless-render toolchain (Chromium, poppler, fonts, python-docx) for the
#      document skills — they emit PDF or DOCX, chosen per document at generate time
#
# It runs as a NON-root user on purpose: the engine invokes
# `claude --permission-mode bypassPermissions`, which refuses to run as root.
#
# Build:  docker build -t likeminds-mcp .
# Run:    docker run --rm -p 8787:8787 --env-file .env --shm-size=1g \
#             -v "$PWD/outputs:/app/outputs" \
#             -v "$HOME:/host:ro" -e LIKEMINDS_HOST_MOUNT="$HOME" likeminds-mcp
#         (--shm-size is important — headless Chromium crashes on Docker's default 64M)
#         (`input_paths` is resolved INSIDE the container, so host paths need the :/host
#          mount to be visible: with it, any path under $HOME can be passed unchanged and
#          the server rebases it. Read-only, but broad — narrow LIKEMINDS_HOST_MOUNT and
#          the matching -v to a smaller directory if that matters. Deliverables land in
#          ./outputs on the host. The container runs as uid 1000 — chown ./outputs to 1000
#          if your host user is not, or the run cannot write. docker-compose wires all of
#          this up automatically, defaulting the host mount to ${HOME}.)

FROM python:3.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ── System packages ────────────────────────────────────────────────────────────
#   chromium        primary PDF renderer (skills invoke `google-chrome --headless`), and
#                   the browser the Playwright MCP driver steers for the web-flow skills
#   poppler-utils   pdftoppm — renders sample/output PDFs to images for the diff pass
#   fonts-*         real fonts in rendered PDFs (crosextra-carlito == Calibri metrics)
#   cairo/pango/…   native libs for the WeasyPrint fallback renderer
#   git/curl/gnupg  general CLI + skill needs; curl+gnupg also bootstrap NodeSource
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        poppler-utils \
        fonts-liberation fonts-dejavu-core fonts-crosextra-carlito fontconfig \
        libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi8 shared-mime-info \
        git curl ca-certificates gnupg \
    && ln -sf /usr/bin/chromium /usr/local/bin/google-chrome \
    && ln -sf /usr/bin/chromium /usr/local/bin/google-chrome-stable \
    && ln -sf /usr/bin/chromium /usr/local/bin/chromium-browser \
    && rm -rf /var/lib/apt/lists/*

# ── Node 20 + the Claude Code CLI + the Playwright MCP browser driver ──────────
# A global npm install puts `claude` on PATH for every user (required since the
# server runs as non-root and shells out to it).
#
# @playwright/mcp is the browser driver the web-flow skills need (kb-builder mapping a
# live site, browser-agent driving one). Installed at BUILD time so a run never fetches it
# over npx — which would be slow every turn and impossible without egress. It is attached
# to those skills only, by the engine's narrow MCP carve-out; every other skill still
# spawns with no MCP servers at all.
#
# PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD stops the `playwright` dependency's postinstall from
# pulling ~400MB of its own browser builds: we point it at the chromium installed above
# via --executable-path instead, so the image ships one browser rather than two.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code @playwright/mcp@0.0.78 \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps ────────────────────────────────────────────────────────────────
# requirements.txt = the server's deps. The rest are the document skills' deps:
#   weasyprint   fallback PDF renderer (Chrome headless is primary)
#   python-docx  the DOCX render pipeline — reads the bundled sample as a style base
#                and writes the .docx deliverable. Document skills offer PDF *or*
#                DOCX per document, so this is required, not optional.
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt weasyprint python-docx

# ── App + non-root user ────────────────────────────────────────────────────────
COPY . .
# HOME must be writable: the claude CLI stores its session transcripts under
# ~/.claude, and the server registers generated skills into /app/.claude/skills.
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/.sessions /app/inputs /app/outputs/mcp \
    && chown -R appuser:appuser /app
USER appuser
ENV HOME=/home/appuser

# ── Host-mounted I/O ─────────────────────────────────────────────────────────────
# The server takes files by PATH and leaves deliverables on disk, so the edges are
# meant to be bind-mounted from the host at run time:
#   /host         — READ-ONLY view of the host directory named by LIKEMINDS_HOST_MOUNT.
#                   This is what lets `input_paths` accept an ordinary host path: the
#                   server rebases anything under that directory onto this mount.
#   /app/outputs  — where deliverables land (RESULTS_DIR = /app/outputs/mcp)
# Deliberately NOT declared as a VOLUME: an anonymous volume on /app/outputs would
# silently swallow the deliverables when the caller forgets the -v flag, which is
# exactly the failure this local-file design exists to avoid. It is created and chowned
# to appuser above so an unmounted run still works (its output just lives in the
# container). /host needs no such treatment — Docker creates the mount point.

# ── Runtime config ─────────────────────────────────────────────────────────────
# Bind on all interfaces so the container is reachable. The Claude credential
# (CLAUDE_TOKEN or ANTHROPIC_API_KEY) is supplied at RUN time via --env-file — never
# baked into the image.
#
# LIKEMINDS_IN_CONTAINER / LIKEMINDS_HOST_MOUNT_AT are declared HERE because both are
# facts about this image, fixed at build time: it is a container, and /host is where the
# host mount lands. Stating them beats sniffing for /.dockerenv, which is a Docker
# implementation detail other runtimes (Podman, plain containerd) do not create.
# Its PARTNER, LIKEMINDS_HOST_MOUNT, cannot live here — that is the HOST-side path being
# mounted, which differs per user and is unknown until run time, so docker-compose.yml
# supplies it from ${HOME}. Anything set in .env overrides these.
ENV LIKEMINDS_MCP_HOST=0.0.0.0 \
    LIKEMINDS_MCP_PORT=8787 \
    LIKEMINDS_IN_CONTAINER=1 \
    LIKEMINDS_HOST_MOUNT_AT=/host \
    DISABLE_AUTOUPDATER=1

EXPOSE 8787

# Liveness: the app-level MCP port is accepting connections.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import socket,os; socket.create_connection(('127.0.0.1', int(os.environ['LIKEMINDS_MCP_PORT'])), 3).close()" || exit 1

CMD ["python", "-m", "likeminds_mcp"]
