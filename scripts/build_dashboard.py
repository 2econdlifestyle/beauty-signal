"""
4단계 ④-2: 대시보드 빌드 — 정적 단일 HTML 생성 (D-026)
- 디자인 v2 (2026-07-05): awwwards 수상작 레퍼런스(Bevel Health — HM, 헬스 데이터 제품) 문법 적용
  소프트 오로라 그라디언트 · 초대형 타이포 · 링 게이지 · 카운트업 · 스크롤 리빌, 라이트 테마
- 이원화(D-001): 상시 뷰(최신 주 전 키워드 판정 상태) + 이벤트성 판정 카드(기회 발생 건)
- 데이터 임베드 방식: 외부 서버·API 불필요 → GitHub Pages 게시 가능
실행: python3 scripts/build_dashboard.py  →  dashboard/beauty-signal.html
"""
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
OUT_DIR = ROOT / "dashboard"

START = date(2023, 7, 3)
N_WEEKS = 157
PERIODS = [(START + timedelta(weeks=i)).isoformat() for i in range(N_WEEKS)]

D_RATIO, D_SEASON, S_STRONG, C_MULT, C_FLOOR, GT_KEEP = 1.30, 1.15, 1.20, 2.00, 4, 0.90
MIN_BASE = 5.0  # D 분모 최소 볼륨 가드 (D-027) — backtest.py와 동일
T_MIN, T_MAX, T_GT_MAX = 55, 156, 152


def ma(arr, t, span, offset=0):
    return arr[t - offset - span + 1: t - offset + 1].mean()


def main():
    W = pd.read_csv(PROC / "search_trend_filled.csv").pivot(index="keyword", columns="period", values="ratio")[PERIODS]
    S = pd.read_csv(RAW / "shopping_click.csv").pivot(index="category", columns="period", values="ratio")[PERIODS]
    N = pd.read_csv(RAW / "news_weekly.csv").pivot(index="keyword", columns="period", values="count")[PERIODS]
    km = pd.read_csv(RAW / "keyword_category_map.csv")
    kw_meta = pd.read_csv(ROOT / "scripts" / "keywords_v1.csv")
    cat = dict(zip(km.keyword, km.s_category))
    seg = dict(zip(kw_meta.keyword, kw_meta.segment))
    summary = json.loads((PROC / "backtest_summary.json").read_text(encoding="utf-8"))
    stats_path = PROC / "stats_rigor.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else None

    latest, cards = [], []
    for k in sorted(W.index):
        w = W.loc[k].to_numpy(float)
        n = N.loc[k].to_numpy(float)
        s = S.loc[cat[k]].to_numpy(float)
        for t in range(T_MIN, T_MAX + 1):
            ma4, ma12, ma4_ly = ma(w, t, 4), ma(w, t, 12, 4), ma(w, t - 52, 4)
            s4, s12 = ma(s, t, 4), ma(s, t, 12, 4)
            n4 = int(n[t - 3:t + 1].sum()); n12s = n[t - 15:t - 3].sum() / 3.0
            d_r = ma4 / ma12 if ma12 > 0 else (99.0 if ma4 > 0 else 0.0)
            season = ma4 >= ma4_ly * D_SEASON
            season_r = (ma4 / ma4_ly) if ma4_ly >= 1.0 else None  # 전년 볼륨 미미 → 배율 무의미(신규)
            D = bool(ma12 >= MIN_BASE and d_r >= D_RATIO and season)
            Ssig = bool(s4 > s12)
            C = bool(n4 >= C_FLOOR and n4 >= C_MULT * n12s)
            opp = D and Ssig and not C
            pt_d = 40 if d_r >= 1.6 else (30 if d_r >= 1.45 else (20 if d_r >= D_RATIO else 0))
            pt_s = 30 if s4 >= s12 * S_STRONG else (15 if Ssig else 0)
            pt_c = 0 if C else (30 if n4 == 0 else 15)
            score = pt_d + pt_s + pt_c
            hit = None
            if t <= T_GT_MAX and ma4 > 0:
                hit = bool(w[t + 1:t + 5].mean() >= ma4 * GT_KEEP)
            rec = {
                "k": k, "t": t, "period": PERIODS[t], "D": D, "S": Ssig, "C": C, "opp": opp,
                "dr": None if not np.isfinite(d_r) else round(float(d_r), 2),
                "sr": None if season_r is None else round(float(season_r), 2),
                "s4v12": round(float(s4 / s12), 2) if s12 > 0 else None,
                "n4": n4, "n12s": round(float(n12s), 1), "score": score, "hit": hit,
            }
            if t == T_MAX:
                latest.append(rec)
            if opp:
                cards.append(rec)

    cards.sort(key=lambda r: (-r["t"], -r["score"]))

    # 교차검증 기여 분해 (백테스트 산출물에서 동적 계산)
    sig = pd.read_csv(PROC / "backtest_signals.csv")
    ev = sig[sig.evaluable]
    filt = ev[ev.D & ~ev.opportunity]
    decomp = {"d_total": int(ev.D.sum()), "d_hit": round(float(ev[ev.D].hit4.mean()), 4),
              "rej_n": int(len(filt)), "rej_hit": round(float(filt.hit4.mean()), 4)}

    data = {
        "decomp": decomp,
        "stats": stats,
        "built": date.today().isoformat(),
        "periods": PERIODS,
        "latest_period": PERIODS[T_MAX],
        "segments": seg, "categories": cat,
        "search": {k: [round(float(x), 1) for x in W.loc[k].to_numpy(float)] for k in W.index},
        "latest": latest, "cards": cards, "summary": summary,
        "thresholds": {"D": D_RATIO, "season": D_SEASON, "C_mult": C_MULT, "C_floor": C_FLOOR},
    }

    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "beauty-signal.html").write_text(html, encoding="utf-8")
    n_opp_latest = sum(1 for r in latest if r["opp"])
    print(f"dashboard/beauty-signal.html 생성 — 최신 주 {PERIODS[T_MAX]}: 기회 {n_opp_latest}건 / 카드 총 {len(cards)}건")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#FBF8F5">
<meta name="description" content="네이버 검색·쇼핑·뉴스 데이터를 교차검증해 K-뷰티 키워드의 진입 기회를 판정하고, 그 적중률을 2년 백테스트로 증명한 대시보드. 실패 사례까지 전부 공개합니다.">
<meta property="og:title" content="뷰티시그널 — 백테스트로 검증된 K-뷰티 진입 타이밍 신호">
<meta property="og:description" content="기회 판정 적중률 67.1% (독립 사건 기준 59.4%) — 검증 방법론과 실패 사례까지 전부 공개. 규칙 기반, 비 블랙박스.">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='9' fill='%23E4577F'/%3E%3Ccircle cx='16' cy='16' r='14' fill='none' stroke='%23FCE9EF' stroke-width='3'/%3E%3C/svg%3E">
<title>뷰티시그널 — 백테스트로 검증된 K-뷰티 진입 타이밍 신호</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>
:root{
  --bg:#FBF8F5; --ink:#17141C; --sub:#75707D; --faint:#A9A4B0;
  --line:rgba(23,20,28,.09); --card:#FFFFFF;
  --rose:#E4577F; --rose-deep:#C93A64; --rose-soft:#FCE9EF;
  --ok:#0E9F73; --ok-soft:#E4F6EE; --no:#DE4D3B; --no-soft:#FCEAE6;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  --r:24px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--ink);font-family:"Pretendard Variable",Pretendard,-apple-system,"Apple SD Gothic Neo",sans-serif;line-height:1.55;-webkit-font-smoothing:antialiased;overflow-x:hidden;
  word-break:keep-all;overflow-wrap:break-word} /* 한국어 단어 중간 줄바꿈 방지 ("키워/드" 현상) */
