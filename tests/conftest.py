import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vcomm.facts import build_all  # noqa: E402


@pytest.fixture(scope="session")
def sheets():
    return {s.id: s for s in build_all()}
