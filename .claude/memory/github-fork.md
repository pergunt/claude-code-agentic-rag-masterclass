# GitHub: this repo is a fork

`origin` is `pergunt/claude-code-agentic-rag-masterclass`, a fork of
`theaiautomators/claude-code-agentic-rag-masterclass`. The `gh` CLI defaults to the **upstream**
repo, so always pass `-R pergunt/claude-code-agentic-rag-masterclass` to `gh release`, `gh pr`,
`gh issue`, etc. Otherwise commands target (or fail against) the course author's repo.

Releases: tags are plain version numbers (`0.1`, first release 2026-10-28) with notes taken from
`CHANGELOG.md`. Version fields live in `frontend/package.json` (+ lock file) and the FastAPI
`version=` in `backend/app/main.py`.
