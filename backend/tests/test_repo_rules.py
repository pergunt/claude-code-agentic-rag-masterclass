"""Static repo-rule checks (STA-04)."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def tracked_and_new() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.splitlines() if (ROOT / p).is_file()]


def scan(paths, pattern, flags=0):
    rx = re.compile(pattern, flags)
    hits = []
    for p in paths:
        try:
            text = (ROOT / p).read_text(errors="ignore")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{p}:{n}: {line.strip()[:120]}")
    return hits


def app_code():
    files = tracked_and_new()
    return [
        p for p in files
        if (p.startswith("backend/app/") and p.endswith(".py"))
        or (p.startswith("frontend/src/") and not p.endswith(".md"))
    ]


def test_STA_04_no_responses_api_remnants():
    hits = scan(app_code(), r"conversations\.|responses\.create|file_search|openai_conversation_id")
    assert not hits, "Responses-API remnants found:\n" + "\n".join(hits)


def test_STA_04_no_langchain_or_langgraph():
    hits = scan(["backend/requirements.txt", "frontend/package.json"], r"langchain|langgraph", re.I)
    assert not hits, "Forbidden frameworks:\n" + "\n".join(hits)


def test_STA_04_service_client_only_in_ingestion():
    allowed = {
        "backend/app/services/ingestion.py",
        "backend/app/services/app_settings.py",
        "backend/app/db.py",
    }
    files = [p for p in tracked_and_new() if p.startswith("backend/app/") and p.endswith(".py")]
    hits = [h for h in scan(files, r"create_service_client\(") if h.split(":")[0] not in allowed]
    assert not hits, "create_service_client( used outside ingestion/app_settings/db:\n" + "\n".join(hits)


def test_STA_04_no_tracked_env_files():
    r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    bad = [p for p in r.stdout.splitlines() if Path(p).name == ".env"]
    assert not bad, f"Tracked .env files: {bad}"


def test_STA_04_every_table_has_rls():
    sql = "\n".join(p.read_text() for p in sorted((ROOT / "supabase" / "migrations").glob("*.sql")))
    tables = re.findall(r"create\s+table\s+(?:if\s+not\s+exists\s+)?public\.(\w+)", sql, re.I)
    assert tables, "no tables found in migrations"
    missing = [
        t for t in tables
        if not re.search(rf"alter\s+table\s+public\.{t}\s+enable\s+row\s+level\s+security", sql, re.I)
    ]
    assert not missing, f"Tables without RLS enabled: {missing}"
