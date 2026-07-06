# 빅카인즈 수집 매뉴얼 (C 신호 갱신 — 셀프서비스, 약 5분)

> D-021의 API 재현 방식을 혼자 실행할 수 있게 도구화한 절차. 2026-07-06 작성
> 소요: 로그인 포함 약 5분 (검색식 60개 × 0.7초 지연 = 수집 자체는 ~2분)

## 언제 하나

- 대시보드의 C 신호(경쟁 기사 수)를 최신 주까지 갱신하고 싶을 때 (권장: 주 1회, 월요일)
- D·S(네이버 API)는 로컬 스크립트로, C(빅카인즈)만 이 절차로

## 절차

**1. 콘솔 스크립트 생성** (터미널, 프로젝트 폴더에서)

```bash
python scripts/make_bigkinds_console.py
```

→ `scripts/bigkinds_console.js` 생성. 기간(2023-07-03 ~ 가장 최근 완결 주 일요일)이 자동 계산돼 들어감

**2. 빅카인즈 준비** (Chrome)

- [bigkinds.or.kr](https://www.bigkinds.or.kr) 로그인
- 뉴스분석 → 뉴스검색·분석 페이지 이동
- 아무 검색어나 입력하고 **적용하기 1회 실행** (페이지 내부 객체 초기화용 — 검색 내용은 무관)

**3. 콘솔에 붙여넣기**

- `⌥⌘I` (개발자도구) → Console 탭
- `scripts/bigkinds_console.js` 파일 내용 전체 복사 → 콘솔에 붙여넣고 Enter
- `[1/60] PDRN — 총 N건` 형식으로 진행 로그가 올라감. 끝나면 `bigkinds_weekly_raw.txt`가 자동 다운로드됨
- ⚠️ 붙여넣기가 막히면 콘솔에 `allow pasting`을 먼저 입력 (Chrome 보호 기능)

**4. CSV 변환** (터미널)

```bash
python scripts/bigkinds_to_csv.py          # 기본: ~/Downloads/bigkinds_weekly_raw.txt 읽음
```

→ `data/raw/news_weekly.csv` 갱신. 키워드 60개·주차 정렬·목록 일치를 자동 검증하고, 하나라도 어긋나면 중단됨

**5. 재계산 + 대시보드 갱신**

```bash
python scripts/backtest.py
python scripts/build_dashboard.py
git add -A && git commit -m "data: C 신호 주간 갱신" && git push   # Pages 자동 재배포
```

## 오류 대응

| 증상 | 원인/조치 |
|---|---|
| `newsResult is not defined` | 2번 단계(아무 검색 1회) 안 하고 붙여넣음 → 검색 실행 후 재시도 |
| `응답 형태 이상 ... 중단` | 빅카인즈 응답 스펙 변경 가능성. 로그의 행 수·첫 날짜를 확인해 공유 |
| 변환기 `키워드 목록 불일치` | 검색식 파일과 keywords_v1.csv가 어긋남 (정상적 방어) — 두 파일의 변경 이력 확인 |
| 특정 키워드만 실패 | 콘솔 재실행 (전체 2분이라 부분 재시도보다 전체가 빠름) |

## ⚠️ 기간 확장 시 함께 바꿔야 하는 것 (분기 1회 수준)

이 절차는 C 데이터만 최신 주까지 늘린다. **백테스트 판정 구간 자체를 확장**하려면 D·S도 같은 끝 주까지 재수집해야 하고, 아래 상수들을 동일한 종료일로 맞춰야 한다:

- `scripts/collect_datalab_search.py` · `collect_shopping_insight.py`: `END_DATE`
- `scripts/backtest.py` · `build_dashboard.py` · `validate_data.py`: `N_WEEKS`(156), 판정 구간(`T_START/T_END` 등)

주차 시작일 `2023-07-03`(월)은 세 소스의 정렬 기준이므로 **절대 변경 금지**. 종료일은 반드시 일요일(완결 주)이어야 한다.
