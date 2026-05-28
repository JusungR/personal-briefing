#!/usr/bin/env python3
"""Daily briefing generator — runs via GitHub Actions, sends email."""

import json
import os
import smtplib
import datetime
import zoneinfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
import markdown
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from tavily import TavilyClient

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
KST = zoneinfo.ZoneInfo("Asia/Seoul")


def get_kst_today() -> datetime.date:
    return datetime.datetime.now(KST).date()


def get_calendar_service():
    token_data = json.loads(os.environ["GOOGLE_TOKEN_JSON"])
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data["refresh_token"],
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data.get("scopes", SCOPES),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("calendar", "v3", credentials=creds)


def list_calendar_events(date_str: str) -> list[dict]:
    service = get_calendar_service()
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=f"{date_str}T00:00:00+09:00",
            timeMax=f"{date_str}T23:59:59+09:00",
            singleEvents=True,
            orderBy="startTime",
            timeZone="Asia/Seoul",
        )
        .execute()
    )
    events = []
    for item in result.get("items", []):
        s = item.get("start", {})
        e = item.get("end", {})
        events.append(
            {
                "summary": item.get("summary", "(제목 없음)"),
                "start": s.get("dateTime", s.get("date", "")),
                "end": e.get("dateTime", e.get("date", "")),
                "location": item.get("location", ""),
                "all_day": "date" in s and "dateTime" not in s,
            }
        )
    return events


def web_search(query: str) -> str:
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    results = client.search(query=query, max_results=5, search_depth="advanced").get(
        "results", []
    )
    parts = [
        f"제목: {r.get('title', '')}\n내용: {r.get('content', '')}\n출처: {r.get('url', '')}"
        for r in results
    ]
    return "\n\n---\n\n".join(parts)


TOOLS = [
    {
        "name": "web_search",
        "description": "웹에서 최신 정보를 검색합니다.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "검색 쿼리"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_calendar_events",
        "description": "Google Calendar에서 특정 날짜의 이벤트를 가져옵니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "날짜 (YYYY-MM-DD, KST 기준)"}
            },
            "required": ["date"],
        },
    },
]


def run_briefing(today_str: str) -> str:
    briefing_prompt = Path("briefing-prompt.md").read_text(encoding="utf-8")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system = (
        f"당신은 개인 일정 비서입니다. 오늘 날짜는 KST 기준 {today_str}입니다.\n\n"
        f"{briefing_prompt}\n\n"
        "위 지침에 따라 오늘의 일일 브리핑을 한국어로 작성하세요. "
        "도구를 적극 활용해 최신 정보를 수집하세요."
    )
    messages = [{"role": "user", "content": f"{today_str} 일일 브리핑을 작성해주세요."}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return "\n".join(b.text for b in response.content if hasattr(b, "text"))

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "web_search":
                content = web_search(block.input["query"])
            elif block.name == "get_calendar_events":
                events = list_calendar_events(block.input["date"])
                content = json.dumps(events, ensure_ascii=False, indent=2)
            else:
                content = "알 수 없는 도구"
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": content}
            )
        messages.append({"role": "user", "content": tool_results})


def send_email(subject: str, body_md: str, recipient: str):
    sender = os.environ["GMAIL_FROM"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    body_html = markdown.markdown(body_md, extensions=["tables", "nl2br"])
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 680px;
         margin: 40px auto; padding: 0 24px; color: #222; line-height: 1.7; }}
  h2 {{ border-bottom: 2px solid #eee; padding-bottom: 8px; margin-top: 32px; }}
  h3 {{ color: #444; margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 14px; text-align: left; }}
  th {{ background: #f7f7f7; }}
  blockquote {{ border-left: 4px solid #ddd; margin: 0; padding: 8px 16px; color: #555; background: #fafafa; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 28px 0; }}
  strong {{ color: #111; }}
</style>
</head><body>
{body_html}
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(body_md, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())


def main():
    today = get_kst_today()
    today_str = today.strftime("%Y-%m-%d")
    display = today.strftime("%Y년 %m월 %d일")

    print(f"브리핑 생성 시작: {display} (KST)")
    briefing = run_briefing(today_str)
    print("브리핑 생성 완료")

    recipient = os.environ.get("RECIPIENT_EMAIL", os.environ["GMAIL_FROM"])
    send_email(f"📋 일일 브리핑 — {display}", briefing, recipient)
    print(f"이메일 전송 완료 → {recipient}")


if __name__ == "__main__":
    main()
