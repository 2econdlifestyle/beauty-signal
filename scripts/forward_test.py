"""
주간 포워드 테스트 (D-033) — 진짜 아웃오브샘플의 축적
- 매주 데이터 갱신 후 실행하면: ①최신 완결 주의 60개 판정을 append-only 로그에 기록
  ②4주가 지난 미채점 행을 정답 규칙(D-005)으로 채점
- 핵심 원칙: 이미 기록된 (period, keyword) 행은 절대 수정하지 않음(판정의 사후 변경 불가).
  채점(hit4 열)만 비어 있던 것을 채움
- 백테스트와 독립: 이 로그의 적중률이 쌓이면 "사후 수정 없는 실전 성적"이 됨
실행: (데이터 갱신 후) python3 scripts/forward_test.py
"""
import csv
from datetime import date
from pathlib import Path

import backtest as bt

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "forward" / "forward_log.csv"
FIELDS = ["logged_at", "period", "keyword", "D", "S", "C", "opportunity", "score",
          "d_ratio", "news_4w", "graded_at", "hit4"]


def load_log():
    if not LOG.exists():
        return []
    with open(LOG, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_log(rows):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    W, S, N, cat = bt.load_matrices()
    today = date.today().isoformat()
    log = load_log()
    seen = {(r["period"], r["keyword"]) for r in log}

    # ① 데이터 최신 완결 주(t = 마지막 인덱스) 기준으로 60개 판정 기록
    #    backtest.compute_rows는 정답 관찰 4주가 필요한 구간까지만 다루므로 여기서 직접 계산
    periods0 = list(W.columns)
    t = len(periods0) - 1
    period = periods0[t]
    added = 0
    for k in sorted(W.index):
        if (period, k) in seen:
            continue
        w = W.loc[k].to_numpy(float)
        n = N.loc[k].to_numpy(float)
        s = S.loc[cat[k]].to_numpy(float)
        ma4, ma12, ma4_ly = bt.ma(w, t, 4), bt.ma(w, t, 12, 4), bt.ma(w, t - 52, 4)
        s4, s12 = bt.ma(s, t, 4), bt.ma(s, t, 12, 4)
        n4 = int(n[t - 3:t + 1].sum()); n12s = n[t - 15:t - 3].sum() / 3.0
        d_r = ma4 / ma12 if ma12 > 0 else 0.0
        D = bool(ma12 >= bt.MIN_BASE and d_r >= bt.D_RATIO and ma4 >= ma4_ly * bt.D_SEASON)
        Ssig = bool(s4 > s12)
        C = bool(n4 >= bt.C_FLOOR and n4 >= bt.C_MULT * n12s)
        opp = D and Ssig and not C
        pt = (40 if d_r >= 1.6 else 30 if d_r >= 1.45 else 20 if d_r >= bt.D_RATIO else 0) \
             + (30 if s4 >= s12 * bt.S_STRONG else 15 if Ssig else 0) \
             + (0 if C else 30 if n4 == 0 else 15)
        log.append({"logged_at": today, "period": period, "keyword": k,
                    "D": D, "S": Ssig, "C": C, "opportunity": opp,
                    "score": pt if opp else "", "d_ratio": round(d_r, 3) if ma12 > 0 else "",
                    "news_4w": n4, "graded_at": "", "hit4": ""})
        added += 1

    # ② 4주 경과 행 채점 (기록은 불변, hit4만 채움)
    Wp = W  # keyword × period 매트릭스
    periods = list(Wp.columns)
    graded = 0
    for r in log:
        if r["hit4"] != "" or r["period"] not in periods:
            continue
        t = periods.index(r["period"])
        if t + 4 >= len(periods):
            continue  # 아직 4주 관찰 불가
        w = Wp.loc[r["keyword"]].to_numpy(float)
        past4 = w[t - 3:t + 1].mean()
        if past4 <= 0:
            r["hit4"], r["graded_at"] = "NA", today
            continue
        r["hit4"] = str(bool(w[t + 1:t + 5].mean() >= past4 * bt.GT_KEEP))
        r["graded_at"] = today
        graded += 1

    save_log(log)
    n_opp = sum(1 for r in log if r["opportunity"] in (True, "True"))
    opp_graded = [r for r in log if r["opportunity"] in (True, "True") and r["hit4"] in ("True", "False")]
    hits = sum(1 for r in opp_graded if r["hit4"] == "True")
    print(f"기록 추가 {added}행 (주차 {period}) · 채점 {graded}행")
    print(f"누적: {len(log)}행 · 기회 신호 {n_opp}건 · 채점 완료 기회 {len(opp_graded)}건"
          + (f" (적중 {hits}, {hits/len(opp_graded):.1%})" if opp_graded else ""))
    print(f"로그: {LOG} (append-only — 기존 행 수정 금지)")


if __name__ == "__main__":
    main()
