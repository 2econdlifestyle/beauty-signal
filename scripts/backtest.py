"""
4단계 ④-1: 규칙 엔진 + 백테스트 (01_design.md 스펙 구현)

신호 정의 (키워드 k, 주 t):
  MA4(t)  = mean(w[t-3..t])          # 최근 4주
  MA12(t) = mean(w[t-15..t-4])       # 직전 12주 (최근 4주와 비중첩 — 구현 결정 D-024)
  D  = MA4 ≥ MA12×1.30  AND  MA4 ≥ MA4(t-52)×1.15   # 계절성 필터: 전년 동일 주차 4주
  S  = 카테고리 MA4 > MA12 (상승)
  C  = 뉴스 sum4 ≥ 2.0×(sum12/12×4)  AND  sum4 ≥ C_FLOOR(4건)   # 절대 하한: 0→소수 건 노이즈 방지 (D-024)
  기회 = D ∧ S ∧ ¬C

정답 (Ground Truth, D-005):
  적중 = mean(w[t+1..t+4]) ≥ MA4(t) × 0.90
  평가 대상 = MA4(t) > 0 인 (k, t)  # 검색 활동이 있는 주만 (0/0 퇴화 방지)

판정 구간: t ∈ [55, 151] (계절성 필터 워밍업 55주 + 정답 관찰 4주 확보) = 2024-07-22 ~ 2026-05-25, 97주
베이스라인: ①무차별(전 평가행 기회) ②D 단독
산출물: data/processed/backtest_signals.csv, data/processed/backtest_summary.json
실행: python scripts/backtest.py
"""
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

START = date(2023, 7, 3)
N_WEEKS = 156
PERIODS = [(START + timedelta(weeks=i)).isoformat() for i in range(N_WEEKS)]

# --- 임계값 (1단계 가설 초기값, D-015 동결 설계) ---
D_RATIO = 1.30       # MA4 / MA12
D_SEASON = 1.15      # MA4 / 전년 동기 MA4
S_RATIO = 1.00       # 상승 (초과)
S_STRONG = 1.20      # S 강도 만점 기준
C_MULT = 2.00        # 뉴스 4주 합 / (직전 12주 평균×4)
C_FLOOR = 4          # C 발동 절대 하한 (건) — 구현 결정 D-024
GT_KEEP = 0.90       # 정답: 이후 4주 평균 ≥ 직전 4주 평균 × 0.90
MIN_BASE = 5.0       # D 분모 최소 볼륨 가드 (D-027): MA12 < 5(자기 스케일 5%)면 비율이
                     # 분모 붕괴로 폭발 → D 판정 보류. 저속노화 신생 구간 거짓 신호 15건의 원인

T_START, T_END = 55, 151          # 판정 구간 (양끝 포함)
T_END_8W = 147                    # 8주 민감도용


def load_matrices():
    st = pd.read_csv(PROC / "search_trend_filled.csv")
    sc = pd.read_csv(RAW / "shopping_click.csv")
    nw = pd.read_csv(RAW / "news_weekly.csv")
    km = pd.read_csv(RAW / "keyword_category_map.csv")
    W = st.pivot(index="keyword", columns="period", values="ratio")[PERIODS]      # 검색
    S = sc.pivot(index="category", columns="period", values="ratio")[PERIODS]     # 쇼핑
    N = nw.pivot(index="keyword", columns="period", values="count")[PERIODS]      # 뉴스
    cat = dict(zip(km.keyword, km.s_category))
    return W, S, N, cat


def ma(arr, t, span, offset=0):
    """arr[t-offset-span+1 .. t-offset] 평균"""
    lo, hi = t - offset - span + 1, t - offset + 1
    return arr[lo:hi].mean()


