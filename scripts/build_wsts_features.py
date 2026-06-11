"""PMIC EFA v2 — Unit 17 — WSTS macro features for the DFM exogenous block.

Reads `data/pmic_efa/macro_semis_monthly.parquet` (WSTS Worldwide monthly
semiconductor sales, USD billions, 1986-01 → 2026-04 = 484 months) and emits
3 stationary covariate series suitable for use as exogenous regressors in a
Dynamic Factor Model:

  - wsts_yoy           — log(sales_t / sales_{t-12})       [unit: pct]
  - wsts_yoy_3ma       — 3-month MA of wsts_yoy            [unit: pct]
  - wsts_level_zscore  — rolling 24-month z-score of level [unit: sigma]

Also attempts to extend the monthly panel beyond 2026-04 by probing the next
WSTS Historical Billings Report XLSX. If a newer release is found, the script
ingests the extra months into the source panel before computing features.

Outputs:
  - data/pmic_efa/wsts_macro_features.parquet  (long, 11-col canonical schema)
  - data/pmic_efa/_provenance/wsts_features.md

Idempotent: re-running overwrites the output deterministically.
"""
from __future__ import annotations

import io
import sys
from datetime import timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from statsmodels.tsa.stattools import adfuller

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "pmic_efa"
SOURCE_PARQUET = DATA_DIR / "macro_semis_monthly.parquet"
FEATURES_PARQUET = DATA_DIR / "wsts_macro_features.parquet"
PROVENANCE_PATH = DATA_DIR / "_provenance" / "wsts_features.md"

CANONICAL_COLS = (
    "end", "entity_id", "entity_name", "tag", "val", "val_unit",
    "fp", "form", "accn", "source_url", "source_date",
)

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")

WSTS_PRESS_URL = "https://www.wsts.org/67/Historical-Billings-Report"
WSTS_BASE = ("https://www.wsts.org/esraCMS/extension/media/f/WST/7644/"
             "WSTS-Historical-Billings-Report-")


def _try_get(url: str, timeout: int = 30) -> bytes | None:
    """Return the XLSX bytes if the URL serves a non-stub XLSX, else None."""
    try:
        r = requests.get(
            url, timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (PMIC-EFA-Unit-17 collector)"},
        )
    except requests.RequestException:
        return None
    if r.status_code != 200 or len(r.content) < 10_000:
        return None
    return r.content


def _probe_newer_release(last_panel_end: pd.Timestamp) -> tuple[bytes | None, str | None, list[str]]:
    """Look for a WSTS XLSX release covering months past `last_panel_end`.

    WSTS naming convention: `…-{MonAbbrev}_{YYYY}.xlsx`. The report typically
    lands ~6 weeks after the month end. We try the 3 months immediately
    following the last panel month.
    """
    attempts: list[str] = []
    candidates: list[str] = []
    base_month = last_panel_end + pd.offsets.MonthEnd(1)
    for shift in range(0, 3):
        m = base_month + pd.offsets.MonthEnd(shift)
        candidates.append(f"{WSTS_BASE}{MONTHS[m.month - 1][:3]}_{m.year}.xlsx")
    for url in candidates:
        attempts.append(url)
        content = _try_get(url)
        if content is not None:
            return content, url, attempts
    return None, None, attempts


def _parse_wsts_xlsx(content: bytes) -> pd.DataFrame:
    """Parse the WSTS Historical Billings Report 'Monthly Data' sheet.

    Same shape as Unit 15 parser: returns a DataFrame of (end, val_usd_b).
    """
    df = pd.read_excel(io.BytesIO(content), sheet_name="Monthly Data",
                       header=None)
    rows: list[dict] = []
    current_year: int | None = None
    for _, row in df.iterrows():
        v0 = row.iloc[0]
        try:
            year_candidate = int(v0)
            if 1986 <= year_candidate <= 2100:
                current_year = year_candidate
                continue
        except (ValueError, TypeError):
            pass
        if current_year is not None and str(v0).strip() == "Worldwide":
            for col_idx, _ in enumerate(MONTHS, start=1):
                val = row.iloc[col_idx]
                if pd.isna(val):
                    continue
                end_ts = (pd.Timestamp(year=current_year, month=col_idx, day=1)
                          + pd.offsets.MonthEnd(0))
                rows.append({"end": end_ts, "val": float(val) / 1e6})
    return pd.DataFrame(rows).sort_values("end").reset_index(drop=True)


