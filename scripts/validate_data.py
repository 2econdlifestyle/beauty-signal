"""
3단계 데이터 검증 (2026-07-05)
- 대상: data/raw/{search_trend, shopping_click, news_weekly, keyword_category_map}.csv
- 점검: ①스키마/중복/값 범위 ②주차 정합(156주, 월요일 시작, 연속) ③키워드/매핑 커버리지
        ④데이터랩 0인 주 생략 → 전체 주 리인덱스(0 채움) ⑤이상 징후 플래그 (D-012 이식)
        ⑥게이트 로직 자체 테스트 (Failure #4 교훈 — 인위적 결측 케이스로 발동 확인)
- 산출: data/processed/search_trend_filled.csv (0 채움본, 신호 계산용)
        data/processed/anomaly_flags.csv (이상 징후 플래그)
        콘솔 리포트 (docs/04_data_validation.md에 편집 수록)
실행: python3 scripts/validate_data.py
"""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
START = date(2023, 7, 3)
N_WEEKS = 157
PERIODS = [(START + timedelta(weeks=i)).isoformat() for i in range(N_WEEKS)]
GATE_THRESHOLD = 0.5
SPIKE_PCT = 0.8  # D-012: 전주 대비 ±80% 급변 플래그


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    return cond


def gate_share(series_nonzero_count: int) -> float:
    """검색량 실재 게이트: 0이 아닌 주 / 전체 주 (Failure #4 정정 로직)"""
    return series_nonzero_count / N_WEEKS


