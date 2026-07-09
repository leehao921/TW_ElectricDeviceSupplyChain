from __future__ import annotations
import sys, json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import disposition_daily_fetch as dt  # noqa: E402


def test_count_to_n():
    assert dt.count_to_n("第一次處置") == 1
    assert dt.count_to_n("第二次處置") == 2
    assert dt.count_to_n("第三次處置") == 3
    assert dt.count_to_n("連續三次") == 1     # condition text, not a count → default 1
    assert dt.count_to_n(None) == 1
