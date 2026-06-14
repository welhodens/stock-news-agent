"""
╔══════════════════════════════════════════════════════════════════╗
║  ILTAKOOSTE — Joka arkipäivä klo 23:00 Suomen aikaa             ║
║  Päivän liikkujat · Sektorianalyysi · Uutiset · Huominen        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, requests
from datetime import datetime
import anthropic

STOCKS = [
    {"ticker": "APLD",  "name": "Applied Digital"},
    {"ticker": "TSLA",  "name": "Tesla"},
    {"ticker": "AMD",   "name": "AMD"},
    {"ticker": "ENVX",  "name": "Enovix"},
]

MACRO = [
    {"ticker": "^GSPC",    "name": "S&P 500"},
    {"ticker": "^IXIC",    "name": "NASDAQ"},
    {"ticker": "^DJI",     "name": "Dow Jones"},
    {"ticker": "^RUT",     "name": "Russell 2000"},
    {"ticker": "^VIX",     "name": "VIX"},
    {"ticker": "^TNX",     "name": "US 10v korko"},
    {"ticker": "DX-Y.NYB", "name": "DXY dollari"},
    {"ticker": "CL=F",     "name": "Öljy WTI"},
    {"ticker": "GC=F",     "name": "Kulta"},
    {"ticker": "BTC-USD",  "name": "Bitcoin"},
]

# S&P 500 sektorit
SECTORS = [
    {"ticker": "XLK",  "name": "Teknologia"},
    {"ticker": "XLF",  "name": "Rahoitus"},
    {"ticker": "XLE",  "name": "Energia"},
    {"ticker": "XLV",  "name": "Terveydenhuolto"},
    {"ticker": "XLI",  "name": "Teollisuus"},
    {"ticker": "XLC",  "name": "Viestintä"},
    {"ticker": "XLY",  "name": "Kuluttaja (harkinnanvarainen)"},
    {"ticker": "XLP",  "name": "Kuluttaja (välttämättömyys)"},
    {"ticker": "XLRE", "name": "Kiinteistöt"},
    {"ticker": "XLU",  "name": "Utilities"},
    {"ticker": "XLB",  "name": "Materiaalit"},
]

def fetch_quote(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, params={"interval": "1d", "range": "2d"},
                        headers=headers, timeout=15)
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        current = meta.get("regularMarketPrice", 0)
        prev    = meta.get("chartPreviousClose", current)
        change  = ((current - prev) / prev * 100) if prev else 0
        return {"price": current, "change": change}
    except:
        return {"price": 0, "change": 0}

def build_data_text():
    lines = ["=== PÄIVÄN DATA ==="]

    lines.append("\n-- Osakkeesi --")
    for s in STOCKS:
        q = fetch_quote(s["ticker"])
        arrow = "▲" if q["change"] >= 0 else "▼"
        lines.append(f"{s['ticker']}: ${q['price']:.2f} {arrow}{abs(q['change']):.1f}%")

    lines.append("\n-- Makroindikaattorit --")
    for m in MACRO:
        q = fetch_quote(m["ticker"])
        arrow = "▲" if q["change"] >= 0 else "▼"
        lines.append(f"{m['name']}: {q['price']:.2f} {arrow}{abs(q['change']):.1f}%")

    lines.append("\n-- Sektorit (S&P 500 ETF) --")
    for s in SECTORS:
        q = fetch_quote(s["ticker"])
        arrow = "▲" if q["change"] >= 0 else "▼"
        lines.append(f"{s['name']}: {arrow}{abs(q['change']):.1f}%")

    return "\n".join(lines)

def ai_evening_report(data_text):
    client = anthropic.Anthropic()
    today = datetime.utcnow().strftime("%d.%m.%Y")
    weekday = datetime.utcnow().strftime("%A")
    weekdays_fi = {
        "Monday": "Maanantai", "Tuesday": "Tiistai", "Wednesday": "Keskiviikko",
        "Thursday": "Torstai", "Friday": "Perjantai", "Saturday": "Lauantai", "Sunday": "Sunnuntai"
    }
    day_fi = weekdays_fi.get(weekday, weekday)

    prompt = f"""Olet kokenut markkinaanalyytikko. Tänään on {day_fi} {today}, Wall Street on juuri sulkeutunut.

Päivän data:
{data_text}

Käytä web-hakua selvittääksesi:
1. Mitkä olivat päivän tärkeimmät uutiset jotka liikuttivat markkinoita
2. Mitä APLD, TSLA, AMD tai ENVX:stä tuli tänään uutisia
3. Geopoliittiset uutiset jotka vaikuttivat markkinoihin
4. Mitä huomenna on odotettavissa

Kirjoita SUOMEKSI kattava iltakooste:

🌙 *ILTAKOOSTE — {day_fi} {today}*

━━━━━━━━━━━━━━━━━━━━━━

📊 *PÄIVÄN MARKKINAT*
[S&P500, NASDAQ, Dow — mitä tapahtui ja miksi]

📈 *OSAKKEESI TÄNÄÄN*
[APLD, TSLA, AMD, ENVX — hinnat, muutokset, uutiset]

🏭 *SEKTORIANALYYSI*
[Mitkä sektorit nousivat/laskivat eniten ja miksi]

🌍 *MAKRO & GEOPOLITIIKKA*
[VIX-taso, korot, dollari, öljy + tärkeimmät uutiset]

📰 *PÄIVÄN TÄRKEIMMÄT UUTISET*
[3-4 tärkeintä markkinauutista analyyseineen]

📅 *HUOMINEN KALENTERI*
[Talousluvut, Fed-puheet, yritysuutiset]

🎯 *YHTEENVETO*
[2-3 lausetta: päivän merkitys ja mitä odottaa huomenna]"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        return "".join(b.text for b in msg.content if hasattr(b, "text"))
    except Exception as e:
        return f"[Iltakooste epäonnistui: {e}]"

def send_telegram(message):
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print(message)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
        try:
            requests.post(url, data={
                "chat_id": chat_id, "text": chunk,
                "parse_mode": "Markdown", "disable_web_page_preview": True
            }, timeout=15)
        except Exception as e:
            print(f"Telegram virhe: {e}")

def main():
    print(f"[{datetime.utcnow().isoformat()}] Iltakooste käynnistyy...")
    data_text = build_data_text()
    print(data_text)
    print("\nLuodaan AI-analyysi...")
    report = ai_evening_report(data_text)
    send_telegram(report)
    print("✓ Iltakooste lähetetty!")

if __name__ == "__main__":
    main()
