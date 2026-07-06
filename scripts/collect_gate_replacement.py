"""
O-005R 재심용: '쑥 토너' 검색량 실재 확인 (D-015 동결 예외 조항)
- 배경: 전체 156주 기준 재계산에서 '쑥 화장품'이 72/156 = 46.2% < 50% → 부재 판정 (Failure #4)
- 교체 후보 '쑥 토너'를 수집해 동일 게이트(전체 주 수 분모)를 적용한다
- 통과 시: data/raw/search_trend_replacement.csv 저장 (본 CSV 반영은 오너 승인 후)
실행: python scripts/collect_gate_replacement.py
"""
import json, os
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

CANDIDATE = "쑥 토너"
START_DATE, END_DATE = "2023-07-03", "2026-06-28"
TOTAL_WEEKS = 156  # 전체 주 수 — 데이터랩은 0인 주를 생략하므로 반드시 이 값을 분모로 사용
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "search_trend_replacement.csv"


def main():
    load_dotenv(ROOT / ".env")
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and secret):
        raise SystemExit(".env에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 필요")
    body = {"startDate": START_DATE, "endDate": END_DATE, "timeUnit": "week",
            "keywordGroups": [{"groupName": CANDIDATE, "keywords": [CANDIDATE]}]}
    r = requests.post("https://openapi.naver.com/v1/datalab/search",
                      headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret,
                               "Content-Type": "application/json"},
                      data=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=15)
    r.raise_for_status()
    data = r.json()["results"][0]["data"]
    df = pd.DataFrame([{"keyword": CANDIDATE, "period": d["period"], "ratio": d["ratio"]} for d in data])
    nz = int((df["ratio"] > 0).sum())
    share = nz / TOTAL_WEEKS
    print(f"[{CANDIDATE}] 반환 {len(df)}행 | 0이 아닌 주 {nz}/{TOTAL_WEEKS} = {share:.1%} | "
          f"최대 {df['ratio'].max():.1f} | 평균 {df['ratio'].mean():.2f}")
    print("게이트 판정:", "통과 (≥50%) → 교체 가능" if share >= 0.5
          else "부재 (<50%) → 교체 불가, 쑥 화장품 유지 검토")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("저장:", OUT)


if __name__ == "__main__":
    main()
