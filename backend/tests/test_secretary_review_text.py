import pytest

import secretary_review_text as srt


@pytest.fixture
def store(mysql_db):
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


def test_delete_texts_unlinks_only_given_blocks(store):
    store.save_texts("2026-09", {"hl_BSL": "a", "hl_BSP": "b"})
    store.save_texts("2026-08", {"hl_BSL": "aug"})
    assert store.delete_texts("2026-09", ["hl_BSL", "hl_SAIL"]) == 1
    assert store.get_texts("2026-09") == {"hl_BSP": "b"}
    assert store.get_texts("2026-08") == {"hl_BSL": "aug"}
    assert store.delete_texts("2026-09", []) == 0
