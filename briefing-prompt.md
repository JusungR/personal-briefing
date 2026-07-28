# 일일 브리핑 루틴

## 날짜 계산 (최우선)

시스템이 제공하는 `currentDate`는 UTC 기준 날짜만 제공한다(시각 미포함).
한국 시간(KST, UTC+9)으로 오늘 날짜를 먼저 계산한다.

- UTC 00:00~14:59 → KST는 UTC와 **같은 날**
- UTC 15:00~23:59 → KST는 UTC **다음 날** (KST_TODAY = UTC currentDate + 1일)
- 예) UTC 2026-05-27, 시각 미상 → 보수적으로 KST 2026-05-28로 간주
- 예) UTC 2026-05-28, 시각 미상 → 보수적으로 KST 2026-05-29로 간주

> 브리핑은 통상 한국 아침에 실행되므로, UTC 시각이 미상일 때는
> KST = UTC currentDate + 1일로 계산한다(보수적 기준).

아래 두 날짜 변수를 먼저 확정한 뒤 이하 모든 섹션에 적용한다.

| 변수 | 값 | 용도 |
|---|---|---|
| **KST_TODAY** | UTC currentDate + 1일 | 날씨·일정·메일 제목 |
| **NEWS_DATE** | KST_TODAY - 1일 (= UTC currentDate) | 간밤 뉴스 검색 날짜 |

---

오늘의 일일 브리핑을 작성한다. 한국어, 간결한 문장.
세 개의 섹션을 순서대로 출력하고, 마지막에 전체를 하나의
정리된 메시지로 한 번 더 모아서 마무리한다.

> **출력 형식:** 최종 산출물의 형식은 `template.md`에 정의돼 있다. 이 파일은
> "무엇을 어떻게 수집·검증·발송하는가"(절차·로직)를 정하고, "결과물이 어떻게
> 보이는가"(레이아웃)는 `template.md`를 따른다.

## 1. 날씨 (서울)

WebSearch로 오늘 서울 날씨 조회:
- 최저/최고 기온, 강수 확률, 미세먼지·초미세먼지 등급
- 한 줄 권고 (우산/겉옷/마스크 여부)

→ 출력 레이아웃: `template.md` **A-2 날씨 블록**.

## 2. 오늘 일정

Google Calendar의 `list_events`로 **KST_TODAY** 00:00 ~ 24:00 (Asia/Seoul) 범위의 이벤트 조회.
- `startTime`: `{KST_TODAY}T00:00:00+09:00`
- `endTime`:   `{KST_TODAY}T23:59:59+09:00`
- `timeZone`: `Asia/Seoul`
- 시간순으로 나열한다. 일정이 비어 있으면 "오늘 등록된 일정 없음".

→ 출력 레이아웃: `template.md` **A-3 일정 블록**.

## 3. 간밤 미국·유럽 주요 뉴스

**NEWS_DATE** 현지 시간 기준(= 한국이 자는 동안 미국·유럽의 낮/저녁) 발생한 주요
뉴스를 수집한다. 검증된 RSS 피드를 먼저 수집하고, WebSearch는 확인·보강용으로만 쓴다.

### 3-1. 피드 수집 (먼저 실행)

Bash로 뉴스 수집 스크립트를 실행해 분야별 후보 목록을 받는다:

```bash
python3 /home/user/personal-briefing/collect-news.py --news-date {NEWS_DATE}
```

- stdout에 `AI/TECH · ECONOMY · MARKETS · POLITICS · OTHER MAJOR` 그룹별로 점수순 후보가 출력된다.
  각 항목은 `[score | 출처(+N 매체) | 지역 | 시각]`, 헤드라인, 요약, url 형식.
- 수집 윈도우는 **NEWS_DATE 00:00 UTC에 고정**돼 있어, 전날 브리핑에 나간 기사가
  다시 후보로 올라오지 않는다(전일자 중복 방지). 별도 `--hours`는 지정하지 않는다.
- **스크립트가 실패하거나(exit≠0) 결과가 비면**, 아래 3-3의 기존 WebSearch-only 방식으로
  폴백한다. (브리핑은 절대 거르지 않는다.)

### 3-2. 선택과 검증

1. **분야별 선별 (기술·경제·정치)**: 후보를 세 분야로 묶어 각 **3~5건** 고른다.
   점수가 높고 여러 매체가 함께 보도한(`+N 매체`) 기사를 우선한다.
   - 분야 매핑: 기술 ← `AI/TECH`, 경제 ← `ECONOMY`+`MARKETS`,
     정치 ← `POLITICS` (부족하면 `OTHER MAJOR`의 지정학·정치 헤드라인으로 보완).
   - 가십·연예·스포츠 제외. (지역 캡 없음 — 미·유럽 뉴스를 분야로만 묶는다.)
