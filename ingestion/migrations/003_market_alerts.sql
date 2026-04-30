-- Market alert log for the intraday monitor (piggybacks on rss_cna/rss_udn cron).
-- One row per detected event; quiet ticks are not logged.

CREATE TABLE IF NOT EXISTS market_alerts (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    alert_type TEXT NOT NULL,  -- fast-move | fx-break | chip-flip | news-catalyst | regime-shift
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warn', 'urgent')),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    snapshot JSONB
);

CREATE INDEX IF NOT EXISTS idx_market_alerts_ts ON market_alerts (ts DESC);
CREATE INDEX IF NOT EXISTS idx_market_alerts_type ON market_alerts (alert_type);
