# CLAUDE.md

매일 아침 한국어 브리핑(서울 날씨 · 오늘 일정 · 간밤 미국·유럽 뉴스 · 경제지표)을
작성해 Gmail 드래프트와 텔레그램으로 발송하는 개인 브리핑 시스템.

## 레포 구조

```
briefing-prompt.md        # 브리핑 루틴 전체 명세 (날짜 계산 → 날씨 → 일정 → 뉴스 → 경제지표 → 발송)
template.md               # 산출물(메일 본문·텔레그램 요약) 캐노니컬 출력 형식. 형식 변경은 여기서
collect-news.py           # RSS 기반 뉴스 수집기 (표준 라이브러리만, pip 불필요)
news-feeds.json           # 피드 목록·키워드·점수 설정
indicators.py             # 주요 경제지표 실적 아카이브 (record/show, 표준 라이브러리만)
send_telegram.py          # 텔레그램 발송 스크립트
gas-auto-send/Code.gs     # Gmail 드래프트 자동 발송 Google Apps Script
archive/                  # 매일 발송된 브리핑 보관 ({YYYY-MM-DD}.md)
archive/indicators.csv    # 경제지표 실적 시계열 (indicators.py가 관리)
.github/workflows/
  auto-merge-claude.yml   # claude/ 브랜치 PR 자동 스쿼시 머지
  sync-archive-to-main.yml # claude/ 브랜치의 archive/ 변경을 main에 자동 동기화
```

## 핵심 동작 흐름

1. **날짜 계산** — KST_TODAY = UTC currentDate + 1일 (보수적), NEWS_DATE = KST_TODAY - 1일
2. **날씨** — WebSearch로 서울 날씨 조회
3. **일정** — Google Calendar `list_events`로 KST_TODAY 일정 조회
4. **뉴스** — `python3 collect-news.py --news-date {NEWS_DATE}` 실행 → 피드 수집 → WebSearch로 상위 기사 검증. 스크립트 실패 시 WebSearch-only 폴백
5. **경제지표** — 전후 1주일. 지난 7일 실제치를 WebSearch로 모아 `indicators.py record`로 기록하고, `indicators.py show`로 되읽어 렌더링. 향후 7일 일정은 WebSearch로 조회(저장하지 않음)
6. **발송** — Gmail 드래프트 생성(`mcp__Gmail__create_draft`) + 텔레그램 요약 발송. 출력 형식은 `template.md` 따름
7. **보관** — `archive/{KST_TODAY}.md` + `archive/indicators.csv` 커밋·푸시

## 코딩 가이드라인

Andrej Karpathy 스타일 원칙. 이 레포를 수정할 때 반드시 따른다.

### 1. 코딩 전에 생각하라

- 가정을 명시적으로 밝힌다. 불확실하면 묻는다.
- 여러 해석이 가능하면 나열한다 — 임의로 선택하지 않는다.
- 더 단순한 방법이 있으면 제안한다. 필요하면 반론한다.

### 2. 단순함 우선

- 요청받은 것만 구현한다. 추측성 기능 금지.
- 단일 용도 코드에 추상화를 만들지 않는다.
- 불가능한 시나리오의 에러 핸들링을 추가하지 않는다.
- 200줄이 50줄로 가능하면 다시 쓴다.

### 3. 수술적 변경

- 요청과 직접 관련된 코드만 수정한다.
- 인접한 코드·주석·포맷을 "개선"하지 않는다.
- 기존 스타일에 맞춘다.
- 내 변경으로 생긴 고아(미사용 import/변수/함수)만 제거한다.

### 4. 목표 기반 실행

- 작업을 검증 가능한 목표로 변환한다.
- 멀티스텝 작업은 간단한 계획과 검증 기준을 명시한다.
- 강한 성공 기준 → 독립적 루프 가능. 약한 기준("되게 해줘") → 확인 필요.

## 프로젝트 규칙

### 의존성

- `collect-news.py`와 `indicators.py`는 **Python 표준 라이브러리만** 사용한다. pip 패키지를 추가하지 않는다.
- `send_telegram.py`만 `requests`를 사용한다.

### 뉴스 수집 (collect-news.py)

