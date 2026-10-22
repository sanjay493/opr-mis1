"""tools.repo_oracle: record repo reads, replay them against another
implementation. No database: a fake repo module pair in a temp package
stands in for repo.<domain> (v1) and repo.v2.<domain>."""
import ast
import datetime as dt
import importlib
import sys
import textwrap
from decimal import Decimal
from pathlib import Path

import pytest

import dbengine
import report_context
from repo import conn as rc
from tools import repo_oracle as ro

V1 = '''
import report_context

def values(plant, months):
    return [{"plant": plant, "month": m, "v": 5} for m in months]

def total(plant):
    return 5

def ordered():
    return [("a", 1), ("b", 2)]

def gone(x):
    return x * 2

def boom(x):
    raise ValueError(f"bad {x}")

def big(n):
    return [{"i": i, "pad": "x" * 20} for i in range(n)]

def with_cursor(cur, plant):
    return (plant, type(cur).__name__)

def ctx_month():
    ctx = report_context.current()
    return None if ctx is None else ("ctx", ctx.report_month, ctx.load("fake", _load))

def _load(first, last):
    return {(first, "A"): 1.5, (last, "B"): None}

def save(x):
    return "written"
'''

CALLER = '''
from fakerepo.v1 import total

def call_total(p):
    return total(p)
'''


def _mutate(src, old, new):
    assert old in src
    return src.replace(old, new)


VARIANTS = {
    "v2_clean": V1,
    "v2_value": _mutate(V1, '"v": 5}', '"v": 6}'),
    "v2_type": _mutate(V1, "def total(plant):\n    return 5", "def total(plant):\n    return 5.0"),
    "v2_order": _mutate(V1, 'return [("a", 1), ("b", 2)]', 'return [("b", 2), ("a", 1)]'),
    "v2_missing": _mutate(V1, "def gone(x):\n    return x * 2\n", ""),
    "v2_exc": _mutate(V1, 'raise ValueError(f"bad {x}")', 'raise KeyError(x)'),
    "v2_big": _mutate(V1, '"pad": "x" * 20}', '"pad": "x" * 20 if i != 7 else "y"}'),
    "v2_ctx": _mutate(V1, "(last, \"B\"): None}", "(last, \"B\"): 0}"),
}


@pytest.fixture
def fake(tmp_path, monkeypatch):
    pkg = tmp_path / "pkgroot" / "fakerepo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "v1.py").write_text(V1)
    (pkg / "caller.py").write_text(CALLER)
    for name, src in VARIANTS.items():
        (pkg / f"{name}.py").write_text(src)
    monkeypatch.syspath_prepend(str(tmp_path / "pkgroot"))
    for m in [k for k in sys.modules if k == "fakerepo" or k.startswith("fakerepo.")]:
        del sys.modules[m]
    importlib.invalidate_caches()
    v1 = importlib.import_module("fakerepo.v1")
    caller = importlib.import_module("fakerepo.caller")
    yield {"v1": v1, "caller": caller, "store": tmp_path / "store"}
    for m in [k for k in sys.modules if k == "fakerepo" or k.startswith("fakerepo.")]:
        del sys.modules[m]


def _recorder(fake, pass_name="sql"):
    return ro.Recorder(fake["store"], pass_name, {"fake": fake["v1"]},
                       write_functions={"fake": {"save"}}, run_info={"test": True})


def _replay(fake, variant, passes=("sql",), functions=None):
    impl = importlib.import_module(f"fakerepo.{variant}")
    out = []
    code = ro.replay_module(fake["store"], "fake", impl, passes=passes,
                            functions=functions, limit_diffs=20, out=out.append)
    return code, "\n".join(out)


def _record(fake):
    v1, caller = fake["v1"], fake["caller"]
    rec = _recorder(fake)
    with rec.installed():
        v1.values("BSP", ["2026-08", "2026-09"])
        v1.values("BSP", ["2026-08", "2026-09"])          # duplicate
        caller.call_total("BSP")                           # through a from-import alias
        v1.ordered()
        v1.gone(21)
        with pytest.raises(ValueError):
            v1.boom(3)
        assert v1.save(1) == "written"
    rec.commit()
    return rec


# ── canonical form ──────────────────────────────────────────────────────────

def test_canonical_scalars_are_type_tagged():
    assert ro.canonical(None) is None
    assert ro.canonical("x") == "x"
    assert ro.canonical(5) == 5
    assert ro.canonical(True) is True
    assert ro.canonical(5.0) == {"$float": "5.0"}
    assert ro.canonical(5) != ro.canonical(5.0)
    assert ro.canonical(Decimal("1.50")) == {"$Decimal": "1.50"}
    assert ro.canonical(dt.datetime(2026, 8, 1, 10, 5)) == {"$datetime": "2026-08-01T10:05:00"}
    assert ro.canonical(dt.date(2026, 8, 1)) == {"$date": "2026-08-01"}
    assert ro.canonical(b"\x01\xff") == {"$bytes": "01ff"}
    assert ro.canonical({3, 1, 2}) == {"$set": [1, 2, 3]}
    assert ro.canonical((1, "a")) == {"$tuple": [1, "a"]}
    assert ro.canonical([1, "a"]) == [1, "a"]


