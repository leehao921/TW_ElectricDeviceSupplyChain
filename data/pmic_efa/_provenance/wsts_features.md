# PMIC EFA Unit 17 — WSTS macro features provenance

**Build run:** 2026-06-11T01:44:15.308176+00:00

## Source panel

- Read from `data/pmic_efa/macro_semis_monthly.parquet`
- Original months: 484
- Months added by Unit 17 extension probe: 0
- Final months: 484 (1986-01-31 -> 2026-04-30)
- Gap-free monthly: YES

## Extension attempts

- [stub/missing] https://www.wsts.org/esraCMS/extension/media/f/WST/7644/WSTS-Historical-Billings-Report-May_2026.xlsx
- [stub/missing] https://www.wsts.org/esraCMS/extension/media/f/WST/7644/WSTS-Historical-Billings-Report-Jun_2026.xlsx
- [stub/missing] https://www.wsts.org/esraCMS/extension/media/f/WST/7644/WSTS-Historical-Billings-Report-Jul_2026.xlsx

Conclusion: WSTS Apr_2026 release is still the latest publicly published Historical Billings Report. May/Jun 2026 are not yet released; the panel is correct through the public data frontier.

## Features emitted

| tag | unit | n | first | last |
|---|---|---|---|---|
| `wsts_level_zscore` | sigma | 461 | 1987-12-31 | 2026-04-30 |
| `wsts_yoy` | pct | 472 | 1987-01-31 | 2026-04-30 |
| `wsts_yoy_3ma` | pct | 470 | 1987-03-31 | 2026-04-30 |

## Stationarity (ADF, H0 = unit root)

| tag | adf stat | p-value | n | stationary @ 5% |
|---|---|---|---|---|
| `wsts_level_zscore` | -5.501 | 0.0000 | 461 | YES |
| `wsts_yoy` | -4.246 | 0.0006 | 472 | YES |
| `wsts_yoy_3ma` | -4.327 | 0.0004 | 470 | YES |

DFM exogenous covariates should be stationary. `wsts_yoy` and `wsts_yoy_3ma` are differenced log returns (intrinsically stationary). `wsts_level_zscore` is a rolling-window z-score; with a 24-month window it absorbs slow level drift and is typically stationary on the WSTS panel.

## Feature correlation matrix

```
tag                wsts_level_zscore  wsts_yoy  wsts_yoy_3ma
tag                                                         
wsts_level_zscore              1.000     0.725         0.707
wsts_yoy                       0.725     1.000         0.970
wsts_yoy_3ma                   0.707     0.970         1.000
```

## Schema

Canonical 11-column long format inherited from the IP DB: `end, entity_id, entity_name, tag, val, val_unit, fp, form, accn, source_url, source_date`. `entity_id = 'WSTS_GLOBAL'`, `form = 'derived_from_wsts_press_release'`, `accn = wsts_features:<build_date>`.

## Source URL (passed through)

`https://www.wsts.org/esraCMS/extension/media/f/WST/7644/WSTS-Historical-Billings-Report-Apr_2026.xlsx`
