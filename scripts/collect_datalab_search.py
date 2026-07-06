"""
네이버 데이터랩 검색어트렌드 수집기 (D 신호용)
- 1키워드 = 1요청 원칙 (D-016: 상대값 해상도 확보)
- 중단 시 재개 가능 (이미 수집된 키워드 스킵)
- 수집 완료 후 '검색량 실재 게이트' 리포트 자동 출력

사전 준비:
  1) pip install requests python-dotenv pandas
  2) 프로젝트 루트에 .env 파일 생성:
       NAVER_CLIENT_ID=발급받은ID
       NAVER_CLIENT_SECRET=발급받은SECRET
실행: python scripts/collect_datalab_search.py
"""
import csv
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# ---------- 설정 ----------
START_DATE = "2023-07-03"   # 백테스트(2024.7~) + 선행 1년 (계절성 필터·MA12 워밍업)
END_DATE = "2026-06-28"
TIME_UNIT = "week"
REQUEST_DELAY_SEC = 0.3
ZERO_GATE_THRESHOLD = 0.5   # 0이 아닌 주 비율이 50% 미만이면 '검색량 부재' 판정 (사전 정의 규칙)

ROOT = Path(__file__).resolve().parent.parent
KEYWORDS_CSV = ROOT / "scripts" / "keywords_v1.csv"
OUT_DIR = ROOT / "data" / "raw"
OUT_CSV = OUT_DIR / "search_trend.csv"
URL = "https://openapi.naver.com/v1/datalab/search"


def load_keywords() -> list[str]:
    with open(KEYWORDS_CSV, newline="", encoding="utf-8") as f:
        return [row["keyword"] for row in csv.DictReader(f)]


def load_done() -> set[str]:
    if not OUT_CSV.exists():
        return set()
    return set(pd.read_csv(OUT_CSV)["keyword"].unique())


def fetch_keyword(kw: str, cid: str, secret: str) -> list[dict]:
    body = {
        "startDate": START_DATE,
        "endDate": END_DATE,
        "timeUnit": TIME_UNIT,
        "keywordGroups": [{"groupName": kw, "keywords": [kw]}],
    }
    headers = {
        "X-Naver-Client-Id": cid,
        "X-Naver-Client-Secret": secret,
        "Content-Type": "application/json",
    }
    for attempt in range(3):
        resp = requests.post(URL, headers=headers,
                             data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                             timeout=15)
        if resp.status_code == 200:
            data = resp.json()["results"][0]["data"]
            return [{"keyword": kw, "period": d["period"], "ratio": d["ratio"]} for d in data]
        if resp.status_code == 429:  # rate limit
            wait = 5 * (attempt + 1)
            print(f"  [429] rate limit, {wait}s 대기 후 재시도")
            time.sleep(wait)
            continue
        raise RuntimeError(f"{kw}: HTTP {resp.status_code} — {resp.text[:200]}")
    raise RuntimeError(f"{kw}: 재시도 초과")


def volume_gate_report(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("검색량 실재 게이트 리포트 (판정 기준: 0이 아닌 주 < 50%)")
    print("=" * 60)
    # ⚠️ 분모 주의 (2026-07-05 수정, Failure #4): 데이터랩은 ratio=0인 주를
    # 응답에서 생략하므로 반환행 기준 비율은 항상 ~100%가 됨.
    # 반드시 요청 기간의 전체 주 수를 분모로 사용한다.
    total_weeks = pd.period_range(START_DATE, END_DATE, freq="W-SUN").size
    flagged = []
    for kw, g in df.groupby("keyword"):
        nonzero = (g["ratio"] > 0).sum() / total_weeks
        line = f"{kw:<20} 0이 아닌 주 {nonzero:6.1%} | max {g['ratio'].max():6.2f} | mean {g['ratio'].mean():6.2f}"
        if nonzero < ZERO_GATE_THRESHOLD:
            flagged.append(kw)
            line += "  ⚠️ 검색량 부재 판정 → 동일 계열 교체 조항 발동 대상"
        print(line)
    print("-" * 60)
    if flagged:
        print(f"⚠️ 교체 판정: {flagged}")
        print("→ decision_log의 동결 예외 조항(D-015)에 따라 동일 계열 내 1회 교체를 진행하고 기록하세요.")
    else:
        print("✅ 전 키워드 게이트 통과 — 유니버스 v1.0 변경 없이 확정")


def main() -> None:
    load_dotenv(ROOT / ".env")
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not cid or not secret:
        raise SystemExit(".env에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET을 설정하세요.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    keywords, done = load_keywords(), load_done()
    todo = [k for k in keywords if k not in done]
    print(f"총 {len(keywords)}개 중 {len(done)}개 완료, {len(todo)}개 수집 시작")

    for i, kw in enumerate(todo, 1):
        rows = fetch_keyword(kw, cid, secret)
        pd.DataFrame(rows).to_csv(OUT_CSV, mode="a", index=False,
                                  header=not OUT_CSV.exists(), encoding="utf-8-sig")
        print(f"[{i}/{len(todo)}] {kw} — {len(rows)}주 저장")
        time.sleep(REQUEST_DELAY_SEC)

    volume_gate_report(pd.read_csv(OUT_CSV))


if __name__ == "__main__":
    main()
