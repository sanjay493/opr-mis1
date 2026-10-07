import sqlite3

import pytest

import secretary_review_text as srt


@pytest.fixture
def store(tmp_path, monkeypatch):
    dbfile = tmp_path / "sr.db"
    conn = sqlite3.connect(dbfile)
    conn.execute("""
        CREATE TABLE secretary_review_text (
            report_month TEXT, block_key TEXT, text TEXT, updated_at TEXT,
            PRIMARY KEY (report_month, block_key)
        )
    """)
    conn.commit()
    conn.close()

    class _Conn:
        def __init__(self):
            self._c = sqlite3.connect(dbfile)

        def cursor(self):
            return self._c.cursor()

        def commit(self):
            self._c.commit()

        def close(self):
            self._c.close()

    monkeypatch.setattr(srt.db, "connect", _Conn)
    return srt


def test_empty_month(store):
    assert store.get_texts("2026-09") == {}


def test_round_trip_and_update(store):
    store.save_texts("2026-09", {"hl_SAIL": "a\nb", "delay_fs": "x"})
    store.save_texts("2026-09", {"hl_SAIL": "c"})
    assert store.get_texts("2026-09") == {"hl_SAIL": "c", "delay_fs": "x"}


def test_empty_text_is_kept_as_intentional_blank(store):
    store.save_texts("2026-09", {"hl_DSP": "   "})
    assert store.get_texts("2026-09") == {"hl_DSP": ""}


def test_latest_saved_before(store):
    store.save_texts("2026-08", {"cr_BSP_prev": "aug"})
    store.save_texts("2026-09", {"cr_BSP_prev": "sep"})
    store.save_texts("2026-03", {"cr_BSP_prev": "last fy"})
    window = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    assert store.latest_saved_before("cr_BSP_prev", "2026-10", window) == "sep"
    assert store.latest_saved_before("cr_BSP_prev", "2026-09", window) == "aug"
    assert store.latest_saved_before("cr_BSP_prev", "2026-04", window) is None
