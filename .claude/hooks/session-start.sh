#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

SUPERPOWERS_DIR="$HOME/.claude/superpowers"
SKILLS_DIR="$HOME/.claude/skills"

# Clone or update superpowers
if [ -d "$SUPERPOWERS_DIR/.git" ]; then
  git -C "$SUPERPOWERS_DIR" pull --ff-only --quiet 2>/dev/null || true
else
  git clone --depth=1 --quiet https://github.com/obra/superpowers.git "$SUPERPOWERS_DIR"
fi

# Symlink each skill into ~/.claude/skills/
mkdir -p "$SKILLS_DIR"
for skill_dir in "$SUPERPOWERS_DIR/skills"/*/; do
  skill_name=$(basename "$skill_dir")
  target="$SKILLS_DIR/$skill_name"
  if [ ! -L "$target" ] && [ ! -d "$target" ]; then
    ln -s "$skill_dir" "$target"
  fi
done

SKILL_COUNT=$(ls "$SUPERPOWERS_DIR/skills" | wc -l | tr -d ' ')
echo "Session start hook: icount repository ready. Superpowers installed ($SKILL_COUNT skills)."
