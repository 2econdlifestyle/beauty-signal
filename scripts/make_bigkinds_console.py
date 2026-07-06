"""
빅카인즈 콘솔 수집 스크립트 생성기 (C 신호 갱신용, D-021 방식의 셀프서비스판)
- scripts/bigkinds_queries.txt의 검색식 60개를 임베드한 브라우저 콘솔용 JS를 생성한다
- 기간: 2023-07-03(고정, 주차 정렬 기준) ~ 가장 최근의 완결 주 일요일(자동 계산)
실행: python3 scripts/make_bigkinds_console.py  →  scripts/bigkinds_console.js
사용법: docs/07_bigkinds_manual.md 참조
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START = date(2023, 7, 3)  # 월요일 — 데이터랩 주차와 정렬 (변경 금지)


def last_complete_sunday(today: date) -> date:
    # 오늘이 일요일이면 지난주 일요일(완결 주만), 아니면 직전 일요일
    offset = (today.weekday() + 1) % 7  # 월=0 → 1, ..., 일=6 → 0
    sunday = today - timedelta(days=offset if offset else 7)
    return sunday


def main():
    txt = (ROOT / "scripts" / "bigkinds_queries.txt").read_text(encoding="utf-8")
    blocks = re.findall(r"\[(.+?)\]\n(.+?)(?=\n\n|\Z)", txt, re.S)
    pairs = [{"k": k.strip(), "q": q.strip()} for k, q in blocks]
    assert len(pairs) == 60, f"검색식 {len(pairs)}개 — 60개여야 함"

    end = last_complete_sunday(date.today())
    n_days = (end - START).days + 1
    assert n_days % 7 == 0, "기간이 7의 배수가 아님"
    n_weeks = n_days // 7

    js = CONSOLE_TEMPLATE
    js = js.replace("__QUERIES__", json.dumps(pairs, ensure_ascii=False))
    js = js.replace("__START__", START.isoformat())
    js = js.replace("__END__", end.isoformat())
    js = js.replace("__NWEEKS__", str(n_weeks))
    (ROOT / "scripts" / "bigkinds_console.js").write_text(js, encoding="utf-8")
    print(f"scripts/bigkinds_console.js 생성 — 기간 {START} ~ {end} ({n_weeks}주)")
    print("다음: 빅카인즈 로그인 → 뉴스검색·분석 페이지에서 아무 검색이나 1회 실행 → 개발자도구 콘솔에 파일 내용 붙여넣기")


CONSOLE_TEMPLATE = r"""/* 뷰티시그널 — 빅카인즈 주간 뉴스 건수 수집 (콘솔용)
 * 사전 조건: bigkinds.or.kr 로그인 + 뉴스검색·분석 페이지에서 아무 검색이나 1회 실행(적용하기)
 * 완료 시 bigkinds_weekly_raw.txt 파일이 다운로드됨 → scripts/bigkinds_to_csv.py로 변환
 */
(async () => {
  const QUERIES = __QUERIES__;
  const START = "__START__", END = "__END__", NWEEKS = __NWEEKS__;
  const out = [];
  console.log(`수집 시작: ${QUERIES.length}개 검색식, ${START}~${END} (${NWEEKS}주)`);
  for (let i = 0; i < QUERIES.length; i++) {
    const {k, q} = QUERIES[i];
    const rp = _.cloneDeep(newsResult.getResultParams());
    rp.searchKey = q;
    rp.startDate = START; rp.endDate = END;
    rp.interval = 3;              // 일간
    rp.sectionDiv = "1000";
    rp.realURI = "/api/analysis/keywordTrends.do";
    rp.isTmUsable = true; rp.isNotTmUsable = false;   // 분석기사 기준 (화면 그래프와 동일)
    try {
      const res = await fetch('/api/analysis/keywordTrends.do', {
        method: 'POST', headers: {'Content-Type': 'application/json;charset=utf-8'},
        body: JSON.stringify(rp)
      }).then(r => r.json());
      const d = (res.root && res.root[0]) ? res.root[0].data : [];
      let weekly;
      if (d.length === 1 && d[0].d === '0') {
        weekly = new Array(NWEEKS).fill(0);            // 전 기간 0건 응답 형태
      } else if (d.length === NWEEKS * 7 && d[0].d === START.replaceAll('-', '')) {
        weekly = [];
        for (let w = 0; w < NWEEKS; w++) {
          let s = 0;
          for (let j = 0; j < 7; j++) s += Number(d[w * 7 + j].c);
          weekly.push(s);
        }
      } else {
        console.error(`[${i+1}/60] ${k}: 응답 형태 이상 (${d.length}행, 첫 날짜 ${d[0] && d[0].d}) — 중단`);
        return;
      }
      out.push(k + ':' + weekly.join(','));
      console.log(`[${i+1}/60] ${k} — 총 ${weekly.reduce((a,b)=>a+b,0)}건`);
    } catch (e) { console.error(`[${i+1}/60] ${k} 실패:`, e); return; }
    await new Promise(r => setTimeout(r, 700));        // 호출 간 지연 (예의)
  }
  const blob = new Blob([out.join(';')], {type: 'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'bigkinds_weekly_raw.txt';
  document.body.appendChild(a); a.click(); a.remove();
  console.log('완료 — bigkinds_weekly_raw.txt 다운로드됨. 다음: python3 scripts/bigkinds_to_csv.py');
})();
"""


if __name__ == "__main__":
    main()
