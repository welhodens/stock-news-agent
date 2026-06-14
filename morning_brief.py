"""
╔══════════════════════════════════════════════════════════════════╗
║  AAMUBRIEF — Joka arkipäivä klo 08:00 Suomen aikaa              ║
║  Futures · Makro · Päivän kalenteri · AI-näkymä                 ║
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
    {"ticker": "^VIX",     "name": "VIX"},
    {"ticker": "^TNX",     "name": "US 10v korko"},
    {"ticker": "DX-Y.NYB", "name": "DXY dollari"},
    {"ticker": "CL=F",     "name": "Öljy WTI"},
    {"ticker": "GC=F",     "name": "Kulta"},
    {"ticker": "ES=F",     "name": "S&P 500 Futures"},
    {"ticker": "NQ=F",     "name": "NASDAQ Futures"},
]

def fetch_quote(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, params={"interval": "1d", "range": "2d"},
                        headers=headers, timeout=15)
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        current   = meta.get("regularMarketPrice", 0)
        prev      = meta.get("chartPreviousClose", current)
        change    = ((current - prev) / prev * 100) if prev else 0
        return {"price": current, "change": change}
    except:
        return {"price": 0, "change": 0}

def build_data_text():
    lines = ["=== AAMUDATA ==="]
    
    lines.append("\n-- Osakkeesi --")
    for s in STOCKS:
        q = fetch_quote(s["ticker"])
        arrow = "▲" if q["change"] >= 0 else "▼"
        lines.append(f"{s['ticker']}: ${q['price']:.2f} {arrow}{abs(q['change']):.1f}%")
    
    lines.append("\n-- Makro & Futures --")
    for m in MACRO:
        q = fetch_quote(m["ticker"])
        arrow = "▲" if q["change"] >= 0 else "▼"
        lines.append(f"{m['name']}: {q['price']:.2f} {arrow}{abs(q['change']):.1f}%")
    
    return "\n".join(lines)

def ai_morning_brief(data_text):
    client = anthropic.Anthropic()
    today = datetime.utcnow().strftime("%d.%m.%Y")
    weekday = datetime.utcnow().strftime("%A")
    
    weekdays_fi = {
        "Monday": "Maanantai", "Tuesday": "Tiistai", "Wednesday": "Keskiviikko",
        "Thursday": "Torstai", "Friday": "Perjantai", "Saturday": "Lauantai", "Sunday": "Sunnuntai"
    }
    day_fi = weekdays_fi.get(weekday, weekday)

    prompt = f"""Olet sijoittajan aamuassistentti. Tänään on {day_fi} {today}.

Tässä on aamudata markkinoilta:
{data_text}

Käytä web-hakua selvittääksesi:
1. Mitä tapahtui Aasian ja Euroopan markkinoilla yön aikana
2. Mitkä ovat tärkeimmät talousuutiset tänä aamuna
3. Mitä tänään on odotettavissa (talousluvut, Fed-puheet, yritysuutiset)
4. Onko APLD, TSLA, AMD tai ENVX:stä tullut yön aikana uutisia

Kirjoita SUOMEKSI tiivis aamubrief Telegram-muodossa:

🌅 *AAMUBRIEF — {day_fi} {today}*

━━━━━━━━━━━━━━━━━━━━━━

📊 *MARKKINATILANNE AAMULLA*
[Futures ja yön liikkeet lyhyesti]

🔢 *OSAKKEESI*
[APLD, TSLA, AMD, ENVX hinnat ja muutos]

🌍 *MAKRO*
[VIX, korot, dollari, öljy — lyhyt tulkinta]

📰 *TÄRKEIMMÄT UUTISET AAMULLA*
[2-3 tärkeintä uutista]

📅 *TÄNÄÄN TAPAHTUU*
[Talousluvut, puheet, muut tärkeät tapahtumat]

🎯 *PÄIVÄN NÄKYMÄ*
[1-2 lausetta: mitä tänään kannattaa seurata]

Pidä tiiviinä — max 30 sekuntia lukea."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        return "".join(b.text for b in msg.content if hasattr(b, "text"))
    except Exception as e:
        return f"[Aamubrief epäonnistui: {e}]"

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
    print(f"[{datetime.utcnow().isoformat()}] Aamubrief käynnistyy...")
    data_text = build_data_text()
    print(data_text)
    print("\nLuodaan AI-analyysi...")
    brief = ai_morning_brief(data_text)
    send_telegram(brief)
    print("✓ Aamubrief lähetetty!")

if __name__ == "__main__":
    main()
