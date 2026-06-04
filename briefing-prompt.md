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

## 1. 날씨 (서울)

WebSearch로 오늘 서울 날씨 조회:
- 최저/최고 기온, 강수 확률, 미세먼지·초미세먼지 등급
- 한 줄 권고 (우산/겉옷/마스크 여부)

## 2. 오늘 일정

Google Calendar의 `list_events`로 **KST_TODAY** 00:00 ~ 24:00 (Asia/Seoul) 범위의 이벤트 조회.
- `startTime`: `{KST_TODAY}T00:00:00+09:00`
- `endTime`:   `{KST_TODAY}T23:59:59+09:00`
- `timeZone`: `Asia/Seoul`
- 시간순 나열: "HH:MM  제목  (위치 또는 회의 링크)"
- 종일 일정: "[종일] 제목"
- 일정이 비어 있으면 "오늘 등록된 일정 없음"

## 3. 간밤 미국·유럽 주요 뉴스

**NEWS_DATE** 현지 시간 기준(= 한국이 자는 동안 미국·유럽의 낮/저녁) 발생한 주요
뉴스를 수집한다. 검증된 RSS 피드를 먼저 수집하고, WebSearch는 확인·보강용으로만 쓴다.

### 3-1. 피드 수집 (먼저 실행)

Bash로 뉴스 수집 스크립트를 실행해 분야별 후보 목록을 받는다:

```bash
python3 /home/user/personal-briefing/collect-news.py --news-date {NEWS_DATE} --hours 30
```

- stdout에 `AI/TECH · ECONOMY · MARKETS · OTHER MAJOR` 그룹별로 점수순 후보가 출력된다.
  각 항목은 `[score | 출처(+N 매체) | 지역 | 시각]`, 헤드라인, 요약, url 형식.
- **스크립트가 실패하거나(exit≠0) 결과가 비면**, 아래 3-3의 기존 WebSearch-only 방식으로
  폴백한다. (브리핑은 절대 거르지 않는다.)

### 3-2. 선택과 검증

1. **중요도·균형 (관심분야 우선)**: 후보에서 **경제·주식시장·AI/기술**을 균형 있게
   고른다(분야별 대략 2~4건). 점수가 높고 여러 매체가 함께 보도한(`+N 매체`) 기사를
   우선한다. 남는 자리는 `OTHER MAJOR`의 주요 미·유럽 뉴스로 채운다.
   - 캡: 미국 최대 5건, 유럽 최대 5건. 가십·연예·스포츠 제외.
2. **신선도·정확도**: 각 후보의 시각이 NEWS_DATE 윈도우 안인지 확인하고, 오래되거나
   어긋나는 항목은 버린다. 상위 2~3개 핵심 기사는 **WebSearch로 사실·최신 전개를 확인**하고,
   스크립트가 닿지 못하는 1차 출처(로이터, FT, NYT, 가디언 등)를 보강한다.
   WebSearch는 확인·확장용이지 주 수집기가 아니다.

### 3-3. 출력 형식 (폴백 시에도 동일)

- 카테고리: 정치, 경제, 산업·기술, 시장. 가십·연예·스포츠 제외.
- 항목 형식:
  **헤드라인 (한국어)**
  1~2문장 요약. 출처: 매체명
- 같은 사건이 여러 매체에 나오면 최상위 1차 출처 한 곳만(병합 시 "다수 매체") 인용.
- 미확인·추측성 보도는 "보도됨", "~로 전해졌다" 같은 표현으로 단정 회피.

> 폴백(스크립트 미작동 시): **NEWS_DATE** 기준 주요 뉴스를 WebSearch로 직접 조회한다.
> 미국 최대 5건, 유럽 최대 5건, 1차 출처(로이터, AP, FT, BBC, Bloomberg, WSJ 등) 우선.

---

## 4. 완성 및 메일 발송 + 텔레그램 전송

전체 브리핑 콘텐츠를 하나의 정리된 메시지로 작성한 후 Gmail로 발송한다.

**메일 발송:**
- 받는 사람: yhwsr92@gmail.com
- 제목: `[Daily Briefing] {KST_TODAY}`
- 본문: 위의 1, 2, 3번 섹션을 정리된 형식으로 구성
- 발송 도구: `mcp__Gmail__create_draft` (Gmail 드래프트 생성)

> **자동 발송 제한:** 현재 Gmail MCP는 `create_draft`(임시저장)만 지원하며
> 직접 발송 API는 제공되지 않는다. 드래프트 생성 후 Gmail에서 수동 발송하거나,
> Google Apps Script로 별도 자동 발송 트리거를 구성해야 한다.

---

## 5. 텔레그램 요약 발송

Gmail 드래프트 생성 완료 후, 아래 Python 코드를 Bash 도구로 실행하여 텔레그램으로 요약본을 발송한다.

**텔레그램 메시지 형식 (Markdown):**
```
📋 *Daily Briefing — {KST_TODAY}*

☁️ *날씨 (서울)*
• 최저/최고 기온, 강수 확률
• 미세먼지 등급
• 한 줄 권고

📅 *오늘 일정*
• HH:MM 제목 (또는 "오늘 등록된 일정 없음")

🌐 *간밤 주요 뉴스*
🇺🇸 미국
• 헤드라인 1 (출처)
• 헤드라인 2 (출처)
...
🇪🇺 유럽
• 헤드라인 1 (출처)
• 헤드라인 2 (출처)
...
```

뉴스는 헤드라인과 출처만 한 줄로 요약한다(본문 설명 제외). 총 메시지 길이가 4000자를 넘으면 뉴스 항목 수를 줄여 조정하되, **점수가 낮은 항목부터 제거하고 관심분야(경제·시장·AI/기술)별 최소 1건은 유지**해 균형을 보존한다.

**토큰 관리 (중요):** 봇 토큰과 chat_id는 코드에 하드코딩하지 않고 **환경 변수**로 주입한다.
원격 실행 환경(클로드루틴)의 환경 설정에서 아래 두 변수를 등록해 둔다.

| 환경 변수 | 값 | 용도 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather 발급 토큰 | 텔레그램 봇 인증 |
| `TELEGRAM_CHAT_ID` | 수신 chat_id | 메시지 수신 대상 |

**Python 실행 코드:**
```python
import os
import sys
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
if not TOKEN or not CHAT_ID:
    sys.exit("환경 변수 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 설정되지 않았습니다.")

text = """<위 형식대로 작성한 브리핑 요약 삽입>"""

r = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
)
print(r.status_code, r.text)
```

`r.status_code`가 200이면 성공. 실패 시 `r.text`의 오류 메시지를 확인한다.

> **참고:** 과거 커밋에 토큰이 노출된 적이 있으면 BotFather에서 토큰을 재발급해 무효화한다.
