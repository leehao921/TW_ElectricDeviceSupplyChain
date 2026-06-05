"""Verify [[X]] wikilinks in vault/**/*.md resolve to a known target.

Catches the [[Vera_Rubin_BOM]]-style cross-PR risk where vault concept pages
reference vault files that only exist in an unmerged PR branch.

Allow-list:
1. WIKILINKS.md entries (auto-generated proper nouns)
2. vault/**/*.md file stems
3. Pilot_Reports/**/*.md stems + ticker prefixes (so [[2330]] resolves to 2330_台積電)
4. tests/wikilinks_baseline.txt (snapshot of pre-existing broken, ratchet-down model)

Failure semantics: only NEW broken wikilinks (not in baseline) fail.
Baseline 是逐步縮小的歷史包袱; 加新 broken → fail (regression guard).
更新 baseline: python3 tests/test_wikilinks.py --rebuild-baseline
"""
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BASELINE_FILE = Path(__file__).resolve().parent / "wikilinks_baseline.txt"
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
TICKER_PREFIX_RE = re.compile(r"^(\d{4,5})(?:[_ ].+)?$")


def build_allowlist() -> set[str]:
    allow: set[str] = set()
    wikilinks_md = REPO / "WIKILINKS.md"
    if wikilinks_md.exists():
        allow.update(WIKILINK_RE.findall(wikilinks_md.read_text()))
    for d in ("vault", "Pilot_Reports"):
        root = REPO / d
        if not root.exists():
            continue
        for f in root.rglob("*.md"):
            stem = f.stem
            allow.add(stem)
            # Pilot_Reports stems are "2330_台積電" — also accept bare ticker [[2330]]
            # and space form [[2330 台積電]]
            m = TICKER_PREFIX_RE.match(stem)
            if m:
                allow.add(m.group(1))
                allow.add(stem.replace("_", " "))
    return allow


def vault_wikilinks() -> dict[str, list[str]]:
    """Returns {target: [files-that-reference-it, ...]}."""
    found: dict[str, list[str]] = {}
    vault = REPO / "vault"
    if not vault.exists():
        return found
    for f in vault.rglob("*.md"):
        for m in WIKILINK_RE.finditer(f.read_text()):
            target = m.group(1).strip()
            found.setdefault(target, []).append(str(f.relative_to(REPO)))
    return found


def load_baseline() -> set[str]:
    if not BASELINE_FILE.exists():
        return set()
    return {
        line.strip()
        for line in BASELINE_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def compute_broken() -> dict[str, list[str]]:
    allow = build_allowlist()
    found = vault_wikilinks()
    return {t: refs for t, refs in found.items() if t not in allow}


def test_no_new_broken_wikilinks():
    broken = compute_broken()
    baseline = load_baseline()
    new_broken = {t: refs for t, refs in broken.items() if t not in baseline}
    if new_broken:
        lines = []
        for t, refs in sorted(new_broken.items()):
            suffix = f" (+{len(refs)-1})" if len(refs) > 1 else ""
            lines.append(f"  [[{t}]] in {refs[0]}{suffix}")
        msg = "\n".join(lines)
        pytest.fail(
            f"{len(new_broken)} 個新 broken wikilink (不在 baseline):\n{msg}\n\n"
            "修正擇一:\n"
            "  (a) 補對應 vault/Pilot_Reports 檔案\n"
            "  (b) typo 修正\n"
            "  (c) 若是合法外部名稱:加進 baseline: "
            "python3 tests/test_wikilinks.py --rebuild-baseline"
        )


def test_baseline_only_shrinks():
    """Baseline 應隨時間縮減 — 若已不存在 broken 列表 → 應從 baseline 移除。"""
    broken = compute_broken()
    baseline = load_baseline()
    stale = baseline - set(broken.keys())
    if stale:
        lines = [f"  - {t}" for t in sorted(stale)]
        pytest.fail(
            f"{len(stale)} 個 baseline entry 已修復 (不在 broken list 內), "
            "應從 baseline 移除:\n" + "\n".join(lines) + "\n\n"
            "重產 baseline: python3 tests/test_wikilinks.py --rebuild-baseline"
        )


def rebuild_baseline():
    broken = compute_broken()
    header = (
        "# wikilinks_baseline.txt — auto-generated, do not edit by hand\n"
        "# Lines below are wikilink targets that were broken at baseline time.\n"
        "# New broken wikilinks not in this list will fail "
        "tests/test_wikilinks.py.\n"
        "# Shrink over time by fixing references or adding to "
        "WIKILINKS.md / vault.\n"
        "# Rebuild: python3 tests/test_wikilinks.py --rebuild-baseline\n"
    )
    body = "\n".join(sorted(broken.keys()))
    BASELINE_FILE.write_text(header + body + "\n")
    print(f"Wrote {len(broken)} entries to {BASELINE_FILE.relative_to(REPO)}")


if __name__ == "__main__":
    if "--rebuild-baseline" in sys.argv:
        rebuild_baseline()
    else:
        broken = compute_broken()
        print(f"{len(broken)} broken wikilinks; baseline has {len(load_baseline())}.")
