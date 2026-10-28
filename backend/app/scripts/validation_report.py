"""Join test results against validation/FEATURES.md and write report.md.

    python -m app.scripts.validation_report <report-dir> --mode quick|full [--only regex]

Exit code 1 if any FAIL or UNCOVERED (or unattributed junit failure), else 0.
"""
import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ID_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,4})[-_](\d{2})(?![0-9])")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
STATUSES = ["PASS", "PASS (flaky)", "FAIL", "SKIP", "NOT RUN", "UNCOVERED"]


def find_id(text: str):
    m = ID_RE.search(text or "")
    return f"{m.group(1)}-{m.group(2)}" if m else None


def first_line(text: str, limit: int = 160) -> str:
    text = ANSI.sub("", text or "").strip()
    line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return line[: limit - 1] + "…" if len(line) > limit else line


def parse_catalogue(path: Path):
    sections: list[tuple[str, list[dict]]] = []
    for line in path.read_text().splitlines():
        if line.startswith("### ") or line.startswith("## "):
            sections.append((line.lstrip("# ").strip(), []))
        elif line.startswith("|") and sections:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and re.fullmatch(r"[A-Z]{2,4}-\d{2}", cells[0]):
                sections[-1][1].append({"id": cells[0], "feature": cells[1], "tier": cells[3]})
    return [(n, rows) for n, rows in sections if rows]


def expected_in(tier: str, mode: str) -> bool:
    if mode == "full":
        return True
    toks = {t.strip() for t in tier.split(",")}
    if "traces" in toks or "llm" in toks:
        return False
    if "e2e" in toks:
        return "smoke" in toks
    return True


# result: (status, evidence, is_failure_detail)
def junit_results(path: Path):
    out, unattributed = [], []
    if not path.exists():
        return out, unattributed
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return out, [f"{path.name}: unparsable ({exc})"]
    for tc in root.iter("testcase"):
        name = tc.get("name", "")
        tid = find_id(name)
        fail = tc.find("failure")
        if fail is None:
            fail = tc.find("error")
        flaky = None
        for prop in tc.iter("property"):
            if prop.get("name") == "flaky":
                try:
                    if int(float(prop.get("value", "1"))) > 0:
                        flaky = prop.get("value")
                except ValueError:
                    flaky = prop.get("value")
        if fail is not None:
            status, ev = "FAIL", first_line(fail.get("message") or fail.text or "failed")
        elif tc.find("skipped") is not None:
            status, ev = "SKIP", first_line(tc.find("skipped").get("message") or "skipped")
        elif flaky:
            status, ev = "PASS (flaky)", f"passed after {flaky} retry (LLM)"
        else:
            status, ev = "PASS", ""
        if tid:
            out.append((tid, status, ev, f"{path.name}::{name}"))
        elif status == "FAIL":
            unattributed.append(f"{path.name}::{tc.get('classname', '')}.{name}: {ev}")
    return out, unattributed


def playwright_results(path: Path):
    out = []
    if not path.exists():
        return out
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return out

    def walk(suite):
        for spec in suite.get("specs", []):
            tid = find_id(spec.get("title", ""))
            for t in spec.get("tests", []):
                results = t.get("results") or []
                last = results[-1] if results else {}
                st = t.get("status")
                ev = ""
                if st == "unexpected":
                    status = "FAIL"
                    err = last.get("error") or {}
                    ev = first_line(err.get("message", "failed"))
                    for a in last.get("attachments", []) or []:
                        if a.get("path"):
                            ev += f" [{a['path']}]"
                            break
                elif st == "flaky":
                    status, ev = "PASS (flaky)", f"passed after {max(len(results) - 1, 1)} retry"
                elif st == "skipped":
                    status = "SKIP"
                else:
                    status = "PASS"
                if tid:
                    out.append((tid, status, ev, f"playwright::{spec.get('title')}"))
        for s in suite.get("suites", []):
            walk(s)

    for s in data.get("suites", []):
        walk(s)
    return out


