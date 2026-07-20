# likeminds_mcp — MCP server that drives the Claude Code CLI (resume-per-turn).
#
# The image bundles the three things the server needs at runtime:
#   1. Python + the server's deps (mcp, python-dotenv, boto3)
#   2. the `claude` CLI — the server spawns `claude -p …` as a subprocess every turn
#   3. a headless-render toolchain (Chromium, poppler, fonts, python-docx) for the
#      document skills — they emit PDF or DOCX, chosen per document at generate time
#
# It runs as a NON-root user on purpose: the engine invokes
# `claude --permission-mode bypassPermissions`, which refuses to run as root.
#
# Build:  docker build -t likeminds-mcp .
# Run:    docker run --rm -p 8787:8787 --env-file .env --shm-size=1g likeminds-mcp
#         (--shm-size is important — headless Chromium crashes on Docker's default 64M)

FROM python:3.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ── System packages ────────────────────────────────────────────────────────────
#   chromium        primary PDF renderer (skills invoke `google-chrome --headless`)
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

# ── Node 20 + the Claude Code CLI ──────────────────────────────────────────────
# A global npm install puts `claude` on PATH for every user (required since the
# server runs as non-root and shells out to it).
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
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
    && mkdir -p /app/.sessions /app/outputs/mcp \
    && chown -R appuser:appuser /app
USER appuser
ENV HOME=/home/appuser

# ── Runtime config ─────────────────────────────────────────────────────────────
# Bind on all interfaces so the container is reachable. Auth (CLAUDE_TOKEN or
# ANTHROPIC_API_KEY) and the four R2_* vars are supplied at RUN time via --env-file
# — never baked into the image.
ENV LIKEMINDS_MCP_HOST=0.0.0.0 \
    LIKEMINDS_MCP_PORT=8787 \
    DISABLE_AUTOUPDATER=1

EXPOSE 8787

# Liveness: the app-level MCP port is accepting connections.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import socket,os; socket.create_connection(('127.0.0.1', int(os.environ['LIKEMINDS_MCP_PORT'])), 3).close()" || exit 1

CMD ["python", "-m", "likeminds_mcp"]
