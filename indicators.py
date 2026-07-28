#!/usr/bin/env python3
"""주요 경제지표 실적 아카이브 (briefing-prompt.md Section 4가 호출).

브리핑 본문과 별개로 CPI·PCE·기준금리 등 핵심 지표의 **발표된 실제치**를
archive/indicators.csv에 시계열로 누적한다. 미래 일정은 매일 바뀌므로 저장하지
않는다 — 실제치가 확정된 것만 기록한다.

CSV를 archive/ 아래 두는 이유: .github/workflows/sync-archive-to-main.yml이
'archive/**' 경로만 main으로 동기화한다. 레포 루트에 두면 main에 도달하지 못한다.

외부 의존성 없음 — Python 표준 라이브러리만 사용한다.

사용 예:
    # 기록 (stdin, 헤더 없는 CSV 행). 같은 키를 다시 넣으면 값이 갱신된다.
    python3 indicators.py record <<'EOF'
    2026-07-29,03:00,US,FOMC 기준금리,2026-07,3.50~3.75%,3.50~3.75%,3.50~3.75%,Reuters
    EOF

    # 조회 (브리핑의 '지난주 발표' 렌더링용)
    python3 indicators.py show --since 2026-07-22 --until 2026-07-29

종료 코드:
    0  정상
    1  기록한 유효 행 0건 / 조회 결과 0건
    2  CSV 입출력 실패
"""

import argparse
import csv
import datetime as dt
import os
import sys

FIELDS = [
    "release_date", "release_time_kst", "country", "indicator", "period",
    "actual", "forecast", "previous", "source",
]
# 같은 발표를 식별하는 키. 재기록 시 이 키가 같으면 덮어쓴다(속보치→확정치 갱신).
KEY = ("release_date", "country", "indicator", "period")

# 시계열이 끊기지 않으려면 같은 지표가 항상 같은 이름이어야 한다.
# 아카이브에서 "미국 CPI" / "미국 5월 CPI" / "5월 소비자물가지수(CPI)" 처럼
# 표기가 갈렸던 문제를 막기 위해 표준명을 강제한다.
WATCHLIST = {
    "US": ["CPI", "근원 CPI", "PCE 물가", "근원 PCE", "PPI", "비농업고용", "실업률",
           "GDP", "소매판매", "ISM 제조업 PMI", "ISM 서비스업 PMI", "FOMC 기준금리"],
    "KR": ["CPI", "기준금리", "GDP"],
    "EU": ["HICP", "ECB 기준금리", "GDP"],
    "UK": ["CPI", "BOE 기준금리"],
    "JP": ["CPI", "BOJ 기준금리"],
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
    """CSV를 dict 리스트로 읽는다. 파일이 없으면 빈 리스트."""
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def save(path, rows):
    rows.sort(key=lambda r: (r["release_date"], r["country"], r["indicator"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


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
    # 미래 일정은 저장하지 않는다 — 실제치가 있어야 시계열이 된다.
    if not row["actual"]:
        log(f"  skip L{lineno}: actual 없음 (발표 전 일정은 기록하지 않는다)")
        return None
    return row


def cmd_record(args):
    rows = load(CSV_PATH)
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
            if index[key] == row:
                unchanged += 1
            else:
                index[key].update(row)
                updated += 1
                log(f"  갱신 {row['release_date']} {row['country']} {row['indicator']}")
        else:
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
    except OSError as e:
        log(f"CSV 쓰기 실패: {e}")
        return 2

    log(f"기록 완료: 신규 {added} · 갱신 {updated} · 변경없음 {unchanged} "
        f"(총 {len(rows)}행) → {CSV_PATH}")
    return 0


def cmd_show(args):
    since, until = parse_date(args.since), parse_date(args.until)
    if since is None or until is None:
        log("--since/--until 형식 오류 (YYYY-MM-DD)")
        return 2

    try:
        rows = load(CSV_PATH)
    except OSError as e:
        log(f"CSV 읽기 실패: {e}")
        return 2

    hits = []
    for r in rows:
        d = parse_date(r["release_date"])
        if d is not None and since <= d <= until:
            hits.append((d, r))
    hits.sort(key=lambda x: (x[0], x[1]["country"], x[1]["indicator"]))

    if not hits:
        log(f"{since} ~ {until} 기록 없음")
        return 1

    for _, r in hits:
        parts = [r["release_date"], r["country"], r["indicator"]]
        if r["period"]:
            parts.append(r["period"])
        parts.append(f"실제 {r['actual']}")
        if r["forecast"]:
            parts.append(f"예상 {r['forecast']}")
        if r["previous"]:
            parts.append(f"이전 {r['previous']}")
        if r["source"]:
            parts.append(r["source"])
        print(" | ".join(parts))

    log(f"조회 완료: {len(hits)}건")
    return 0


def main():
    ap = argparse.ArgumentParser(description="주요 경제지표 실적 아카이브")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="stdin의 CSV 행을 upsert (헤더 없음)")
    p_rec.set_defaults(func=cmd_record)

    p_show = sub.add_parser("show", help="기간 내 기록 조회")
    p_show.add_argument("--since", required=True, help="시작일 (YYYY-MM-DD)")
    p_show.add_argument("--until", required=True, help="종료일 (YYYY-MM-DD)")
    p_show.set_defaults(func=cmd_show)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