- 수집 윈도우는 NEWS_DATE 00:00 UTC에 고정 (전일자 중복 방지). `--hours`는 디버그용.
- 키워드 매칭은 **단어경계** 기반이다. substring 매칭으로 바꾸지 않는다 (`ai`→rain 오탐 방지).
- `exclude_keywords`에 걸린 기사는 수집 단계에서 버린다(스포츠·연예). 미설정이면 무동작.
- 종료 코드: `0` 정상, `1` 기사 0건(WebSearch 폴백), `2` 설정 로드 실패.
- 일부 피드 실패 → 해당 피드만 건너뛰고 계속 진행. 브리핑은 절대 거르지 않는다.

### 피드 설정 (news-feeds.json)

- `area`: `economy` | `markets` | `ai_tech` | `politics`
- `tier`: `1` (주요 1차 출처) | `2`
- `region`: `US` | `EU` | `GLOBAL`
- `type: "gnews"` → Google News RSS 간접 수집 (직접 접근 불가 출처용)
- 직접 접근 불가 출처: Reuters, FT, NYT, The Verge, Ars Technica, AP → Google News로 우회
- Guardian은 섹션 RSS(`world/europe-news`, `us-news`)만 직접 접근되고, 비즈니스는 gnews로 받는다

### 시크릿 관리

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`는 **환경변수**로만 주입한다.
- 토큰·비밀값을 코드나 저장소에 절대 하드코딩하지 않는다.
- 미설정 시 텔레그램 발송만 건너뛴다 (브리핑 자체 영향 없음).

### 브리핑 보관

- 파일 경로: `archive/{KST_TODAY}.md`
- Gmail 드래프트 본문 그대로 저장 (텔레그램 요약본이 아닌 상세 버전).
- 커밋 메시지: `Archive daily briefing {KST_TODAY}`

### 경제지표 아카이빙 (indicators.py)

- 저장 위치는 **`archive/indicators.csv`로 고정**한다. 레포 루트로 옮기지 않는다 —
  `sync-archive-to-main.yml`이 `archive/**`만 main에 동기화하고 일일 브리핑은 PR을
  만들지 않으므로, 루트에 두면 main에 영원히 반영되지 않는다.
- **발표가 끝나 실제치가 확정된 것만** 기록한다. 미래 일정은 매일 바뀌므로 저장하지
  않는다 (`actual`이 비면 스크립트가 해당 행을 거부한다).
- `country`·`indicator`는 스크립트의 `WATCHLIST` 표준명만 허용한다. 시계열이 끊기지
  않게 하려는 것이므로 임의 표기를 넣지 않는다. 지표를 늘리려면 `WATCHLIST`에 추가한다.
- upsert 키는 `(release_date, country, indicator, period)`. 매일 겹치는 7일 윈도우를
  그대로 다시 넣어도 중복이 쌓이지 않는다. 같은 키의 값이 바뀌면 갱신된다(속보치→확정치).
- 수치는 단위가 이질적이므로(`+3.5%`, `216K`, `3.50~3.75%`) **문자열 그대로** 저장한다.
  파싱 레이어를 만들지 않는다.
- 상회/부합/하회 판정은 스크립트가 하지 않는다. 브리핑이 렌더링할 때 판단한다.
- 종료 코드: `0` 정상, `1` 유효 행/조회 결과 0건, `2` 입출력·인자 오류.
  기록 실패는 best-effort로 취급하고 브리핑은 계속한다.

### Git 브랜치 전략

- `claude/` 접두사 브랜치의 PR은 자동 스쿼시 머지된다.
- `claude/` 브랜치의 `archive/` 변경은 GitHub Actions로 main에 자동 동기화된다.

### 브리핑 품질 기준

- 뉴스: 기술·경제·정치 분야별 한 줄에 한 주제씩 3~5건. 가십·연예·스포츠 제외.
- 1차 출처 우선 (Reuters, AP, FT, BBC, Bloomberg, WSJ).
- 미확인 보도는 "보도됨", "~로 전해졌다" 표현 사용.
- 텔레그램 메시지 4000자 초과 시 점수 낮은 항목부터 제거, 분야별 최소 1건 유지.
