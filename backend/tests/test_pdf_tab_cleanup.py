"""A failed PDF job must not leave tabs open in the persistent Chromium
(pdf._get_persistent_browser) — the browser outlives every job, so a tab a
failed job never closed stays open (and keeps its half-loaded document)
until the backend restarts. Regression for a Page.set_content timeout
(2026-10-04) that left its probe tab open: _render_pdf only closed its tab
after a successful print.

Needs Playwright's Chromium (skipped if it can't launch).
"""

import pytest

import pdf


def _browser():
    try:
        return pdf._get_persistent_browser()
    except Exception as e:  # no Chromium on this machine
        pytest.skip(f"Chromium unavailable: {e}")


def test_failed_job_closes_its_tabs():
    browser = _browser()
    before = len(browser.contexts)

    def job():
        page = browser.new_page()
        page.set_content("<p>half-done</p>")
        browser.new_page()            # a second tab, also never closed
        raise TimeoutError("simulated set_content timeout")

    with pytest.raises(TimeoutError):
        pdf._run_closing_tabs_on_error(job)
    assert len(browser.contexts) == before


def test_successful_job_result_passes_through():
    _browser()
    assert pdf._run_closing_tabs_on_error(lambda a, b: a + b, 2, 3) == 5


def test_set_content_timeout_is_generous():
    # Playwright's 30s default turned a slow-but-healthy load into a failed
    # report; the largest report HTML takes ~11s even on an idle machine.
    assert pdf._SET_CONTENT_TIMEOUT_MS >= 120_000