def combine(items):
    statuses = [s for s, _ in items]
    evid = lambda st: next((e for s, e in items if s == st and e), "")
    if "FAIL" in statuses:
        return "FAIL", evid("FAIL")
    if "PASS (flaky)" in statuses:
        return "PASS (flaky)", evid("PASS (flaky)")
    if all(s == "SKIP" for s in statuses):
        return "SKIP", evid("SKIP")
    return "PASS", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--mode", choices=["quick", "full"], default="full")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    d = Path(args.dir)

    raw: list[tuple[str, str, str, str]] = []
    unattributed: list[str] = []
    for name in ("junit-unit.xml", "junit-live.xml"):
        r, u = junit_results(d / name)
        raw += r
        unattributed += u
    raw += playwright_results(d / "playwright.json")
    tj = d / "traces.json"
    if tj.exists():
        try:
            for e in json.loads(tj.read_text()):
                raw.append((e["id"], e["status"], e.get("message", "") if e["status"] != "PASS" else e.get("message", ""), "traces.json"))
        except (json.JSONDecodeError, KeyError):
            pass
    for sf in sorted((d / "static").glob("*.status")):
        lines = sf.read_text().splitlines()
        raw.append((sf.stem, lines[0].strip() if lines else "FAIL", lines[1] if len(lines) > 1 else "", sf.name))

    by_id = defaultdict(list)
    for tid, st, ev, _src in raw:
        by_id[tid].append((st, ev))

    services_reason = ""
    ss = d / "services.status"
    if ss.exists():
        lines = ss.read_text().splitlines()
        if lines and lines[0].strip() == "FAIL":
            services_reason = lines[1] if len(lines) > 1 else "services unavailable"

    only_re = re.compile(args.only.replace("_", "-")) if args.only else None
    catalogue = parse_catalogue(ROOT / "validation" / "FEATURES.md")
    known = {r["id"] for _, rows in catalogue for r in rows}

    counts = defaultdict(int)
    sections_out = []
    failures = []
    for sname, rows in catalogue:
        lines = ["| ID | Feature | Status | Evidence |", "|---|---|---|---|"]
        for r in rows:
            tid = r["id"]
            if tid in by_id:
                status, ev = combine(by_id[tid])
            elif only_re and not only_re.search(tid):
                status, ev = "NOT RUN", "excluded by --only"
            elif expected_in(r["tier"], args.mode):
                status = "UNCOVERED"
                tier = r["tier"]
                ev = "no test result"
                if services_reason and ("live" in tier or "e2e" in tier):
                    ev = f"no result: {services_reason}"
            else:
                status, ev = "NOT RUN", f"tier '{r['tier']}' not run in {args.mode} mode"
            counts[status] += 1
            if status == "FAIL":
                failures.append((tid, r["feature"], ev))
            lines.append(f"| {tid} | {r['feature']} | {status} | {ev.replace('|', '/')} |")
        sections_out.append(f"### {sname}\n\n" + "\n".join(lines))

    unknown = sorted(t for t in by_id if t not in known)

    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        except OSError:
            return ""

    sha = git("rev-parse", "--short", "HEAD") or "unknown"
    dirty = bool(git("status", "--porcelain"))
    meta = {}
    if (d / "meta.json").exists():
        try:
            meta = json.loads((d / "meta.json").read_text())
        except json.JSONDecodeError:
            pass
    totals = " · ".join(f"{s} {counts[s]}" for s in STATUSES)

    md = [
        "# Validation report",
        "",
        f"- Mode: {args.mode}" + (f" (only: `{args.only}`)" if args.only else ""),
        f"- Commit: {sha}{' (dirty)' if dirty else ''}",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
    ]
    if "duration_s" in meta:
        md.append(f"- Duration: {meta['duration_s']} s")
    if services_reason:
        md.append(f"- **Services: {services_reason}**")
    md += ["", f"**{totals}**", ""] + [s + "\n" for s in sections_out]
    md += ["### Unknown test IDs", ""]
    md += [f"- {u}" for u in unknown] or ["None."]
    md += ["", "### Failures", ""]
    md += [f"- **{t}** ({f}): {e}" for t, f, e in failures] or ["None."]
    if unattributed:
        md += ["", "### Unattributed junit failures (no catalogue ID in the test name)", ""]
        md += [f"- {u}" for u in unattributed]
    (d / "report.md").write_text("\n".join(md) + "\n")
    print(totals)
    return 1 if counts["FAIL"] or counts["UNCOVERED"] or unattributed else 0


if __name__ == "__main__":
    sys.exit(main())
