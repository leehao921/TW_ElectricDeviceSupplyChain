"""IV 定時快照 (2026-10-12): 盤中每 30 分鐘推 IV 期限表 + 前月 ATM 變化到 #guyu。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import discord_forward  # noqa: E402
from iv_snapshot import snapshot_header  # noqa: E402


def test_header_shows_level_and_changes():
    h = snapshot_header("10/21", 20.3, iv_30m=20.5, iv_open=19.8)
    assert h == "前月 10/21 ATM 20.3% · 30分 -0.2 · 開盤來 +0.5"


def test_header_without_history():
    assert snapshot_header("10/21", 20.3, None, None) == "前月 10/21 ATM 20.3% · 30分 n/a · 開盤來 n/a"


def test_header_fits_mobile():
    assert discord_forward._disp_width(snapshot_header("10/21", 20.3, 20.5, 19.8)) <= 46


def test_snapshot_routes_to_trading_channel():
    assert discord_forward.route_topic({"topic": "iv-snapshot"}) == "trading"
