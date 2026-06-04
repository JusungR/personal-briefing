#!/usr/bin/env python3
"""간밤 미국·유럽 뉴스 수집기 (RSS 피드 기반).

브리핑 프롬프트(briefing-prompt.md Section 3)가 Bash로 실행한다.
검증된 RSS 피드 집합에서 기사를 수집·정규화·중복제거·점수화하여
관심분야(경제/시장/AI·기술)별로 균형 잡힌 후보 목록을 stdout으로 출력한다.

외부 의존성 없음 — Python 표준 라이브러리만 사용한다.

수집 윈도우는 기본적으로 NEWS_DATE 00:00 UTC에 고정된다(전일자 중복 방지).
--hours N 을 주면 기존 롤링(now-N) 방식으로 디버그할 수 있다.

사용 예:
    python3 collect-news.py --news-date 2026-05-27
    python3 collect-news.py --news-date 2026-05-27 --hours 30 --config news-feeds.json

종료 코드:
    0  정상(후보 1건 이상 출력)
    1  사용 가능한 기사 0건(모든 피드 실패/빈 결과) → 프롬프트는 WebSearch 폴백
    2  설정 파일 로드 실패
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}
TIMEOUT = 15
AREAS = ("economy", "markets", "ai_tech")
AREA_LABEL = {
    "economy": "ECONOMY (경제)",
    "markets": "MARKETS (시장)",
    "ai_tech": "AI / TECH (기술)",
    "other_major": "OTHER MAJOR (기타 주요)",
}

# Atom/RSS 네임스페이스 정리를 위한 태그 로컬명 추출
_TAG = re.compile(r"\{.*\}")
_HTML_TAG = re.compile(r"<[^>]+>")
_WORD = re.compile(r"[a-z0-9&]+")
# 구글뉴스 제목의 " - 출처" 접미사
_GNEWS_SUFFIX = re.compile(r"\s+-\s+[^-]+$")
# 도메인 → 지역 매핑 (구글뉴스 항목의 <source url>에서 실제 지역 추론)
_DOMAIN_REGION = {
    "reuters.com": "GLOBAL",
    "ft.com": "EU",
    "theguardian.com": "EU",
    "bbc.co.uk": "EU",
    "bbc.com": "EU",
    "nytimes.com": "US",
    "theverge.com": "US",
    "arstechnica.com": "US",
}
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "as", "at",
    "by", "is", "are", "be", "with", "from", "after", "over", "amid",
    "says", "say", "new", "us", "uk",
}


def localname(tag):
    return _TAG.sub("", tag or "")


def domain_to_region(domain):
    """도메인 문자열에서 지역(US/EU/GLOBAL) 추론. 매칭 없으면 None."""
    if not domain:
        return None
    domain = domain.lower()
    for host, region in _DOMAIN_REGION.items():
        if host in domain:
            return region
    return None


def log(msg):
    print(msg, file=sys.stderr)


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def strip_html(text):
    if not text:
        return ""
    text = _HTML_TAG.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value):
    """RFC-822 / ISO-8601 등 여러 포맷을 tz-aware UTC로 정규화. 실패 시 None."""
    if not value:
        return None
    value = value.strip()
    # RFC-822 (pubDate)
    try:
        d = parsedate_to_datetime(value)
        if d is not None:
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            return d.astimezone(dt.timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    # ISO-8601 (Atom updated/published). 'Z' 처리.
    iso = value.replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(iso)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc)
    except ValueError:
        pass
    # 마지막 폴백: 흔한 포맷 몇 개
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            d = dt.datetime.strptime(value, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            return d.astimezone(dt.timezone.utc)
        except ValueError:
            continue
    return None


def extract_entries(raw, feed):
    """RSS <item> 와 Atom <entry> 모두 처리해 정규화된 dict 리스트 반환."""
    is_gnews = feed.get("type") == "gnews"
    entries = []
    root = ET.fromstring(raw)
    nodes = []
    for el in root.iter():
        if localname(el.tag) in ("item", "entry"):
            nodes.append(el)
    for node in nodes:
        title = ""
        link = ""
        summary = ""
        published = None
        src_name = ""
        src_domain = ""
        for child in node:
            name = localname(child.tag)
            if name == "title":
                title = strip_html(child.text or "")
            elif name == "link":
                # RSS: text. Atom: href 속성.
                href = child.attrib.get("href")
                if href:
                    # rel="alternate" 또는 rel 없는 것을 우선
                    if child.attrib.get("rel", "alternate") == "alternate" or not link:
                        link = href
                elif child.text:
                    link = child.text.strip()
            elif name == "source":
                # 구글뉴스: <source url="https://www.reuters.com">Reuters</source>
                src_name = strip_html(child.text or "")
                src_domain = child.attrib.get("url", "")
            elif name in ("description", "summary", "content"):
                if not summary:
                    summary = strip_html(child.text or "")
            elif name in ("pubDate", "published", "updated", "date"):
                if published is None:
                    published = parse_date(child.text or "")
        if not title:
            continue

        source = feed["name"]
        region = feed.get("region", "US")
        if is_gnews:
            # 실제 출처/지역은 <source>에서 파생 (config 값은 폴백).
            if src_name:
                source = src_name
            region = domain_to_region(src_domain) or region
            # 제목 끝 " - 출처" 접미사 제거: <source> 텍스트와 일치할 때만 잘라
            # 하이픈 포함 헤드라인의 과제거를 방지한다.
            m = _GNEWS_SUFFIX.search(title)
            if m and (not src_name or m.group(0).strip(" -") == src_name):
                title = title[:m.start()].strip()
            # 구글뉴스 description은 <a> 링크일 뿐 요약이 아니다 → 비운다.
            summary = ""

        entries.append({
            "title": title,
            "link": link,
            "summary": summary[:400],
            "published": published,
            "source": source,
            "tier": feed.get("tier", 2),
            "region": region,
            "feed_area": feed.get("area", "economy"),
        })
    return entries


def load_one_feed(feed):
    try:
        raw = fetch(feed["url"])
        items = extract_entries(raw, feed)
        log(f"  ok   {feed['name']}: {len(items)} items")
        return items
    except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError,
            ValueError, OSError) as e:
        log(f"  skip {feed['name']}: {type(e).__name__}: {e}")
        return []


def norm_title_words(title):
    words = _WORD.findall(title.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


def title_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def dedupe(entries, threshold):
    """제목 유사도로 동일 사건 병합. 높은 tier/최신을 대표로, 나머지는 출처로 기록."""
    kept = []
    for e in entries:
        e_norm = " ".join(norm_title_words(e["title"]))
        merged = False
        for k in kept:
            if title_similarity(e_norm, k["_norm"]) > threshold:
                k["corroboration"] += 1
                # 대표 교체: 더 높은 tier(작은 숫자) 우선, 동률이면 최신
                better_tier = e["tier"] < k["tier"]
                same_tier_newer = (
                    e["tier"] == k["tier"]
                    and e["published"] is not None
                    and (k["published"] is None or e["published"] > k["published"])
                )
                if better_tier or same_tier_newer:
                    corr = k["corroboration"]
                    e["_norm"] = e_norm
                    e["corroboration"] = corr
                    kept[kept.index(k)] = e
                merged = True
                break
        if not merged:
            e["_norm"] = e_norm
            e["corroboration"] = 0
            kept.append(e)
    return kept


def compile_keyword_patterns(words):
    """키워드 리스트를 단어경계 정규식 리스트로 사전컴파일.

    substring 매칭의 오탐(ai→rain/said, oil→boiling, meta→metadata, rate→accurate)을
    막기 위해 영숫자 경계 lookaround를 쓴다. \\b는 's&p'의 '&' 같은 비단어문자에
    맞지 않으므로 커스텀 경계 `(?<![a-z0-9]) ... (?![a-z0-9])`를 사용한다.
    다단어구('interest rate', 'data center')는 공백을 \\s+로 치환해 매칭한다.
    """
    patterns = []
    for w in words:
        body = re.escape(w).replace(r"\ ", r"\s+")
        patterns.append(re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])",
                                   re.IGNORECASE))
    return patterns


def keyword_hits(text, patterns):
    return sum(1 for p in patterns if p.search(text))


def score_and_classify(entry, keywords, now):
    text = entry["title"] + " " + entry["summary"]
    hits = {area: keyword_hits(text, keywords[area]) for area in AREAS}
    best_area = max(AREAS, key=lambda a: hits[a])
    if hits[best_area] == 0:
        # 키워드 매칭 없음 → 피드의 기본 area 유지하되 기타로도 갈 수 있게 표시
        best_area = entry["feed_area"]
        area_score = 0
    else:
        area_score = hits[best_area]

    tier_score = 3 - entry["tier"]  # tier1 -> 2, tier2 -> 1

    if entry["published"] is not None:
        age_h = max(0.0, (now - entry["published"]).total_seconds() / 3600.0)
        recency_score = max(0.0, 2.0 - age_h / 15.0)  # 신선할수록 가산
    else:
        recency_score = 0.0

    corroboration_score = min(entry["corroboration"], 4) * 0.8

    total = (
        area_score * 1.5
        + tier_score * 1.0
        + recency_score * 1.0
        + corroboration_score
    )
    entry["area"] = best_area
    entry["score"] = round(total, 2)
    entry["had_keyword"] = area_score > 0
    return entry


def group_entries(entries, cap):
    groups = {a: [] for a in AREAS}
    groups["other_major"] = []
    for e in entries:
        if e["had_keyword"]:
            groups[e["area"]].append(e)
        else:
            groups["other_major"].append(e)
    for key in groups:
        groups[key].sort(key=lambda x: x["score"], reverse=True)
        groups[key] = groups[key][:cap]
    return groups


def fmt_entry(e):
    when = e["published"].strftime("%Y-%m-%d %H:%MZ") if e["published"] else "날짜미상"
    src = e["source"]
    if e["corroboration"] > 0:
        src += f" (+{e['corroboration']} 매체)"
    lines = [
        f"[score {e['score']} | {src} | {e['region']} | {when}]",
        e["title"],
    ]
    if e["summary"]:
        lines.append(f"요약: {e['summary']}")
    if e["link"]:
        lines.append(f"url: {e['link']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="RSS 기반 간밤 뉴스 수집기")
    ap.add_argument("--news-date", required=True, help="NEWS_DATE (YYYY-MM-DD)")
    ap.add_argument("--hours", type=int, default=None,
                    help="롤링 윈도우(시간) 강제. 미지정 시 NEWS_DATE 00:00 UTC에 고정(전일자 중복 방지)")
    default_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news-feeds.json")
    ap.add_argument("--config", default=default_cfg, help="피드 설정 JSON 경로")
    args = ap.parse_args()

    try:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log(f"설정 로드 실패: {e}")
        return 2

    feeds = cfg.get("feeds", [])
    patterns = {a: compile_keyword_patterns(cfg.get("keywords", {}).get(a, [])) for a in AREAS}
    cap = int(cfg.get("per_group_cap", 8))
    threshold = float(cfg.get("dedupe_threshold", 0.72))

    now = dt.datetime.now(dt.timezone.utc)

    # 수집 윈도우.
    #  - 기본: NEWS_DATE 00:00 UTC에 고정(전일자 중복 방지). 연속 이틀 윈도우가 겹치지 않아
    #    롤링 30h가 미 오후 프라임타임에서 만들던 6h 재노출이 사라진다.
    #  - --hours N 명시 시: 기존 롤링(now - N)으로 복귀(디버그용 escape hatch).
    if args.hours is not None:
        hours = args.hours
        cutoff = now - dt.timedelta(hours=hours)
        window_desc = f"롤링 {hours}h"
    else:
        lead = int(cfg.get("window_lead_hours", 0))
        try:
            nd = dt.datetime.strptime(args.news_date, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            log(f"--news-date 파싱 실패: {args.news_date!r} (YYYY-MM-DD)")
            return 2
        cutoff = nd - dt.timedelta(hours=lead)
        window_desc = f"NEWS_DATE 고정(lead {lead}h)"

    log(f"수집 시작: {len(feeds)}개 피드, 윈도우 {window_desc} (cutoff {cutoff:%Y-%m-%d %H:%MZ} ~ now {now:%Y-%m-%d %H:%MZ})")

    all_entries = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for items in ex.map(load_one_feed, feeds):
            all_entries.extend(items)

    log(f"수집 합계: {len(all_entries)} items (필터 전)")

    # 신선도 필터: 윈도우 [cutoff, now] 내 항목만. 날짜미상·미래일자는 제외.
    fresh = [
        e for e in all_entries
        if e["published"] is not None and cutoff <= e["published"] <= now
    ]
    log(f"윈도우 내: {len(fresh)} items")

    if not fresh:
        log("사용 가능한 신선한 기사 0건 → 프롬프트는 WebSearch로 폴백해야 함")
        return 1

    deduped = dedupe(fresh, threshold)
    log(f"중복제거 후: {len(deduped)} items")

    scored = [score_and_classify(e, patterns, now) for e in deduped]
    groups = group_entries(scored, cap)

    out = []
    out.append(f"# 간밤 뉴스 후보 (NEWS_DATE={args.news_date}, 윈도우 {window_desc}, 생성 {now:%Y-%m-%d %H:%MZ})")
    out.append(f"# 수집 {len(all_entries)} → 신선 {len(fresh)} → 중복제거 {len(deduped)} items")
    out.append("")
    total_shown = 0
    for key in ("ai_tech", "economy", "markets", "other_major"):
        items = groups.get(key, [])
        out.append(f"=== FOCUS: {AREA_LABEL[key]} — {len(items)}건 ===")
        if not items:
            out.append("(해당 없음)")
        for e in items:
            out.append(fmt_entry(e))
            out.append("---")
            total_shown += 1
        out.append("")

    print("\n".join(out))
    log(f"출력 완료: {total_shown} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
