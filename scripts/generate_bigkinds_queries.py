"""
빅카인즈 C 신호 검색식 생성기
- 키워드 60개 × 세그먼트 브랜드 목록으로 `키워드 AND (브랜드 OR ...)` 검색식 생성
- 출력: scripts/bigkinds_queries.txt (빅카인즈 웹에 복붙용)
실행: python3 scripts/generate_bigkinds_queries.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
kw_rows = list(csv.DictReader(open(ROOT / "keywords_v1.csv", encoding="utf-8")))
brands = {r["segment"]: r["brands"].split("|")
          for r in csv.DictReader(open(ROOT / "brands_v1.csv", encoding="utf-8"))}

lines = []
for r in kw_rows:
    segs = r["segment"].split("|")
    bset = []
    for s in segs:
        bset += brands.get(s, [])
    bset = list(dict.fromkeys(bset))  # 중복 제거, 순서 유지 (복수 세그먼트 = 합집합, D-011)
    query = f'{r["keyword"]} AND ({" OR ".join(bset)})'
    lines.append(f'[{r["keyword"]}]\n{query}\n')

out = ROOT / "bigkinds_queries.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"{len(kw_rows)}개 검색식 생성 → {out}")
print("빅카인즈에서 기간 2023-07-03 ~ 2026-06-28, 주간 그래프 Excel 다운로드")