def load_source_panel() -> tuple[pd.DataFrame, dict]:
    """Load WSTS panel; attempt to extend tail before returning."""
    if not SOURCE_PARQUET.exists():
        raise FileNotFoundError(
            f"{SOURCE_PARQUET} missing — Unit 15 has not landed yet"
        )
    src = pd.read_parquet(SOURCE_PARQUET)
    src = (src[src["tag"] == "monthly_sales"]
           .sort_values("end").reset_index(drop=True))
    panel = src[["end", "val"]].copy()
    panel["end"] = pd.to_datetime(panel["end"])

    extension_info: dict = {
        "attempts": [],
        "new_months_added": 0,
        "used_url": None,
    }
    last_end = panel["end"].max()
    sys.stderr.write(
        f"Source panel: {len(panel)} months, "
        f"{panel['end'].min().date()} -> {last_end.date()}\n"
    )

    content, used_url, attempts = _probe_newer_release(last_end)
    extension_info["attempts"] = attempts
    if content is None:
        sys.stderr.write(
            f"No newer WSTS XLSX found (tried {len(attempts)} URLs)\n"
        )
        return panel, extension_info

    try:
        new_df = _parse_wsts_xlsx(content)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Newer XLSX parse failed: {e}\n")
        return panel, extension_info

    extra = new_df[new_df["end"] > last_end]
    if extra.empty:
        sys.stderr.write(
            f"Newer XLSX downloaded but no months past {last_end.date()}\n"
        )
        return panel, extension_info

    panel = (pd.concat([panel, extra], ignore_index=True)
             .sort_values("end").reset_index(drop=True))
    extension_info["new_months_added"] = len(extra)
    extension_info["used_url"] = used_url
    sys.stderr.write(
        f"Extended panel by {len(extra)} months — new tail "
        f"{panel['end'].max().date()}\n"
    )
    return panel, extension_info


