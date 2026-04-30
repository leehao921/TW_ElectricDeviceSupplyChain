-- Schema for lean-forward event-driven factor extraction (issue #12).
-- One row per (event_name, ticker). Top-15 long + top-15 short loadings per event.
-- See analysis/event_factor_extractor.py and docs/quant_claim_verification.md § 9.

CREATE TABLE IF NOT EXISTS emergent_factor_baskets (
    id BIGSERIAL PRIMARY KEY,
    event_name TEXT NOT NULL,
    event_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    loading DOUBLE PRECISION NOT NULL,
    rank INTEGER NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('long', 'short')),
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_name, ticker)
);

CREATE INDEX IF NOT EXISTS idx_efb_event ON emergent_factor_baskets (event_name);
CREATE INDEX IF NOT EXISTS idx_efb_ticker ON emergent_factor_baskets (ticker);
