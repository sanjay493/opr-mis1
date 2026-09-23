"""PDF report layout guard - warns when anything that controls the PDF
layout changes, and verifies a real render against a known-good reference.

Why: the report's layout is tuned to the millimetre (whole-report shrink,
trend-page breaks, one page's CSS leaking into another all happened
before). What each file controls, the failure modes, and how to recover:
backend/docs/PDF_LAYOUT_GUARDRAILS.md.

Usage (from backend/, with the venv's python):
  python layout_guard.py                 check files vs baseline + CSS class clashes
  python layout_guard.py --strict        same, exit 1 if anything is flagged
  python layout_guard.py --staged        only files staged for commit (git pre-commit hook)
  python layout_guard.py --hook          Claude Code PostToolUse hook (reads JSON on stdin)
  python layout_guard.py --render 2026-08
                                         full render: runtime layout warnings + compare
                                         against the reference render (same month only)
  python layout_guard.py --accept [--render 2026-08]
                                         record the current files (and optionally a
                                         reference render) as the new known-good baseline

pdf.py also calls changed_file_warnings() at the start of every render, so
a changed layout file shows up as a "[pdf] LAYOUT WARNING" in the backend
console even if nobody ran this script.
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

BACKEND = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BACKEND)
BASELINE_PATH = os.path.join(BACKEND, "layout_baseline.json")
DOC = "backend/docs/PDF_LAYOUT_GUARDRAILS.md"

# Layout-critical files (relative to backend/) -> the doc section describing
# what they control. Every page template is included via the glob below.
LAYOUT_FILES = {
    "pdf.py": "Render pipeline (pdf.py)",
    "layout_config.json": "Per-page margins & fonts (layout_config.json)",
    "chart_utils.py": "Charts",
    "page_at_a_glance.py": "Charts",
    "page_special_steel_donut.py": "Charts",
    "page_coal_consumption.py": "Charts",
    "page_templates/main.html": "Global CSS (main.html)",
    "page_templates/trend_section.html": "Production trend pages",
    "page_templates/css/production_trend.css": "Production trend pages",
}
TEMPLATE_GLOB = "page_templates/*.html"


def _layout_files() -> dict:
    files = dict(LAYOUT_FILES)
    for path in sorted(glob.glob(os.path.join(BACKEND, TEMPLATE_GLOB))):
        rel = os.path.relpath(path, BACKEND).replace(os.sep, "/")
        files.setdefault(rel, "Page templates & per-page <style> blocks")
    return files


def _digest(rel: str):
    """sha256 of the file with line endings normalized, so a CRLF checkout
    on one PC and an LF one on another fingerprint the same."""
    path = os.path.join(BACKEND, rel)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = f.read().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _load_baseline() -> dict:
    try:
        with open(BASELINE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def changed_files() -> list:
    """[(rel_path, status, doc_section)] for every layout file that differs
    from the baseline: 'changed', 'deleted', or 'new' (a template added
    since the baseline was recorded)."""
    base = _load_baseline().get("files", {})
    out = []
    for rel, section in _layout_files().items():
        cur = _digest(rel)
        old = base.get(rel)
        if old is None and cur is not None:
            out.append((rel, "new", section))
        elif cur is None and old is not None:
            out.append((rel, "deleted", section))
        elif cur != old:
            out.append((rel, "changed", section))
    return out


def changed_file_warnings() -> list:
    """One message per changed layout file (used by pdf.py at render start)."""
    if not os.path.exists(BASELINE_PATH):
        return ["no layout baseline recorded (backend/layout_baseline.json missing)"]
    return [f"{rel} is {status} since the layout baseline - section '{section}'"
            for rel, status, section in changed_files()]


def css_class_clashes() -> list:
    """Classes styled in one page template's own <style> block but also used
    or styled by another template. Every page shares ONE document in the PDF
    render, so such a rule silently restyles the other page — but only in
    exports that include both pages (the Steel Sales .ssp-table leak)."""
    defs, uses = {}, {}
    for path in glob.glob(os.path.join(BACKEND, TEMPLATE_GLOB)) + \
            glob.glob(os.path.join(BACKEND, "page_templates/css/*.css")):
        name = os.path.relpath(path, BACKEND).replace(os.sep, "/")
        with open(path, encoding="utf-8") as f:
            src = re.sub(r"\{#.*?#\}", "", f.read(), flags=re.S)
        blocks = re.findall(r"<style[^>]*>(.*?)</style>", src, flags=re.S) if name.endswith(".html") else [src]
        for block in blocks:
            block = re.sub(r"/\*.*?\*/|\{\{.*?\}\}|\{%.*?%\}", "", block, flags=re.S)
            for selector in re.findall(r"([^{}]+)\{", block):
                for cls in re.findall(r"\.([a-zA-Z][\w-]*)", selector):
                    defs.setdefault(cls, set()).add(name)
        for attr in re.findall(r'class="([^"]*)"', src):
            for cls in re.sub(r"\{\{.*?\}\}|\{%.*?%\}", " ", attr).split():
                uses.setdefault(cls, set()).add(name)
    out = []
    for cls, where in sorted(defs.items()):
        own = {n for n in where if n != "page_templates/main.html" and not n.startswith("page_templates/css/")}
        if not own:
            continue
        others = (uses.get(cls, set()) | where) - own - {"page_templates/main.html"}
        styled_elsewhere = where - own
        if others or styled_elsewhere:
            out.append(f".{cls} is styled in {sorted(own)} but also used/styled in "
                       f"{sorted(others | styled_elsewhere)}")
    return out


def _latest_baseline_tag() -> str:
    """Newest pdf-layout-baseline-* git tag (the known-good layout)."""
    try:
        tags = subprocess.run(["git", "tag", "-l", "pdf-layout-baseline-*", "--sort=-creatordate"],
                              cwd=REPO, capture_output=True, text=True, timeout=10).stdout.split()
    except Exception:
        tags = []
    return tags[0] if tags else "<pdf-layout-baseline-YYYY-MM-DD tag>"


def _print_report(changed: list, clashes: list) -> None:
    if not changed and not clashes:
        print("layout_guard: OK - all layout files match the baseline, no CSS class clashes.")
        return
    print("=" * 78)
    print("  PDF LAYOUT WARNING - changes that can affect the PDF report layout")
    print("=" * 78)
    for rel, status, section in changed:
        print(f"  * backend/{rel}  [{status}]  -> {DOC} : '{section}'")
    for msg in clashes:
        print(f"  * CSS class clash: {msg}")
    print("-" * 78)
    print("  Before relying on this change: python layout_guard.py --render <month>")
    print(f"  To restore a file:  git checkout {_latest_baseline_tag()} -- backend/<file>")
    print("  After verifying an intended change:  python layout_guard.py --accept")
    print("=" * 78)


def _staged_layout_files() -> list:
    names = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=REPO,
                           capture_output=True, text=True).stdout.split()
    files = _layout_files()
    return [(n[len("backend/"):], "staged", files[n[len("backend/"):]])
            for n in names if n.startswith("backend/") and n[len("backend/"):] in files]


def _hook() -> int:
    """Claude Code PostToolUse hook: stdin carries the tool call as JSON.
    Emits additionalContext (never blocks) when a layout file was edited."""
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    norm = os.path.abspath(path).replace(os.sep, "/").lower()
    files = _layout_files()
    hit = next((rel for rel in files
                if norm == os.path.join(BACKEND, rel).replace(os.sep, "/").lower()), None)
    if not hit:
        return 0
    msg = (f"PDF LAYOUT WARNING: backend/{hit} controls the PDF report layout "
           f"(section '{files[hit]}' of {DOC}). Read that section before changing it further; "
           f"verify with `backend/venv/Scripts/python.exe backend/layout_guard.py --render <month>` "
           f"(no global shrink, trend splits >= 3 rows each side, page counts vs reference) and tell "
           f"the user this change can affect the PDF layout.")
    print(json.dumps({
        "systemMessage": f"PDF LAYOUT WARNING: backend/{hit} controls the PDF layout - see {DOC}",
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg},
    }))
    return 0


def _render(month: str) -> dict:
    """Full-report render in-process; returns the reference-render record
    and prints runtime layout warnings + differences from the stored one."""
    import asyncio
    import re as _re
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)
    import main
    import pdf
    from models import PDFRequest
    pages = main.get_data(month)
    req = PDFRequest(month=month, pages=pages, full_export=True)
    enriched, dyn = main._enrich_pdf_pages(req)
    data, _ = asyncio.run(pdf.generate_pdf_bytes(req, pages_override=enriched, page_layouts=dyn or None))
    texts = pdf._page_texts(data)
    start = {}
    for i, t in enumerate(texts):
        for m in _re.findall(r"@@PGSTART_([\d.]+)@@", t):
            start.setdefault(m, i)
    order = sorted(start.items(), key=lambda kv: kv[1])
    spans = {pg: (order[j + 1][1] if j + 1 < len(order) else len(texts)) - s for j, (pg, s) in enumerate(order)}
    footers = [int(m.group(1)) for t in texts if (m := _re.search(r"Page (\d+) of \d+", t))]
    record = {"month": month, "total_pages": len(texts), "section_pages": spans}
    problems = list(pdf._LAYOUT_WARNINGS)
    if footers != list(range(1, len(footers) + 1)):
        problems.append("footer page numbers are not sequential")
    ref = _load_baseline().get("reference_render")
    if ref and ref.get("month") == month:
        if ref["total_pages"] != record["total_pages"]:
            problems.append(f"total pages {record['total_pages']} vs reference {ref['total_pages']}")
        for pg in sorted(set(ref["section_pages"]) | set(spans), key=float):
            a, b = ref["section_pages"].get(pg), spans.get(pg)
            if a != b:
                problems.append(f"report page {pg}: {b} physical page(s) vs reference {a}")
    elif ref:
        print(f"layout_guard: reference render is for {ref.get('month')}; page counts not compared for {month}.")
    print("-" * 78)
    if problems:
        print(f"layout_guard --render {month}: {len(problems)} problem(s):")
        for p in problems:
            print(f"  * {p}")
    else:
        print(f"layout_guard --render {month}: OK - {record['total_pages']} pages, no layout warnings"
              + (", matches the reference render." if ref and ref.get("month") == month else "."))
    record["_problems"] = problems
    return record


def main_cli(argv: list) -> int:
    if "--hook" in argv:
        return _hook()
    render_month = argv[argv.index("--render") + 1] if "--render" in argv else None
    if "--accept" in argv:
        base = _load_baseline()
        base["files"] = {rel: _digest(rel) for rel in _layout_files() if _digest(rel)}
        if render_month:
            rec = _render(render_month)
            if rec.pop("_problems"):
                print("layout_guard: NOT accepted - fix the problems above first.")
                return 1
            base["reference_render"] = rec
        with open(BASELINE_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(base, f, indent=1, sort_keys=True)
            f.write("\n")
        print(f"layout_guard: baseline recorded for {len(base['files'])} files"
              + (f" + reference render of {render_month}" if render_month else "") + f" -> {BASELINE_PATH}")
        return 0
    if render_month:
        return 1 if _render(render_month)["_problems"] and "--strict" in argv else 0
    changed = _staged_layout_files() if "--staged" in argv else changed_files()
    clashes = css_class_clashes()
    _print_report(changed, clashes)
    return 1 if (changed or clashes) and "--strict" in argv else 0


if __name__ == "__main__":
    sys.exit(main_cli(sys.argv[1:]))
