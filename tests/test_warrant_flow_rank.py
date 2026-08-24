"""warrant_flow_rank 純函式測試 — 排行/追蹤 (2026-08-24 warrant 系統 v1)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import warrant_flow_rank as wr  # noqa: E402


def _row(u, score):
    return {"underlying": u, "score": score, "call_value": abs(score) * 2,
            "put_value": abs(score), "n_call": 5, "n_put": 3}


def test_rank_top_sides():
    rows = [_row("2330", -500), _row("2454", -300), _row("3037", 400),
            _row("2324", -800), _row("3017", 100)]
    shorts = wr.rank_top(rows, n=2, side="short")
    longs = wr.rank_top(rows, n=2, side="long")
    assert [r["underlying"] for r in shorts] == ["2324", "2330"]  # 最負優先
    assert [r["underlying"] for r in longs] == ["3037", "3017"]   # 最正優先
    assert all(r["score"] < 0 for r in shorts) and all(r["score"] > 0 for r in longs)


def test_update_tracking_enter_and_fill():
    state = {"tracked": {}}
    wr.update_tracking(state, shorts=[_row("2324", -800)], longs=[],
                       as_of="2026-08-24", close_fn=lambda t, d: 41.6,
                       nth_close_fn=lambda t, d, n: None)
    e = state["tracked"]["2324"]
    assert e["side"] == "short" and e["enter_close"] == 41.6
    # 隔日: 已追蹤者不重複 enter, nth_close 可用時填 t1
    wr.update_tracking(state, shorts=[], longs=[], as_of="2026-08-25",
                       close_fn=lambda t, d: 40.0,
                       nth_close_fn=lambda t, d, n: 40.0 if n == 1 else None)
    assert state["tracked"]["2324"]["post"]["t1"] == round((40.0 / 41.6 - 1) * 100, 2)
    assert state["tracked"]["2324"]["enter_close"] == 41.6  # 不被覆寫


def test_update_tracking_graduate_t20(tmp_path):
    state = {"tracked": {"2330": {"side": "short", "enter_date": "2026-07-01",
                                  "enter_close": 100.0, "score_at_enter": -500,
                                  "post": {"t1": 1.0, "t5": 2.0, "t20": None}}}}
    graduated = wr.update_tracking(state, shorts=[], longs=[], as_of="2026-08-24",
                                   close_fn=lambda t, d: 110.0,
                                   nth_close_fn=lambda t, d, n: 110.0)
    assert "2330" not in state["tracked"]          # t20 填滿即畢業
    assert graduated and graduated[0]["post"]["t20"] == 10.0


def test_render_no_literal_newline():
    msg = wr.render_summary("2026-08-24", [_row("2324", -800)], [_row("3037", 400)],
                            hits={"short": (3, 5), "long": (2, 4)})
    assert "2324" in msg and "3037" in msg
    assert "\\n" not in msg
