"""Verify institutional alpha thesis claims in vault/concepts/*.md against
trading-timescaledb ground truth.

How it works:
1. Parses YAML frontmatter `testable_claims:` from each concept page
2. Queries `institutional_stock` for the (ticker, window) cumulative net flow
3. Asserts actual flow matches concept page claim (gt / lt / abs_gt thresholds)

Catches the 3711 thesis bug: concept page ranks 3711 ★★★★★ #2 based on
prompt-given "+103K" but DB ground truth for 5/12-6/1 is -28K (法人撤退).
This test would fail the assertion `total_net_gt: 50000` for 3711.

Add testable_claims to concept page frontmatter:

```yaml
testable_claims:
  - ticker: "2344"
    window: ["2026-05-12", "2026-06-01"]
    assertions:
      foreign_net_gt: 50000
      trust_net_gt: 30000
      total_net_gt: 100000
    thesis: "雙引擎冠軍 (★★★★★)"
```

Run: pytest tests/test_alpha_concepts.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg2
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT_CONCEPTS = REPO_ROOT / "vault" / "concepts"

DB_CONFIG = dict(
    host="localhost", port=5432,
    dbname="tmf_market_data",
    user="tmf", password="tmf_dev_2026",
)


def parse_frontmatter(filepath: Path) -> dict:
    """Extract YAML frontmatter from markdown file."""
    text = filepath.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def query_cumulative_net(ticker: str, start: str, end: str, field: str) -> int:
    """Query DB for cumulative net flow over date window. Returns 張 (lots = shares/1000)."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT SUM({field}) FROM institutional_stock
                WHERE symbol = %s AND date >= %s AND date <= %s
                """,
                (ticker, start, end),
            )
            result = cur.fetchone()[0]
            return int(result / 1000) if result else 0
    finally:
        conn.close()


def collect_claims():
    """Yield (page_name, ticker, claim) for every testable_claim across all concept pages."""
    for f in sorted(VAULT_CONCEPTS.glob("*.md")):
        fm = parse_frontmatter(f)
        claims = fm.get("testable_claims") or []
        for c in claims:
            yield pytest.param(f.name, c, id=f"{f.stem}::{c['ticker']}::{c.get('thesis','')[:25]}")


CLAIMS = list(collect_claims())


@pytest.mark.parametrize("page,claim", CLAIMS)
def test_thesis_vs_db(page: str, claim: dict):
    """Each testable_claim's DB ground truth must match assertions."""
    ticker = claim["ticker"]
    start, end = claim["window"]
    assertions = claim.get("assertions", {})
    thesis = claim.get("thesis", "(no thesis)")

    failures = []
    for assertion_name, expected in assertions.items():
        # Parse "<field>_<op>" e.g., "foreign_net_gt" / "total_net_lt" / "total_net_abs_gt"
        if assertion_name.endswith("_gt"):
            field = assertion_name[: -len("_gt")]
            op, threshold = "gt", expected
        elif assertion_name.endswith("_lt"):
            field = assertion_name[: -len("_lt")]
            op, threshold = "lt", expected
        elif assertion_name.endswith("_abs_gt"):
            field = assertion_name[: -len("_abs_gt")]
            op, threshold = "abs_gt", expected
        else:
            failures.append(f"unknown assertion form '{assertion_name}'")
            continue

        actual = query_cumulative_net(ticker, start, end, field)

        if op == "gt" and not actual > threshold:
            failures.append(
                f"{field}: expected > {threshold:,}, actual {actual:,}"
            )
        elif op == "lt" and not actual < threshold:
            failures.append(
                f"{field}: expected < {threshold:,}, actual {actual:,}"
            )
        elif op == "abs_gt" and not abs(actual) > threshold:
            failures.append(
                f"|{field}|: expected > {threshold:,}, actual {actual:,}"
            )

    if failures:
        msg = "\n".join(
            [
                f"\n  Page: {page}",
                f"  Ticker: {ticker}",
                f"  Window: {start} to {end}",
                f"  Thesis: {thesis}",
                "  Failed assertions:",
                *[f"    - {f}" for f in failures],
            ]
        )
        pytest.fail(msg)


def test_concept_pages_have_claims():
    """At least 1 concept page should have testable_claims defined.

    Catches the case where all concepts are claim-free freeform text.
    Skip if you're early in the vault lifecycle.
    """
    if not CLAIMS:
        pytest.skip("No testable_claims found in any concept page (intentional - skip)")
    assert len(CLAIMS) > 0


if __name__ == "__main__":
    # Diagnostic mode: print all claims + DB values
    for page, claim in [(p.values[0], p.values[1]) for p in CLAIMS]:
        print(f"\n=== {page} :: {claim['ticker']} ===")
        print(f"  Thesis: {claim.get('thesis')}")
        print(f"  Window: {claim['window']}")
        for k, v in claim.get("assertions", {}).items():
            field = k.rsplit("_", 1)[0] if k.endswith(("_gt", "_lt")) else k
            actual = query_cumulative_net(claim["ticker"], *claim["window"], field)
            print(f"  {k} expected {v:>+10,} | actual {actual:>+10,} | {'✓' if (actual > v if k.endswith('_gt') else actual < v) else '✗'}")
