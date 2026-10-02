"""Shared pytest configuration for backend tests.

Makes the backend package importable and adds the --update-goldens flag
used by the golden-file extraction tests to (re)generate expected output.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


_SAMPLE_ROOTS = [
    Path(p) for p in (
        __import__("os").environ.get("REPORT_FORMAT_DIR"),
        str(BACKEND_DIR.parent / "Report_format"),
        r"G:\My Drive\Report_format",   # the shared Report_format folder (Google Drive)
    ) if p
]


def find_sample(relative):
    """First existing copy of a sample file (path relative to Report_format/)
    across REPORT_FORMAT_DIR, the repo's Report_format/ and the shared
    Google Drive Report_format folder — or None."""
    for root in _SAMPLE_ROOTS:
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


def pytest_addoption(parser):
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Regenerate the golden JSON files from current extractor output "
             "instead of comparing against them.",
    )


@pytest.fixture
def update_goldens(request):
    return request.config.getoption("--update-goldens")
