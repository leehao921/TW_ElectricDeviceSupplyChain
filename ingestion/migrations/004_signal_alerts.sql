-- Per-ticker signal alerts emitted daily by ingestion.snapshots.ticker_signal.
-- One row per (trade_date, ticker). Rows kept even when factors_hit < 2 so
-- the table doubles as a debug log for tuning thresholds.

CREATE TABLE IF NOT EXISTS signal_alerts (
    id            BIGSERIAL PRIMARY KEY,
    trade_date    DATE NOT NULL,
    ticker        TEXT NOT NULL,
    flow_z        REAL,
    news_z        REAL,
    wikilink_heat INTEGER,
    factors_hit   INTEGER NOT NULL,
    composite     REAL NOT NULL,
    details       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (trade_date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_signal_alerts_date_composite
    ON signal_alerts (trade_date DESC, composite DESC);
CREATE INDEX IF NOT EXISTS idx_signal_alerts_ticker_date
    ON signal_alerts (ticker, trade_date DESC);
