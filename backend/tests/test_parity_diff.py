"""Tests for tools/parity_diff.py - the comparison half of the parity harness."""

import json
from pathlib import Path

from tools import parity_diff
from tools.parity_diff import diff, main


def _write(root: Path, rel: str, obj) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")


def test_diff_equal_snapshots_is_empty(tmp_path):
    for d in ("a", "b"):
        _write(tmp_path / d, "2026-08/api_data.json", {"x": [1, 2.5, {"y": "z"}]})
        (tmp_path / d / "2026-08" / "report.pdf.txt").write_text("page 1\n", encoding="utf-8")
    assert diff(tmp_path / "a", tmp_path / "b") == []


def test_diff_detects_number_change(tmp_path):
    _write(tmp_path / "a", "2026-08/api_data.json", {"pages": [{"rows": [{"v": 12.3}]}]})
    _write(tmp_path / "b", "2026-08/api_data.json", {"pages": [{"rows": [{"v": 12.30001}]}]})
    out = diff(tmp_path / "a", tmp_path / "b")
    assert len(out) == 1
    assert "2026-08/api_data.json" in out[0]
    assert "pages[0].rows[0].v" in out[0]
    assert "12.3" in out[0] and "12.30001" in out[0]


def test_diff_ignores_volatile_fields(tmp_path):
    assert "generated_at" in parity_diff.VOLATILE_KEYS
    _write(tmp_path / "a", "2026-08/api_data.json",
           {"generated_at": "2026-10-19T10:00:00", "n": 1, "rows": [{"generated_at": "t1", "v": 2}]})
    _write(tmp_path / "b", "2026-08/api_data.json",
           {"generated_at": "2026-10-19T11:30:00", "n": 1, "rows": [{"generated_at": "t2", "v": 2}]})
    assert diff(tmp_path / "a", tmp_path / "b") == []


def test_diff_reports_missing_and_extra_keys_and_files(tmp_path):
    _write(tmp_path / "a", "m/one.json", {"k": 1, "gone": 2})
    _write(tmp_path / "b", "m/one.json", {"k": 1, "new": 3})
    _write(tmp_path / "a", "m/only_a.json", {})
    _write(tmp_path / "b", "m/only_b.json", {})
    out = "\n".join(diff(tmp_path / "a", tmp_path / "b"))
    assert "gone" in out and "new" in out
    assert "only_a.json" in out and "only_b.json" in out


def test_diff_reports_list_length_and_type_change(tmp_path):
    _write(tmp_path / "a", "x.json", {"l": [1, 2], "s": 5})
    _write(tmp_path / "b", "x.json", {"l": [1, 2, 3], "s": "5"})
    out = "\n".join(diff(tmp_path / "a", tmp_path / "b"))
    assert "length" in out
    assert "s:" in out


def test_diff_text_files_report_first_differing_line(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "report.pdf.txt").write_text("a\nb\nc\n", encoding="utf-8")
    (tmp_path / "b" / "report.pdf.txt").write_text("a\nB\nc\n", encoding="utf-8")
    out = diff(tmp_path / "a", tmp_path / "b")
    assert len(out) == 1 and "line 2" in out[0]


def test_cli_exit_code(tmp_path, capsys):
    _write(tmp_path / "a", "x.json", {"v": 1})
    _write(tmp_path / "b", "x.json", {"v": 1})
    assert main([str(tmp_path / "a"), str(tmp_path / "b")]) == 0
    _write(tmp_path / "b", "x.json", {"v": 2})
    assert main([str(tmp_path / "a"), str(tmp_path / "b")]) == 1
    assert "x.json" in capsys.readouterr().out


def test_diff_ignores_summary_file(tmp_path):
    _write(tmp_path / "a", "x.json", {"v": 1})
    _write(tmp_path / "b", "x.json", {"v": 1})
    _write(tmp_path / "a", "_summary.json", {"status_counts": {"200": 1}})
    _write(tmp_path / "b", "_summary.json", {"status_counts": {"200": 2}})
    assert diff(tmp_path / "a", tmp_path / "b") == []
