"""
통계적 엄밀성 보강 분석 (D-033) — 외부 리뷰 지적 4건에 대한 정면 응답
  ①정밀도의 신뢰구간 ②필터 통과 vs 기각의 유의성 검정
  ③에피소드(연속 신호 묶음) 단위 재집계 — 롤링 신호의 자기상관 반영
  ④정답 임계값(0.90) 민감도
- 외부 패키지 없이 Wilson 구간·2표본 비율 z검정을 직접 구현
산출: data/processed/stats_rigor.json + 콘솔 리포트
실행: python scripts/stats_rigor.py
"""
import json
import math
from pathlib import Path

import backtest as bt

OUT = Path(__file__).resolve().parent.parent / "data" / "processed" / "stats_rigor.json"


def wilson(k, n, z=1.96):
    """Wilson score interval — 소표본에서 정규근사보다 안정적"""
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return {"p": round(p, 4), "lo": round(center - half, 4), "hi": round(center + half, 4), "k": k, "n": n}


def two_prop_z(k1, n1, k2, n2):
    """2표본 비율 z검정 (양측). 귀무가설: p1 == p2"""
    p1, p2 = k1 / n1, k2 / n2
    pool = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se
    p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return {"p1": round(p1, 4), "p2": round(p2, 4), "diff_pp": round((p1 - p2) * 100, 1),
            "z": round(z, 3), "p_value": round(p_val, 4)}


def episodes_of(opp_df, gap=0):
    """키워드별 신호 묶음. gap = 에피소드 내에서 허용하는 신호 공백 주 수
    (gap=0: 연속 주만 한 묶음, gap=1: 1주 쉬고 재발화해도 같은 에피소드, ...)
    에피소드 판정 = 첫 신호 주의 hit4 (담당자가 실제로 반응하는 시점은 첫 신호)"""
    eps = []
    for k, g in opp_df.groupby("keyword"):
        g = g.sort_values("t")
        cur = None
        for _, r in g.iterrows():
            if cur is None or r.t - cur["t_end"] > gap + 1:
                if cur:
                    eps.append(cur)
                cur = {"keyword": k, "t_start": int(r.t), "t_end": int(r.t),
                       "period_start": r.period, "weeks": 1, "first_hit": r.hit4}
            else:
                cur["t_end"] = int(r.t)
                cur["weeks"] += 1
        if cur:
            eps.append(cur)
    return eps


