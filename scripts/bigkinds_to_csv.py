"""
빅카인즈 콘솔 수집 결과 → data/raw/news_weekly.csv 변환기
- 입력: ~/Downloads/bigkinds_weekly_raw.txt (bigkinds_console.js가 다운로드한 파일)
- 검증: 60키워드 · 주 수 정렬(2023-07-03 월요일 기준) · keywords_v1.csv와 목록 일치
실행: python3 scripts/bigkinds_to_csv.py [입력파일경로]
"""
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START = date(2023, 7, 3)
DEFAULT_IN = Path.home() / "Downloads" / "bigkinds_weekly_raw.txt"
OUT = ROOT / "data" / "raw" / "news_weekly.csv"


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IN
    if not src.exists():
        raise SystemExit(f"입력 파일 없음: {src}")
    raw = src.read_text(encoding="utf-8").strip()
    blocks = [b for b in raw.split(";") if b]
    assert len(blocks) == 60, f"키워드 블록 {len(blocks)}개 — 60개여야 함"

    with open(ROOT / "scripts" / "keywords_v1.csv", newline="", encoding="utf-8") as f:
        expected = sorted(r["keyword"] for r in csv.DictReader(f))

    parsed, n_weeks = {}, None
    for b in blocks:
        k, vals = b.split(":")
        w = [int(x) for x in vals.split(",")]
        if n_weeks is None:
            n_weeks = len(w)
        assert len(w) == n_weeks, f"{k}: 주 수 불일치 ({len(w)} vs {n_weeks})"
        parsed[k] = w
    assert sorted(parsed) == expected, "키워드 목록이 keywords_v1.csv와 불일치"

    rows = [("keyword", "period", "count")]
    for k in sorted(parsed):
        for i, c in enumerate(parsed[k]):
            rows.append((k, (START + timedelta(weeks=i)).isoformat(), c))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(rows)
    total = sum(sum(w) for w in parsed.values())
    print(f"저장: {OUT} — 60키워드 × {n_weeks}주 = {len(rows)-1}행, 총 {total}건")
    print("다음: python3 scripts/backtest.py && python3 scripts/build_dashboard.py")


if __name__ == "__main__":
    main()
