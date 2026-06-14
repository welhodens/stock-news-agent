"""
╔══════════════════════════════════════════════════════════════════╗
║  KURSSI-HÄLYTYS — Tarkistaa joka 15 min                         ║
║  Hälyttää jos APLD/TSLA/AMD/ENVX tai S&P500 liikkuu ±5%+        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, json, requests
from datetime import datetime
import anthropic

ALERT_THRESHOLD = 5.0  # prosenttia

WATCH_LIST = [
    {"ticker": "APLD",  "name": "Applied Digital",  "type": "stock"},
    {"ticker": "TSLA",  "name": "Tesla",             "type": "stock"},
    {"ticker": "AMD",   "name": "AMD",               "type": "stock"},
    {"ticker": "ENVX",  "name": "Enovix",            "type": "stock"},
    {"ticker": "^GSPC", "name": "S&P 500",           "type": "index"},
    {"ticker": "^IXIC", "name": "NASDAQ",            "type": "index"},
    {"ticker": "^DJI",  "name": "Dow Jones",         "type": "index"},
    {"ticker": "^VIX",  "name": "VIX",               "type": "index"},
]

STATE_FILE = "price_alert_state.json"

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
        return {"price": current, "change": change, "prev": prev}
    except:
        return None

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return {"alerted_today": {}}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2)

def ai_analyze_move(item, quote):
    client = anthropic.Anthropic()
    direction = "nousi" if quote["change"] > 0 else "laski"
    prompt = f"""{item['name']} ({item['ticker']}) {direction} {abs(quote['change']):.1f}% tänään.
Hinta: ${quote['price']:.2f} (eilen: ${quote['prev']:.2f})

Käytä web-hakua selvittääksesi miksi tämä liike tapahtui.
Kirjoita SUOMEKSI 2-3 lausetta: mikä aiheutti liikkeen ja mitä se tarkoittaa sijoittajalle."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        return "".join(b.text for b in msg.content if hasattr(b, "text"))
    except Exception as e:
        return f"[Analyysi epäonnistui: {e}]"

def send_telegram(message):
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print(message)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": chat_id, "text": message,
            "parse_mode": "Markdown", "disable_web_page_preview": True
        }, timeout=15)
    except Exception as e:
        print(f"Telegram virhe: {e}")

def main():
    print(f"[{datetime.utcnow().isoformat()}] Kurssi-hälytys tarkistaa...")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    state = load_state()

    # Nollaa päivittäinen hälytystila uuden päivän alkaessa
    if state.get("date") != today:
        state = {"date": today, "alerted_today": {}}

    for item in WATCH_LIST:
        quote = fetch_quote(item["ticker"])
        if not quote:
            continue

        change = quote["change"]
        already_alerted = state["alerted_today"].get(item["ticker"], 0)

        # Hälytä jos liike ylittää raja-arvon eikä ole jo hälyttänyt
        if abs(change) >= ALERT_THRESHOLD and abs(change) > abs(already_alerted):
            print(f"  🚨 {item['ticker']}: {change:+.1f}% — hälytys!")

            direction_emoji = "📈" if change > 0 else "📉"
            direction_text  = "NOUSI" if change > 0 else "LASKI"

            analysis = ai_analyze_move(item, quote)

            msg = (
                f"{direction_emoji} *KURSSI-HÄLYTYS — {item['name']} ({item['ticker']})*\n"
                f"_{datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC_\n\n"
                f"*{direction_text} {abs(change):.1f}%* päivässä\n"
                f"Hinta: ${quote['price']:.2f} (eilen: ${quote['prev']:.2f})\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"*AI-analyysi:*\n{analysis}"
            )
            send_telegram(msg)
            state["alerted_today"][item["ticker"]] = change
        else:
            print(f"  {item['ticker']}: {change:+.1f}% — ei hälytystä")

    save_state(state)
    print("✓ Tarkistus valmis!")

if __name__ == "__main__":
    main()