def main():
    fails = 0
    st = pd.read_csv(RAW / "search_trend.csv")
    sc = pd.read_csv(RAW / "shopping_click.csv")
    nw = pd.read_csv(RAW / "news_weekly.csv")
    km = pd.read_csv(RAW / "keyword_category_map.csv")

    print("=" * 70)
    print("① 스키마 / 중복 / 값 범위")
    print("=" * 70)
    fails += not check("search_trend 스키마", list(st.columns) == ["keyword", "period", "ratio"])
    fails += not check("shopping_click 스키마", list(sc.columns) == ["category", "period", "ratio"])
    fails += not check("news_weekly 스키마", list(nw.columns) == ["keyword", "period", "count"])
    fails += not check("중복 (keyword, period) 없음",
                       not st.duplicated(["keyword", "period"]).any()
                       and not sc.duplicated(["category", "period"]).any()
                       and not nw.duplicated(["keyword", "period"]).any())
    fails += not check("결측값 없음", st.isna().sum().sum() == 0 and sc.isna().sum().sum() == 0 and nw.isna().sum().sum() == 0)
    fails += not check("search_trend ratio 범위 (0, 100]",
                       (st.ratio > 0).all() and (st.ratio <= 100).all(),
                       "데이터랩은 0인 주를 생략하므로 0 값이 있으면 오히려 이상")
    fails += not check("shopping_click ratio 범위 (0, 100]", (sc.ratio > 0).all() and (sc.ratio <= 100).all())
    fails += not check("news_weekly count 음수 없음·정수", (nw["count"] >= 0).all() and (nw["count"] % 1 == 0).all())
    fails += not check("키워드별 최대 ratio = 100 (1키워드 1요청 검증, D-016)",
                       (st.groupby("keyword").ratio.max().round(0) == 100).all(),
                       "각 키워드가 자신의 최대값=100 기준 full range 사용")

    print()
    print("=" * 70)
    print(f"② 주차 정합 ({N_WEEKS}주 · 월요일 시작 · 연속)")
    print("=" * 70)
    fails += not check("표준 주차 목록과 일치 (뉴스)", sorted(nw.period.unique()) == PERIODS)
    fails += not check("표준 주차 목록과 일치 (쇼핑)", sorted(sc.period.unique()) == PERIODS)
    fails += not check("검색 주차 ⊆ 표준 주차", set(st.period) <= set(PERIODS))
    mondays = pd.to_datetime(pd.Series(PERIODS)).dt.dayofweek.eq(0).all()
    fails += not check("전 주차 월요일 시작", mondays)

    print()
    print("=" * 70)
    print("③ 키워드 / 매핑 커버리지")
    print("=" * 70)
    kws = sorted(st.keyword.unique())
    fails += not check("키워드 60개 · 3파일 일치",
                       len(kws) == 60 and kws == sorted(nw.keyword.unique()) == sorted(km.keyword.unique()))
    fails += not check(f"뉴스: 전 키워드 {N_WEEKS}주 완비", (nw.groupby("keyword").size() == N_WEEKS).all())
    fails += not check(f"쇼핑: 7카테고리 × {N_WEEKS}주", sc.category.nunique() == 7 and (sc.groupby("category").size() == N_WEEKS).all())
    fails += not check("키워드→쇼핑 카테고리 매핑 전건 유효", set(km.s_category) <= set(sc.category.unique()))

    print()
    print("=" * 70)
    print("④ 데이터랩 0인 주 생략 → 리인덱스 (0 채움)")
    print("=" * 70)
    OUT.mkdir(parents=True, exist_ok=True)
    idx = pd.MultiIndex.from_product([kws, PERIODS], names=["keyword", "period"])
    filled = st.set_index(["keyword", "period"]).reindex(idx, fill_value=0.0).reset_index()
    filled.to_csv(OUT / "search_trend_filled.csv", index=False, encoding="utf-8-sig")
    n_filled = len(filled) - len(st)
    print(f"0으로 채운 셀: {n_filled}개 / {len(filled)}셀 ({n_filled/len(filled):.1%})")
    incomplete = st.groupby("keyword").size()
    incomplete = incomplete[incomplete < N_WEEKS].sort_values()
    print(f"{N_WEEKS}주 미만 키워드 (0 채움 대상):")
    for k, n in incomplete.items():
        print(f"  - {k}: {n}주 → 게이트 {gate_share(n):.1%}")
    fails += not check("전 키워드 게이트 ≥50% (v1.1 유니버스)",
                       all(gate_share(n) >= GATE_THRESHOLD for n in st.groupby("keyword").size()))

    print()
    print("=" * 70)
    print("⑤ 이상 징후 플래그 (D-012 이식 — 신호 계산 전 데이터 이상 선별)")
    print("=" * 70)
    flags = []
    for k, g in filled.groupby("keyword"):
        s = g.sort_values("period").ratio.reset_index(drop=True)
        # (a) 전주 대비 ±80% 급변 (양쪽 주 모두 유의미한 볼륨일 때만: 노이즈 저감)
        for i in range(1, len(s)):
            prev, cur = s[i-1], s[i]
            if prev >= 5 and abs(cur - prev) / prev >= SPIKE_PCT:
                flags.append({"keyword": k, "period": PERIODS[i], "type": "spike",
                              "detail": f"{prev:.1f}→{cur:.1f} ({(cur-prev)/prev:+.0%})"})
        # (b) 8주 이상 연속 0 (검색 신호 공백 구간)
        run = 0
        for i, v in enumerate(s):
            run = run + 1 if v == 0 else 0
            if run == 8:
                flags.append({"keyword": k, "period": PERIODS[i], "type": "zero_run_8w",
                              "detail": f"~{PERIODS[i]}까지 8주+ 연속 0"})
    fl = pd.DataFrame(flags)
    fl.to_csv(OUT / "anomaly_flags.csv", index=False, encoding="utf-8-sig")
    print(f"플래그 총 {len(fl)}건 → data/processed/anomaly_flags.csv")
    if len(fl):
        print(fl.groupby("type").size().to_string())
        top = fl.groupby("keyword").size().sort_values(ascending=False).head(5)
        print("플래그 다수 키워드:", dict(top))

    print()
    print("=" * 70)
    print("⑥ 게이트 로직 자체 테스트 (Failure #4 교훈)")
    print("=" * 70)
    # 인위적 케이스: 70주만 반환된 키워드 → 반드시 부재 판정이어야 함
    synthetic_returned_weeks = 70
    fails += not check(f"인위적 결측 키워드(70/{N_WEEKS}주)가 부재 판정되는가",
                       gate_share(synthetic_returned_weeks) < GATE_THRESHOLD,
                       f"{gate_share(synthetic_returned_weeks):.1%} < 50%")
    # 구(舊) 로직 재현: 반환행 기준이면 100%가 나와 발동 불가 → 차이를 명시적으로 검증
    old_logic_share = 70 / 70
    fails += not check("구 로직(반환행 분모)이라면 통과로 오판됨을 확인", old_logic_share >= GATE_THRESHOLD,
                       "구 로직은 100% → 발동 불가 (버그 재현 확인)")

    print()
    print("=" * 70)
    print(f"결과: {'전체 통과' if fails == 0 else f'FAIL {fails}건'}")
    print("=" * 70)
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
