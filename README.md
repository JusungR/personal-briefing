# personal-briefing

매일 아침 한국어 브리핑(서울 날씨 · 오늘 일정 · 간밤 미국·유럽 뉴스)을 작성해
Gmail 드래프트와 텔레그램으로 보낸다.

## 구성 파일

| 파일 | 역할 |
|---|---|
| `briefing-prompt.md` | 브리핑 작성 루틴(날짜 계산, 날씨, 일정, 뉴스, 발송)의 핵심 명세. Claude가 도구로 실행한다. |
| `template.md` | 메일 본문·텔레그램 요약의 캐노니컬 출력 형식. 형식(레이아웃) 변경은 여기서 한다. |
| `collect-news.py` | 간밤 뉴스 수집기. 검증된 RSS 피드에서 기사를 모아 분야별 후보 목록을 출력한다. |
| `news-feeds.json` | 뉴스 피드 목록과 키워드·점수 설정(데이터 기반, 자유롭게 편집). |
| `indicators.py` | 주요 경제지표(CPI·PCE·기준금리 등)의 발표 실제치를 시계열로 누적·조회. |
| `archive/indicators.csv` | 위 스크립트가 관리하는 지표 실적 시계열(한 줄 = 한 발표). |
| `gas-auto-send/Code.gs` | `[Daily Briefing]` Gmail 드래프트를 매일 자동 발송하는 Google Apps Script. |
| `archive/` | 매일 발송된 브리핑 본문(`{날짜}.md`)을 누적 보관(향후 리뷰·개선용). |

## 환경변수 (시크릿)

텔레그램 발송에 쓰는 시크릿은 **저장소에 하드코딩하지 않고 환경변수로 주입**한다.
클로드루틴 환경설정에 아래 값을 등록한다(미설정 시 텔레그램 발송만 건너뛴다).

| 변수 | 용도 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰(BotFather 발급) |
| `TELEGRAM_CHAT_ID` | 요약본을 받을 챗 ID |

> 과거 커밋에 토큰이 평문으로 남아 있었다면 노출된 것으로 간주하고 BotFather에서
> **토큰을 재발급(revoke)** 한 뒤 환경변수만 새 값으로 갱신한다.

## 뉴스 수집 (collect-news.py)

기존에는 뉴스가 WebSearch 단일 지시에만 의존해 분야 누락·오래된 기사 등 품질이
들쭉날쭉했다. 이를 보완하기 위해 검증된 RSS 피드에서 결정적으로 수집한 뒤,
WebSearch는 상위 기사 확인·보강용으로만 쓴다.

```bash
python3 collect-news.py --news-date 2026-05-27          # 기본 윈도우 30h
python3 collect-news.py --news-date 2026-05-27 --hours 24
```

동작: 피드 수집 → 날짜 윈도우 필터(신선도) → 제목 유사도 중복제거 →
관심분야(경제·시장·AI/기술) 키워드·출처·신선도·교차보도 점수화 → 그룹별 정렬 출력.

- **요구사항**: `python3`(표준 라이브러리만, pip 설치 불필요) + 아웃바운드 HTTPS.
- **종료 코드**: `0` 정상, `1` 신선 기사 0건(프롬프트가 WebSearch로 폴백), `2` 설정 로드 실패.
- 일부 피드가 죽어도 해당 피드만 건너뛰고 나머지로 계속 진행한다.

#### 수집 윈도우 (전일자 중복 방지)

기본 윈도우는 **NEWS_DATE 00:00 UTC ~ 실행시각**으로 날짜에 고정된다. 과거의 롤링
30h 방식은 연속 이틀 윈도우가 미 오후 프라임타임에서 약 6h 겹쳐, 같은 기사가 이틀
연속 후보로 올라오는 "전일자 중복"을 만들었다. 날짜 고정 시 겹침이 없어진다.
경계 퍼지를 흡수하려면 `news-feeds.json`의 `window_lead_hours`(기본 0)를 키운다.
디버그용으로 `--hours N`을 주면 기존 롤링(`now - N`) 방식으로 강제할 수 있다.
(영속 이력 파일은 두지 않으므로, 타 매체가 익일 재게시한 동일 사건은 잡지 못한다.)

#### 키워드 매칭 (단어경계)

분야 분류는 키워드 **단어경계** 매칭을 쓴다. 과거 substring 매칭은 `ai`→rain/said,
`oil`→boiling, `meta`→metadata, `rate`→accurate 같은 오탐을 냈다. 현재는 영숫자 경계
lookaround로 매칭해 `s&p`·`interest rate` 같은 특수문자/다단어구도 정확히 잡는다.

### 피드 편집 (news-feeds.json)

`feeds` 배열에 `{name, url, area, tier, region}`을 추가/삭제하면 된다.
`area`는 `economy|markets|ai_tech`, `tier`는 `1`(주요 1차 출처) 또는 `2`, `region`은 `US|EU|GLOBAL`.
`keywords`로 분야 분류 키워드를, `window_lead_hours`/`per_group_cap`/`dedupe_threshold`로
동작을 조정한다.

