"""Saved narrative for the Secretary Review deck, keyed by
(report_month, block_key) in `secretary_review_text`. Block keys are listed
in secretary_review_layout.BLOCKS. An empty text is stored as '' — it means
"leave this block empty", unlike a missing row, which falls back to the DB
default (page_secretary_review_texts.effective_texts).

The functions live in repo/text.py (moved verbatim) and are re-exported here."""

from repo.text import get_texts, save_texts, delete_texts, latest_saved_before  # noqa: F401
