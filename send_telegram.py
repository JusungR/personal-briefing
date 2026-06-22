import os
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

text = (
    "📋 *Daily Briefing — 2026-06-23*\n\n"
    "☁️ *날씨 (서울)*\n"
    "• 최저 약 19°C / 최고 약 24°C, 부분적 비 가능성\n"
    "• 미세먼지: 보통 (강수 영향)\n"
    "• 우산 지참 권장\n\n"
    "📅 *오늘 일정*\n"
    "• 오늘 등록된 일정 없음\n\n"
    "📊 *이번 주 경제지표*\n"
    "• 06/25(목) 21:30 🇺🇸 PCE 물가지수 (5월) — 연준 선호 인플레이션 지표\n"
    "• 06/25(목) 21:30 🇺🇸 Core PCE 물가지수 (5월)\n\n"
    "🌐 *간밤 주요 뉴스*\n"
    "🇺🇸 미국\n"
    "• Alphabet AI 인재(Shazeer→OpenAI, Jumper→Anthropic) 연속 이탈, 주가 6.5% 폭락 (Bloomberg)\n"
    "• SpaceX, Reflection AI와 63억 달러 컴퓨팅 계약 — Colossus 2 데이터센터 (CNBC)\n"
    "• 앨런 그린스펀 전 연준 의장 별세, 향년 100세 (CNBC)\n"
    "• SpaceX 주가 IPO 후 3거래일 24% 급락, 200억 달러 채권 발행 동시 진행 (Bloomberg)\n"
    "• 미국 2년물 국채금리 2025년 2월 이후 최고치, BofA·도이치뱅크 9월 금리인상 전망 (CNBC)\n\n"
    "🇪🇺 유럽\n"
    "• ECB 라가르드, 유로존 2차 인플레이션 파급 우려 낮다고 언급 (Reuters)\n"
    "• 캐나다 5월 CPI 3.2% — 29개월래 최고치 (Reuters)\n"
    "• 영국 스타머 총리 집권 1주년 경제 성과 분석 (Guardian)\n"
)

if not TOKEN or not CHAT_ID:
    print("텔레그램 발송 건너뜀: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 환경변수 미설정")
else:
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    )
    print(r.status_code, r.text)