def test_canonical_row_and_dict_keep_order_and_types():
    row = dbengine.Row(["b", "a", "c"], (1, 2.5, None))
    assert ro.canonical(row) == {"$Row": [["b", "int", 1], ["a", "float", {"$float": "2.5"}],
                                          ["c", "NoneType", None]]}
    d = {"z": Decimal("3"), "a": None}
    assert ro.canonical(d) == {"$dict": [["z", "Decimal", {"$Decimal": "3"}], ["a", "NoneType", None]]}
    assert ro.canonical({"a": 1, "z": 2}) != ro.canonical({"z": 2, "a": 1})
    assert ro.canonical({("2026-08", "bsp"): 1}) == {"$dict": [[{"$tuple": ["2026-08", "bsp"]}, "int", 1]]}


def test_canonical_cursor_and_connection_placeholders():
    assert ro.canonical(rc.Cursor(None)) == {"$cursor": "repo"}


def test_args_round_trip_through_canonical():
    args = [1, 2.5, Decimal("1.5"), ("a", None), ["x"], {"k": (1, 2)}, {"s"}, b"\x00", None, True]
    back = ro.decanonical(ro.canonical(args), live=None)
    assert back == args
    assert [type(x) for x in back] == [type(x) for x in args]


# ── record ──────────────────────────────────────────────────────────────────

def test_record_dedupes_records_aliases_and_skips_writes(fake):
    rec = _record(fake)
    recs = list(ro.Store(fake["store"]).iter_records("fake", "sql"))
    fns = sorted(r["f"] for r in recs)
    assert fns == ["boom", "gone", "ordered", "total", "values"]       # values once, no save
    assert rec.calls[("fake", "values")] == 2
    assert rec.calls[("fake", "total")] == 1                            # via caller's alias
    assert rec.write_calls[("fake", "save")] == 1
    assert ("fake", "save") not in rec.calls
    # unpatched afterwards
    assert fake["caller"].total is ro.unwrap(fake["caller"].total)
    assert not hasattr(fake["v1"].values, "__oracle_original__")


def test_record_appends_across_runs_and_flags_nondeterminism(fake):
    _record(fake)
    v1 = fake["v1"]
    rec = _recorder(fake)
    orig = v1.total
    with rec.installed():
        v1.total("BSP")                  # same as run 1: no new unique record
    rec.commit()
    assert rec.unique_new == {}
    assert rec.conflicts == []
    # now make total() nondeterministic
    fake["v1"].total = lambda plant: 7
    fake["v1"].total.__module__ = v1.__name__
    fake["v1"].total.__name__ = "total"
    rec = _recorder(fake)
    with rec.installed():
        v1.total("BSP")
    rec.commit()
    v1.total = orig
    assert len(rec.conflicts) == 1 and rec.conflicts[0]["function"] == "total"
    idx = ro.Store(fake["store"]).load_index()
    assert idx["functions"]["fake.values"]["sql"]["calls"] == 2
    assert idx["functions"]["fake.total"]["sql"]["calls"] == 3
    assert idx["functions"]["fake.total"]["sql"]["unique"] == 1
    assert len(idx["conflicts"]) == 1


def test_order_only_nondeterminism_is_classified_and_replayed_as_a_multiset(fake):
    """A query without ORDER BY whose plan (and so row order) varies between
    runs: the conflict is kind 'order', and replay compares that function's
    rows as a multiset (every record of it), still catching value changes."""
    _record(fake)
    v1 = fake["v1"]
    orig = v1.ordered
    flipped = lambda: [("b", 2), ("a", 1)]      # noqa: E731
    flipped.__module__, flipped.__name__ = v1.__name__, "ordered"
    v1.ordered = flipped
    rec = _recorder(fake)
    with rec.installed():
        v1.ordered()
    rec.commit()
    v1.ordered = orig
    assert [c["kind"] for c in rec.conflicts] == ["order"]
    code, out = _replay(fake, "v2_order")
    assert code == 0, out
    assert "multiset" in out
    # a value change in the same function is still a diff
    v1src = importlib.import_module("fakerepo.v2_order")
    v1src.ordered = lambda: [("b", 2), ("a", 9)]
    out = []
    assert ro.replay_module(fake["store"], "fake", v1src, passes=("sql",), out=out.append) == 1


def test_value_nondeterminism_is_kind_value(fake):
    _record(fake)
    v1 = fake["v1"]
    orig = v1.total
    other = lambda plant: 6                     # noqa: E731
    other.__module__, other.__name__ = v1.__name__, "total"
    v1.total = other
    rec = _recorder(fake)
    with rec.installed():
        v1.total("BSP")
    rec.commit()
    v1.total = orig
    assert [c["kind"] for c in rec.conflicts] == ["value"]


# ── replay ──────────────────────────────────────────────────────────────────

def test_clean_replay_exits_0(fake):
    _record(fake)
    code, out = _replay(fake, "v2_clean")
    assert code == 0, out