2. **신선도·정확도**: 각 후보의 시각이 NEWS_DATE 윈도우 안인지 확인하고, 오래되거나
   어긋나는 항목은 버린다. 상위 2~3개 핵심 기사는 **WebSearch로 사실·최신 전개를 확인**한다.
   - 로이터·FT·NYT·가디언·The Verge·Ars Technica는 이제 Google News(`출처`가 매체명으로
     표기되는 항목)로 직접 유입된다. 단 이 항목들은 **요약이 비어 있고 url이 Google
     리다이렉트**이므로, 헤드라인만 보고 인용하지 말고 상위 기사는 WebSearch로 사실을
     확인한 뒤 인용한다.
   - WebSearch는 확인·확장용이지 주 수집기가 아니다.

### 3-3. 출력 형식 (폴백 시에도 동일)

- 분야: 기술 · 경제 · 정치. 분야별 **한 줄에 한 주제씩 3~5건**. 가십·연예·스포츠 제외.
- 1~2문장 요약 없이, 주제를 한 줄로 압축하고 끝에 (출처)를 붙인다.
- 미확인·추측성 보도는 "보도됨", "~로 전해졌다" 같은 표현으로 단정 회피.

→ 출력 레이아웃: `template.md` **A-4 뉴스 블록**.

> 폴백(스크립트 미작동 시): **NEWS_DATE** 기준 미·유럽 주요 뉴스를 WebSearch로 직접
> 조회해 기술·경제·정치 분야별 3~5건씩 채운다. 1차 출처(로이터, AP, FT, BBC, Bloomberg, WSJ 등) 우선.

---

## 4. 경제지표 (지난 7일 실적 + 향후 7일 일정)

범위는 **KST_TODAY - 7일 ~ KST_TODAY + 7일**이다. 지난 7일은 이미 발표된 **실제치**를,
향후 7일은 아직 안 나온 **일정**을 다룬다.

→ 출력 레이아웃: `template.md` **A-5 경제지표 블록**.

### 4-1. 지난 7일 실제치 수집

WebSearch로 **KST_TODAY-7일 ~ KST_TODAY** 사이에 발표된 핵심 지표의 결과를 조회한다.
대상은 `indicators.py`의 watchlist 지표(미국·한국·유로존·영국·일본의 CPI·PCE·PPI·
고용·GDP·소매판매·PMI·기준금리)로 한정한다.

**검색 쿼리 예시:**
```
US CPI actual vs forecast {지난주 범위}
economic calendar results last week {KST_TODAY}
{국가} {지표명} 발표 결과 예상치
```

### 4-2. 아카이브 기록

실제치가 확정된 것만 `indicators.py record`로 기록한다. **발표 전 일정은 넣지 않는다.**

```bash
python3 /home/user/personal-briefing/indicators.py record <<'EOF'
{release_date},{HH:MM},{country},{indicator},{period},{actual},{forecast},{previous},{source}
EOF
```

- 필드 순서: `release_date,release_time_kst,country,indicator,period,actual,forecast,previous,source`
  (`release_date`는 KST 발표일 `YYYY-MM-DD`, `period`는 대상 기간 `2026-06` 또는 `2026Q2`)
- `country`/`indicator`는 **watchlist 표준명**이어야 한다. 틀리면 해당 행만 거부되고
  stderr에 유효 목록이 출력되므로 그걸 보고 고친다.
- 7일 윈도우가 매일 겹치지만 스크립트가 키 `(release_date, country, indicator, period)`로
  upsert하므로 **그대로 다시 넣어도 안전하다**. 속보치가 확정치로 바뀌면 값만 갱신된다.
- 이 단계는 best-effort다. 실패해도 브리핑은 계속 진행한다.

### 4-3. 「지난주 발표」 렌더링

기록된 내용을 다시 읽어 렌더링한다. 오늘 검색에서 놓친 항목도 이전에 기록됐다면
포함되므로, CSV가 이 섹션의 단일 진실 원천이다.

```bash
python3 /home/user/personal-briefing/indicators.py show --since {KST_TODAY-7일} --until {KST_TODAY}
```

- 출력 각 행을 A-5 「▸ 지난주 발표」 형식으로 옮긴다.
- **상회/부합/하회 판단은 여기서 붙인다** (스크립트는 판정하지 않는다).
- exit 1(기록 없음)이면 `기록된 발표 없음` 한 줄만 둔다.

### 4-4. 향후 7일 일정

**KST_TODAY** 기준 향후 7일 내 발표 예정인 한국·미국·유럽·글로벌 주요 지표를
WebSearch로 조회한다. **미래 일정은 CSV에 저장하지 않는다** (매일 바뀌므로).

**검색 쿼리 예시:**
```
economic calendar this week {KST_TODAY} Korea US EU
주요 경제지표 일정 {KST_TODAY} 이번주
```

**포함할 지표 (발표 예정인 것만):**
- 금리 결정 (한국은행, 연준 FOMC, ECB, BOJ 등)
- 물가 지표: CPI, PCE, PPI
- 고용 지표: 비농업 고용(NFP), 실업률, ADP
- 성장 지표: GDP(속보·확정치), 소매판매
- 제조업·서비스업: PMI, ISM
- 기타 시장 주목도 높은 지표

