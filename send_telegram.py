#!/usr/bin/env python3
"""텔레그램 요약 발송 (briefing-prompt.md Section 6이 stdin으로 호출).

견고화: 길이 캡(4096) · timeout · 네트워크 재시도 · Markdown 실패 시 plain 폴백.
TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 미설정 시 발송만 건너뛴다(브리핑 영향 없음).
"""
import os
import sys
import time
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
API = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
MAX_LEN = 4096
TIMEOUT = 15


def send(text, parse_mode):
    payload = {"chat_id": CHAT_ID, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return requests.post(API, json=payload, timeout=TIMEOUT)


def main():
    text = sys.stdin.read().strip()

    if not TOKEN or not CHAT_ID:
        print("텔레그램 발송 건너뜀: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 환경변수 미설정")
        return

    # Telegram 한계(4096) 안전망. 프롬프트의 4000자 트림이 1차 제어.
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 10].rstrip() + "\n…(이하 생략)"

    # 네트워크 오류 재시도(지수 백오프 2s·4s).
    for attempt in range(3):
        try:
            r = send(text, "Markdown")
            # Markdown 파싱 실패(400) → plain text로 1회 폴백(항상 파싱됨).
            if r.status_code == 400 and "parse" in r.text.lower():
                r = send(text, None)
            print(r.status_code, r.text)
            return
        except requests.RequestException as e:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
            else:
                print(f"텔레그램 발송 실패(네트워크): {e}")


if __name__ == "__main__":
    main()