def compute_rows(W, S, N, cat, d_ratio=D_RATIO, d_season=D_SEASON, min_base=MIN_BASE, gt_keep=GT_KEEP):
    rows = []
    for k in W.index:
        w = W.loc[k].to_numpy(dtype=float)
        n = N.loc[k].to_numpy(dtype=float)
        s = S.loc[cat[k]].to_numpy(dtype=float)
        for t in range(T_START, T_END + 1):
            ma4 = ma(w, t, 4)
            ma12 = ma(w, t, 12, offset=4)
            ma4_ly = ma(w, t - 52, 4)
            s4, s12 = ma(s, t, 4), ma(s, t, 12, offset=4)
            n4 = n[t - 3:t + 1].sum()
            n12_scaled = n[t - 15:t - 3].sum() / 3.0   # 직전 12주 합의 4주 환산
            # --- 신호 ---
            d_r = ma4 / ma12 if ma12 > 0 else (np.inf if ma4 > 0 else 0.0)
            season_ok = ma4 >= ma4_ly * d_season       # ma4_ly=0이면 ma4>0으로 충족
            base_ok = ma12 >= min_base                 # 분모 최소 볼륨 가드 (D-027)
            sig_d = base_ok and (d_r >= d_ratio) and season_ok
            sig_s = s4 > s12 * S_RATIO
            sig_c = (n4 >= C_FLOOR) and (n4 >= C_MULT * n12_scaled)
            opp = sig_d and sig_s and not sig_c
            # --- 신뢰도 (기회 행 기준으로도, 전 행 기록) ---
            pt_d = 40 if d_r >= 1.60 else (30 if d_r >= 1.45 else (20 if d_r >= d_ratio else 0))
            pt_s = 30 if s4 >= s12 * S_STRONG else (15 if sig_s else 0)
            pt_c = 0 if sig_c else (30 if n4 == 0 else 15)
            # --- 정답 ---
            past4 = ma4
            fut4 = w[t + 1:t + 5].mean()
            evaluable = past4 > 0
            hit4 = bool(fut4 >= past4 * gt_keep) if evaluable else None
            hit8 = None
            if evaluable and t <= T_END_8W:
                hit8 = bool(w[t + 1:t + 9].mean() >= past4 * gt_keep)
            rows.append({
                "keyword": k, "period": PERIODS[t], "t": t,
                "ma4": round(ma4, 3), "ma12": round(ma12, 3), "d_ratio": round(d_r, 3) if np.isfinite(d_r) else None,
                "season_ok": season_ok, "base_ok": base_ok, "D": sig_d, "S": sig_s, "C": sig_c, "opportunity": opp,
                "score": pt_d + pt_s + pt_c if opp else None,
                "news_4w": int(n4), "evaluable": evaluable, "hit4": hit4, "hit8": hit8,
            })
    return pd.DataFrame(rows)


def metrics(df, pred_col_or_mask, label):
    ev = df[df.evaluable].copy()
    pred = pred_col_or_mask if isinstance(pred_col_or_mask, pd.Series) else ev[pred_col_or_mask]
    pred = pred.loc[ev.index].astype(bool)
    pos = ev.hit4.astype(bool)
    tp = int((pred & pos).sum()); fp = int((pred & ~pos).sum()); fn = int((~pred & pos).sum())
    n_pred = int(pred.sum())
    prec = tp / n_pred if n_pred else None
    rec = tp / (tp + fn) if (tp + fn) else None
    yearly = n_pred / (len(ev.period.unique()) / 52.0)
    return {"rule": label, "signals": n_pred, "precision": round(prec, 4) if prec is not None else None,
            "recall": round(rec, 4) if rec is not None else None, "signals_per_year": round(yearly, 1)}


def main():
    W, S, N, cat = load_matrices()
    df = compute_rows(W, S, N, cat)
    df.to_csv(PROC / "backtest_signals.csv", index=False, encoding="utf-8-sig")

    ev = df[df.evaluable]
    base_rate = ev.hit4.mean()
    res = []
    res.append(metrics(df, pd.Series(True, index=df.index), "무차별(베이스라인1)"))
    res.append(metrics(df, "D", "D 단독(베이스라인2)"))
    res.append(metrics(df, "opportunity", "기회 = D∧S∧¬C (본 신호)"))

    # 8주 민감도 (t ≤ 147 행만)
    ev8 = df[df.evaluable & df.hit8.notna()]
    def prec8(mask):
        m = mask.loc[ev8.index].astype(bool)
        return round((m & ev8.hit8.astype(bool)).sum() / m.sum(), 4) if m.sum() else None
    sens8 = {"D 단독": prec8(ev8.D), "기회": prec8(ev8.opportunity)}

    # 임계값 그리드 (민감도 분석 — 과적합 방지 위해 주 결과는 초기값 유지)
    grid = []
    for a in (1.20, 1.30, 1.40):
        for b in (1.10, 1.15, 1.20):
            g = compute_rows(W, S, N, cat, d_ratio=a, d_season=b)
            m = metrics(g, "opportunity", f"D≥{a}, 계절≥{b}")
            grid.append(m)

    # 가드 임계값 민감도 (D-027: 사후 규칙 추가이므로 값 선택이 결과를 좌우하지 않음을 확인)
    guard_sens = []
    for mb in (0.0, 3.0, 5.0, 7.0):
        g = compute_rows(W, S, N, cat, min_base=mb)
        m = metrics(g, "opportunity", f"MIN_BASE={mb:g}")
        guard_sens.append(m)

    # 신뢰도 점수 구간별 정밀도 (기회 행)
    opp = df[df.opportunity & df.evaluable].copy()
    bands = {}
    for lo, hi in ((50, 70), (70, 85), (85, 101)):
        b = opp[(opp.score >= lo) & (opp.score < hi)]
        bands[f"{lo}-{hi-1}"] = {"n": len(b), "precision": round(b.hit4.mean(), 4) if len(b) else None}

    summary = {
        "eval_rows": int(len(ev)), "judgment_weeks": f"{PERIODS[T_START]}~{PERIODS[T_END]} (97주)",
        "base_rate_hit4": round(float(base_rate), 4),
        "results": res, "precision_8w": sens8, "grid_sensitivity": grid, "guard_sensitivity": guard_sens,
        "score_bands": bands,
    }
    (PROC / "backtest_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
