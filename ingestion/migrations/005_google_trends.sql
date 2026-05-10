-- Google Trends daily + hourly snapshot table.
-- Score = relative interest (0-100) per pytrends; not absolute search count.
-- See analysis/google_trends_collector.py.

CREATE TABLE IF NOT EXISTS google_trends_daily (
    id BIGSERIAL PRIMARY KEY,
    keyword TEXT NOT NULL,
    geo TEXT NOT NULL DEFAULT 'TW',          -- 'TW' or '' (global)
    ts TIMESTAMPTZ NOT NULL,                 -- bucket timestamp
    granularity TEXT NOT NULL,               -- 'daily' or 'hourly'
    score INTEGER NOT NULL,                  -- 0-100 relative
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (keyword, geo, ts, granularity)
);

CREATE INDEX IF NOT EXISTS idx_gt_keyword_ts ON google_trends_daily (keyword, ts DESC);
CREATE INDEX IF NOT EXISTS idx_gt_ts          ON google_trends_daily (ts DESC);
