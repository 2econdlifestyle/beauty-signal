/* 뷰티시그널 — 빅카인즈 주간 뉴스 건수 수집 (콘솔용)
 * 사전 조건: bigkinds.or.kr 로그인 + 뉴스검색·분석 페이지에서 아무 검색이나 1회 실행(적용하기)
 * 완료 시 bigkinds_weekly_raw.txt 파일이 다운로드됨 → scripts/bigkinds_to_csv.py로 변환
 */
(async () => {
  const QUERIES = [{"k": "PDRN", "q": "PDRN AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "엑소좀", "q": "엑소좀 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "콜라겐", "q": "콜라겐 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든 OR 비비랩 OR 에버콜라겐 OR 정관장 OR 뉴트리원)"}, {"k": "글루타치온", "q": "글루타치온 AND (비비랩 OR 에버콜라겐 OR 정관장 OR 뉴트리원)"}, {"k": "레티놀", "q": "레티놀 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "레티날", "q": "레티날 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "나이아신아마이드", "q": "나이아신아마이드 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "비타민C 세럼", "q": "비타민C 세럼 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "히알루론산", "q": "히알루론산 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "세라마이드", "q": "세라마이드 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "판테놀", "q": "판테놀 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "시카", "q": "시카 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "어성초", "q": "어성초 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "쑥 토너", "q": "쑥 토너 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "티트리", "q": "티트리 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "프로폴리스", "q": "프로폴리스 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "갈락토미세스", "q": "갈락토미세스 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "펩타이드", "q": "펩타이드 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "아젤라익애씨드", "q": "아젤라익애씨드 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "트라넥삼산", "q": "트라넥삼산 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "살리실산", "q": "살리실산 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "PHA", "q": "PHA AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "엑토인", "q": "엑토인 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "마이크로바이옴 화장품", "q": "마이크로바이옴 화장품 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "아스타잔틴", "q": "아스타잔틴 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든 OR 비비랩 OR 에버콜라겐 OR 정관장 OR 뉴트리원)"}, {"k": "앰플", "q": "앰플 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "토너 패드", "q": "토너 패드 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "필링 패드", "q": "필링 패드 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "스틱 선크림", "q": "스틱 선크림 AND (라운드랩 OR 구달 OR 닥터지 OR 조선미녀 OR 스킨아쿠아)"}, {"k": "선쿠션", "q": "선쿠션 AND (라운드랩 OR 구달 OR 닥터지 OR 조선미녀 OR 스킨아쿠아)"}, {"k": "선세럼", "q": "선세럼 AND (라운드랩 OR 구달 OR 닥터지 OR 조선미녀 OR 스킨아쿠아)"}, {"k": "톤업 선크림", "q": "톤업 선크림 AND (라운드랩 OR 구달 OR 닥터지 OR 조선미녀 OR 스킨아쿠아)"}, {"k": "클렌징 밤", "q": "클렌징 밤 AND (마녀공장 OR 바닐라코 OR 라운드랩 OR 센카)"}, {"k": "클렌징 오일", "q": "클렌징 오일 AND (마녀공장 OR 바닐라코 OR 라운드랩 OR 센카)"}, {"k": "슬리핑 마스크", "q": "슬리핑 마스크 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "모델링 팩", "q": "모델링 팩 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "립 오일", "q": "립 오일 AND (투쿨포스쿨 OR 페리페라 OR 클리오 OR 롬앤 OR 웨이크메이크 OR 힌스)"}, {"k": "립 틴트", "q": "립 틴트 AND (투쿨포스쿨 OR 페리페라 OR 클리오 OR 롬앤 OR 웨이크메이크 OR 힌스)"}, {"k": "쿠션 파운데이션", "q": "쿠션 파운데이션 AND (투쿨포스쿨 OR 페리페라 OR 클리오 OR 롬앤 OR 웨이크메이크 OR 힌스)"}, {"k": "세럼 파운데이션", "q": "세럼 파운데이션 AND (투쿨포스쿨 OR 페리페라 OR 클리오 OR 롬앤 OR 웨이크메이크 OR 힌스)"}, {"k": "두피 앰플", "q": "두피 앰플 AND (어노브 OR 닥터포헤어 OR 라보에이치 OR 려 OR 쿤달)"}, {"k": "헤어 에센스", "q": "헤어 에센스 AND (어노브 OR 닥터포헤어 OR 라보에이치 OR 려 OR 쿤달)"}, {"k": "미스트", "q": "미스트 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "모공 축소", "q": "모공 축소 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "트러블 진정", "q": "트러블 진정 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "미백", "q": "미백 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "잡티", "q": "잡티 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "주름 개선", "q": "주름 개선 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "피부 탄력", "q": "피부 탄력 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "피부 장벽", "q": "피부 장벽 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "속건조", "q": "속건조 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "홍조", "q": "홍조 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "피지 조절", "q": "피지 조절 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "각질 제거", "q": "각질 제거 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "다크서클", "q": "다크서클 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든)"}, {"k": "두피 각질", "q": "두피 각질 AND (어노브 OR 닥터포헤어 OR 라보에이치 OR 려 OR 쿤달)"}, {"k": "여성 탈모", "q": "여성 탈모 AND (어노브 OR 닥터포헤어 OR 라보에이치 OR 려 OR 쿤달)"}, {"k": "물광 피부", "q": "물광 피부 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든 OR 투쿨포스쿨 OR 페리페라 OR 클리오 OR 롬앤 OR 웨이크메이크 OR 힌스)"}, {"k": "저속노화", "q": "저속노화 AND (라운드랩 OR 에스트라 OR 구달 OR 아누아 OR 메디큐브 OR 코스알엑스 OR 토리든 OR 비비랩 OR 에버콜라겐 OR 정관장 OR 뉴트리원)"}, {"k": "먹는 콜라겐", "q": "먹는 콜라겐 AND (비비랩 OR 에버콜라겐 OR 정관장 OR 뉴트리원)"}];
  const START = "2023-07-03", END = "2026-07-05", NWEEKS = 157;
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
