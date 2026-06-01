#!/usr/bin/env python3
"""Vault health check — orphans, stale claims, contradictions, missing wikilinks, index drift.

Per LLM Wiki manifesto: never auto-fixes. Surfaces issues + appends summary to vault/log.md.

Usage:
    python3 scripts/vault_lint.py
    python3 scripts/vault_lint.py --rebuild-index
    python3 scripts/vault_lint.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pytz

TPE = pytz.timezone("Asia/Taipei")
REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT = REPO_ROOT / "vault"
STALE_DAYS = 30


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    yaml_block = text[4:end]
    out = {}
    for line in yaml_block.splitlines():
        if ":" not in line: continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


def list_vault_pages() -> list[Path]:
    return sorted(p for p in VAULT.rglob("*.md") if p.is_file())


def extract_links(text: str) -> set[str]:
    """Find markdown links + Obsidian wikilinks."""
    links = set()
    # [text](path)
    for m in re.finditer(r"\[[^\]]+\]\(([^)]+\.md)(?:#[^)]*)?\)", text):
        links.add(m.group(1))
    # [[X]] wikilinks
    for m in re.finditer(r"\[\[([^\]]+)\]\]", text):
        target = m.group(1).split("|")[0].split("#")[0]
        if not target.endswith(".md"):
            target = target + ".md"
        links.add(target)
    return links


def check_orphans(pages: list[Path]) -> list[Path]:
    """A page is orphan if nothing links to it (except index.md itself)."""
    incoming: dict[str, int] = defaultdict(int)
    page_basenames = {p.relative_to(VAULT).as_posix(): p for p in pages}
    # also index by basename only
    by_basename = {p.name: p for p in pages}

    for p in pages:
        text = p.read_text()
        for link in extract_links(text):
            # try absolute relative-to-vault first
            normalized = None
            link_path = (p.parent / link).resolve()
            try:
                rel = link_path.relative_to(VAULT).as_posix()
                normalized = rel
            except ValueError:
                pass
            # then try basename
            if not normalized:
                base = Path(link).name
                if base in by_basename:
                    normalized = by_basename[base].relative_to(VAULT).as_posix()
            if normalized:
                incoming[normalized] += 1

    orphans = []
    for p in pages:
        rel = p.relative_to(VAULT).as_posix()
        # exclude entry points and dynamic dumps
        if rel in ("index.md", "log.md"):
            continue
        if rel.startswith("inbox/"):  # weekly dumps are leaf nodes by design
            continue
        if incoming.get(rel, 0) == 0:
            orphans.append(p)
    return orphans


def check_stale(pages: list[Path]) -> list[tuple[Path, str]]:
    """Pages with `last_updated` > STALE_DAYS days old."""
    today = datetime.now(TPE).date()
    stale = []
    for p in pages:
        fm = parse_frontmatter(p.read_text())
        lu = fm.get("last_updated")
        if not lu: continue
        try:
            d = datetime.fromisoformat(lu).date() if "-" in lu else None
            if d and (today - d).days > STALE_DAYS:
                stale.append((p, lu))
        except (ValueError, AttributeError):
            pass
    return stale


def check_contradictions(pages: list[Path]) -> list[dict]:
    """Same exact metric label with conflicting values across pages.

    Only flags when the SAME context phrase (e.g., 'full 3y β', '60d β current')
    has different values. Different time-window labels (60d vs full) are NOT
    treated as contradiction.
    """
    candidates: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    # Match labelled metrics with their time-window context
    patterns = [
        # 60d β: e.g., "60d β = -1.47" "60d rolling β -1.47"
        (re.compile(r"(60d[^\n]{0,15}?β)[^\n]{0,15}?(-?\d+\.\d+)", re.IGNORECASE), "beta_60d"),
        # full 3y β: e.g., "full 3y β = -0.37" "β (full 3y) -0.37"
        (re.compile(r"(full[^\n]{0,20}?β|β[^\n]{0,15}?full)[^\n]{0,15}?(-?\d+\.\d+)", re.IGNORECASE), "beta_full3y"),
        # USDTWD corr
        (re.compile(r"(TWII[\-–]USDTWD|USD/TWD[^\n]{0,15}?corr)[^\n]{0,15}?(-?\d+\.\d+)", re.IGNORECASE), "corr_twii_usdtwd"),
    ]
    for p in pages:
        # Skip inbox/log (snapshots, not canonical claims)
        rel = p.relative_to(VAULT).as_posix()
        if rel.startswith("inbox/") or rel == "log.md":
            continue
        text = p.read_text()
        for pat, key in patterns:
            for m in pat.finditer(text):
                candidates[key].append((p, m.group(2)))
    contradictions = []
    for key, hits in candidates.items():
        values = {v for _, v in hits}
        if len(values) > 1:
            contradictions.append({
                "metric": key,
                "values": sorted(values),
                "pages": sorted({str(p.relative_to(VAULT)) for p, _ in hits}),
            })
    return contradictions


def check_index_drift(pages: list[Path]) -> tuple[list[str], list[str]]:
    """Files in vault/ not listed in index.md, or links in index.md not matching files."""
    index = VAULT / "index.md"
    if not index.exists():
        return [], []
    index_links = extract_links(index.read_text())
    index_basenames = {Path(l).name for l in index_links}

    actual = {p.relative_to(VAULT).as_posix() for p in pages}
    actual_basenames = {p.name for p in pages}

    missing_from_index = [
        p.relative_to(VAULT).as_posix() for p in pages
        if p.name not in index_basenames
           and p.relative_to(VAULT).as_posix() not in ("index.md", "log.md")
           and not p.relative_to(VAULT).as_posix().startswith("inbox/")
    ]
    stale_in_index = [
        l for l in index_basenames
        if l not in actual_basenames and not l.startswith("(")
    ]
    return missing_from_index, stale_in_index


def append_log(report_summary: str) -> None:
    log = VAULT / "log.md"
    now = datetime.now(TPE)
    line = f"\n## [{now.strftime('%Y-%m-%d %H:%M TWT')}] lint | {report_summary}\n"
    with open(log, "a") as f:
        f.write(line)


def rebuild_index(pages: list[Path]) -> None:
    """Stub — full impl would scan frontmatter type/description and rebuild categories."""
    print("[rebuild-index] not yet implemented (current index.md is hand-curated)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--rebuild-index", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-log", action="store_true", help="don't append to vault/log.md")
    args = p.parse_args()

    pages = list_vault_pages()
    print(f"Vault lint at {datetime.now(TPE).isoformat()}")
    print(f"  scanned {len(pages)} pages\n")

    orphans = check_orphans(pages)
    stale = check_stale(pages)
    contradictions = check_contradictions(pages)
    missing_index, stale_index = check_index_drift(pages)

    report = {
        "scanned": len(pages),
        "orphans": [str(o.relative_to(VAULT)) for o in orphans],
        "stale": [{"page": str(p.relative_to(VAULT)), "last_updated": lu} for p, lu in stale],
        "contradictions": contradictions,
        "missing_from_index": missing_index,
        "stale_in_index": stale_index,
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        if orphans:
            print(f"## Orphans ({len(orphans)})")
            for o in orphans: print(f"  - {o.relative_to(VAULT)}")
        else: print("## Orphans: 0 ✓")

        if stale:
            print(f"\n## Stale (>{STALE_DAYS}d) ({len(stale)})")
            for p, lu in stale: print(f"  - {p.relative_to(VAULT)} (last_updated: {lu})")
        else: print("\n## Stale: 0 ✓")

        if contradictions:
            print(f"\n## Contradictions ({len(contradictions)})")
            for c in contradictions:
                print(f"  - {c['metric']}: values {c['values']} across {len(c['pages'])} pages: {c['pages']}")
        else: print("\n## Contradictions: 0 ✓")

        if missing_index:
            print(f"\n## Missing from index.md ({len(missing_index)})")
            for m in missing_index: print(f"  - {m}")
        else: print("\n## Index coverage: ✓")

        if stale_index:
            print(f"\n## Stale entries in index.md ({len(stale_index)})")
            for s in stale_index: print(f"  - {s}")

    if not args.no_log:
        summary = (
            f"{len(orphans)} orphans, {len(stale)} stale, "
            f"{len(contradictions)} contradictions, "
            f"{len(missing_index)} missing-from-index, {len(stale_index)} stale-in-index"
        )
        append_log(summary)

    if args.rebuild_index:
        rebuild_index(pages)

    return 0


if __name__ == "__main__":
    sys.exit(main())