- 날짜·시간은 KST 기준으로 표기한다.
- 예상치·이전치가 없으면 생략해도 된다.
- 발표 일정이 없는 날은 출력하지 않는다.
- 조회 결과가 불확실하면 "일정 미확인"으로 표기하고 넘어간다(브리핑 전체에 영향 없음).

---

## 5. 완성 및 메일 발송

전체 브리핑 콘텐츠를 하나의 정리된 메시지로 작성한 후 Gmail로 발송한다.

**메일 발송:**
- 받는 사람: yhwsr92@gmail.com
- 제목: `[Daily Briefing] {KST_TODAY}`
- 본문: 위의 1, 2, 3, 4번 섹션을 `template.md` **A 형식**으로 구성한 뒤,
  **맨 아래에 뉴스 원문 링크 목록을 추가**한다.
- 발송 도구: `mcp__Gmail__create_draft` (Gmail 드래프트 생성)

**뉴스 원문 링크 (본문 최하단):** 레이아웃은 `template.md` **A-6 원문 링크 블록**.

- 본문에 인용된 기사 순서대로 나열한다.
- URL은 collect-news.py 출력의 url 필드를 그대로 사용한다.
  Google News 리다이렉트 URL도 그대로 남긴다(원문 확인용으로 충분).
- WebSearch로 사실 확인한 기사는 해당 WebSearch 결과 URL을 사용한다.
- 폴백(WebSearch-only) 시에도 동일하게 링크 목록을 추가한다.

> **자동 발송 제한:** 현재 Gmail MCP는 `create_draft`(임시저장)만 지원하며
> 직접 발송 API는 제공되지 않는다. 드래프트 생성 후 Gmail에서 수동 발송하거나,
> Google Apps Script로 별도 자동 발송 트리거를 구성해야 한다.

---

## 6. 텔레그램 요약 발송

Gmail 드래프트 생성 완료 후, 아래 Python 코드를 Bash 도구로 실행하여 텔레그램으로 요약본을 발송한다.

**텔레그램 메시지 형식:** 레이아웃은 `template.md` **B 텔레그램 요약**.
뉴스는 분야(기술→경제→정치)별로 한 줄에 한 주제씩 적는다(본문 설명 제외). 총 메시지 길이가 4000자를 넘으면 뉴스 항목 수를 줄여 조정하되, **점수가 낮은 항목부터 제거하고 분야(기술·경제·정치)별 최소 1건은 유지**해 균형을 보존한다.

**발송 명령어:**

> **시크릿 주입:** 토큰과 챗 ID는 코드/저장소에 하드코딩하지 않고 **환경변수**로 읽는다.
> 클로드루틴 환경설정에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 등록해 두어야 한다.
> 둘 중 하나라도 비어 있으면 발송을 건너뛰고 그 사실을 출력한다(브리핑 자체는 영향 없음).

메시지를 stdin으로 전달한다. 파일에 메시지를 저장하거나 수정하지 않는다.

```bash
python3 /home/user/personal-briefing/send_telegram.py << 'EOF'
<위 형식대로 작성한 브리핑 요약 삽입>
EOF
```

`r.status_code`가 200이면 성공. 실패 시 `r.text`의 오류 메시지를 확인한다.
스크립트는 4096자 안전 캡·timeout·네트워크 재시도·Markdown 파싱 실패 시 plain text
폴백을 적용한다(4000자 트림은 위 1차 제어로 유지).

---

## 7. 브리핑 기록 및 보관 (git commit)

발송이 끝나면, 향후 리뷰·개선 분석을 위해 오늘 브리핑을 레포에 보관한다.
이 단계는 best-effort이며, 실패해도 이미 나간 브리핑에는 영향이 없다.

1. Section 5에서 `mcp__Gmail__create_draft`에 넘긴 **메일 본문 그대로**(=
   `template.md` A 형식)를 `archive/{KST_TODAY}.md` 파일로 저장한다(폴더가 없으면 생성).
   텔레그램 요약본(B 형식)이 아닌, 날씨·일정·뉴스 전체 상세 버전이어야 한다.
2. 아래를 Bash로 실행해 커밋·푸시한다(`{KST_TODAY}`는 실제 날짜로 치환):

```bash
cd /home/user/personal-briefing
git add archive/{KST_TODAY}.md archive/indicators.csv
git commit -m "Archive daily briefing {KST_TODAY}"
git push -u origin HEAD || (sleep 2 && git push -u origin HEAD)
```

- 커밋 메시지는 위 형식을 따른다.
- Section 4-2에서 갱신된 `archive/indicators.csv`도 함께 커밋한다. 변경이 없으면
  `git add`는 아무 일도 하지 않으므로 그대로 둔다.
- 푸시가 네트워크 오류로 실패하면 몇 차례 재시도하되, 끝내 실패해도 브리핑 자체는
  완료된 것으로 간주한다.