def main():
    W, S, N, cat = bt.load_matrices()
    df = bt.compute_rows(W, S, N, cat)
    ev = df[df.evaluable]
    opp = ev[ev.opportunity]
    rej = ev[ev.D & ~ev.opportunity]

    print("=" * 66)
    print("① 정밀도 신뢰구간 (Wilson 95%)")
    print("=" * 66)
    ci_opp = wilson(int(opp.hit4.sum()), len(opp))
    ci_d = wilson(int(ev[ev.D].hit4.sum()), int(ev.D.sum()))
    print(f"기회 신호: {ci_opp['k']}/{ci_opp['n']} = {ci_opp['p']:.1%} [ {ci_opp['lo']:.1%} ~ {ci_opp['hi']:.1%} ]")
    print(f"D 발동 전체: {ci_d['k']}/{ci_d['n']} = {ci_d['p']:.1%} [ {ci_d['lo']:.1%} ~ {ci_d['hi']:.1%} ]")

    print()
    print("=" * 66)
    print("② 유의성 검정 — 필터 통과(기회) vs 기각 (서로소 집단, D 발동 내)")
    print("=" * 66)
    test = two_prop_z(int(opp.hit4.sum()), len(opp), int(rej.hit4.sum()), len(rej))
    print(f"통과 {test['p1']:.1%} vs 기각 {test['p2']:.1%} → 차이 +{test['diff_pp']}%p, z={test['z']}, p={test['p_value']}")
    verdict = "유의 (p<0.05)" if test["p_value"] < 0.05 else "유의하지 않음 (p≥0.05)"
    print("판정:", verdict)

    print()
    print("=" * 66)
    print("③ 에피소드 단위 재집계 (연속 주 신호 = 1건, 첫 신호로 판정)")
    print("=" * 66)
    eps = episodes_of(opp)
    ep_hit = sum(1 for e in eps if e["first_hit"])
    ci_ep = wilson(ep_hit, len(eps))
    lens = [e["weeks"] for e in eps]
    print(f"주 단위 82건 → 에피소드 {len(eps)}건 (평균 {sum(lens)/len(lens):.1f}주, 최장 {max(lens)}주)")
    print(f"에피소드 적중률(첫 신호 기준): {ep_hit}/{len(eps)} = {ci_ep['p']:.1%} [ {ci_ep['lo']:.1%} ~ {ci_ep['hi']:.1%} ]")
    print(f"키워드 커버: {len(set(e['keyword'] for e in eps))}개")
    # 에피소드 수준 베이스라인: D 발동 에피소드의 첫 신호 적중률
    eps_d = episodes_of(ev[ev.D])
    epd_hit = sum(1 for e in eps_d if e["first_hit"])
    ci_epd = wilson(epd_hit, len(eps_d))
    print(f"베이스라인 — D 발동 에피소드: {epd_hit}/{len(eps_d)} = {ci_epd['p']:.1%} [ {ci_epd['lo']:.1%} ~ {ci_epd['hi']:.1%} ]")
    ep_test = two_prop_z(ep_hit, len(eps), epd_hit, len(eps_d))
    print(f"에피소드 수준 개선: +{(ci_ep['p']-ci_epd['p'])*100:.1f}%p (z={ep_test['z']}, p={ep_test['p_value']})")
    # 에피소드 정의(허용 공백) 민감도 — n이 정의에 민감한지 확인
    gap_sens = []
    for gp in (0, 1, 2):
        e_o = episodes_of(opp, gap=gp); e_d = episodes_of(ev[ev.D], gap=gp)
        ho = sum(1 for e in e_o if e["first_hit"]); hd = sum(1 for e in e_d if e["first_hit"])
        gap_sens.append({"gap": gp, "n": len(e_o), "hit_rate": round(ho/len(e_o), 4),
                         "baseline_n": len(e_d), "baseline_rate": round(hd/len(e_d), 4),
                         "gain_pp": round((ho/len(e_o) - hd/len(e_d))*100, 1)})
        print(f"  갭 허용 {gp}주: 기회 {len(e_o)}건 {ho/len(e_o):.1%} vs D {len(e_d)}건 {hd/len(e_d):.1%} → +{(ho/len(e_o)-hd/len(e_d))*100:.1f}%p")

    print()
    print("=" * 66)
    print("④ 정답 임계값 민감도 (기준: 이후 4주 평균 ≥ 직전 4주 × K)")
    print("=" * 66)
    gt_sens = []
    for gt in (0.85, 0.90, 0.95, 1.00):
        g = bt.compute_rows(W, S, N, cat, gt_keep=gt)
        ge = g[g.evaluable]
        go, gd = ge[ge.opportunity], ge[ge.D]
        row = {"gt": gt,
               "opp": round(float(go.hit4.mean()), 4),
               "d_only": round(float(gd.hit4.mean()), 4),
               "gain_pp": round((float(go.hit4.mean()) - float(gd.hit4.mean())) * 100, 1)}
        gt_sens.append(row)
        tag = " (채택)" if gt == 0.90 else ""
        print(f"K={gt:.2f}{tag}: 기회 {row['opp']:.1%} vs D단독 {row['d_only']:.1%} → +{row['gain_pp']}%p")

    result = {"ci_opportunity": ci_opp, "ci_d_fired": ci_d, "pass_vs_reject": test,
              "episodes": {"n": len(eps), "hit": ep_hit, "ci": ci_ep,
                           "avg_weeks": round(sum(lens)/len(lens), 1), "max_weeks": max(lens),
                           "keywords": len(set(e['keyword'] for e in eps)),
                           "baseline_d": ci_epd, "vs_baseline": ep_test, "gap_sensitivity": gap_sens},
              "gt_sensitivity": gt_sens}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()
