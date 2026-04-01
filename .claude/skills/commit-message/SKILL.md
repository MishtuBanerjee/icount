---
name: commit-message
description: Use when about to write a git commit message, especially for staged changes with mixed concerns or unclear intent.
---

# Commit Message

Write commit messages that explain WHY, not WHAT.

## Pattern

```
<type>: <what changed and why in one line>

<optional body: motivation, trade-offs, or non-obvious context>
```

**Types:** `fix`, `feat`, `refactor`, `docs`, `test`, `chore`

## Rules

- Subject line: 50 chars max, imperative mood ("Add X" not "Added X")
- Body: wrap at 72 chars, blank line between subject and body
- Explain the problem being solved, not the solution mechanics
- Never mention file names, ticket numbers, or "as requested"

## Quick Reference

| ❌ Bad | ✅ Good |
|---|---|
| `fix bug` | `fix: prevent crash when user list is empty` |
| `update README` | `docs: clarify install steps for Windows users` |
| `changes per review` | `refactor: simplify auth flow per code review` |

## Common Mistakes

- Writing "WIP" or "misc fixes" — always describe the intent
- Summarizing the diff — git diff already does that
- Past tense — use imperative: "Add" not "Added"