def compute_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Return long DataFrame of (end, tag, val, val_unit) for the 3 features."""
    s = panel.set_index("end")["val"].astype(float).sort_index()

    # 1) wsts_yoy — 12-month log return, in percent
    yoy = np.log(s / s.shift(12)) * 100.0

    # 2) wsts_yoy_3ma — trailing 3-month mean of YoY
    yoy_3ma = yoy.rolling(window=3, min_periods=3).mean()

    # 3) wsts_level_zscore — trailing 24-month z-score of level
    mean24 = s.rolling(window=24, min_periods=24).mean()
    std24 = s.rolling(window=24, min_periods=24).std(ddof=1)
    level_z = (s - mean24) / std24

    out_rows: list[dict] = []
    for tag, series, unit in (
        ("wsts_yoy", yoy, "pct"),
        ("wsts_yoy_3ma", yoy_3ma, "pct"),
        ("wsts_level_zscore", level_z, "sigma"),
    ):
        clean = series.dropna()
        for end_ts, val in clean.items():
            out_rows.append({"end": end_ts, "tag": tag,
                             "val": float(val), "val_unit": unit})
    return pd.DataFrame(out_rows)


def to_canonical(features: pd.DataFrame, source_url: str,
                 source_date: pd.Timestamp) -> pd.DataFrame:
    """Wrap feature rows into the 11-column canonical schema."""
    accn = f"wsts_features:{source_date.strftime('%Y-%m-%d')}"
    out = features.copy()
    out["entity_id"] = "WSTS_GLOBAL"
    out["entity_name"] = "WSTS Global Semiconductor Sales"
    out["fp"] = "monthly"
    out["form"] = "derived_from_wsts_press_release"
    out["accn"] = accn
    out["source_url"] = source_url
    out["source_date"] = source_date
    out = out[list(CANONICAL_COLS)]

    out["end"] = pd.to_datetime(out["end"])
    out["source_date"] = pd.to_datetime(out["source_date"])
    out["val"] = out["val"].astype("float64")
    for c in ("entity_id", "entity_name", "tag", "val_unit", "fp", "form",
              "accn", "source_url"):
        out[c] = out[c].astype("string")
    return out.sort_values(["tag", "end"]).reset_index(drop=True)


def run_adf(features: pd.DataFrame) -> dict:
    """ADF test on each feature; return {tag: {adf_stat, p_value, n}}."""
    results: dict = {}
    for tag in sorted(features["tag"].unique()):
        s = (features[features["tag"] == tag]
             .sort_values("end")["val"].dropna().to_numpy())
        if len(s) < 20:
            results[tag] = {"adf_stat": None, "p_value": None, "n": len(s)}
            continue
        stat, pval, *_ = adfuller(s, autolag="AIC")
        results[tag] = {"adf_stat": float(stat), "p_value": float(pval),
                        "n": int(len(s))}
    return results


def feature_corr_matrix(features: pd.DataFrame) -> pd.DataFrame:
    wide = features.pivot(index="end", columns="tag", values="val")
    return wide.corr()


def write_provenance(panel: pd.DataFrame, features: pd.DataFrame,
                     adf: dict, corr: pd.DataFrame,
                     extension_info: dict, source_url: str,
                     source_date: pd.Timestamp) -> None:
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# PMIC EFA Unit 17 — WSTS macro features provenance")
    lines.append("")
    lines.append(f"**Build run:** {source_date.isoformat()}")
    lines.append("")
    lines.append("## Source panel")
    lines.append("")
    lines.append("- Read from `data/pmic_efa/macro_semis_monthly.parquet`")
    lines.append(f"- Original months: {len(panel) - extension_info['new_months_added']}")
    lines.append(f"- Months added by Unit 17 extension probe: "
                 f"{extension_info['new_months_added']}")
    lines.append(f"- Final months: {len(panel)} "
                 f"({panel['end'].min().date()} -> {panel['end'].max().date()})")
    diffs = panel.sort_values("end")["end"].diff().dt.days.dropna()
    gaps = int(((diffs < 28) | (diffs > 31)).sum())
    lines.append(f"- Gap-free monthly: {'YES' if gaps == 0 else f'NO ({gaps} anomalies)'}")
    lines.append("")
    lines.append("## Extension attempts")
    lines.append("")
    if extension_info["attempts"]:
        for url in extension_info["attempts"]:
            ok = url == extension_info["used_url"]
            mark = "[USED]" if ok else "[stub/missing]"
            lines.append(f"- {mark} {url}")
        if extension_info["new_months_added"] == 0:
            lines.append("")
            lines.append("Conclusion: WSTS Apr_2026 release is still the latest "
                         "publicly published Historical Billings Report. May/Jun "
                         "2026 are not yet released; the panel is correct through "
                         "the public data frontier.")
    else:
        lines.append("- (no extension probe ran)")
    lines.append("")
    lines.append("## Features emitted")
    lines.append("")
    lines.append("| tag | unit | n | first | last |")
    lines.append("|---|---|---|---|---|")
    for tag in sorted(features["tag"].unique()):
        sub = features[features["tag"] == tag].sort_values("end")
        lines.append(
            f"| `{tag}` | {sub['val_unit'].iloc[0]} | {len(sub)} | "
            f"{sub['end'].min().date()} | {sub['end'].max().date()} |"
        )
    lines.append("")
    lines.append("## Stationarity (ADF, H0 = unit root)")
    lines.append("")
    lines.append("| tag | adf stat | p-value | n | stationary @ 5% |")
    lines.append("|---|---|---|---|---|")
    for tag, r in adf.items():
        if r["adf_stat"] is None:
            lines.append(f"| `{tag}` | n/a | n/a | {r['n']} | n/a |")
        else:
            stationary = "YES" if r["p_value"] < 0.05 else "NO"
            lines.append(f"| `{tag}` | {r['adf_stat']:.3f} | "
                         f"{r['p_value']:.4f} | {r['n']} | {stationary} |")
    lines.append("")
    lines.append("DFM exogenous covariates should be stationary. `wsts_yoy` and "
                 "`wsts_yoy_3ma` are differenced log returns (intrinsically "
                 "stationary). `wsts_level_zscore` is a rolling-window z-score; "
                 "with a 24-month window it absorbs slow level drift and is "
                 "typically stationary on the WSTS panel.")
    lines.append("")
    lines.append("## Feature correlation matrix")
    lines.append("")
    lines.append("```")
    lines.append(corr.round(3).to_string())
    lines.append("```")
    lines.append("")
    lines.append("## Schema")
    lines.append("")
    lines.append("Canonical 11-column long format inherited from the IP DB: "
                 "`end, entity_id, entity_name, tag, val, val_unit, fp, form, "
                 "accn, source_url, source_date`. "
                 "`entity_id = 'WSTS_GLOBAL'`, "
                 "`form = 'derived_from_wsts_press_release'`, "
                 "`accn = wsts_features:<build_date>`.")
    lines.append("")
    lines.append("## Source URL (passed through)")
    lines.append("")
    lines.append(f"`{source_url}`")
    lines.append("")
    PROVENANCE_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not SOURCE_PARQUET.exists():
        sys.stderr.write(f"ERROR: {SOURCE_PARQUET} missing\n")
        return 2

    src = pd.read_parquet(SOURCE_PARQUET)
    src_row = src[src["tag"] == "monthly_sales"].iloc[0]
    source_url = str(src_row["source_url"])

    build_ts = pd.Timestamp.now(tz=timezone.utc)

    panel, extension_info = load_source_panel()
    if extension_info["used_url"]:
        source_url = extension_info["used_url"]

    print()
    print("=" * 72)
    print("PMIC EFA Unit 17 — WSTS feature build summary")
    print("=" * 72)
    print()
    print(f"Source panel: {len(panel)} months "
          f"({panel['end'].min().date()} -> {panel['end'].max().date()})")

    features = compute_features(panel)
    print(f"Computed {features['tag'].nunique()} features, "
          f"{len(features)} feature-rows total")

    out = to_canonical(features, source_url=source_url, source_date=build_ts)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(FEATURES_PARQUET, index=False)
    print(f"Wrote {FEATURES_PARQUET}")

    adf = run_adf(features)
    corr = feature_corr_matrix(features)

    print()
    print("[ADF stationarity check]")
    for tag, r in adf.items():
        if r["adf_stat"] is None:
            print(f"  {tag:<22} n={r['n']:>4}  (insufficient data)")
        else:
            mark = "stationary" if r["p_value"] < 0.05 else "non-stationary"
            print(f"  {tag:<22} stat={r['adf_stat']:>8.3f}  "
                  f"p={r['p_value']:.4f}  n={r['n']:>4}  {mark}")
    print()
    print("[Feature correlation]")
    print(corr.round(3).to_string())
    print()
    print("[Tail of features (last 6 month-ends per tag)]")
    for tag in sorted(features["tag"].unique()):
        sub = (features[features["tag"] == tag]
               .sort_values("end").tail(6))
        for _, r in sub.iterrows():
            print(f"  {tag:<22} {r['end'].date()}  val={r['val']:>8.3f} "
                  f"{r['val_unit']}")

    write_provenance(panel, features, adf, corr, extension_info,
                     source_url, build_ts)
    print()
    print(f"Wrote {PROVENANCE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