`type: "gnews"`를 주면 해당 피드는 **Google News RSS** 항목으로 처리된다:
실제 출처명·지역은 항목별 `<source>` 요소(예: `<source url="reuters.com">Reuters</source>`)에서
파생하고(`name`/`region`은 폴백), 제목 끝 `" - 출처"` 접미사를 제거하며, 요약은 비운다
(Google News description은 본문이 아니라 링크일 뿐). url은 Google 리다이렉트 주소다.
`site:domain` 검색으로 특정 1차 출처를 타깃할 수 있다.

#### 직접 접근 불가 출처 → Google News로 간접 복구

아래 출처는 직접 RSS 접근이 막혀 있어, `type:"gnews"` 항목으로 **Google News RSS를 통해
간접 복구**한다. (헤드라인·출처·시각은 확보되나 요약이 없고 url이 리다이렉트이므로,
상위 기사는 `briefing-prompt.md` Section 3-2의 WebSearch 확인 단계에서 보강한다.)

- **Reuters · FT · The Guardian · NYT · The Verge · Ars Technica**: 직접 접근 시 403/DNS 실패
  → `news.google.com/rss/search?q=...site:<domain>`으로 우회 수집.
- **WSJ** (`feeds.a.dj.com/...`): 갱신 장기 중단 이력 → 신선도 오염 우려로 제외 유지.

### 브리핑 보관 (archive/)

발송된 브리핑은 매일 `archive/{KST_TODAY}.md`로 git 커밋해 누적 보관한다
(`briefing-prompt.md` Section 6). 향후 분야 균형·출처 다양성·중복 패턴 리뷰의 입력으로 쓴다.

## 경제지표 아카이브 (indicators.py)

브리핑의 지표 블록은 원래 **미래 일정만** 담아, 발표 후 결과가 어땠는지는 남지 않았다
(아카이브 55일치에서 "실제" 언급 3회). 지표명 표기도 날마다 갈려("미국 CPI" /
"5월 소비자물가지수(CPI)") 시계열을 만들 수 없었다. 이를 위해 **발표된 실제치만**
표준명으로 `archive/indicators.csv`에 누적한다.

```bash
# 기록 (stdin, 헤더 없는 CSV). 같은 발표를 다시 넣으면 값만 갱신된다.
python3 indicators.py record <<'EOF'
US,CPI,2026-07-14,21:30,2026-06,325.4,+3.5%,,-0.4%,+3.8%,+4.2%,BLS
US,FOMC 기준금리,2026-07-30,03:00,2026-07,3.50~3.75%,,,,3.50~3.75%,3.50~3.75%,Fed
EOF

# 조회 — 기간 (브리핑의 '지난주 발표' 렌더링용)
python3 indicators.py show --since 2026-07-22 --until 2026-07-29

# 조회 — 지표 시계열
python3 indicators.py show --country US --indicator CPI
```

- **스키마**: `country,indicator,release_date,release_time_kst,period,level,yoy,qoq,mom,forecast,previous,source`
- **발표값을 기준별로 나눈다**: `level`(지수 원계열) · `yoy`(전년비) · `qoq`(전분기비
  연율, GDP) · `mom`(전월비).
  브리핑은 보통 yoy/mom만 쓰지만 원계열을 남겨야 나중에 재계산·검증이 된다.
  지표에 해당하는 것만 채우면 되고(금리는 `level`만, 고용은 `mom`만), 어느 칸을
  헤드라인으로 쓸지는 `WATCHLIST`가 정한다.
- **지표별로 정렬·저장한다** (`country, indicator, release_date`). 정렬키를 그대로 열
  순서로 두어, 파일을 열면 같은 지표가 연속 블록으로 보인다.
- **upsert 키**: `(country, indicator, release_date, period)` — 매일 겹치는 7일 윈도우를
  그대로 다시 넣어도 중복이 쌓이지 않는다. 속보치가 확정치로 바뀌면 값만 갱신된다.
- **표준명 강제**: `country`/`indicator`가 스크립트의 `WATCHLIST`에 없으면 해당 행을
  거부하고 유효 목록을 알려준다. 시계열이 표기 변이로 끊기는 걸 막는다.
- **미래 일정은 저장하지 않는다** — 신규 행은 발표값 칸 중 하나가 있어야
  한다. 일정은 매일 바뀌므로 보존 가치가 없다. 기존 행에 예상치·이전치만 덧붙이는
  보강은 허용된다.
- **부분 갱신을 지원한다** — `record`는 값이 있는 칸만 반영하므로, 나중에 지수
  원계열만 알게 되면 그 칸만 담은 행을 같은 키로 넣으면 된다.
- `level`의 기준은 지표마다 고정한다(미국 CPI 계열 = NSA `1982-84=100`, 유로존
  HICP = `2025=100`). `mom`은 계절조정 기준이라 `level`의 전월 대비 변화율과
  일치하지 않는 게 정상이다.
- 수치는 단위가 이질적이라(`+3.5%`, `216K`, `3.50~3.75%`) 문자열 그대로 저장한다.
- **요구사항**: `python3`(표준 라이브러리만). **종료 코드**: `0` 정상, `1` 유효 행/조회
  결과 0건, `2` 입출력·인자 오류.

> CSV를 `archive/` 아래 두는 건 의도적이다. `sync-archive-to-main.yml`은 `archive/**`만
> main으로 동기화하고 일일 브리핑은 PR을 만들지 않으므로, 레포 루트에 두면 main에
> 반영되지 않는다.