def test_replay_detects_a_value_change(fake):
    _record(fake)
    code, out = _replay(fake, "v2_value")
    assert code == 1
    assert "values" in out and "[0]" in out and "'v'" in out


def test_replay_detects_a_type_change(fake):
    _record(fake)
    code, out = _replay(fake, "v2_type")
    assert code == 1
    assert "total" in out and "$float" in out


def test_replay_detects_a_row_order_change(fake):
    _record(fake)
    code, out = _replay(fake, "v2_order")
    assert code == 1
    assert "ordered" in out and "[0]" in out


def test_replay_detects_a_missing_function(fake):
    _record(fake)
    code, out = _replay(fake, "v2_missing")
    assert code == 1
    assert "MISSING" in out and "gone" in out


def test_replay_detects_a_changed_exception(fake):
    _record(fake)
    code, out = _replay(fake, "v2_exc")
    assert code == 1
    assert "boom" in out and "KeyError" in out


def test_replay_function_filter(fake):
    _record(fake)
    assert _replay(fake, "v2_value", functions={"total", "ordered"})[0] == 0
    assert _replay(fake, "v2_missing", functions={"total"})[0] == 0


def test_big_results_store_a_digest_and_still_compare(fake, monkeypatch):
    monkeypatch.setattr(ro, "BIG_LIMIT", 2000)
    rec = _recorder(fake)
    with rec.installed():
        fake["v1"].big(300)
        fake["v1"].big(2)
    rec.commit()
    recs = {r["a"][0]: r for r in ro.Store(fake["store"]).iter_records("fake", "sql")}
    assert "big" in recs[300] and "r" not in recs[300]
    assert recs[300]["big"]["rows"] == 300 and len(recs[300]["big"]["head"]) == 3
    assert "r" in recs[2]
    assert _replay(fake, "v2_clean")[0] == 0
    code, out = _replay(fake, "v2_big")
    assert code == 1 and "big" in out and "chunk" in out


def test_bulk_pass_records_context_calls_and_loaders_and_replays_them_in_context(fake):
    v1 = fake["v1"]
    rec = _recorder(fake, "bulk")
    with rec.installed():
        assert v1.ctx_month() is None                       # no context: not recorded
        with report_context.activate("2026-08"):
            got = v1.ctx_month()
        assert got[1] == "2026-08"
    rec.commit()
    recs = list(ro.Store(fake["store"]).iter_records("fake", "bulk"))
    assert sorted(r["f"] for r in recs) == ["_load", "ctx_month"]
    assert [r["ctx"] for r in recs if r["f"] == "ctx_month"] == ["2026-08"]
    assert _replay(fake, "v2_clean", passes=("bulk",))[0] == 0
    code, out = _replay(fake, "v2_ctx", passes=("bulk",))
    assert code == 1 and "_load" in out and "ctx_month" in out


# ── guards and classification ───────────────────────────────────────────────

@pytest.mark.parametrize("name", ["mis_reports", "MIS_REPORTS", "mis_reports_baseline", "Mis_Reports_Baseline"])
def test_refuses_live_and_baseline_databases(name):
    with pytest.raises(SystemExit):
        ro.check_db_name(name)


@pytest.mark.parametrize("name", ["mis_reports_rehearsal", "mis_reports_v2_rehearsal"])
def test_allows_rehearsal_databases(name):
    ro.check_db_name(name)


def test_domain_modules_are_every_repo_module_but_the_shared_ones():
    repo_dir = Path(ro.BACKEND_DIR) / "repo"
    found = {p.stem for p in repo_dir.glob("*.py")} - {"__init__"}
    assert set(ro.DOMAIN_MODULES) == found - set(ro.SHARED_MODULES)


def test_write_functions_match_the_bump_tests_write_detection():
    """WRITE_FUNCTIONS = the public functions holding write SQL (the AST scan
    of test_repo_writes_bump) plus those calling one in the same module."""
    from test_repo_writes_bump import _called_names, _write_functions
    direct = _write_functions()
    for module in ro.DOMAIN_MODULES:
        path = Path(ro.BACKEND_DIR) / "repo" / f"{module}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        writers = {n for n in funcs if (module, n) in direct}
        grew = True
        while grew:
            grew = False
            for n, f in funcs.items():
                if n not in writers and _called_names(f) & writers:
                    writers.add(n)
                    grew = True
        public = {n for n in writers if not n.startswith("_")}
        assert set(ro.WRITE_FUNCTIONS.get(module, ())) == public, module


def test_every_public_function_is_classified_once():
    for module in ro.DOMAIN_MODULES:
        mod = importlib.import_module(f"repo.{module}")
        public = set(ro.public_functions(mod))
        reads = set(ro.read_functions(mod, module))
        writes = set(ro.WRITE_FUNCTIONS.get(module, ()))
        skipped = {f for (m, f) in ro.NOT_RECORDED if m == module}
        assert reads | writes | skipped == public, module
        assert not (reads & writes) and not (reads & skipped) and not (writes & skipped), module
