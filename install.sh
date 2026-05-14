#!/bin/bash

# Claude Code Bug-Fix System — Installer

COMMANDS_DIR="$HOME/.claude/commands"

mkdir -p "$COMMANDS_DIR"

# Determine script directory (works whether cloned or piped)
if [ -d ".claude/commands" ]; then
  SRC=".claude/commands"
elif [ -d "$(dirname "$0")/.claude/commands" ]; then
  SRC="$(dirname "$0")/.claude/commands"
else
  echo "Error: .claude/commands/ folder not found. Run this from the repo root."
  exit 1
fi

cp "$SRC"/fix-bug.md "$COMMANDS_DIR/"
cp "$SRC"/apply-fixes.md "$COMMANDS_DIR/"
cp "$SRC"/batch-fix.md "$COMMANDS_DIR/"
cp "$SRC"/init-project.md "$COMMANDS_DIR/"
cp "$SRC"/review-approval-sheet.md "$COMMANDS_DIR/"
cp "$SRC"/triage-bug.md "$COMMANDS_DIR/"
cp "$SRC"/process-backlog.md "$COMMANDS_DIR/"
cp "$SRC"/find-bugs.md "$COMMANDS_DIR/"
cp "$SRC"/find-bugs-exotel.md "$COMMANDS_DIR/"
cp "$SRC"/process-comparison.md "$COMMANDS_DIR/"
cp "$SRC"/generate-document.md "$COMMANDS_DIR/"
cp "$SRC"/platform-kb.md "$COMMANDS_DIR/"

echo ""
echo "✅ Installed 12 commands to $COMMANDS_DIR"
echo ""
echo "Commands available in every project:"
echo "  /init-project          — bootstrap any new project"
echo "  /triage-bug            — enrich a vague bug report and add to backlog"
echo "  /fix-bug               — diagnose and propose a fix"
echo "  /batch-fix             — process multiple bugs"
echo "  /process-backlog       — move approved backlog bugs into approval sheet"
echo "  /find-bugs             — compare generated vs expected files"
echo "  /find-bugs-exotel      — Exotel IVR JSON comparison (wraps /find-bugs)"
echo "  /process-comparison    — process approved comparisons into fix proposals"
echo "  /review-approval-sheet — summarize approval sheet"
echo "  /apply-fixes           — apply approved fixes"
echo "  /generate-document     — generate document from KB + source materials"
echo "  /platform-kb           — platform knowledge base generator"
echo ""
echo "Next: cd into any project, run 'claude', then '/init-project'"
echo "Tip: when new commands are added to this repo, re-run ./install.sh to pick them up."
