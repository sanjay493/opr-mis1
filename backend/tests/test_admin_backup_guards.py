"""Admin backup/restore guards: v1 dumps are refused on a v2 database, and
dumps are named after the current database."""
import pytest
from fastapi import HTTPException

import api_admin_backup as ab


@pytest.fixture
def wired(mysql_db, monkeypatch, tmp_path):
    monkeypatch.setattr(ab, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(ab, "_require_mysql", lambda: None)
    monkeypatch.setattr(ab.auth, "log_activity", lambda *a, **k: None)
    return tmp_path


def test_v1_dump_is_refused_before_anything_else(wired, monkeypatch):
    # the marker sits across a 1 MB chunk edge, deep in a large file
    pad = b"x" * ((1 << 20) - 10)
    (wired / "old.sql").write_bytes(
        b"-- dump\n" + pad + b"\nDROP TABLE IF EXISTS `techno_data`;\nCREATE TABLE `techno_data` (\n id int\n);\n")
    called = []
    monkeypatch.setattr(ab, "_acquire_admin_lock", lambda: called.append("lock"))
    monkeypatch.setattr(ab, "_run_dump", lambda d: called.append("dump"))
    for confirm in (False, True):
        with pytest.raises(HTTPException) as e:
            ab.restore_backup("old.sql", confirm_data_loss=confirm, admin={"email": "a"})
        assert e.value.status_code == 409 and "old (v1) schema" in e.value.detail
    assert called == []


def test_scan_finds_marker_only_when_present(wired):
    (wired / "v2.sql").write_bytes(b"CREATE TABLE `techno_value` (id int);\n" * 50000)
    (wired / "v1.sql").write_bytes(b"-- x\nCREATE TABLE `techno_data` (id int);\n")
    assert ab._is_v1_dump(wired / "v2.sql") is False
    assert ab._is_v1_dump(wired / "v1.sql") is True


def test_v2_dump_is_not_refused(wired, monkeypatch):
    (wired / "ok.sql").write_text("CREATE TABLE `techno_value` (id int);\n")
    monkeypatch.setattr(ab, "_acquire_admin_lock", lambda: (_ for _ in ()).throw(RuntimeError("past the guard")))
    with pytest.raises(RuntimeError, match="past the guard"):
        ab.restore_backup("ok.sql", admin={"email": "a"})


def test_source_counts_include_inserts_with_a_column_list(tmp_path):
    # mysqldump names the columns for a table with generated columns
    # (report_text's plant_key / item_key); those rows must count too, or
    # every restore flags report_text as data loss
    (tmp_path / "d.sql").write_text(
        "INSERT INTO `plant` VALUES ('BSP','Bhilai'),('DSP','Durgapur');\n"
        "INSERT INTO `report_text` (`id`, `scope`, `text`) VALUES (1,'a','x'),(2,'b','y'),(3,'c','z');\n",
        encoding="utf-8")
    assert ab._source_table_counts(tmp_path / "d.sql") == {"plant": 2, "report_text": 3}


def test_backups_are_named_after_the_database(wired, monkeypatch, mysql_db):
    dumps = []
    monkeypatch.setattr(ab, "_acquire_admin_lock", lambda: object())
    monkeypatch.setattr(ab, "_release_admin_lock", lambda c: None)
    monkeypatch.setattr(ab, "_run_dump", lambda dest: dumps.append(dest.name))
    out = ab.create_backup(admin={"email": "a"})
    assert out["filename"].startswith(f"{mysql_db}_admin_") and out["filename"].endswith(".sql")

    (wired / "ok.sql").write_text("CREATE TABLE `techno_value` (id int);\n")
    monkeypatch.setattr(ab, "_tables_at_risk", lambda s: [])
    monkeypatch.setattr(ab, "_mysql_bin_dir", lambda: wired)
    # stop after the pre-restore snapshot
    monkeypatch.setattr(ab, "_client_ini", lambda: (_ for _ in ()).throw(RuntimeError("stop")))
    with pytest.raises(RuntimeError, match="stop"):
        ab.restore_backup("ok.sql", admin={"email": "a"})
    assert dumps[1].startswith(f"{mysql_db}_prerestore_")
