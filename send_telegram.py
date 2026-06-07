import os
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

text = (
    "📋 *Daily Briefing — 2026-06-08*\n\n"
    "☁️ *날씨 (서울)*\n"
    "• 최저 14°C / 최고 27°C, 흐림\n"
    "• 미세먼지: 양호\n"
    "• 가벼운 겉옷 챙기기, 우산 불필요\n\n"
    "📅 *오늘 일정*\n"
    "• 09:30 알클립스작업\n"
    "• 11:00 관수프로님\n\n"
    "📊 *이번 주 경제지표*\n"
    "• 06/10(화) 21:30 🇺🇸 CPI(5월) 예상 ~6.0%\n"
    "• 06/11(수) 21:30 🇺🇸 PPI(5월)\n"
    "• 06/16~17(화수) 🇺🇸 FOMC 금리 결정\n\n"
    "🌐 *간밤 주요 뉴스*\n"
    "🇺🇸 미국\n"
    "• 나스닥 사상 최대 포인트 낙폭(-1,121p), S&P500 1.8조달러 증발 (MarketWatch)\n"
    "• 채권시장 CPI 급등 베팅, 연준 금리 인상 압박 고조 (Bloomberg)\n"
    "• 트럼프, 연준 워시에 금리 인하 압박 — FOMC는 인상 배제 안 해 (FT)\n"
    "• 비트코인 2024년 이후 최저, HYPE ETF 부상 (CNBC)\n"
    "• 엔비디아·SK하이닉스 협력 발표, 황 CEO '메모리 부족 수년 지속' (Reuters)\n\n"
    "🇪🇺/🌍 유럽·지정학\n"
    "• 이란, 이스라엘에 탄도미사일 10여 발 — 4월 휴전 이후 첫 공격, 전부 요격 (NPR)\n"
    "• 젤렌스키, 런던서 스타머·마크롱·메르츠와 회담 (Reuters)\n"
    "• 러시아 드론, 체르노빌 인근 핵연료 저장시설 타격 (Reuters)\n"
    "• 스위스 기업들, 관세 합의 후 미국에 270억 달러 투자 발표 (Reuters)\n"
)

if not TOKEN or not CHAT_ID:
    print("텔레그램 발송 건너뜀: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 환경변수 미설정")
else:
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    )
    print(r.status_code, r.text)
