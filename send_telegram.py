import os
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

text = (
    "📋 *Daily Briefing — 2026-06-22*\n\n"
    "☁️ *날씨 (서울)*\n"
    "• 최저 19°C / 최고 27°C\n"
    "• 미세먼지: 보통 (AQI ~89)\n"
    "• ☂️ 우산 지참 권고 (오후 소나기 대비, 장마철 진입)\n\n"
    "📅 *오늘 일정*\n"
    "• 11:00 문식보미프로님\n\n"
    "📊 *이번 주 경제지표*\n"
    "• 06/25(목) 22:30 🇺🇸 PCE(5월) 예상 YoY 4.1%\n"
    "• 06/25(목) 22:30 🇺🇸 Core PCE(5월) 예상 YoY 3.4%\n"
    "• 06/26(금) 🇺🇸 Micron 실적 발표 (이익 성장률 ~1,000%)\n\n"
    "🌐 *간밤 주요 뉴스*\n"
    "🇺🇸 미국\n"
    "• 연준, 금리 3.5~3.75% 동결 — 위원 9명 연내 인상 전망 (NYT)\n"
    "• 트럼프 행정부, Anthropic Fable 5 모델 강제 오프라인 (TechCrunch)\n"
    "• Apple iOS 27, Siri 외 실용 AI 기능 다수 탑재 예정 (TechCrunch)\n"
    "• SpaceX 역대 최대 규모 IPO 완료 (Yahoo Finance)\n\n"
    "🇪🇺 유럽\n"
    "• 미·이란 스위스 협상 — 트럼프, 헤즈볼라 억제 않으면 공격 경고 (BBC)\n"
    "• 영국 통계청, 핵심 고용 데이터 오류 인정 (FT)\n"
    "• AI 생성 인플루언서 소셜 마케팅 확산 (Guardian)\n"
    "• 독일 KNDS 탱크기업 지분 40% 인수 — IPO 준비 (Bloomberg)\n\n"
    "💹 *시장*\n"
    "• 유가 급락 — 미·이란 협상 진전으로 WTI $78.24 (Bloomberg)\n"
    "• 채권 트레이더, 목요일 PCE 주목 (Bloomberg)\n"
)

if not TOKEN or not CHAT_ID:
    print("텔레그램 발송 건너뜀: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 환경변수 미설정")
else:
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    )
    print(r.status_code, r.text)
