# 유지보수 런북 — 다음 세션(어느 AI든/사람이든)을 위한 인수인계

> 작성 2026-07-06. 이 문서 하나로 프로젝트를 이어받을 수 있어야 한다.

## 0. 세션 시작 프롬프트 (복사해서 사용)

```
beauty-signal 폴더의 docs/를 전부 읽고 시작해. 특히:
- decision_log.md의 D-001~D-034가 지금까지의 모든 결정이야 (상단 결정 맵부터)
- 09_maintenance.md(이 문서)가 유지보수 런북이야
프로젝트는 전 단계(설계~게시) 완료·라이브 상태고, 남은 운영은 주간 포워드 테스트야.
원칙: 유니버스·규칙 변경 금지(동결), 사후 변경은 전/후 수치 공개, forward_log는 append-only.
.env 파일은 읽지 마.
```

## 1. 아키텍처 한 장

```
[수집]  collect_datalab_search.py (D: 네이버 API, .env 필요)
        collect_shopping_insight.py (S: 네이버 API)
        make_bigkinds_console.py → 브라우저 콘솔 → bigkinds_to_csv.py (C: docs/07)
   ↓ data/raw/{search_trend, shopping_click, news_weekly, keyword_category_map}.csv
[검증]  validate_data.py → data/processed/search_trend_filled.csv (0 채움 표준 입력) + anomaly_flags.csv
[분석]  backtest.py → backtest_signals.csv + backtest_summary.json
        stats_rigor.py → stats_rigor.json (CI·유의성·에피소드·민감도)
        forward_test.py → data/forward/forward_log.csv (append-only 실전 성적)
[출력]  build_dashboard.py → dashboard/beauty-signal.html (정적 단일 파일, 데이터 임베드)
게시:   GitHub Pages (루트 index.html → dashboard/로 리다이렉트) · push하면 자동 재배포
```

핵심 상수는 `backtest.py` 상단에 집중: D_RATIO 1.30 · D_SEASON 1.15 · C_MULT 2.0 · C_FLOOR 4 · GT_KEEP 0.90 · MIN_BASE 5.0 (분모 가드, D-027). `build_dashboard.py`·`forward_test.py`는 이를 import해서 씀 — **규칙 수정은 backtest.py 한 곳만.**

## 2. 주간 운영 루틴 (Actions 이슈가 매주 월요일 자동 생성됨)

1. D·S 수집 스크립트 실행 (.env 필요) → 2. 빅카인즈 5분 절차 (docs/07) → 3. `forward_test.py` (기록+채점) → 4. `build_dashboard.py` → 5. commit & push
⚠️ forward_log.csv의 기존 행은 절대 수정 금지 — 스크립트가 멱등 처리하지만, 수동 편집도 하지 말 것.

## 3. 기간(윈도) 확장 런북 — 분기 1회쯤 필요

현재 윈도: 2023-07-03(월, **변경 절대 금지** — 3소스 주차 정렬 앵커) ~ 2026-06-28, 156주 고정.
새 종료일은 반드시 **일요일**(완결 주). 확장 시 아래를 같은 값으로 일괄 변경:

| 파일 | 상수 |
|---|---|
| collect_datalab_search.py / collect_shopping_insight.py | `END_DATE` |
| backtest.py | `N_WEEKS`, `T_END`(= 마지막 주 − 4), `T_END_8W`(= 마지막 주 − 8) |
| build_dashboard.py | `N_WEEKS`, `T_MAX`(= 마지막 주 인덱스), `T_GT_MAX`(= T_MAX − 4) |
| validate_data.py | `N_WEEKS` |
| make_bigkinds_console.py | 종료일 자동 계산이므로 수정 불요 |

확장 후: 전체 재수집 → `validate_data.py` 통과 확인 → `backtest.py`·`stats_rigor.py` 재실행 → 수치가 바뀌면 **바뀐 이유를 decision_log에 기록** (기간 연장은 정당한 갱신, 규칙 변경 아님).

## 4. 문제 발생 시 진단 순서

1. `python scripts/validate_data.py` — 21항목 자동 점검 (스키마·주차·매핑·게이트 자체 테스트)
2. 데이터랩 응답 관련: **0인 주는 응답에서 생략됨** (Failure #4의 근원) — 분모는 항상 전체 주 수
3. 빅카인즈 스크립트 중단: 응답 형태 로그 확인 → docs/07 오류 대응표
4. 대시보드 이상: `build_dashboard.py` 재실행 → 브라우저 콘솔 에러 확인. 과거 사례: 리빌 threshold 함정(D-030), 서브탭 전역 핸들러 충돌(mountSubtabs로 해결), CSS 스코프(.stat span)
5. 수치가 문서와 다르면: backtest_summary.json이 진실의 원천 — 문서·대시보드가 이를 따라야 함

## 5. 건드리면 안 되는 것 (동결 목록)

- 키워드 유니버스 60개·브랜드 목록 (v1.1, 예외 조항 소진 — D-022)
- 신호 규칙·임계값 (변경하려면 "사후 변경 공개 + 민감도" 원칙: D-027이 선례)
- 주차 시작일 2023-07-03 · forward_log 기존 행 · decision_log 과거 항목(추가만 가능)

## 6. 열린 과제 (v2 백로그)

1. 페르소나 인터뷰 3명 (docs/08 — 가이드 완성, 실행만 남음. H3 기각 시 주 지표 재검토)
2. 포워드 테스트 표본 축적 → 에피소드 유의성 재검정 (§ 05-9-3의 p=0.18 해소)
3. 수집 완전 자동화 (윈도 확장 리팩터링 선행 필요 — D-034에서 이월)
4. 신뢰도 점수 배점 재설계 (D-025) · 규칙 vs 간단 ML 비교 (D-004) · 유니버스 확장 시 신호 분산 검증
5. 회고 글 블로그 게시 (docs/retrospective.md 초안)
