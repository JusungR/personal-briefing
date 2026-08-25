#!/usr/bin/env python3
"""날씨 예보·우산 권고 아카이브 (briefing-prompt.md Section 1이 호출).

아침 브리핑이 그날의 예보(강수확률·우산 권고 등급)를 기록하고, 다음 날 브리핑이
같은 행에 실제 강수 여부를 덧씌운다. 권고가 실제와 얼마나 맞았는지 사후 검증하기
위한 데이터다 — 아카이브 80일치에서 74일(93%)에 우산이 언급됐는데 그중 얼마가
옳았는지 되짚을 방법이 없었다.

CSV를 archive/ 아래 두는 이유: .github/workflows/sync-archive-to-main.yml이
'archive/**' 경로만 main으로 동기화한다. 레포 루트에 두면 main에 도달하지 못한다.

외부 의존성 없음 — Python 표준 라이브러리만 사용한다.

사용 예:
    # 오늘 예보 기록 (stdin, 헤더 없는 CSV 행)
    #   date,tmin,tmax,pop,advice,actual_rain,actual_mm,note
    python3 weather.py record <<'EOF'
    2026-08-25,24,32,20%,불필요,,,
    EOF

    # 다음 날 실제 강수만 덧씌우기 (값이 있는 칸만 반영되므로 예보는 보존된다)
    python3 weather.py record <<'EOF'
    2026-08-25,,,,,Y,12mm,
    EOF

    # 조회 — 마지막 줄에 적중 집계가 붙는다
    python3 weather.py show --since 2026-08-01 --until 2026-08-25

종료 코드:
    0  정상
    1  기록한 유효 행 0건 / 조회 결과 0건
    2  CSV 입출력 실패 · CSV 손상 · 인자 오류
"""

import argparse
import csv
import datetime as dt
import os
import re
import sys

FIELDS = [
    "date", "tmin", "tmax", "pop", "advice", "actual_rain", "actual_mm", "note",
]
# 하루에 한 행이므로 날짜가 곧 키다. 예보를 넣은 뒤 다음 날 실제치를 같은 키로 덧씌운다.
KEY = ("date",)
# 신규 행은 이 중 최소 하나가 있어야 한다 — 빈 껍데기 행 방지.
VALUE_FIELDS = ("pop", "advice")

# 권고 등급 표준명. 자유서술("가벼운 우산 휴대 권장")을 허용하면 집계가 불가능해진다.
ADVICE_GRADES = ("필수", "권장", "선택", "불필요")
RAIN_VALUES = ("Y", "N", "미확인")

# 강수확률 하한 → 권고 등급. **정본은 briefing-prompt.md Section 1의 임계값 표**이고,
# 여기 사본은 기록 시점에 어긋난 등급을 잡아내는 방어선으로만 쓴다.
THRESHOLDS = ((70, "필수"), (50, "권장"), (30, "선택"), (0, "불필요"))

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "archive", "weather.csv")


def log(msg):
    print(msg, file=sys.stderr)


def parse_date(value):
    """YYYY-MM-DD → date. 실패 시 None."""
    try:
        return dt.datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def parse_pop(value):
    """강수확률 문자열에서 숫자를 뽑는다. '미확인'처럼 숫자가 없으면 None."""
    m = re.search(r"\d+", value or "")
    return int(m.group()) if m else None


def expected_advice(pop):
    for floor, grade in THRESHOLDS:
        if pop >= floor:
            return grade
    return "불필요"


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
        reader = csv.DictReader(f)
        if reader.fieldnames is not None and reader.fieldnames != FIELDS:
            raise ValueError(
                f"{path}: 헤더가 스키마와 다르다 — 마이그레이션이 필요하다\n"
                f"         파일: {','.join(reader.fieldnames)}\n"
                f"         기대: {','.join(FIELDS)}")
        for lineno, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"{path} L{lineno}: 필드가 헤더보다 많다 — 값에 쉼표가 들어갔는지 확인하라")
            if any(v is None for v in row.values()):
                raise ValueError(f"{path} L{lineno}: 필드가 헤더보다 적다")
            rows.append(dict(row))
    return rows


def save(path, rows):
    """날짜순으로 저장한다.

    임시 파일에 다 쓴 뒤 갈아끼운다. 대상 파일을 바로 열면 쓰다가 예외가 났을 때
    이미 비워진 파일만 남아 아카이브가 잘린다.
    """
    rows.sort(key=lambda r: r["date"])
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

    if parse_date(row["date"]) is None:
        log(f"  skip L{lineno}: date 형식 오류 {row['date']!r} (YYYY-MM-DD)")
        return None
    # 빈 칸은 부분 갱신이므로 통과시킨다. 값이 있을 때만 표준명을 강제한다.
    if row["advice"] and row["advice"] not in ADVICE_GRADES:
        log(f"  skip L{lineno}: 알 수 없는 advice {row['advice']!r} "
            f"(유효: {', '.join(ADVICE_GRADES)})")
        return None
    if row["actual_rain"] and row["actual_rain"] not in RAIN_VALUES:
        log(f"  skip L{lineno}: 알 수 없는 actual_rain {row['actual_rain']!r} "
            f"(유효: {', '.join(RAIN_VALUES)})")
        return None
    return row


