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
| `archive/` | 매일 발송된 브리핑 본문(`{날짜}.md`)을 누적 보관(향후 리뷰·개선용). |

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
