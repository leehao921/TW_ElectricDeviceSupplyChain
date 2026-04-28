"""One-shot: insert manually-authored research analyses into news_items.

Used to seed the ``tw_electronics`` DB with high-value analyses produced
during a Claude Code session before the live news collectors have caught up.
Each analysis is treated as a single ``news_items`` row with ``source='claude_research'``,
manually-tagged ``tickers[]`` / ``wikilinks[]``, and an Ollama bge-m3 embedding.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

import asyncpg
import httpx

PG_NEWS_DSN = os.environ.get(
    "PG_NEWS_DSN",
    "postgresql://knowledge:knowledge@localhost:5433/tw_electronics",
)
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")


async def embed(client: httpx.AsyncClient, text: str) -> list[float]:
    r = await client.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text[:8000]},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()["embedding"]


ANALYSES = [
    {
        "source": "claude_research",
        "source_url": "claude://session/2026-04-28/mediatek-2454-surge-analysis",
        "published_at": datetime(2026, 4, 28, 10, 30, tzinfo=timezone.utc),
        "title": "聯發科 (2454) 暴漲分析：Google TPU v8x ASIC 訂單與 76% 營收上修",
        "tickers": ["2454", "2330", "2303", "3711", "2449", "3037", "8046", "3189",
                    "3043", "2383", "6213", "2313", "6269", "6274", "3289", "3587",
                    "6191", "3443", "3661", "3035", "6533", "6526", "7749"],
        "wikilinks": ["聯發科", "Google", "TPU", "ASIC", "CoWoS", "HBM", "ABF 載板",
                      "台積電", "聯華電子", "日月光投控", "京元電子", "欣興", "南電",
                      "景碩", "創意", "世芯-KY", "智原", "AI 伺服器", "天璣",
                      "NVIDIA", "Samsung"],
        "body": (
            "聯發科 (2454) 4/13–4/27 漲幅 +50.3% (1,620 → 2,435)，外資連 8 日買超，"
            "4/15+4/17 外資合計近萬張，投信 4/22+4/24 接力。\n\n"
            "催化劑：美系外資 4/21 起調升 AI ASIC 營收預估，2026 從 $1.5B 上修至 $2.0B (10% 占比)，"
            "2027 從 $7.0B 暴增至 $12.3B (39% 占比，76% 上修)。核心專案是 Google TPU v8x (Zebrafish)，"
            "聯發科是 ASIC 設計合作夥伴，台積電 2nm 製程，CoWoS-S 先進封裝。\n\n"
            "供應鏈：上游 [[台積電]] 2nm/[[聯華電子]] 成熟製程；封裝 [[台積電]] CoWoS + [[日月光投控]]；"
            "後段封測 [[京元電子]]；ABF 載板 [[欣興]]/[[南電]]/[[景碩]]；CCL [[台光電]]/[[聯茂]]；"
            "高階 PCB [[華通]]/[[台郡]]/[[台燿]]；驗證 [[宜特]]/[[閎康]]。"
            "TPU UBB 直接供應商：[[精成科]] (6191)。"
            "ASIC 設計同業：[[創意]] (3443)、[[世芯-KY]] (3661)、[[智原]] (3035)。\n\n"
            "風險：(1) Ajinomoto ABF Film 寡占 95%，全球單點；"
            "(2) HBM 集中 [[Samsung]]+SK Hynix 韓系；"
            "(3) CoWoS 產能瓶頸 (聯發科要求 TSMC 7 倍擴產 20k→150k wafers by 2027)；"
            "(4) 客戶集中於 [[Google]] TPU；(5) 估值已 price-in 部分樂觀情境，P/E TTM ~24x。\n\n"
            "4/30 法說會將揭露 ASIC 收入細節。\n\n"
            "Sources: BigGo Finance, Trendforce, Tom's Hardware, Digitimes, Yahoo Finance."
        ),
    },
    {
        "source": "claude_research",
        "source_url": "claude://session/2026-04-28/abf-film-ajinomoto-monopoly",
        "published_at": datetime(2026, 4, 28, 11, 0, tzinfo=timezone.utc),
        "title": "ABF Film (Ajinomoto Build-up Film) 結構解析：味精公司如何 30 年寡占 95% IC 載板絕緣材料",
        "tickers": ["3037", "8046", "3189"],
        "wikilinks": ["ABF", "ABF 載板", "Ajinomoto", "味之素", "CoWoS", "FC-BGA",
                      "HBM", "AI 伺服器", "NVIDIA", "Intel", "Google", "TPU",
                      "聯發科", "欣興", "南電", "景碩", "BT 載板"],
        "body": (
            "ABF = Ajinomoto Build-up Film，厚 25-40 µm 的絕緣樹脂膜，IC 載板 (FC-BGA / "
            "[[ABF 載板]]) 銅佈線層之間的層間絕緣材料。功能：低介電 (Dk/Df)、CTE 與銅匹配、"
            "可雷射鑽孔 (microvia 25 µm)、超薄均一。所有先進 FC-BGA 封裝必備：[[NVIDIA]] H100/B200、"
            "[[Google]] TPU、[[聯發科]] 天璣旗艦、[[Intel]]/[[AMD]] CPU。\n\n"
            "歷史: 1909 創辦人發明 MSG 工業化；1970s 發現 MSG 製程副產物氯化石蠟有軟化樹脂能力，"
            "進入胺基酸+環氧樹脂研究；1996 [[Intel]] 從陶瓷封裝轉 FC-BGA 找上門；1999 量產被 [[Intel]] 採用；"
            "2010 後客戶需求發散 → 7-8 個系列。現在福島工廠產 ~95% 全球市占。\n\n"
            "30 年沒人打破寡占的四個原因：(1) 配方+黑盒 (胺基酸衍生硬化劑 + 無機填料分散)；"
            "(2) 客戶認證週期 >18 個月、數百萬美元成本；(3) 共設計綁定 (Ajinomoto 從晶片設計階段介入)；"
            "(4) 福島單一產地反向強化均衡 (客戶寧可承受集中風險也不切換)。\n\n"
            "對台股投資意義：直接投資 ABF 無台股標的 (味之素 JP:2802 東京掛牌)。"
            "下游 ABF 載板廠才是台股受惠路徑：[[欣興]] (3037, 龍頭)、[[南電]] (8046)、[[景碩]] (3189)。\n\n"
            "結構性風險：福島單點 = 全球瓶頸，2021 颱風+火災一度停產差點讓 [[Intel]] CPU/[[NVIDIA]] GPU 全球缺貨。\n\n"
            "翻轉訊號：若見「[[南亞塑膠]] 自製 ABF」「日東電工 ABF 量產」「韓系 ABF 過 [[Intel]] 認證」"
            "等新聞，30 年寡占可能要結束。\n\n"
            "Sources: Ajinomoto Group official innovation story, Cadence PCB blog, Polymer Innovation Blog."
        ),
    },
]


async def main() -> int:
    pool = await asyncpg.create_pool(PG_NEWS_DSN, min_size=1, max_size=2)
    inserted = 0
    skipped = 0
    async with httpx.AsyncClient() as client:
        async with pool.acquire() as conn:
            for a in ANALYSES:
                text = a["title"] + "\n\n" + a["body"]
                try:
                    vec = await embed(client, text)
                except Exception as e:
                    print(f"[skip] embedding failed for {a['source_url']}: {e}",
                          file=sys.stderr)
                    skipped += 1
                    continue
                vec_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
                row = await conn.fetchrow(
                    """
                    INSERT INTO news_items
                      (source, source_url, published_at, title, body,
                       tickers, wikilinks, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector)
                    ON CONFLICT (source_url) DO UPDATE SET
                      title = EXCLUDED.title,
                      body = EXCLUDED.body,
                      tickers = EXCLUDED.tickers,
                      wikilinks = EXCLUDED.wikilinks,
                      embedding = EXCLUDED.embedding,
                      ingested_at = now()
                    RETURNING id, (xmax = 0) AS is_insert
                    """,
                    a["source"], a["source_url"], a["published_at"],
                    a["title"], a["body"],
                    a["tickers"], a["wikilinks"], vec_str,
                )
                inserted += 1
                marker = "INSERT" if row["is_insert"] else "UPDATE"
                print(f"[{marker}] id={row['id']} {a['title'][:60]}...")
            await conn.execute(
                """
                INSERT INTO ingest_runs
                  (job_name, started_at, finished_at, status, rows_written)
                VALUES ($1, now(), now(), $2, $3)
                """,
                "claude_research_seed", "ok" if not skipped else "partial", inserted,
            )
    await pool.close()
    print(f"\nDone: {inserted} written, {skipped} skipped")
    return 0 if not skipped else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
