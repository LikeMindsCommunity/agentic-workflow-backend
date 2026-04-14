#!/bin/bash

# Claude Code Bug-Fix System — Installer

COMMANDS_DIR="$HOME/.claude/commands"

mkdir -p "$COMMANDS_DIR"

# Determine script directory (works whether cloned or piped)
if [ -d "commands" ]; then
  SRC="commands"
elif [ -d "$(dirname "$0")/commands" ]; then
  SRC="$(dirname "$0")/commands"
else
  echo "Error: commands/ folder not found. Run this from the repo root."
  exit 1
fi

cp "$SRC"/fix-bug.md "$COMMANDS_DIR/"
cp "$SRC"/apply-fixes.md "$COMMANDS_DIR/"
cp "$SRC"/batch-fix.md "$COMMANDS_DIR/"
cp "$SRC"/init-project.md "$COMMANDS_DIR/"
cp "$SRC"/review-approval-sheet.md "$COMMANDS_DIR/"
cp "$SRC"/triage-bug.md "$COMMANDS_DIR/"
cp "$SRC"/process-backlog.md "$COMMANDS_DIR/"

echo ""
echo "✅ Installed 7 commands to $COMMANDS_DIR"
echo ""
echo "Commands available in every project:"
echo "  /init-project          — bootstrap any new project"
echo "  /triage-bug            — enrich a vague bug report and add to backlog"
echo "  /fix-bug               — diagnose and propose a fix"
echo "  /batch-fix             — process multiple bugs"
echo "  /process-backlog       — move approved backlog bugs into approval sheet"
echo "  /review-approval-sheet — summarize approval sheet"
echo "  /apply-fixes           — apply approved fixes"
echo ""
echo "Next: cd into any project, run 'claude', then '/init-project'"
