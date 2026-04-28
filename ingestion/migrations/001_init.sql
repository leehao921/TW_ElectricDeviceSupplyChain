CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS news_items (
  id           BIGSERIAL PRIMARY KEY,
  source       TEXT NOT NULL,
  source_url   TEXT UNIQUE,
  published_at TIMESTAMPTZ NOT NULL,
  title        TEXT NOT NULL,
  body         TEXT,
  tickers      TEXT[] NOT NULL DEFAULT '{}',
  wikilinks    TEXT[] NOT NULL DEFAULT '{}',
  embedding    vector(1024),
  ingested_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_news_tickers   ON news_items USING gin(tickers);
CREATE INDEX IF NOT EXISTS idx_news_wikilinks ON news_items USING gin(wikilinks);
CREATE INDEX IF NOT EXISTS idx_news_embedding ON news_items USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS mops_disclosures (
  id            BIGSERIAL PRIMARY KEY,
  ticker        TEXT NOT NULL,
  disclosure_ts TIMESTAMPTZ NOT NULL,
  category      TEXT,
  subject       TEXT NOT NULL,
  body          TEXT,
  source_url    TEXT UNIQUE,
  ingested_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mops_ticker_ts ON mops_disclosures (ticker, disclosure_ts DESC);

CREATE TABLE IF NOT EXISTS finmind_fundamentals (
  ticker          TEXT NOT NULL,
  report_month    DATE NOT NULL,
  monthly_revenue BIGINT,
  yoy_pct         NUMERIC,
  mom_pct         NUMERIC,
  PRIMARY KEY (ticker, report_month)
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  id           BIGSERIAL PRIMARY KEY,
  job_name     TEXT NOT NULL,
  started_at   TIMESTAMPTZ NOT NULL,
  finished_at  TIMESTAMPTZ,
  status       TEXT NOT NULL,
  rows_written INT,
  error        TEXT
);
