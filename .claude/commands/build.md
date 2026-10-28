---
description: Build from the plan (coder subagent implements, main model reviews)
argument-hint: [link-to-plan]
---

# Build

Plan: `$ARGUMENTS`

The `coder` subagent (Sonnet) writes the code. You (the main model) delegate the work, review it and validate it. Don't write the feature code yourself.

## Process

1. **Read the entire plan** - Understand all tasks, dependencies, human gates (keys, migrations) and success criteria. If something is ambiguous, tighten the plan file first so the coder doesn't have to guess.

2. **Work out the execution order** - Before spawning anything, build a dependency map of the plan's tasks:
   - For each task, list the files it creates or edits, and what it needs first: code from another task (imports, types, an API shape), an applied migration, an installed dependency, a human gate, or running services.
   - Group the tasks into **waves**. A wave holds tasks that don't depend on each other and **don't touch the same files**. Each wave starts only after everything it depends on is done. Shared files such as `config.py`, `.env.example`, `requirements.txt`, `package.json`, `main.py` and `App.tsx` belong to exactly one task in a wave. Otherwise, put that edit in an earlier wave on its own.
   - Typical shape: shared foundations (config, dependencies, schema/migration file, shared types) → independent pieces in parallel (for example backend service + frontend UI, or separate modules) → wiring that joins them (routers, routes, nav) → live validation.
   - Human gates (keys, applying a migration) split waves: ask the user as soon as nothing before the gate is still needed, and keep running work that doesn't depend on it while you wait.
   - If no tasks can run in parallel, or the plan is small enough that splitting costs more than it saves, use one `coder` and give it the tasks in that valid order.
   - Tell the user the waves in a few lines (which tasks run in parallel, which run in order and why) before you start.

3. **Delegate to `coder`** - For each wave, spawn one `coder` subagent per parallel task group in a single message, so they run at the same time. Wait until every agent in the wave reports before starting the next wave. Give each coder:
   - the plan path and **exactly** which tasks it owns
   - the files it may edit, and the files other coders in the same wave own, which it must not touch
   - any reconciliation notes or decisions made since the plan was written
   - an instruction to run its own tasks' validation commands that need no running services and no human action, and to report files changed, validation output and any deviations
   - for parallel coders: don't run shared-state commands (`pip install`, `npm install`, `npx shadcn add`, starting services). The task that owns the dependency change does those, in an earlier wave or alone.

   Handle human gates yourself: ask the user, wait, then continue the right coder with `SendMessage` (or start the next wave).

4. **Review the coder's work** - After each wave (or at the end, for a single coder), read the diff (`git diff` plus new files) against the plan:
   - the waves didn't collide: each file was edited only by its owner, and the pieces fit together (imports, names and API shapes match across tasks)
   - every task done, nothing extra, no silent deviations
   - correctness bugs, missing error handling, RLS/auth gaps, secrets in code
   - the code matches the surrounding conventions
   - the validation suite was updated: new or changed `validation/FEATURES.md` rows, plus ID-named tests for each (see CLAUDE.md "Validation suite"). If the plan forgot this, add the task and give it to a coder; don't skip it

   Fix trivial issues directly. Send anything bigger back to the `coder` that owns the file with precise instructions (file, what's wrong, what it should be), then review again.

5. **Validate** - Run the plan's validation steps yourself, including the live and browser tests (Playwright / Chrome MCP). Then run the regression suite with `/validate full`. Every ID must be PASS or PASS (flaky) and none UNCOVERED, so new features are covered and old ones aren't broken. Route failures back through step 4.

6. **Report completion** - Summarise:
   - tasks completed
   - files created or modified
   - test results, including the `/validate full` totals line and the new catalogue IDs
   - review findings and how they were resolved
   - how the work was split into waves (what ran in parallel)
   - any deviations from the plan and why

7. **Shut down** - Follow the CLAUDE.md shutdown step.
