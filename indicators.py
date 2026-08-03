#!/usr/bin/env python3
"""주요 경제지표 실적 아카이브 (briefing-prompt.md Section 4가 호출).

브리핑 본문과 별개로 CPI·PCE·기준금리 등 핵심 지표의 **발표된 실제치**를
archive/indicators.csv에 시계열로 누적한다. 미래 일정은 매일 바뀌므로 저장하지
않는다 — 실제치가 확정된 것만 기록한다.

CSV를 archive/ 아래 두는 이유: .github/workflows/sync-archive-to-main.yml이
'archive/**' 경로만 main으로 동기화한다. 레포 루트에 두면 main에 도달하지 못한다.

외부 의존성 없음 — Python 표준 라이브러리만 사용한다.

발표값은 level(원계열)·yoy(전년비)·mom(전월비) 세 칸에 나눠 담는다. 브리핑은 보통
yoy/mom만 쓰지만 지수 원계열도 함께 남겨야 나중에 재계산·검증이 가능하다.
셋 중 지표에 해당하는 것만 채우면 되고, 브리핑이 어느 칸을 헤드라인으로 쓸지는
WATCHLIST가 정한다.

사용 예:
    # 기록 (stdin, 헤더 없는 CSV 행). 같은 키를 다시 넣으면 값이 갱신된다.
    #   country,indicator,release_date,release_time_kst,period,
    #   level,yoy,mom,forecast,previous,source
    python3 indicators.py record <<'EOF'
    US,CPI,2026-07-14,21:30,2026-06,325.4,+3.5%,-0.4%,+3.8%,+4.2%,BLS
    US,FOMC 기준금리,2026-07-29,03:00,2026-07,3.50~3.75%,,,3.50~3.75%,3.50~3.75%,Reuters
    EOF

    # 조회 — 기간(브리핑의 '지난주 발표' 렌더링용)
    python3 indicators.py show --since 2026-07-22 --until 2026-07-29

    # 조회 — 지표 시계열
    python3 indicators.py show --country US --indicator CPI

종료 코드:
    0  정상
    1  기록한 유효 행 0건 / 조회 결과 0건
    2  CSV 입출력 실패 · CSV 손상 · 인자 오류
"""

import argparse
import csv
import datetime as dt
import os
import sys

# country·indicator를 앞에 두어 정렬키가 곧 열 순서가 되게 한다 —
# 파일을 그냥 열어도 같은 지표가 연속 블록으로 보인다.
FIELDS = [
    "country", "indicator", "release_date", "release_time_kst", "period",
    "level", "yoy", "mom", "forecast", "previous", "source",
]
# 같은 발표를 식별하는 키. 재기록 시 이 키가 같으면 덮어쓴다(속보치→확정치 갱신).
KEY = ("country", "indicator", "release_date", "period")
# 발표값을 담는 칸. 셋 중 최소 하나는 있어야 기록된다.
VALUE_FIELDS = ("level", "yoy", "mom")

# 시계열이 끊기지 않으려면 같은 지표가 항상 같은 이름이어야 한다.
# 아카이브에서 "미국 CPI" / "미국 5월 CPI" / "5월 소비자물가지수(CPI)" 처럼
# 표기가 갈렸던 문제를 막기 위해 표준명을 강제한다.
#
# 값은 브리핑이 헤드라인으로 쓰는 칸이다. 지표마다 관례가 다르다 —
# 물가는 전년비(yoy), 고용·소매판매는 전월 증감(mom), 금리·PMI는 수준(level).
WATCHLIST = {
    "US": {"CPI": "yoy", "근원 CPI": "yoy", "PCE 물가": "yoy", "근원 PCE": "yoy",
           "PPI": "yoy", "비농업고용": "mom", "실업률": "level", "GDP": "yoy",
           "소매판매": "mom", "ISM 제조업 PMI": "level", "ISM 서비스업 PMI": "level",
           "FOMC 기준금리": "level"},
    "KR": {"CPI": "yoy", "기준금리": "level", "GDP": "yoy"},
    "EU": {"HICP": "yoy", "ECB 기준금리": "level", "GDP": "yoy"},
    "UK": {"CPI": "yoy", "BOE 기준금리": "level"},
    "JP": {"CPI": "yoy", "BOJ 기준금리": "level"},
}

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "archive", "indicators.csv")