def check_threshold(pop, advice, lineno):
    """권고 등급이 강수확률 임계값과 어긋나면 경고한다. **행은 거부하지 않는다.**

    호우·뇌우 특보가 걸리면 낮은 강수확률에도 '필수'가 정당하므로 판단은 사람(브리핑)에게
    남기고, 어긋났다는 사실만 기록 시점에 드러낸다. 40%에 '우산 필수'를 적던 과거
    오탐이 여기서 잡힌다.
    """
    p = parse_pop(pop)
    if p is None:
        return
    expected = expected_advice(p)
    if expected != advice:
        log(f"  경고 L{lineno}: 강수확률 {pop} → 기대 등급 {expected!r}인데 {advice!r} "
            f"(특보 예외면 note에 특보명을 적는다)")


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
        existing = index.get(key)

        # 등급을 새로 주장하는 행만 검사한다. 다음 날 실제치만 덧씌우는 행은
        # 이미 경고했던 예보를 다시 경고하지 않는다.
        if row["advice"]:
            check_threshold(row["pop"] or (existing or {}).get("pop", ""),
                            row["advice"], lineno)

        if existing is not None:
            # 값이 있는 칸만 반영한다. 전체를 덮어쓰면 실제 강수만 담은 부분 행을
            # 넣었을 때 예보(기온·강수확률·권고)가 지워진다.
            incoming = {k: v for k, v in row.items() if v}
            if all(existing.get(k) == v for k, v in incoming.items()):
                unchanged += 1
            else:
                existing.update(incoming)
                updated += 1
                log(f"  갱신 {row['date']}")
        else:
            # 새 행은 예보값이 있어야 한다 — 빈 껍데기 행을 만들지 않기 위해서다.
            if not any(row[f] for f in VALUE_FIELDS):
                log(f"  skip L{lineno}: pop·advice가 모두 빈 신규 행")
                continue
            index[key] = row
            rows.append(row)
            added += 1

    # 같은 날을 다시 밀어넣는 게 정상 사용이므로 "전부 이미 최신"은 성공이다.
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
    parts = [r["date"], r["pop"] or "강수확률 미확인", r["advice"] or "권고 미기입"]
    if r["tmin"] or r["tmax"]:
        parts.append(f"최저 {r['tmin'] or '?'} / 최고 {r['tmax'] or '?'}")
    if r["actual_rain"]:
        actual = f"실제 {r['actual_rain']}"
        if r["actual_mm"]:
            actual += f" {r['actual_mm']}"
        parts.append(actual)
    else:
        parts.append("실제 미기입")
    if r["note"]:
        parts.append(r["note"])
    return " | ".join(parts)


def tally(rows):
    """우산을 권한 날과 권하지 않은 날 각각에서 실제로 비가 왔는지 센다.

    강수확률이 미확인인 행과 실제 강수가 아직 안 채워진 행은 빼고 센다. 섞으면
    '0%라서 불필요'와 '몰라서 불필요'가 같은 칸에 들어가 적중률이 흐려진다.
    """
    advised = advised_rain = skipped = skipped_rain = 0
    no_pop = no_actual = 0
    for r in rows:
        if r["actual_rain"] not in ("Y", "N"):
            no_actual += 1
            continue
        if parse_pop(r["pop"]) is None:
            no_pop += 1
            continue
        rained = r["actual_rain"] == "Y"
        if r["advice"] in ("필수", "권장"):
            advised += 1
            advised_rain += rained
        else:
            skipped += 1
            skipped_rain += rained
    return (f"집계: 우산 권고(필수·권장) {advised}일 중 실제 강수 {advised_rain}일 · "
            f"우산 없음(선택·불필요) {skipped}일 중 실제 강수 {skipped_rain}일 "
            f"(제외: 강수확률 미확인 {no_pop}일 · 실제 미기입 {no_actual}일)")


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
        d = parse_date(r["date"])
        if d is None:
            continue
        if since and d < since:
            continue
        if until and d > until:
            continue
        hits.append((d, r))

    if not hits:
        log("조건에 맞는 기록 없음")
        return 1

    hits.sort(key=lambda x: x[0])
    for _, r in hits:
        print(fmt_row(r))
    # 검증이 이 아카이브의 존재 이유이므로 집계는 플래그 없이 항상 붙인다.
    print(tally([r for _, r in hits]))

    log(f"조회 완료: {len(hits)}건")
    return 0


def main():
    ap = argparse.ArgumentParser(description="날씨 예보·우산 권고 아카이브")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="stdin의 CSV 행을 upsert (헤더 없음)")
    p_rec.set_defaults(func=cmd_record)

    p_show = sub.add_parser("show", help="기록 조회 + 적중 집계")
    p_show.add_argument("--since", help="시작일 (YYYY-MM-DD)")
    p_show.add_argument("--until", help="종료일 (YYYY-MM-DD)")
    p_show.set_defaults(func=cmd_show)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
