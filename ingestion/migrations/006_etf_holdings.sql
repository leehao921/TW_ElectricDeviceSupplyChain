-- 主動型 ETF 持股快照 + 共識度指標表
-- 每月由 etf_holdings_monthly cron 自動更新（每月 16 日，主動 ETF 月公告後）

CREATE TABLE IF NOT EXISTS etf_holdings (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    etf_ticker TEXT NOT NULL,                -- e.g. '00981A'
    etf_name TEXT,
    etf_aum_b NUMERIC(12, 2),                -- AUM in NTD billions
    holding_ticker TEXT NOT NULL,
    holding_name TEXT,
    holding_pct NUMERIC(8, 5) NOT NULL,      -- 0.10056 = 10.056%
    rank INTEGER,                            -- 1-10
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (snapshot_date, etf_ticker, holding_ticker)
);

CREATE INDEX IF NOT EXISTS idx_etf_holdings_date ON etf_holdings (snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_etf_holdings_etf ON etf_holdings (etf_ticker, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_etf_holdings_target ON etf_holdings (holding_ticker, snapshot_date DESC);

-- 共識度匯總（每月由 collector 一併計算寫入）
CREATE TABLE IF NOT EXISTS etf_consensus (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT,
    n_etfs INTEGER NOT NULL,                 -- 被幾檔 ETF 持有
    avg_pct NUMERIC(8, 5) NOT NULL,
    max_pct NUMERIC(8, 5) NOT NULL,
    weighted_aum NUMERIC(14, 2) NOT NULL,    -- ∑ (pct × AUM) — proxy 資金加權
    consensus_score NUMERIC(10, 3),          -- normalized 0-100
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (snapshot_date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_consensus_score ON etf_consensus (snapshot_date DESC, consensus_score DESC);
