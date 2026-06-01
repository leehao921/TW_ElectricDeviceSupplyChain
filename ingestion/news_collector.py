"""Phase 4: RSS news collector.

Fetches a small set of business/finance feeds, dedupes by normalized-title
hash, tags themes via regex, and UPSERTs into `market_news` (TIMESTAMPTZ in
Asia/Taipei). On duplicate hash → DO NOTHING (idempotent).

Run: python3 -m ingestion.news_collector
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import pytz

TWT = pytz.timezone("Asia/Taipei")

DOCKER_CONTAINER = "trading-timescaledb"
PSQL_USER = "tmf"
PSQL_DB = "tmf_market_data"

FEEDS = {
    "cnyes_intl":     "https://news.cnyes.com/rss/cat/wd_stock",
    "cnyes_tw":       "https://news.cnyes.com/rss/cat/tw_stock",
    "reuters_asia":   "https://feeds.reuters.com/reuters/APbusinessNews",
    "yahoo_tw_fin":   "https://tw.news.yahoo.com/rss/finance",
    # Resilient supplemental sources (Google News query feeds rarely 403).
    "gnews_taiex":    "https://news.google.com/rss/search?q=TAIEX+OR+%E5%8F%B0%E8%82%A1&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "gnews_fed":      "https://news.google.com/rss/search?q=Federal+Reserve+OR+FOMC&hl=en-US&gl=US&ceid=US:en",
    "gnews_yencarry": "https://news.google.com/rss/search?q=yen+carry+OR+BoJ+OR+Nikkei&hl=en-US&gl=US&ceid=US:en",
    "gnews_tsmc":     "https://news.google.com/rss/search?q=TSMC+OR+%E5%8F%B0%E7%A9%8D%E9%9B%BB&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
}

THEMES = {
    "trump_xi": r"(Trump.*Xi|習.*川普|US.?China summit|美中.{0,3}峰會)",
    "iran":     r"(Iran|伊朗|Hormuz|荷莫茲)",
    "ppi":      r"(PPI|CPI|inflation|通膨)",
    "fed":      r"(Fed|FOMC|聯準會|降息|升息)",
    "boj":      r"(BoJ|日銀|yen carry|日圓)",
    "tsmc":     r"(TSMC|台積電|2330)",
    "nvidia":   r"(NVIDIA|GTC|Jensen|輝達)",
}


def normalize_title(s: str) -> str:
    return re.sub(r"\W+", "", s.lower())


def hash_title(s: str) -> str:
    return hashlib.sha1(normalize_title(s).encode()).hexdigest()


def tag_themes(text: str) -> list[str]:
    return [k for k, p in THEMES.items() if re.search(p, text, re.I)]


def fetch_all() -> list[dict]:
    items: list[dict] = []
    for src, url in FEEDS.items():
        try:
            d = feedparser.parse(url, agent="Mozilla/5.0 TWCoverageBot/1.0")
            print(f"[feed] {src} entries={len(d.entries)}", file=sys.stderr)
            for e in d.entries:
                pub = e.get("published_parsed") or e.get("updated_parsed")
                if not pub:
                    continue
                pub_dt = datetime(*pub[:6], tzinfo=timezone.utc).astimezone(TWT)
                title = e.get("title", "")
                desc = e.get("summary", "")[:280]
                items.append({
                    "pub_ts": pub_dt,
                    "hash": hash_title(title),
                    "source": src,
                    "title": title,
                    "description": desc,
                    "url": e.get("link", ""),
                    "themes": tag_themes(title + " " + desc),
                })
        except Exception as ex:  # noqa: BLE001
            print(f"[WARN] feed {src} failed: {ex}", file=sys.stderr)
    return items


def _sql_lit_str(s: str) -> str:
    s = (s or "").replace("'", "''").replace("\\", "\\\\")
    return f"'{s}'"


def _sql_lit_array(items: list[str]) -> str:
    if not items:
        return "ARRAY[]::text[]"
    inner = ",".join(_sql_lit_str(x) for x in items)
    return f"ARRAY[{inner}]::text[]"


def _psql_exec_sql_file(sql_path: Path) -> None:
    in_container = f"/tmp/{sql_path.name}"
    subprocess.run(
        ["docker", "cp", str(sql_path), f"{DOCKER_CONTAINER}:{in_container}"],
        check=True,
    )
    subprocess.run(
        ["docker", "exec", DOCKER_CONTAINER,
         "psql", "-U", PSQL_USER, "-d", PSQL_DB, "-v", "ON_ERROR_STOP=1",
         "-q", "-f", in_container],
        check=True,
    )


def upsert_news(items: list[dict]) -> int:
    if not items:
        return 0
    # dedupe within-batch by hash
    by_hash: dict[str, dict] = {}
    for it in items:
        by_hash[it["hash"]] = it
    rows = list(by_hash.values())

    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write("BEGIN;\n")
        for i in range(0, len(rows), 200):
            chunk = rows[i:i + 200]
            values = []
            for r in chunk:
                ts_iso = r["pub_ts"].isoformat()
                values.append(
                    f"('{ts_iso}', {_sql_lit_str(r['hash'])}, "
                    f"{_sql_lit_str(r['source'])}, {_sql_lit_str(r['title'])}, "
                    f"{_sql_lit_str(r['description'])}, {_sql_lit_str(r['url'])}, "
                    f"{_sql_lit_array(r['themes'])})"
                )
            f.write(
                "INSERT INTO market_news "
                "(pub_ts, hash, source, title, description, url, themes) VALUES\n"
                + ",\n".join(values) + "\n"
                "ON CONFLICT (hash) DO NOTHING;\n"
            )
        f.write("COMMIT;\n")
        sql_path = Path(f.name)
    _psql_exec_sql_file(sql_path)
    sql_path.unlink(missing_ok=True)
    return len(rows)


def main() -> None:
    items = fetch_all()
    print(f"[collect] fetched {len(items)} raw items")
    n = upsert_news(items)
    print(f"[db] upsert wrote {n} unique items (ON CONFLICT DO NOTHING for dups)")


if __name__ == "__main__":
    main()