::selection{background:var(--rose-soft)}
:focus-visible{outline:2px solid var(--rose);outline-offset:2px;border-radius:6px} /* 키보드 사용자 포커스 표시 */

/* ---------- header ---------- */
header{position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:50;display:flex;align-items:center;gap:18px;
  background:rgba(255,255,255,.72);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border:1px solid var(--line);border-radius:999px;padding:10px 12px 10px 20px;box-shadow:0 8px 30px rgba(23,20,28,.06);
  transition:transform .35s cubic-bezier(.2,.7,.3,1),opacity .3s}
header.hide{transform:translate(-50%,-90px);opacity:0;pointer-events:none}
.logo{display:flex;align-items:center;gap:9px;font-weight:800;letter-spacing:-.02em;font-size:15px;white-space:nowrap}
.logo i{width:10px;height:10px;border-radius:50%;background:var(--rose);display:inline-block;box-shadow:0 0 0 4px var(--rose-soft)}
.hdr-chip{font-family:var(--mono);font-size:11px;color:var(--sub);background:#F4F0EC;border-radius:999px;padding:6px 12px;white-space:nowrap}

/* ---------- hero ---------- */
.hero{position:relative;padding:150px 24px 64px;text-align:center;overflow:hidden}
.aurora{position:absolute;inset:0;z-index:-1;pointer-events:none}
.aurora b{position:absolute;border-radius:50%;filter:blur(90px);opacity:.55;animation:float 16s ease-in-out infinite alternate}
.aurora b:nth-child(1){width:560px;height:460px;left:-120px;top:-80px;background:#FFD9E4}
.aurora b:nth-child(2){width:520px;height:480px;right:-140px;top:-40px;background:#E6DCFF;animation-delay:-5s}
.aurora b:nth-child(3){width:640px;height:400px;left:30%;top:200px;background:#D8F1E6;animation-delay:-9s;opacity:.5}
@keyframes float{from{transform:translate(0,0) scale(1)}to{transform:translate(40px,28px) scale(1.08)}}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.22em;color:var(--sub);text-transform:uppercase;margin-bottom:22px}
h1{font-size:clamp(44px,7.2vw,86px);font-weight:800;letter-spacing:-.045em;line-height:1.04}
h1 .q{color:var(--rose)}
.hero p.sub{max-width:560px;margin:22px auto 0;color:var(--sub);font-size:16px}
.hero p.sub b{color:var(--ink);font-weight:700}

/* how-to steps */
.how{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;max-width:1072px;margin:44px auto 0;text-align:left}
@media(max-width:760px){.how{grid-template-columns:1fr}}
.how-step{background:rgba(255,255,255,.66);backdrop-filter:blur(10px);border:1px solid var(--line);border-radius:18px;padding:18px 18px 16px}
.how-step i{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:var(--ink);color:#fff;font-style:normal;font-family:var(--mono);font-size:11.5px;font-weight:700;margin-bottom:10px}
.how-step b{display:block;font-size:14.5px;font-weight:800;letter-spacing:-.01em;margin-bottom:5px}
.how-step span{font-size:12.5px;color:var(--sub);line-height:1.6}
.how-step em{font-style:normal;color:var(--rose);font-weight:700}

/* stat strip */
.stats{display:flex;flex-wrap:wrap;justify-content:center;gap:0;margin:56px auto 0;max-width:1072px;background:rgba(255,255,255,.66);
  backdrop-filter:blur(10px);border:1px solid var(--line);border-radius:var(--r);box-shadow:0 20px 60px rgba(23,20,28,.07)}
.stat{flex:1;min-width:150px;padding:26px 12px;position:relative}
.stat+.stat:before{content:"";position:absolute;left:0;top:22%;height:56%;width:1px;background:var(--line)}
@media(max-width:680px){
  .stat{flex:1 1 45%}
  .stat:nth-child(3):before{display:none} /* 2×2 배치 시 줄 시작 칸의 세로선 제거 */
}
.stat b{display:block;font-size:clamp(26px,3.4vw,40px);font-weight:800;letter-spacing:-.03em;font-variant-numeric:tabular-nums;
  height:clamp(32px,4.2vw,48px);line-height:clamp(32px,4.2vw,48px)} /* 4칸 동일 라인 박스 — 크기가 달라도 베이스라인 통일 */
.stat b.date{font-size:clamp(16px,1.9vw,21px);font-family:var(--mono);font-weight:700;letter-spacing:.02em}
.stat b em{font-style:normal;color:var(--rose)}
.stat b span{font:inherit;display:inline}
.stat b small{font-size:.55em}
.stat > span{display:block;font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;color:var(--sub);margin-top:6px;text-transform:uppercase}
.stats-note{max-width:640px;margin:16px auto 0;font-size:12px;color:var(--sub);line-height:1.65}
.stats-note b{color:var(--ink)}

/* ---------- nav tabs ---------- */
.tabs-wrap{position:sticky;top:0;z-index:40;padding:14px 0 12px;background:linear-gradient(var(--bg) 65%,transparent)}
.tabs{display:flex;gap:6px;width:max-content;margin:0 auto;background:#F1EDE9;border-radius:999px;padding:5px}
.tab{border:0;cursor:pointer;font:inherit;font-size:13.5px;font-weight:600;color:var(--sub);padding:9px 20px;border-radius:999px;background:transparent;transition:.25s}
.tab.on{background:var(--ink);color:#fff;box-shadow:0 4px 14px rgba(23,20,28,.22)}

/* ---------- layout ---------- */
.wrap{max-width:1120px;margin:0 auto;padding:34px 24px 90px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:0 2px 6px rgba(23,20,28,.03)}
.note{max-width:760px;margin:0 auto 26px;text-align:center;color:var(--sub);font-size:14px}
.note b{color:var(--ink)}
.note .f{font-family:var(--mono);font-size:12px;background:#F4F0EC;border-radius:6px;padding:2px 7px;color:var(--ink)}

/* legend — 4카드 내부 그리드 통일: [배지 44px | 텍스트], 제목·설명 왼쪽 라인 동일 */
.legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:0 0 22px}
.legend>div{display:grid;grid-template-columns:44px 1fr;column-gap:2px;align-items:start;
  background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 16px;font-size:12.5px}
.legend i{grid-row:1 / span 2;justify-self:start;margin-top:1px;font-style:normal} /* <i> 기본 이탤릭 제거 */
.legend b{grid-column:2;font-size:13px;letter-spacing:-.01em;line-height:1.7}
.legend span{grid-column:2;color:var(--sub);margin-top:3px;line-height:1.55}

/* ---------- today table ---------- */
.tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.tbl th{font-family:var(--mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);font-weight:500;text-align:left;padding:16px 14px;border-bottom:1px solid var(--line)}
.tbl td{padding:11px 14px;border-bottom:1px solid var(--line);white-space:nowrap;font-variant-numeric:tabular-nums}
.tbl tr:last-child td{border-bottom:0}
.tbl tr{transition:background .2s}
.tbl tbody tr:hover{background:#FAF6F3}
.tbl tr.opp{background:linear-gradient(90deg,var(--rose-soft),transparent 70%)}
.kwd{font-weight:700;letter-spacing:-.01em}
.seg{font-family:var(--mono);font-size:10.5px;color:var(--faint)}
.chip{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:7px;font-family:var(--mono);font-size:10px;font-weight:700;font-style:normal;background:#F1EDE9;color:var(--faint)}
.chip.d{background:var(--ok-soft);color:var(--ok)} .chip.s{background:#E8ECFB;color:#4059C9} .chip.c{background:var(--no-soft);color:var(--no)}
.pill{border-radius:999px;padding:4px 12px;font-size:11.5px;font-weight:700;font-style:normal}
.pill.o{background:var(--rose);color:#fff}
.pill.x{background:#F1EDE9;color:var(--faint)}
.num{font-family:var(--mono);font-size:12px}

/* ---------- filter bar (조건 검색) ---------- */
.fbar{display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin:0 auto 20px}
.fbar input[type=search]{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:999px;
  padding:10px 18px;font:inherit;font-size:13.5px;width:200px;box-shadow:0 2px 6px rgba(23,20,28,.04)}
.fbar input[type=search]:focus{outline:2px solid var(--rose-soft);border-color:var(--rose)}
.fcount{font-family:var(--mono);font-size:11.5px;color:var(--faint);align-self:center;padding:0 4px}
.empty{padding:44px 20px;text-align:center;color:var(--faint);font-size:13.5px}

/* ---------- cards ---------- */
.filter{display:flex;justify-content:center;margin-bottom:22px}
select{appearance:none;background:var(--card) url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6"><path d="M1 1l4 4 4-4" stroke="%2375707D" fill="none" stroke-width="1.5"/></svg>') no-repeat right 16px center;
  color:var(--ink);border:1px solid var(--line);border-radius:999px;padding:10px 42px 10px 18px;font:inherit;font-size:13.5px;cursor:pointer;box-shadow:0 2px 6px rgba(23,20,28,.04)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:22px 22px 16px;position:relative;
  transition:transform .3s cubic-bezier(.2,.7,.3,1),box-shadow .3s;box-shadow:0 2px 6px rgba(23,20,28,.03)}
.card:hover{transform:translateY(-4px);box-shadow:0 22px 44px rgba(23,20,28,.10)}
.card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.card h3{font-size:17.5px;font-weight:800;letter-spacing:-.02em}
.card .wk{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:3px}
.ring{position:relative;width:52px;height:52px;flex:none}
.ring svg{transform:rotate(-90deg)}
.ring .bgc{stroke:#F1EDE9}
.ring .fgc{stroke:var(--rose);stroke-linecap:round;transition:stroke-dashoffset 1.1s cubic-bezier(.2,.7,.3,1)}
.ring b{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:13px;font-weight:700}
.res{display:inline-block;font-size:11px;font-weight:700;border-radius:999px;padding:4px 11px;margin-top:10px}
.res.hit{background:var(--ok-soft);color:var(--ok)} .res.miss{background:var(--no-soft);color:var(--no)} .res.tbd{background:#F1EDE9;color:var(--sub)}
.ev{list-style:none;margin:14px 0 4px;font-size:12.5px;color:var(--sub)}
.ev li{display:flex;gap:9px;align-items:baseline;padding:4.5px 0}
.ev i{flex:none;width:17px;height:17px;border-radius:6px;font-family:var(--mono);font-size:9.5px;font-weight:700;font-style:normal;display:inline-flex;align-items:center;justify-content:center;transform:translateY(2px)}
.ev .id{background:var(--ok-soft);color:var(--ok)} .ev .is{background:#E8ECFB;color:#4059C9} .ev .ic{background:var(--no-soft);color:var(--no)}
.ev b{color:var(--ink);font-variant-numeric:tabular-nums}
svg.spark{display:block;width:100%;margin-top:10px}

/* ---------- simple hero (입문자 뷰 공통) ---------- */
.shero{margin:4px 0 28px;text-align:center;background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:34px 30px;box-shadow:0 2px 6px rgba(23,20,28,.03)}
.shero-badge{display:inline-block;font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--sub);background:#F4F0EC;border-radius:999px;padding:5px 12px;margin-bottom:14px}
.shero-big{font-size:clamp(22px,3.2vw,32px);font-weight:800;letter-spacing:-.03em;line-height:1.3}
.shero-big em{font-style:normal;color:var(--rose)}
.shero p{color:var(--sub);font-size:13.5px;max-width:560px;margin:14px auto 0;line-height:1.7}
.shero p b{color:var(--ink)}

/* ---------- backtest ---------- */
.subtabs{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin:2px 0 30px}
.stab{border:1px solid var(--line);cursor:pointer;font:inherit;font-size:12.5px;font-weight:600;color:var(--sub);
  padding:8px 16px;border-radius:999px;background:var(--card);transition:.25s}
.stab.on{background:var(--rose);border-color:var(--rose);color:#fff;box-shadow:0 4px 14px rgba(228,87,127,.3)}
.steps{display:grid;gap:12px}
.step{display:grid;grid-template-columns:34px 1fr;gap:14px;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.step i{width:26px;height:26px;border-radius:50%;background:var(--ink);color:#fff;font-style:normal;font-family:var(--mono);font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:2px}
.step b{display:block;font-size:14px;letter-spacing:-.01em;margin-bottom:4px}
.step p{font-size:12.5px;color:var(--sub);line-height:1.65}
.step p em{font-style:normal;color:var(--ink);font-weight:700}
.bt-hl{text-align:center;margin:26px auto 44px;max-width:860px}
.bt-hl .big{font-size:clamp(30px,4.6vw,54px);font-weight:800;letter-spacing:-.04em;line-height:1.15}
.bt-hl .big em{font-style:normal;color:var(--rose)}
.bt-hl .exp{color:var(--sub);font-size:14.5px;max-width:640px;margin:18px auto 0}
.bars{margin:0 0 46px;padding:30px 34px}
.bar-row{display:grid;grid-template-columns:150px 1fr 76px;align-items:center;gap:16px;padding:11px 0}
.bar-row+.bar-row{border-top:1px dashed var(--line)}
.bar-row .lb{font-size:13px;font-weight:600;color:var(--sub)}
.bar-row.hero-bar .lb{color:var(--ink);font-weight:800}
.track{height:14px;background:#F1EDE9;border-radius:999px;overflow:hidden}
.fill{height:100%;width:0;border-radius:999px;background:#CFC9C3;transition:width 1.2s cubic-bezier(.2,.7,.3,1)}
.hero-bar .fill{background:linear-gradient(90deg,var(--rose),var(--rose-deep))}
.bar-row .vl{font-family:var(--mono);font-size:13px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.hero-bar .vl{color:var(--rose-deep)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:760px){.grid2{grid-template-columns:1fr}.bar-row{grid-template-columns:104px 1fr 64px}}
.mini{padding:24px 26px}
.mini h4{font-size:14px;font-weight:800;letter-spacing:-.01em;margin-bottom:12px}
.mini table{width:100%;font-size:13px;border-collapse:collapse}
.mini td,.mini th{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;font-variant-numeric:tabular-nums}
.mini th{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);font-weight:500}
.mini tr:last-child td{border-bottom:0}
.mini .warn{color:var(--no);font-weight:700}
.foot-note{max-width:860px;margin:26px auto 0;font-size:12.5px;color:var(--sub);text-align:center}

/* glossary */
.glossary{max-width:1120px;margin:70px auto 0;padding:0 24px}
.glossary h4{font-size:15px;font-weight:800;letter-spacing:-.01em;margin-bottom:14px;text-align:center}
.glossary dl{display:grid;gap:10px}
.glossary dl>div{display:grid;grid-template-columns:120px 1fr;gap:14px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:13px 16px}
@media(max-width:600px){.glossary dl>div{grid-template-columns:1fr;gap:4px}}
.glossary dt{font-weight:800;font-size:13px}
.glossary dd{font-size:12.5px;color:var(--sub);line-height:1.6}

footer{border-top:1px solid var(--line);margin-top:40px;padding:30px 24px 46px;text-align:center;color:var(--faint);font-size:12px;font-family:var(--mono)}
footer a{color:var(--sub)}

/* reveal */
.rv{opacity:0;transform:translateY(16px);transition:opacity .7s ease,transform .7s cubic-bezier(.2,.7,.3,1)}
.rv.in{opacity:1;transform:none}
@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}.rv{opacity:1;transform:none}}
</style>
</head>
<body>
<header>
  <div class="logo"><i></i>뷰티시그널</div>
  <div class="hdr-chip" id="hdrChip"></div>
</header>

<section class="hero">
  <div class="aurora"><b></b><b></b><b></b></div>
  <div class="eyebrow">Beauty Signal · Backtested K-Beauty Entry Signals</div>
  <h1>지금 이 키워드,<br>들어가도 <span class="q">될까?</span></h1>
  <p class="sub">뷰티 브랜드에서 신제품·캠페인을 기획할 때 가장 어려운 질문에 답합니다.
  매주 뷰티 키워드 <b>60개</b>를 네이버 검색·쇼핑·뉴스 데이터로 교차검증해 <b>"기회 O/X"를 자동 판정</b>하고,
  그 판정이 얼마나 맞았는지 <b>과거 2년으로 검증한 성적표</b>까지 함께 공개합니다.</p>
  <div class="how rv">
    <div class="how-step"><i>1</i><b>오늘의 판정 보기</b><span>이번 주 60개 키워드 중 <em>기회</em> 배지가 붙은 키워드가 있는지 확인하세요. 없으면 "이번 주는 서두를 필요 없다"는 뜻입니다.</span></div>
    <div class="how-step"><i>2</i><b>근거 확인하기</b><span>판정 카드에서 왜 기회인지 근거 3줄(수요 급등·구매 관심·경쟁 동향)을 읽고, 점수(0~100)로 규칙 충족 강도를 확인하세요.</span></div>
    <div class="how-step"><i>3</i><b>믿어도 되는지 검증</b><span>백테스트 탭에서 이 판정 방식이 과거 2년간 얼마나 맞았는지 성적표로 직접 확인한 뒤 기획 검토를 시작하세요.</span></div>
  </div>
  <div class="stats rv">
    <div class="stat"><b><em id="st1">0</em><em>%</em></b><span>기회 판정 적중률 (4주 지속)</span></div>
    <div class="stat"><b>+<span id="st2">0</span><small style="font-size:.55em">%p</small></b><span>급등 단독 판정 대비</span></div>
    <div class="stat"><b><span id="st3">0</span><small style="font-size:.55em">건</small></b><span>주 단위 신호 · 독립 32 에피소드</span></div>
    <div class="stat"><b id="st4" class="date"></b><span>최신 판정 주</span></div>
  </div>
  <p class="stats-note rv">위 적중률은 담당자가 매주 받는 <b>주 단위 판정</b> 기준입니다. 연속 신호를 1건으로 묶은
  <b>독립 에피소드 기준으로는 32건 중 19건 = 59.4%</b> — 유리한 쪽만 헤드라인에 올리지 않습니다 (상세: 백테스트 검증 탭)</p>
</section>

<div class="tabs-wrap"><div class="tabs">
  <button class="tab on" data-v="now">오늘의 판정</button>
  <button class="tab" data-v="cards">판정 카드</button>
  <button class="tab" data-v="bt">백테스트 검증</button>
</div></div>

<div class="wrap">
  <div id="v-now"></div>
  <div id="v-cards" style="display:none"></div>
  <div id="v-bt" style="display:none"></div>
</div>

<section class="glossary">
  <h4>처음이라면 — 용어 한 줄 정리</h4>
  <dl>
    <div><dt>기회</dt><dd>수요가 뜨고(D) 구매 관심이 따라오는데(S) 경쟁은 아직 조용한(¬C) 키워드. "신제품·캠페인 기획 검토를 시작할 타이밍"이라는 뜻입니다.</dd></div>
    <div><dt>점수 (0~100)</dt><dd>규칙을 얼마나 강하게 충족했는지. 높을수록 "확실히 맞다"가 아니라 "규칙에 강하게 걸렸다"는 의미입니다 (한계는 백테스트 탭 참고).</dd></div>
    <div><dt>적중 / 실패</dt><dd>기회 판정 4주 뒤에도 검색 수요가 유지·성장했으면 적중, 반짝하고 꺼졌으면 실패로 사후 채점합니다.</dd></div>
    <div><dt>백테스트</dt><dd>이 판정 규칙을 과거 2년치 데이터에 그대로 돌려 "실제로 얼마나 맞았는지" 검증한 것. 성적표를 공개하는 이유는 주장 대신 증명을 하기 위해서입니다.</dd></div>
    <div><dt>무신호</dt><dd>기회가 하나도 없는 주. 도구가 조용한 것도 판정입니다 — 아무 때나 울리는 알림은 신뢰를 깎기 때문입니다.</dd></div>
  </dl>
</section>
<footer>
  DATA: NAVER DATALAB (SEARCH·SHOPPING) + BIGKINDS (NEWS) · RULE: 기회 = D ∧ S ∧ ¬C ·
  <span id="built"></span> · BUILD: scripts/build_dashboard.py
</footer>

<script>
const DATA = __DATA__;
const $ = s => document.querySelector(s);
const fmtP = p => p==null ? "—" : (p*100).toFixed(1)+"%";
const S = DATA.summary, main = S.results[2], dOnly = S.results[1], all = S.results[0];

$("#hdrChip").textContent = "LATEST " + DATA.latest_period;
$("#built").textContent = "BUILT " + DATA.built;

/* ---------- 탭 ---------- */
document.querySelectorAll(".tab").forEach(el=>el.onclick=()=>{
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on")); el.classList.add("on");
  ["now","cards","bt"].forEach(v=>$("#v-"+v).style.display = v===el.dataset.v?"":"none");
  // 깊이 스크롤된 상태에서 탭 전환 시 새 뷰의 시작(탭 바 위치)으로 복귀
  const top = document.querySelector(".hero").offsetHeight - 4;
  if (scrollY > top) scrollTo({top, behavior: "smooth"});
  bindReveal();
});

/* ---------- 스파크라인 (영역 채움 + 판정 주 도트) ---------- */
let gid = 0;
function spark(k, t, w=300, h=56, mark=true){
  const arr = DATA.search[k]; const lo = Math.max(0, t-51), seg = arr.slice(lo, t+1);
  const mx = Math.max(...seg, 1), n = seg.length;
  const X = i => (i/(n-1))*(w-6)+3, Y = v => h-6-(v/mx)*(h-16);
  const pts = seg.map((v,i)=>`${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  const id = "g"+(gid++);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#E4577F" stop-opacity=".22"/><stop offset="1" stop-color="#E4577F" stop-opacity="0"/>
    </linearGradient></defs>
    <polygon points="3,${h-6} ${pts} ${w-3},${h-6}" fill="url(#${id})"/>
    <polyline points="${pts}" fill="none" stroke="#17141C" stroke-width="1.5" stroke-linejoin="round"/>
    ${mark?`<circle cx="${X(n-1)}" cy="${Y(seg[n-1])}" r="3.4" fill="#E4577F" stroke="#fff" stroke-width="1.4"/>`:""}
  </svg>`;
}

/* ---------- 서브탭 공통 헬퍼 ---------- */
function mountSubtabs(rootSel, tabs){
  // tabs: [{id, label, html}]
  const root = $(rootSel);
  root.innerHTML = `
  <div class="subtabs rv">${tabs.map((t,i)=>`<button class="stab ${i===0?'on':''}" data-s="${t.id}">${t.label}</button>`).join("")}</div>
  ${tabs.map((t,i)=>`<div id="${t.id}" ${i?'style="display:none"':''}>${t.html}</div>`).join("")}`;
  root.querySelectorAll(".stab").forEach(el=>el.onclick=()=>{
    root.querySelectorAll(".stab").forEach(x=>x.classList.remove("on")); el.classList.add("on");
    tabs.forEach(t=>$("#"+t.id).style.display = t.id===el.dataset.s?"":"none");
    bindReveal();
  });
}

/* ---------- 오늘의 판정 ---------- */
const SEGS = [...new Set(Object.values(DATA.segments).flatMap(s=>s.split('|')))].sort();
function whyNot(r){
  if(!r.D) return "";
  if(!r.S && r.C) return "검색은 늘었지만 쇼핑 클릭이 아직이고, 경쟁 보도도 급증했어요";
  if(!r.S) return "검색은 늘었지만 실제 쇼핑 클릭이 아직 따라오지 않았어요 — 지켜보는 중";
  if(r.C) return "검색·쇼핑 모두 좋지만 경쟁 보도가 급증 — 이미 늦었을 수 있어요";
  return "";
}
function renderNow(){
  const rows0 = [...DATA.latest].sort((a,b)=>(b.opp-a.opp)||(b.D-a.D)||((b.dr||0)-(a.dr||0)));
  const nOpp = rows0.filter(r=>r.opp).length;
  const opps = rows0.filter(r=>r.opp);
  const watch = rows0.filter(r=>r.D && !r.opp).slice(0,6);

  /* --- 간단히 보기 (입문자·일반) --- */
  const simple = `
  <div class="shero rv">
    <div class="shero-badge">${DATA.latest_period} 주 판정</div>
    <div class="shero-big">${nOpp===0?"이번 주는 <em>서두르지 않아도</em> 됩니다":`지금 검토해볼 키워드가 <em>${nOpp}개</em> 있습니다`}</div>
    <p>뷰티 키워드 60개를 전부 점검했습니다. ${nOpp===0
      ?"세 조건(수요 급등·구매 관심·경쟁 여유)을 모두 충족한 키워드가 없었어요. 조용한 것도 판정입니다 — 무리하게 움직일 이유가 없다는 뜻이니까요."
      :"아래 키워드는 검색이 뜨고, 실제 쇼핑 클릭이 따라오고, 경쟁 보도는 아직 조용합니다."}</p>
  </div>
  ${opps.length?`<div class="cards rv" style="margin-bottom:26px">${opps.map(r=>`
    <div class="card"><div class="card-top"><div><h3>${r.k}</h3><div class="wk">${(DATA.segments[r.k]||'').toUpperCase()}</div>
    <span class="res hit">기회 · 검토 추천</span></div>${ringSVG(r.score)}</div>
    <ul class="ev">
      <li><i class="id">D</i><span>검색이 평소(직전 12주)의 <b>${r.dr==null?'—':'×'+r.dr.toFixed(2)}</b> 수준으로 늘었어요</span></li>
      <li><i class="is">S</i><span>실제 쇼핑 클릭도 함께 늘고 있어요</span></li>
      <li><i class="ic">C</i><span>경쟁 브랜드 보도는 ${r.n4}건 — 아직 조용합니다</span></li>
    </ul>${spark(r.k, DATA.periods.indexOf(r.period))}</div>`).join("")}</div>`:""}
  ${watch.length?`
  <p class="note rv" style="margin-top:8px"><b>기회는 아니지만 움직임이 보이는 키워드</b> — 검색이 늘고 있어서 다음 주가 궁금한 후보들입니다.</p>
  <div class="cards rv">${watch.map(r=>`
    <div class="card"><div class="card-top"><div><h3>${r.k}</h3><div class="wk">${(DATA.segments[r.k]||'').toUpperCase()}</div></div></div>
    <p style="font-size:12.5px;color:var(--sub);margin-top:8px;line-height:1.6">${whyNot(r)}</p>
    ${spark(r.k, DATA.periods.indexOf(r.period))}</div>`).join("")}</div>`
  :(opps.length?"":`<p class="note rv">수요 급등(D) 단계에 들어선 키워드조차 없는 아주 조용한 주입니다.</p>`)}
  <p class="foot-note rv">판정 기준이 궁금하다면 <b>전체 데이터 · 전문가</b> 탭에서 60개 키워드의 신호 상태를 직접 볼 수 있습니다.</p>`;

  /* --- 전체 데이터 (전문가) --- */
  const pro = `
  <p class="note rv">최신 주 <span class="f">${DATA.latest_period}</span> 기준, 키워드 60개의 이번 주 상태입니다.
  ${nOpp===0?"<b>이번 주는 기회 신호가 없습니다</b> — 서두를 필요 없다는 뜻이고, 무신호도 판정입니다.":`이번 주 기회 신호 <b>${nOpp}건</b>이 있습니다.`}</p>
  <div class="legend rv">
    <div><i class="chip d">D</i><b>수요 급등</b><span>사람들이 이 키워드를 갑자기 많이 검색하기 시작했나요? (작년 이맘때의 시즌 효과는 제외)</span></div>
    <div><i class="chip s">S</i><b>구매 관심 동반</b><span>검색만 늘어난 게 아니라, 실제 쇼핑 클릭도 함께 늘고 있나요?</span></div>
    <div><i class="chip c">C</i><b>경쟁 과열 (역신호)</b><span>경쟁 브랜드가 이미 뉴스에 등장하고 있나요? 그렇다면 이미 늦었을 수 있습니다.</span></div>
    <div><i class="pill o" style="padding:3px 8px;font-size:10px">기회</i><b>세 조건 충족</b><span>수요는 뜨는데(D) 지갑도 열리고(S) 경쟁은 아직 조용할 때(C 아님) — 이때만 켜집니다.</span></div>
  </div>
  <div class="fbar rv">
    <input type="search" id="nowQ" placeholder="키워드 검색">
    <select id="nowSeg"><option value="">전체 분야</option>${SEGS.map(s=>`<option>${s}</option>`).join("")}</select>
    <select id="nowState"><option value="">전체 상태</option><option value="opp">기회만</option><option value="d">D 발동</option><option value="s">S 발동</option><option value="c">C 발동</option><option value="quiet">무신호</option></select>
    <span class="fcount" id="nowCount"></span>
  </div>
  <div class="panel rv" style="overflow-x:auto" id="nowTblWrap"></div>`;
  function draw(){
    const q = $("#nowQ").value.trim().toLowerCase();
    const seg = $("#nowSeg").value, st = $("#nowState").value;
    const rows = rows0.filter(r=>{
      if(q && !r.k.toLowerCase().includes(q)) return false;
      if(seg && !(DATA.segments[r.k]||'').split('|').includes(seg)) return false;
      if(st==='opp' && !r.opp) return false;
      if(st==='d' && !r.D) return false;
      if(st==='s' && !r.S) return false;
      if(st==='c' && !r.C) return false;
      if(st==='quiet' && (r.D||r.S||r.C)) return false;
      return true;
    });
    $("#nowCount").textContent = rows.length + '/60';
    $("#nowTblWrap").innerHTML = rows.length ? `
    <table class="tbl"><thead><tr><th>키워드</th><th>분야</th><th title="수요 급등">D</th><th title="구매 관심 동반">S</th><th title="경쟁 과열(역신호)">C</th><th>판정</th><th title="최근 4주 검색량이 직전 12주의 몇 배인지">급등 배율</th><th title="작년 같은 시기 대비 몇 배인지">작년 대비</th><th title="최근 4주 경쟁 브랜드 관련 기사 수">경쟁 기사</th><th style="min-width:190px">최근 1년 검색 추이</th></tr></thead><tbody>
    ${rows.map(r=>`<tr class="${r.opp?'opp':''}">
      <td class="kwd">${r.k}</td><td class="seg">${(DATA.segments[r.k]||'').toUpperCase()}</td>
      <td><span class="chip ${r.D?'d':''}">D</span></td>
      <td><span class="chip ${r.S?'s':''}">S</span></td>
      <td><span class="chip ${r.C?'c':''}">C</span></td>
      <td>${r.opp?`<span class="pill o">기회 ${r.score}</span>`:`<span class="pill x">—</span>`}</td>
      <td class="num">${r.dr==null?'—':'×'+r.dr.toFixed(2)}</td><td class="num">${r.sr==null?'신규':'×'+r.sr.toFixed(2)}</td><td class="num">${r.n4}</td>
      <td>${spark(r.k, DATA.periods.indexOf(r.period), 190, 34, false)}</td>
    </tr>`).join("")}
    </tbody></table>` : `<div class="empty">조건에 맞는 키워드가 없습니다</div>`;
  }
  mountSubtabs("#v-now", [
    {id: "now-simple", label: "간단히 보기", html: simple},
    {id: "now-pro", label: "전체 데이터 · 전문가", html: pro},
  ]);
  ["nowQ","nowSeg","nowState"].forEach(id=>$("#"+id).addEventListener("input", draw));
  draw();
}

/* ---------- 판정 카드 ---------- */
function ringSVG(score){
  const r=21, c=2*Math.PI*r, off=c*(1-score/100);
  return `<div class="ring"><svg width="52" height="52" viewBox="0 0 52 52">
    <circle class="bgc" cx="26" cy="26" r="${r}" fill="none" stroke-width="5"/>
    <circle class="fgc" cx="26" cy="26" r="${r}" fill="none" stroke-width="5" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${c.toFixed(1)}" data-off="${off.toFixed(1)}"/>
  </svg><b>${score}</b></div>`;
}
function cardHTML(c){
  const r = c.hit==null?`<span class="res tbd">관찰 중</span>`:c.hit?`<span class="res hit">적중 · 4주 지속</span>`:`<span class="res miss">실패 · 수요 회귀</span>`;
  return `<div class="card rv">
  <div class="card-top"><div><h3>${c.k}</h3><div class="wk">${c.period} · ${(DATA.segments[c.k]||'').toUpperCase()}</div>${r}</div>${ringSVG(c.score)}</div>
  <ul class="ev">
    <li><i class="id">D</i><span>최근 4주 = 직전 12주의 <b>×${c.dr?.toFixed(2)}</b> · ${c.sr==null?'전년 검색량 없음(신규 키워드)':'전년 동기 ×'+c.sr.toFixed(2)+' 계절성 통과'}</span></li>
    <li><i class="is">S</i><span>${DATA.categories[c.k]} 클릭 4주/12주 <b>×${c.s4v12==null?'—':c.s4v12.toFixed(2)}</b> 동반 상승</span></li>
    <li><i class="ic">C</i><span>경쟁 보도 4주 <b>${c.n4}건</b> — 기준(${Math.max(Math.round(c.n12s*2), DATA.thresholds.C_floor)}건) 미만, 과열 아님</span></li>
  </ul>
  ${spark(c.k, c.t)}
  </div>`;
}
function renderCards(){
  const kws = [...new Set(DATA.cards.map(c=>c.k))].sort();

  /* --- 대표 사례 (입문자·일반) --- */
  const judged = DATA.cards.filter(c=>c.hit!=null);
  const topHits = [...judged].filter(c=>c.hit).sort((a,b)=>(b.score-a.score)||(b.t-a.t)).slice(0,3);
  const topMiss = [...judged].filter(c=>!c.hit).sort((a,b)=>(b.score-a.score)||(b.t-a.t)).slice(0,3);
  const nHit = judged.filter(c=>c.hit).length;
  const simple = `
  <div class="shero rv">
    <div class="shero-badge">지난 2년의 기록</div>
    <div class="shero-big">기회라고 말한 ${judged.length}번 중<br><em>${nHit}번이 실제로 맞았습니다</em></div>
    <p>맞춘 것만 골라 보여주는 성적표는 믿을 수 없죠. 아래에 가장 강하게 "기회"라고 판단했던 사례를
    <b>맞춘 것과 틀린 것 모두</b> 보여드립니다. 각 카드의 곡선은 판정 시점까지 1년의 검색 흐름이고, 배지가 4주 뒤 채점 결과입니다.</p>
  </div>
  <p class="note rv"><b>강하게 확신했고, 실제로 맞은 사례</b> — 판정 4주 뒤에도 수요가 유지·성장했습니다.</p>
  <div class="cards rv" style="margin-bottom:26px">${topHits.map(cardHTML).join("")}</div>
  <p class="note rv"><b>강하게 확신했지만, 틀린 사례</b> — 판정 직후 수요가 꺼졌습니다. 이런 실패도 숨기지 않는 것이 이 도구의 원칙입니다.</p>
  <div class="cards rv">${topMiss.map(cardHTML).join("")}</div>
  <p class="foot-note rv">전체 ${DATA.cards.length}건을 조건별로 탐색하려면 <b>전체 기록 · 전문가</b> 탭을 여세요 — "실패만" 필터도 있습니다.</p>`;

  /* --- 전체 기록 (전문가) --- */
  const pro = `
  <p class="note rv">지난 2년간 '기회'로 판정됐던 <b>${DATA.cards.length}건</b>의 기록입니다. 카드마다 <b>왜 기회로 봤는지 근거 3줄</b>이 붙고,
  오른쪽 원형 점수(0~100)는 규칙을 얼마나 강하게 충족했는지입니다. 상단 배지는 <b>4주 뒤 실제로 수요가 유지됐는지 사후 채점한 결과</b> —
  실패 사례도 숨기지 않고 그대로 보여드립니다.</p>
  <div class="fbar rv">
    <select id="cKw"><option value="">전체 키워드 (${kws.length}개)</option>${kws.map(k=>`<option>${k}</option>`).join("")}</select>
    <select id="cSeg"><option value="">전체 분야</option>${SEGS.map(s=>`<option>${s}</option>`).join("")}</select>
    <select id="cRes"><option value="">전체 결과</option><option value="hit">적중만</option><option value="miss">실패만</option><option value="tbd">관찰 중</option></select>
    <select id="cSort"><option value="latest">최신순</option><option value="score">점수 높은순</option></select>
    <span class="fcount" id="cCount"></span>
  </div>
  <div class="cards" id="cardGrid"></div>`;

  mountSubtabs("#v-cards", [
    {id: "cards-simple", label: "대표 사례", html: simple},
    {id: "cards-pro", label: "전체 기록 · 전문가", html: pro},
  ]);
  const grid = $("#cardGrid");
  function draw(){
    const kw = $("#cKw").value, seg = $("#cSeg").value, res = $("#cRes").value, sort = $("#cSort").value;
    let list = DATA.cards.filter(c=>{
      if(kw && c.k!==kw) return false;
      if(seg && !(DATA.segments[c.k]||'').split('|').includes(seg)) return false;
      if(res==='hit' && c.hit!==true) return false;
      if(res==='miss' && c.hit!==false) return false;
      if(res==='tbd' && c.hit!=null) return false;
      return true;
    });
    if(sort==='score') list = [...list].sort((a,b)=>(b.score-a.score)||(b.t-a.t));
    $("#cCount").textContent = list.length + '/' + DATA.cards.length;
    grid.innerHTML = list.length ? list.map(cardHTML).join("") : `<div class="empty" style="grid-column:1/-1">조건에 맞는 판정이 없습니다</div>`;
    bindReveal();
  }
  ["cKw","cSeg","cRes","cSort"].forEach(id=>$("#"+id).addEventListener("input", draw));
  draw();
}

/* ---------- 백테스트 (서브탭: 성적표 / 검증 방법 / 자세한 결과) ---------- */
function renderBT(){
  const gain = ((main.precision-dOnly.precision)*100).toFixed(1);
  const D = DATA.decomp;

  const sum = `
  <div class="bt-hl rv">
    <div class="big">급등 맥락의 동전 던지기 <em>${fmtP(dOnly.precision)}</em>를<br>교차검증이 <em>${fmtP(main.precision)}</em>로 끌어올립니다</div>
    <p class="exp">${S.judgment_weeks} 주간 롤링 백테스트. 기회 판정 ${main.signals}건 중 ${fmtP(main.precision)}가 이후 4주간
    수요를 유지·성장 — 검색량 급등 하나만 보는 판정 대비 <b style="color:var(--rose-deep)">+${gain}%p</b>.
    8주 기준으로도 ${fmtP(S.precision_8w["기회"])} vs ${fmtP(S.precision_8w["D 단독"])}로 우위가 유지됩니다.${DATA.stats?`
    95% 신뢰구간은 ${fmtP(DATA.stats.ci_opportunity.lo)}~${fmtP(DATA.stats.ci_opportunity.hi)}이며, 필터 통과와 기각의 차이는 통계적으로 유의합니다(p<0.001).
    연속 신호를 1건으로 묶은 <b>독립 에피소드 기준으로는 ${DATA.stats.episodes.n}건 중 ${DATA.stats.episodes.hit}건(${fmtP(DATA.stats.episodes.ci.p)})</b> —
    주 단위를 헤드라인으로 쓰는 이유는 담당자가 실제로 받는 의사결정 단위가 주간 판정이기 때문이며, 두 수치를 항상 병기합니다.`:""}</p>
  </div>
  <div class="panel bars rv">
    <div class="bar-row"><span class="lb">무차별 판정 *</span><div class="track"><div class="fill" data-w="${all.precision*100}"></div></div><span class="vl">${fmtP(all.precision)}</span></div>
    <div class="bar-row"><span class="lb">검색량 급등 단독</span><div class="track"><div class="fill" data-w="${dOnly.precision*100}"></div></div><span class="vl">${fmtP(dOnly.precision)}</span></div>
    <div class="bar-row hero-bar"><span class="lb">기회 = D∧S∧¬C</span><div class="track"><div class="fill" data-w="${main.precision*100}"></div></div><span class="vl">${fmtP(main.precision)}</span></div>
    <p style="font-size:12px;color:var(--faint);margin-top:14px">* 무차별 ${fmtP(all.precision)}는 급등이 없는 평탄한 주가 지배하는 수치 — 정답 정의상 "유지"가 자명하게 참이 되는 구간입니다.
    판정이 실제로 필요한 급등 맥락(D 발동 ${D.d_total}건)의 기저 적중률은 ${fmtP(dOnly.precision)}이며, 이것이 올바른 비교선입니다.</p>
  </div>
  <p class="foot-note rv">이 성적표가 어떻게 나왔는지 궁금하다면 위의 <b>어떻게 검증했나</b>, 숫자를 더 파고들고 싶다면 <b>자세한 결과</b> 탭을 여세요.</p>`;

  const how = `
  <p class="note rv">공정한 성적표를 만들기 위해 지킨 절차입니다. 핵심은 <b>미래 정보를 몰래 쓰지 않는 것</b>과 <b>유리한 문제만 고르지 않는 것</b>.</p>
  <div class="steps rv">
    <div class="step"><i>1</i><div><b>문제지를 먼저 봉인</b><p>키워드 60개를 백테스트 시작 <em>전에</em> 확정하고 이후 추가·삭제를 금지했습니다. 잘된 키워드만 골라 넣는 선택 편향을 차단하기 위해서입니다. 정체·하락 키워드를 절반 이상 일부러 포함했고, 예외적 교체 1회(데이터 부재 키워드)는 사전 정의된 규칙에 따라 이뤄졌으며 이력을 공개합니다.</p></div></div>
    <div class="step"><i>2</i><div><b>매주 롤링 판정</b><p>${S.judgment_weeks} 동안 매주 월요일마다, <em>그 시점까지의 데이터만으로</em> 60개 키워드 전체를 판정했습니다. 총 ${(5820).toLocaleString()}회의 판정 기회 중 규칙(D∧S∧¬C)을 충족한 것이 기회 신호 ${main.signals}건입니다.</p></div></div>
    <div class="step"><i>3</i><div><b>4주 뒤 사후 채점</b><p>기회로 판정한 각 건에 대해 4주를 기다린 뒤 채점했습니다. 정답 기준: <em>이후 4주 검색량 평균 ≥ 직전 4주 평균 × 0.90</em> — 진짜 기회라면 수요가 반짝하고 꺼지지 않아야 하니까요. 1~2주 폭등 후 소멸하는 반짝 밈은 실패로 분류됩니다.</p></div></div>
    <div class="step"><i>4</i><div><b>베이스라인과 비교</b><p>67.1%가 의미 있으려면 비교 대상이 필요합니다. ①모든 키워드를 항상 기회로 보는 무차별 판정 ②검색량 급등(D) 하나만 보는 판정 — 특히 ②가 실전의 대안이며, 교차검증의 기여는 ②와의 차이(+${gain}%p)로 측정합니다.</p></div></div>
    <div class="step"><i>5</i><div><b>민감도와 사후 수정까지 공개</b><p>임계값을 바꿔도 결과가 흔들리지 않는지(그리드 3×3), 관찰 기간을 8주로 늘려도 우위가 유지되는지 확인했습니다. 백테스트 후 발견된 버그(신생 키워드 분모 붕괴)의 수정은 <em>전/후 수치를 함께 공개</em>해 유리한 쪽만 보여주지 않았습니다 — 전체 기록은 저장소 docs/decision_log.md에 있습니다.</p></div></div>
  </div>
  <p class="foot-note rv">한계도 명시합니다: 정답이 매출이 아닌 검색 수요 지속성(공개 매출 데이터 부재), 유니버스 구성에 남는 사후 지식 편향, 97주라는 검증 기간. 완전한 목록: 저장소 README의 "한계" 섹션.</p>`;

  const gridRows = S.grid_sensitivity.map(g=>`<tr><td>${g.rule}</td><td>${g.signals}</td><td>${fmtP(g.precision)}</td></tr>`).join("");
  const guardRows = (S.guard_sensitivity||[]).map(g=>`<tr><td>${g.rule.replace('MIN_BASE=','가드 ')}${g.rule==='MIN_BASE=5'?' (채택)':''}</td><td>${g.signals}</td><td>${fmtP(g.precision)}</td></tr>`).join("");
  const deep = `
  <p class="note rv">규칙별 성능부터 민감도까지, 성적표 뒤의 전체 숫자입니다. 실패를 포함한 원자료는 <b>판정 카드</b> 탭에서 건별로 볼 수 있습니다.</p>
  <div class="grid2" style="margin-bottom:18px">
    <div class="panel mini rv">
      <h4>규칙별 성능</h4>
      <table><thead><tr><th>규칙</th><th>신호</th><th>4주 적중률</th><th>8주</th><th>연간</th></tr></thead><tbody>
        <tr><td>무차별</td><td>${all.signals}</td><td>${fmtP(all.precision)}</td><td>—</td><td>—</td></tr>
        <tr><td>D 단독</td><td>${dOnly.signals}</td><td>${fmtP(dOnly.precision)}</td><td>${fmtP(S.precision_8w["D 단독"])}</td><td>${dOnly.signals_per_year}건</td></tr>
        <tr><td><b>기회 = D∧S∧¬C</b></td><td><b>${main.signals}</b></td><td style="color:var(--ok);font-weight:700">${fmtP(main.precision)}</td><td>${fmtP(S.precision_8w["기회"])}</td><td>${main.signals_per_year}건</td></tr>
      </tbody></table>
    </div>
    <div class="panel mini rv">
      <h4>교차검증 기여 분해 — 필터는 나쁜 신호를 골라 버린다</h4>
      <table><thead><tr><th>구분</th><th>건수</th><th>적중률</th></tr></thead><tbody>
        <tr><td>D 발동 전체</td><td>${D.d_total}</td><td>${fmtP(D.d_hit)}</td></tr>
        <tr><td>ㄴ S·C 필터로 기각</td><td>${D.rej_n}</td><td class="warn">${fmtP(D.rej_hit)}</td></tr>
        <tr><td>ㄴ 필터 통과 = 기회</td><td>${main.signals}</td><td style="color:var(--ok);font-weight:700">${fmtP(main.precision)}</td></tr>
      </tbody></table>
      <p style="font-size:12px;color:var(--sub);margin-top:10px">기각된 신호의 적중률(${fmtP(D.rej_hit)})이 통과 신호(${fmtP(main.precision)})의 절반 수준 — 필터가 무작위로 줄인 게 아니라는 직접 증거입니다.</p>
    </div>
    <div class="panel mini rv">
      <h4>임계값 민감도 (그리드 3×3)</h4>
      <table><thead><tr><th>조건</th><th>신호</th><th>적중률</th></tr></thead><tbody>${gridRows}</tbody></table>
      <p style="font-size:12px;color:var(--sub);margin-top:10px">어떤 조합에서도 64~67%로 안정 — 채택값(D≥1.3, 계절≥1.15)은 사후 튜닝이 아니라 설계 때의 초기 가설값입니다.</p>
    </div>
    <div class="panel mini rv">
      <h4>분모 붕괴 가드 전/후 (사후 수정 공개)</h4>
      <table><thead><tr><th>조건</th><th>신호</th><th>적중률</th></tr></thead><tbody>${guardRows}</tbody></table>
      <p style="font-size:12px;color:var(--sub);margin-top:10px">신생 키워드의 분모(직전 12주 평균)가 0에 수렴해 배율이 폭발하던 버그를 가드로 수정 — 수정 전 63.9%였음을 숨기지 않습니다 (decision_log D-027).</p>
    </div>
    <div class="panel mini rv">
      <h4>신뢰도 점수 밴드별 적중률 — 공개된 한계</h4>
      <table><thead><tr><th>점수</th><th>n</th><th>적중률</th></tr></thead><tbody>
        ${Object.entries(S.score_bands).map(([b,v])=>`<tr><td>${b}</td><td>${v.n}</td><td>${fmtP(v.precision)}</td></tr>`).join("")}
      </tbody></table>
      <p style="font-size:12px;color:var(--sub);margin-top:10px">점수는 "확신도"가 아니라 "규칙 충족 강도" — 밴드 간 차이가 크지 않으므로 점수 서열을 과신하지 마세요.</p>
    </div>
    ${DATA.stats?`<div class="panel mini rv">
      <h4>통계적 엄밀성 — 불리한 숫자까지 공개</h4>
      <table><thead><tr><th>분석</th><th>결과</th></tr></thead><tbody>
        <tr><td>기회 적중률 95% CI (Wilson)</td><td>${fmtP(DATA.stats.ci_opportunity.p)} [${fmtP(DATA.stats.ci_opportunity.lo)}~${fmtP(DATA.stats.ci_opportunity.hi)}]</td></tr>
        <tr><td>통과 vs 기각 유의성</td><td>z=${DATA.stats.pass_vs_reject.z}, p&lt;0.001 <b style="color:var(--ok)">유의</b></td></tr>
        <tr><td>에피소드 재집계 (연속 신호=1건)</td><td>${DATA.stats.episodes.n}건 중 ${DATA.stats.episodes.hit}건 = ${fmtP(DATA.stats.episodes.ci.p)}</td></tr>
        <tr><td>ㄴ 에피소드 수준 개선</td><td>+${((DATA.stats.episodes.ci.p-DATA.stats.episodes.baseline_d.p)*100).toFixed(1)}%p, p=${DATA.stats.episodes.vs_baseline.p_value} <b class="warn">유의성 미달</b></td></tr>
        <tr><td>ㄴ 에피소드 정의(갭 0/1/2주) 민감도</td><td>n=${(DATA.stats.episodes.gap_sensitivity||[]).map(g=>g.n).join('/')} · 개선 +${(DATA.stats.episodes.gap_sensitivity||[]).map(g=>g.gain_pp).join('/+')}%p — 정의에 둔감</td></tr>
        <tr><td>정답 임계값 민감도 (0.85~1.00)</td><td>개선 폭 +8.5~+19.2%p 방향 일관</td></tr>
      </tbody></table>
      <p style="font-size:12px;color:var(--sub);margin-top:10px">주 단위 신호는 자기상관이 있어(같은 키워드의 연속 신호), 독립 사건에 가까운 에피소드 단위로 재집계하면
      개선은 방향은 유지되나 표본 부족으로 유의성에 못 미칩니다. <b style="color:var(--ink)">그래서 매주 판정을 기록·채점하는 포워드 테스트를 가동 중입니다</b>
      — 사후 수정이 불가능한 실전 성적이 이 숫자를 최종 검증할 것입니다 (저장소 data/forward/).</p>
    </div>`:""}
    <div class="panel mini rv">
      <h4>신호 분포 — 조용한 유니버스는 설계의 결과</h4>
      <p style="font-size:12.5px;color:var(--sub);line-height:1.7">키워드 60개 중 신호를 낸 것은 18개. 나머지 42개가 2년간 침묵한 것은 결함이 아니라,
      의도적으로 절반 이상 포함한 정체·하락 키워드(음성 대조군)에서 <b style="color:var(--ink)">오탐이 억제되고 있다는 증거</b>입니다.
      연간 44건은 담당자가 전수 검토할 수 있는 빈도입니다.</p>
    </div>
  </div>
  <p class="foot-note rv">전체 방법론 문서: 저장소 docs/05_backtest_results.md · 의사결정 기록 31건: docs/decision_log.md</p>`;

  mountSubtabs("#v-bt", [
    {id: "bt-sum", label: "성적표 · 한눈에", html: sum},
    {id: "bt-how", label: "어떻게 검증했나", html: how},
    {id: "bt-deep", label: "자세한 결과", html: deep},
  ]);
}

/* ---------- 카운트업 + 리빌 ---------- */
function countUp(el, target, decimals=1, dur=1400){
  const t0 = performance.now();
  function step(now){
    const p = Math.min((now-t0)/dur, 1), e = 1-Math.pow(1-p,3);
    el.textContent = (target*e).toFixed(decimals);
    if(p<1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
/* threshold 0: 60행 표처럼 뷰포트보다 훨씬 큰 요소도 1px만 보이면 리빌
   (threshold 0.15는 요소 높이가 뷰포트의 ~6.7배를 넘으면 영원히 발화하지 않음) */
const io = new IntersectionObserver(es=>es.forEach(e=>{
  if(!e.isIntersecting) return;
  e.target.classList.add("in");
  e.target.querySelectorAll(".fill").forEach(f=>f.style.width=f.dataset.w+"%");
  e.target.querySelectorAll(".fgc").forEach(r=>r.style.strokeDashoffset=r.dataset.off);
  io.unobserve(e.target);
}),{threshold:0,rootMargin:"0px 0px -40px 0px"});
function bindReveal(){document.querySelectorAll(".rv:not(.in)").forEach(el=>io.observe(el))}

/* 탭 바가 상단에 붙으면 로고 배너 숨김 (겹침 방지) */
const _hdr = document.querySelector("header"), _tw = document.querySelector(".tabs-wrap");
addEventListener("scroll", () => {
  _hdr.classList.toggle("hide", _tw.getBoundingClientRect().top <= 20);
}, {passive: true});

renderNow(); renderCards(); renderBT();
countUp($("#st1"), main.precision*100, 1);
countUp($("#st2"), (main.precision-dOnly.precision)*100, 1);
countUp($("#st3"), main.signals, 0);
$("#st4").textContent = DATA.latest_period;
bindReveal();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
