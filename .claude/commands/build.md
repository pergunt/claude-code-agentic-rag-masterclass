---
description: Build from the plan (coder subagent implements, main model reviews)
argument-hint: [link-to-plan]
---

# Build

Plan: `$ARGUMENTS`

The `coder` subagent (Sonnet) writes the code. You (the main model) delegate the work, review it and validate it. Don't write the feature code yourself.

## Process

1. **Read the entire plan** - Understand all tasks, dependencies, human gates (keys, migrations) and success criteria. If something is ambiguous, tighten the plan file first so the coder doesn't have to guess.

2. **Delegate to `coder`** - Spawn the `coder` subagent with:
   - the plan path, and which tasks to do (all of them, or a batch that stops at a human gate or a natural checkpoint)
   - any reconciliation notes or decisions made since the plan was written
   - an instruction to run each task's validation commands that don't need running services or human action, and to report files changed, validation output and any deviations

   Handle human gates yourself: ask the user, wait, then continue the coder with `SendMessage`.

3. **Review the coder's work** - Read the diff (`git diff` plus new files) against the plan:
   - every task done, nothing extra, no silent deviations
   - correctness bugs, missing error handling, RLS/auth gaps, secrets in code
   - the code matches the surrounding conventions

   Fix trivial issues directly. Send anything bigger back to `coder` with precise instructions (file, what's wrong, what it should be), then review again.

4. **Validate** - Run the plan's validation steps yourself, including the live and browser tests (Playwright / Chrome MCP). Route failures back through step 3.

5. **Report completion** - Summarise:
   - tasks completed
   - files created or modified
   - test results
   - review findings and how they were resolved
   - any deviations from the plan and why

6. **Shut down** - Follow the CLAUDE.md shutdown step.
