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
