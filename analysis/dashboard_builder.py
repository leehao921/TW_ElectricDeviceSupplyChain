"""Phase 6: Asia panel HTML dashboard with TXF-anchored views + news sidebar.

Builds four Plotly figures and renders them into a self-contained HTML page
via Jinja2:
  1. TAIEX candlestick (^TWII) + top news event vertical lines
  2. 60d rolling correlation strip heatmap (anchor = TWII, last 365d)
  3. Hierarchical-cluster-sorted static 3y correlation matrix
  4. TXF-TAIEX basis line (skipped with placeholder if no basis data)

Run: python3 analysis/dashboard_builder.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jinja2
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.cluster.hierarchy import linkage, leaves_list

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DASH_ROOT = REPO_ROOT / "analysis" / "dashboards"
TODAY = "2026-05-15"
OUT_DIR = DASH_ROOT / f"{TODAY}_asia_panel"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOCKER_CONTAINER = "trading-timescaledb"
PSQL_USER = "tmf"
PSQL_DB = "tmf_market_data"


def _psql_query_json(sql: str) -> list[dict]:
    """Run a SELECT via docker exec and parse the JSON output."""
    wrapped = f"SELECT json_agg(row_to_json(t)) FROM ({sql}) t;"
    p = subprocess.run(
        ["docker", "exec", DOCKER_CONTAINER,
         "psql", "-U", PSQL_USER, "-d", PSQL_DB, "-t", "-A", "-c", wrapped],
        capture_output=True, text=True, check=True,
    )
    raw = p.stdout.strip()
    if not raw or raw == "":
        return []
    return json.loads(raw) or []


def build_candlestick_with_news() -> str:
    taiex = pd.read_parquet(RAW_DIR / "taiex_3y.parquet").reset_index()
    # Pull top recent news (180d) for vertical lines + hover
    rows = _psql_query_json(
        "SELECT pub_ts::date AS d, title, themes "
        "FROM market_news "
        "WHERE pub_ts >= NOW() - INTERVAL '180 days' "
        "AND CARDINALITY(COALESCE(themes,ARRAY[]::text[])) > 0 "
        "ORDER BY pub_ts DESC LIMIT 30"
    )
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=taiex["ts"],
        open=taiex["open"], high=taiex["high"],
        low=taiex["low"], close=taiex["close"],
        name="^TWII",
    ))
    # Group news by date for annotations
    by_date: dict[str, list[str]] = {}
    for r in rows:
        by_date.setdefault(r["d"], []).append(r["title"])
    for d, titles in list(by_date.items())[:15]:
        fig.add_vline(
            x=pd.Timestamp(d).timestamp() * 1000,
            line_width=1, line_dash="dot", line_color="#888",
        )
        fig.add_annotation(
            x=pd.Timestamp(d), y=taiex["high"].max() * 0.99,
            text=f"\u25CF {len(titles)} news",
            hovertext="<br>".join(titles[:3]),
            showarrow=False, font=dict(size=9, color="#666"),
        )
    fig.update_layout(
        title="^TWII (TAIEX) — 3y daily · vertical marks = top news events",
        height=480, xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=False)


def build_rolling_corr_strip() -> str:
    rc = pd.read_parquet(DATA_DIR / "rolling_corr_twii.parquet")
    rc = rc[rc["window"] == 60]
    # last 365d
    end = rc["date"].max()
    start = end - pd.Timedelta(days=365)
    rc = rc[rc["date"] >= start]
    pivot = rc.pivot_table(index="symbol", columns="date", values="corr_vs_twii")
    # sort rows by mean abs corr (most influential first)
    order = pivot.abs().mean(axis=1).sort_values(ascending=False).index
    pivot = pivot.loc[order]

    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns, y=pivot.index,
        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
        colorbar=dict(title="60d corr vs TWII"),
    ))
    fig.update_layout(
        title="60d rolling correlation vs ^TWII (last 365d)",
        height=620, margin=dict(l=80, r=20, t=50, b=40),
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=False)


def build_cov_heatmap() -> str:
    corr = pd.read_parquet(DATA_DIR / "corr_3y.parquet")
    # hierarchical cluster ordering
    dist = 1.0 - corr.abs().clip(0, 1).values
    np.fill_diagonal(dist, 0.0)
    # condensed distance vector
    n = dist.shape[0]
    cond = []
    for i in range(n):
        for j in range(i + 1, n):
            cond.append(dist[i, j])
    Z = linkage(cond, method="average")
    order = leaves_list(Z)
    syms = [corr.index[i] for i in order]
    corr_sorted = corr.loc[syms, syms]

    fig = go.Figure(go.Heatmap(
        z=corr_sorted.values, x=corr_sorted.columns, y=corr_sorted.index,
        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
        colorbar=dict(title="3y corr"),
    ))
    fig.update_layout(
        title="Static 3y correlation matrix (hierarchical-cluster sorted)",
        height=720, margin=dict(l=80, r=20, t=50, b=80),
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=False)


def build_basis() -> str:
    basis_path = RAW_DIR / "txf_basis_180d.parquet"
    if not basis_path.exists():
        fig = go.Figure()
        fig.add_annotation(
            text=("TXF–TAIEX basis unavailable: TAIFEX scraper blocked "
                  "(html5lib missing / 403). Falling back to ^TWII as TXF tracker proxy."),
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=12, color="#888"),
        )
        fig.update_layout(
            title="TXF – ^TWII basis (last 180d)", height=260,
            xaxis=dict(visible=False), yaxis=dict(visible=False),
        )
        return fig.to_html(include_plotlyjs="cdn", full_html=False)

    basis = pd.read_parquet(basis_path).reset_index()
    fig = go.Figure(go.Scatter(x=basis["ts"], y=basis["basis"], mode="lines"))
    fig.update_layout(
        title="TXF – ^TWII basis (last 180d)", height=320,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=False)


def fetch_news_cards() -> tuple[list[dict], list[str]]:
    rows = _psql_query_json(
        "SELECT pub_ts, title, COALESCE(description,'') AS description, "
        "url, source, COALESCE(themes,ARRAY[]::text[]) AS themes "
        "FROM market_news "
        "WHERE pub_ts >= NOW() - INTERVAL '90 days' "
        "ORDER BY pub_ts DESC LIMIT 80"
    )
    cards = []
    theme_set: set[str] = set()
    for r in rows:
        themes = r.get("themes") or []
        theme_set.update(themes)
        cards.append({
            "date": str(r["pub_ts"])[:10],
            "title": r["title"][:160],
            "description": (r.get("description") or "")[:240],
            "url": r.get("url") or "#",
            "source": r.get("source", ""),
            "themes": themes,
            "themes_str": " ".join(f"#{t}" for t in themes) if themes else "",
        })
    return cards, sorted(theme_set)


TEMPLATE = """<!DOCTYPE html>
<html><head>
  <meta charset="utf-8">
  <title>Asia Market Panel — {{today}}</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body { font-family: -apple-system, sans-serif; max-width: 1600px; margin: auto; padding: 16px; }
    h1 { margin-bottom: 4px; }
    .meta { color: #5e6c84; margin-bottom: 16px; }
    .layout { display: grid; grid-template-columns: 1fr 340px; gap: 16px; }
    .charts > div { margin-bottom: 24px; border: 1px solid #e1e4e8; border-radius: 6px; padding: 4px; }
    .news-sidebar { max-height: 1800px; overflow-y: auto; }
    .news-card { padding: 12px; margin-bottom: 8px; border-left: 3px solid #2C7BE5; background: #f7fafc; }
    .news-card .theme-tag { font-size: 0.75em; color: #5e6c84; margin-top: 4px; }
    .news-card a { color: #1f4dba; text-decoration: none; }
    .news-card a:hover { text-decoration: underline; }
    .theme-chips { margin-bottom: 12px; }
    .theme-chips button { margin: 2px; padding: 4px 8px; border: 1px solid #ccc; background: #fff; cursor: pointer; border-radius: 12px; font-size: 0.8em; }
    .theme-chips button.active { background: #2C7BE5; color: white; }
    h3 { margin-top: 0; }
  </style>
</head>
<body>
  <h1>Asia Market Panel — TXF-Centric Covariance</h1>
  <div class="meta">Data window: 2023-05-15 → 2026-05-15 (3y daily) · Generated: {{today}} · 13 indices + 10 FX pairs · {{news_count}} news items (90d)</div>
  <div class="layout">
    <div class="charts">
      <div id="chart-txf">{{ chart_txf | safe }}</div>
      <div id="chart-rolling-corr">{{ chart_rolling | safe }}</div>
      <div id="chart-cov-heatmap">{{ chart_cov | safe }}</div>
      <div id="chart-basis">{{ chart_basis | safe }}</div>
    </div>
    <aside class="news-sidebar">
      <h3>Recent News (90d)</h3>
      <div class="theme-chips">
        <button data-theme="" class="active">all</button>
        {% for t in themes %}<button data-theme="{{t}}">{{t}}</button>{% endfor %}
      </div>
      <div id="news-list">
      {% for n in news_cards %}
      <div class="news-card" data-date="{{n.date}}" data-themes="{{ n.themes|join(',') }}">
        <a href="{{n.url}}" target="_blank"><strong>{{n.title}}</strong></a>
        {% if n.description %}<div>{{n.description}}</div>{% endif %}
        <div class="theme-tag">{{n.source}} · {{n.date}} · {{n.themes_str}}</div>
      </div>
      {% endfor %}
      </div>
    </aside>
  </div>
  <script>
    document.querySelectorAll('.theme-chips button').forEach(b => {
      b.addEventListener('click', () => {
        document.querySelectorAll('.theme-chips button').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        const want = b.dataset.theme;
        document.querySelectorAll('.news-card').forEach(card => {
          const themes = (card.dataset.themes || '').split(',');
          card.style.display = (!want || themes.includes(want)) ? '' : 'none';
        });
      });
    });
  </script>
</body></html>
"""


def main() -> None:
    print("[dash] building candlestick + news...")
    chart_txf = build_candlestick_with_news()
    print("[dash] building rolling corr strip...")
    chart_rolling = build_rolling_corr_strip()
    print("[dash] building cov heatmap...")
    chart_cov = build_cov_heatmap()
    print("[dash] building basis...")
    chart_basis = build_basis()
    print("[dash] fetching news cards...")
    news_cards, themes = fetch_news_cards()

    tmpl = jinja2.Template(TEMPLATE)
    html = tmpl.render(
        today=TODAY,
        chart_txf=chart_txf,
        chart_rolling=chart_rolling,
        chart_cov=chart_cov,
        chart_basis=chart_basis,
        news_cards=news_cards,
        themes=themes,
        news_count=len(news_cards),
    )
    out = OUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    size = out.stat().st_size
    print(f"[dash] wrote {out} ({size:,} bytes)")

    # symlink latest -> this dir
    latest = DASH_ROOT / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(OUT_DIR.name, target_is_directory=True)
    print(f"[dash] symlink {latest} -> {OUT_DIR.name}")


if __name__ == "__main__":
    main()
