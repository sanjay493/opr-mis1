"""Compare two parity snapshots (see parity_snapshot.py).

    python -m tools.parity_diff <snapshot-dir-a> <snapshot-dir-b>

Prints one line per difference and exits 1 if there are any. Numbers are
compared exactly (12.3 vs 12.30001 is a difference); 1 and 1.0 are the same
number. Only keys listed in VOLATILE_KEYS are ignored, wherever they occur.
"""

import json
import sys
from pathlib import Path

# Explicit allow-list of JSON keys whose value legitimately changes between two
# identical runs. Add a key only after seeing it change between two runs of the
# same data, and record why.
VOLATILE_KEYS = {
    "generated_at",   # wall-clock stamp some payloads carry
}

# Files that describe a snapshot rather than being part of it. _summary.json is
# derived from the other files (status counts), so any change in it already
# shows up in the files it was built from.
IGNORED_FILES = {"_summary.json"}

_MAX_DIFFS_PER_FILE = 50


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _short(v) -> str:
    s = json.dumps(v, sort_keys=True, ensure_ascii=False)
    return s if len(s) <= 120 else s[:117] + "..."


def _walk(a, b, path: str, out: list) -> None:
    if len(out) >= _MAX_DIFFS_PER_FILE:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k in VOLATILE_KEYS:
                continue
            sub = f"{path}.{k}" if path else str(k)
            if k not in b:
                out.append(f"{sub}: only in A ({_short(a[k])})")
            elif k not in a:
                out.append(f"{sub}: only in B ({_short(b[k])})")
            else:
                _walk(a[k], b[k], sub, out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path or '<root>'}: list length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _walk(x, y, f"{path}[{i}]", out)
    elif _num(a) and _num(b):
        if a != b:
            out.append(f"{path or '<root>'}: {a!r} vs {b!r}")
    elif type(a) is not type(b):
        out.append(f"{path or '<root>'}: {_short(a)} vs {_short(b)} (type {type(a).__name__} vs {type(b).__name__})")
    elif a != b:
        out.append(f"{path or '<root>'}: {_short(a)} vs {_short(b)}")


def _diff_json(pa: Path, pb: Path) -> list:
    try:
        a = json.loads(pa.read_text(encoding="utf-8"))
        b = json.loads(pb.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"unreadable JSON: {e}"]
    out: list = []
    _walk(a, b, "", out)
    return out


def _diff_text(pa: Path, pb: Path) -> list:
    la = pa.read_text(encoding="utf-8").splitlines()
    lb = pb.read_text(encoding="utf-8").splitlines()
    for i in range(max(len(la), len(lb))):
        x = la[i] if i < len(la) else "<missing>"
        y = lb[i] if i < len(lb) else "<missing>"
        if x != y:
            return [f"first difference at line {i + 1}: {x[:100]!r} vs {y[:100]!r}"
                    f" ({len(la)} vs {len(lb)} lines)"]
    return []


def _files(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file() and p.name not in IGNORED_FILES}


def diff(a: Path, b: Path) -> list:
    """Human-readable differences between two snapshot dirs; [] when equal."""
    a, b = Path(a), Path(b)
    fa, fb = _files(a), _files(b)
    out = []
    for rel in sorted(set(fa) | set(fb)):
        if rel not in fb:
            out.append(f"{rel}: file only in A")
        elif rel not in fa:
            out.append(f"{rel}: file only in B")
        else:
            fn = _diff_json if rel.endswith(".json") else _diff_text
            out.extend(f"{rel}: {d}" for d in fn(fa[rel], fb[rel]))
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m tools.parity_diff <snapshot-a> <snapshot-b>")
        return 2
    diffs = diff(Path(argv[0]), Path(argv[1]))
    for d in diffs:
        print(d)
    print(f"{len(diffs)} difference(s)")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
