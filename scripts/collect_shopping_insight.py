"""
네이버 쇼핑인사이트 카테고리 클릭 추이 수집기 (S 신호용) — v2
- 키워드 단위 카테고리 매핑 (기본: 세그먼트 매핑, 예외: KEYWORD_CAT_OVERRIDES)
- 실행: python3 scripts/collect_shopping_insight.py
"""
import json, os, time
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

START_DATE, END_DATE, TIME_UNIT = "2023-07-03", "2026-07-05", "week"
ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "raw" / "shopping_click.csv"
URL = "https://openapi.naver.com/v1/datalab/shopping/categories"

# 카테고리 ID (2026-07-04 확인, D-020)
CATS = {
    "스킨케어":     "50000190",
    "선케어":       "50000191",
    "클렌징":       "50000192",
    "메이크업베이스": "50000194",
    "색조메이크업":  "50000195",
    "헤어두피":     "50000198",
    "건강식품":     "50000023",  # 이너뷰티 대리 카테고리
}

# 세그먼트 → 기본 카테고리
SEGMENT_DEFAULT = {
    "스킨케어": "스킨케어",
    "선케어": "선케어",
    "클렌징": "클렌징",
    "메이크업": "메이크업베이스",
    "헤어두피": "헤어두피",
    "이너뷰티": "건강식품",
}

# 키워드 단위 예외 (립 계열은 색조메이크업으로)
KEYWORD_CAT_OVERRIDES = {
    "립 오일": "색조메이크업",
    "립 틴트": "색조메이크업",
}

def main():
    load_dotenv(ROOT / ".env")
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    missing = [k for k, v in CATS.items() if not v]
    if missing:
        raise SystemExit(f"cat_id 미입력: {missing}")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret,
               "Content-Type": "application/json"}
    rows = []
    for name, cat in CATS.items():
        body = {"startDate": START_DATE, "endDate": END_DATE, "timeUnit": TIME_UNIT,
                "category": [{"name": name, "param": [cat]}]}
        r = requests.post(URL, headers=headers,
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=15)
        r.raise_for_status()
        for d in r.json()["results"][0]["data"]:
            rows.append({"category": name, "period": d["period"], "ratio": d["ratio"]})
        print(f"{name} 완료")
        time.sleep(0.3)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    # 키워드→카테고리 매핑 테이블 저장 (신호 계산 단계에서 조인용)
    import csv as _csv
    kw_rows = list(_csv.DictReader(open(ROOT / "scripts" / "keywords_v1.csv", encoding="utf-8")))
    mapping = []
    for r in kw_rows:
        kw = r["keyword"]
        seg_first = r["segment"].split("|")[0]
        cat_name = KEYWORD_CAT_OVERRIDES.get(kw, SEGMENT_DEFAULT[seg_first])
        mapping.append({"keyword": kw, "s_category": cat_name})
    pd.DataFrame(mapping).to_csv(ROOT / "data" / "raw" / "keyword_category_map.csv",
                                 index=False, encoding="utf-8-sig")
    print(f"저장: {OUT_CSV} + keyword_category_map.csv")

if __name__ == "__main__":
    main()
