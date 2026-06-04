# personal-briefing

매일 아침 한국어 브리핑(서울 날씨 · 오늘 일정 · 간밤 미국·유럽 뉴스)을 작성해
Gmail 드래프트와 텔레그램으로 보낸다.

## 구성 파일

| 파일 | 역할 |
|---|---|
| `briefing-prompt.md` | 브리핑 작성 루틴(날짜 계산, 날씨, 일정, 뉴스, 발송)의 핵심 명세. Claude가 도구로 실행한다. |
| `collect-news.py` | 간밤 뉴스 수집기. 검증된 RSS 피드에서 기사를 모아 분야별 후보 목록을 출력한다. |
| `news-feeds.json` | 뉴스 피드 목록과 키워드·점수 설정(데이터 기반, 자유롭게 편집). |
| `gas-auto-send/Code.gs` | `[Daily Briefing]` Gmail 드래프트를 매일 자동 발송하는 Google Apps Script. |

## 환경 변수

비밀값은 코드/깃에 두지 않고 원격 실행 환경(클로드루틴)의 환경 설정에 등록한다.

| 환경 변수 | 용도 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 인증 토큰(BotFather 발급) |
| `TELEGRAM_CHAT_ID` | 브리핑 요약을 받을 chat_id |

> 토큰이 과거 커밋에 노출된 적이 있으면 BotFather에서 **재발급(revoke)** 해 무효화한다.
> 깃 히스토리에 남은 값은 코드 수정만으로는 사라지지 않는다.

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

### 피드 편집 (news-feeds.json)

`feeds` 배열에 `{name, url, area, tier, region}`을 추가/삭제하면 된다.
`area`는 `economy|markets|ai_tech`, `tier`는 `1`(주요 1차 출처) 또는 `2`, `region`은 `US|EU|GLOBAL`.
`keywords`로 분야 분류 키워드를, `window_hours_default`/`per_group_cap`/`dedupe_threshold`로
동작을 조정한다.

#### 제외된 피드 (재추가 금지)

아래 출처는 RSS 품질이 좋지만 스크립트 접근이 불가하거나 갱신이 멈춰 **의도적으로 제외**했다.
대신 `briefing-prompt.md` Section 3의 WebSearch 확인 단계에서 보강한다.

- **WSJ** (`feeds.a.dj.com/...`): HTTP 200이지만 2025-01 이후 갱신 중단(약 16개월 묵은 기사) → 신선도 오염.
- **FT · The Guardian · NYT · The Verge · Ars Technica**: 스크립트 접근 시 403(봇 차단).
- **Reuters** (`feeds.reuters.com`): 공개 RSS 폐지(DNS 실패).