def log(msg):
    print(msg, file=sys.stderr)


def parse_date(value):
    """YYYY-MM-DD → date. 실패 시 None."""
    try:
        return dt.datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def load(path):
    """CSV를 dict 리스트로 읽는다. 파일이 없으면 빈 리스트.

    손상된 행은 조용히 넘기지 않고 ValueError를 낸다. 필드 수가 헤더와 어긋난 행을
    그대로 들고 가면 쓰기 단계에서 터지는데, 그때는 이미 파일을 연 뒤라 손을 쓰기
    어렵다. 읽는 즉시 멈추는 편이 안전하고 원인도 분명하다.
    """
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for lineno, row in enumerate(csv.DictReader(f), start=2):
            if None in row:
                raise ValueError(
                    f"{path} L{lineno}: 필드가 헤더보다 많다 — 값에 쉼표가 들어갔는지 확인하라")
            if any(v is None for v in row.values()):
                raise ValueError(f"{path} L{lineno}: 필드가 헤더보다 적다")
            rows.append(dict(row))
    return rows


def save(path, rows):
    """지표별로 묶어 저장한다. 한 지표의 추이를 연속으로 읽을 수 있다.

    임시 파일에 다 쓴 뒤 갈아끼운다. 대상 파일을 바로 열면 쓰다가 예외가 났을 때
    이미 비워진 파일만 남아 아카이브가 잘린다.
    """
    rows.sort(key=lambda r: (r["country"], r["indicator"], r["release_date"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def validate(values, lineno):
    """입력 행 하나를 검증해 dict로 반환. 부적합하면 사유를 남기고 None."""
    if len(values) > len(FIELDS):
        log(f"  skip L{lineno}: 필드가 {len(values)}개 (최대 {len(FIELDS)}개)")
        return None
    values = values + [""] * (len(FIELDS) - len(values))
    row = {k: v.strip() for k, v in zip(FIELDS, values)}

    if parse_date(row["release_date"]) is None:
        log(f"  skip L{lineno}: release_date 형식 오류 {row['release_date']!r} (YYYY-MM-DD)")
        return None
    if row["country"] not in WATCHLIST:
        log(f"  skip L{lineno}: 알 수 없는 country {row['country']!r} "
            f"(유효: {', '.join(WATCHLIST)})")
        return None
    if row["indicator"] not in WATCHLIST[row["country"]]:
        log(f"  skip L{lineno}: {row['country']}의 알 수 없는 indicator {row['indicator']!r}")
        log(f"         유효: {', '.join(WATCHLIST[row['country']])}")
        return None
    return row


def cmd_record(args):
    try:
        rows = load(CSV_PATH)
    except (OSError, ValueError) as e:
        log(f"CSV 읽기 실패: {e}")
        return 2
    index = {tuple(r[k] for k in KEY): r for r in rows}

    added = updated = unchanged = 0
    for lineno, values in enumerate(csv.reader(sys.stdin), start=1):
        if not values or not "".join(values).strip():
            continue
        row = validate(values, lineno)
        if row is None:
            continue
        key = tuple(row[k] for k in KEY)
        if key in index:
            # 값이 있는 칸만 반영한다. 전체를 덮어쓰면 빈 칸 하나를 채우려고 부분 행을
            # 넣었을 때 나머지가 지워진다(나중에 지수 원계열만 알게 되는 경우가 그렇다).
            incoming = {k: v for k, v in row.items() if v}
            if all(index[key].get(k) == v for k, v in incoming.items()):
                unchanged += 1
            else:
                index[key].update(incoming)
                updated += 1
                log(f"  갱신 {row['release_date']} {row['country']} {row['indicator']}")
        else:
            # 새 행은 실제 발표값이 있어야 한다 — 발표 전 일정을 저장하지 않기 위해서다.
            # 기존 행에 예상치·이전치만 덧붙이는 건 보강이므로 이 검사에 걸리지 않는다.
            if not any(row[f] for f in VALUE_FIELDS):
                log(f"  skip L{lineno}: level·yoy·mom이 모두 빈 신규 행 "
                    f"(발표 전 일정은 기록하지 않는다)")
                continue
            index[key] = row
            rows.append(row)
            added += 1

    # 매일 겹치는 7일 윈도우를 그대로 밀어넣는 게 정상 사용이므로,
    # "전부 이미 최신"은 성공이다. 유효 행이 아예 없을 때만 1을 낸다.
    if not (added or updated or unchanged):
        log("기록할 유효 행 없음")
        return 1

    if not (added or updated):
        log(f"변경 없음: {unchanged}행 모두 최신 (총 {len(rows)}행)")
        return 0

    try:
        save(CSV_PATH, rows)
    except (OSError, ValueError) as e:
        log(f"CSV 쓰기 실패: {e}")
        return 2

    log(f"기록 완료: 신규 {added} · 갱신 {updated} · 변경없음 {unchanged} "
        f"(총 {len(rows)}행) → {CSV_PATH}")
    return 0


def fmt_row(r):
    """한 발표를 한 줄로. 헤드라인 값을 앞에 두고 나머지 표현을 뒤에 붙인다."""
    # WATCHLIST에서 빠진 지표(손편집·표준명 변경)도 조회는 되게 한다.
    # 예전엔 KeyError로 죽어 브리핑의 렌더링 단계가 통째로 멈췄다.
    head = WATCHLIST.get(r["country"], {}).get(r["indicator"])
    # 헤드라인 칸이 비어 있으면(예: 지수만 먼저 기록) 값이 있는 칸으로 대체한다.
    if not head or not r[head]:
        head = next((f for f in VALUE_FIELDS if r[f]), None)
    parts = [r["release_date"], r["country"], r["indicator"]]
    if r["period"]:
        parts.append(r["period"])
    parts.append(f"실제 {r[head]}" if head else "실제 미상")
    if r["forecast"]:
        parts.append(f"예상 {r['forecast']}")
    if r["previous"]:
        parts.append(f"이전 {r['previous']}")
    # 헤드라인이 아닌 나머지 표현도 함께 보여준다(원계열·다른 기준).
    extra = [f"{f} {r[f]}" for f in VALUE_FIELDS if f != head and r[f]]
    if extra:
        parts.append("(" + " · ".join(extra) + ")")
    if r["source"]:
        parts.append(r["source"])
    return " | ".join(parts)


def cmd_show(args):
    since = parse_date(args.since) if args.since else None
    until = parse_date(args.until) if args.until else None
    if (args.since and since is None) or (args.until and until is None):
        log("--since/--until 형식 오류 (YYYY-MM-DD)")
        return 2

    try:
        rows = load(CSV_PATH)
    except (OSError, ValueError) as e:
        log(f"CSV 읽기 실패: {e}")
        return 2

    hits = []
    for r in rows:
        d = parse_date(r["release_date"])
        if d is None:
            continue
        if since and d < since:
            continue
        if until and d > until:
            continue
        if args.country and r["country"] != args.country:
            continue
        if args.indicator and r["indicator"] != args.indicator:
            continue
        hits.append((d, r))

    if not hits:
        log("조건에 맞는 기록 없음")
        return 1

    if args.indicator or args.country:
        # 시계열 보기: 지표별로 묶어 추이를 읽는다.
        hits.sort(key=lambda x: (x[1]["country"], x[1]["indicator"], x[0]))
    else:
        # 브리핑의 '지난주 발표' 보기: 발표일 순.
        hits.sort(key=lambda x: (x[0], x[1]["country"], x[1]["indicator"]))

    for _, r in hits:
        print(fmt_row(r))

    log(f"조회 완료: {len(hits)}건")
    return 0


def main():
    ap = argparse.ArgumentParser(description="주요 경제지표 실적 아카이브")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="stdin의 CSV 행을 upsert (헤더 없음)")
    p_rec.set_defaults(func=cmd_record)

    p_show = sub.add_parser("show", help="기록 조회 (기간·국가·지표로 거른다)")
    p_show.add_argument("--since", help="시작일 (YYYY-MM-DD)")
    p_show.add_argument("--until", help="종료일 (YYYY-MM-DD)")
    p_show.add_argument("--country", help="국가 코드 (US/KR/EU/UK/JP)")
    p_show.add_argument("--indicator", help="지표 표준명 (예: CPI)")
    p_show.set_defaults(func=cmd_show)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
