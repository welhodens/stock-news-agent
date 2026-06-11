"""
╔══════════════════════════════════════════════════════════════════╗
║  VIIKKOKOOSTE — Perjantai 23:30 Suomen aikaa                    ║
║  Osakkeet · Makro · Indikaattorit · Tulevat tapahtumat          ║
╚══════════════════════════════════════════════════════════════════╝

ASENNUS:
  pip install requests anthropic

YMPÄRISTÖMUUTTUJAT (GitHub Secrets):
  ANTHROPIC_API_KEY
  TELEGRAM_TOKEN
  TELEGRAM_CHAT_ID
"""

import os, requests
from datetime import datetime
import anthropic

# ═══════════════════════════════════════════════════════════════════
#  SEURATTAVAT OSAKKEET
# ═══════════════════════════════════════════════════════════════════

STOCKS = [
    {"ticker": "APLD",  "name": "Applied Digital",  "desc": "AI/HPC datakeskukset"},
    {"ticker": "TSLA",  "name": "Tesla",             "desc": "Sähköautot, energia, robotit"},
    {"ticker": "AMD",   "name": "AMD",               "desc": "CPU/GPU, AI-kiihdyttimet"},
    {"ticker": "ENVX",  "name": "Enovix",            "desc": "Piianoodi-akkuteknologia"},
]

# Indeksit ja makroindikaattorit
INDICES = [
    {"ticker": "^GSPC",  "name": "S&P 500"},
    {"ticker": "^IXIC",  "name": "NASDAQ"},
    {"ticker": "^VIX",   "name": "VIX (pelkoindeksi)"},
    {"ticker": "^TNX",   "name": "US 10v korko"},
    {"ticker": "DX-Y.NYB", "name": "DXY (dollari)"},
    {"ticker": "CL=F",   "name": "Öljy WTI"},
    {"ticker": "GC=F",   "name": "Kulta"},
]

# ═══════════════════════════════════════════════════════════════════
#  KURSSITIEDOT — Yahoo Finance (ilmainen, ei API-avainta)
# ═══════════════════════════════════════════════════════════════════

def fetch_quote(ticker):
    """Hakee osakkeen/indeksin kurssitiedot Yahoo Financesta."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "interval": "1d",
        "range": "5d",
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        
        current = meta.get("regularMarketPrice", 0)
        prev_close = meta.get("chartPreviousClose", current)
        week_change = ((current - prev_close) / prev_close * 100) if prev_close else 0
        
        return {
            "ticker":      ticker,
            "price":       current,
            "week_change": week_change,
            "currency":    meta.get("currency", "USD"),
        }
    except Exception as e:
        return {"ticker": ticker, "price": 0, "week_change": 0, "error": str(e)}


def fetch_all_quotes():
    """Hakee kaikki kurssit."""
    results = {}
    all_tickers = [s["ticker"] for s in STOCKS] + [i["ticker"] for i in INDICES]
    for ticker in all_tickers:
        results[ticker] = fetch_quote(ticker)
    return results


# ═══════════════════════════════════════════════════════════════════
#  AI-ANALYYSI — Claude hakee webistä uutiset ja koostaa raportin
# ═══════════════════════════════════════════════════════════════════

def build_quotes_summary(quotes):
    """Muotoilee kurssitiedot tekstiksi AI:lle."""
    lines = []
    
    lines.append("=== OSAKEKURSSIT VIIKOLLA ===")
    for s in STOCKS:
        q = quotes.get(s["ticker"], {})
        price = q.get("price", 0)
        chg   = q.get("week_change", 0)
        arrow = "▲" if chg >= 0 else "▼"
        lines.append(f"{s['ticker']} ({s['name']}): ${price:.2f} {arrow}{abs(chg):.1f}%")
    
    lines.append("\n=== MAKROINDIKAATTORIT ===")
    for idx in INDICES:
        q = quotes.get(idx["ticker"], {})
        price = q.get("price", 0)
        chg   = q.get("week_change", 0)
        arrow = "▲" if chg >= 0 else "▼"
        lines.append(f"{idx['name']}: {price:.2f} {arrow}{abs(chg):.1f}%")
    
    return "\n".join(lines)


def ai_weekly_report(quotes_text):
    """Claude hakee uutiset webistä ja kirjoittaa viikkokooste."""
    client = anthropic.Anthropic()
    
    today = datetime.utcnow().strftime("%d.%m.%Y")
    
    prompt = f"""Olet kokenut makrotalousanalyytikko ja sijoitusstrategi. Tänään on perjantai {today}.

Tässä on viikon kurssitiedot:
{quotes_text}

Tehtäväsi on kirjoittaa kattava VIIKKOKOOSTE sijoittajalle. Käytä web-hakutyökalua hakemaan tuoreimmat tiedot seuraaviin osioihin:

1. Hae viikon tärkeimmät makrotalousuutiset (Fed, EKP, geopolitiikka, talousindikaattorit)
2. Hae uutiset seurattavista yhtiöistä: APLD, TSLA, AMD, ENVX
3. Hae ensi viikon tärkeät tapahtumat: Fed-puheet, FOMC, keskuspankkikokoukset, CPI/NFP/GDP-julkaisut

Kirjoita raportti SUOMEKSI seuraavassa rakenteessa:

📊 *VIIKKOKOOSTE — {today}*
_Markkinakatsaus perjantai-ilta_

━━━━━━━━━━━━━━━━━━━━━━

📈 *OSAKKEESI VIIKOLLA*
[kurssit ja lyhyt kommentti jokaisesta]

━━━━━━━━━━━━━━━━━━━━━━

🌍 *MAKROINDIKAATTORIT*
[VIX-analyysi, korot, dollari, öljy — mitä nämä kertovat markkinatunnelmasta]

━━━━━━━━━━━━━━━━━━━━━━

📰 *VIIKON TÄRKEIMMÄT UUTISET*
[3-5 tärkeintä makrouutista lyhyine analyyseineen]

━━━━━━━━━━━━━━━━━━━━━━

🏦 *ENSI VIIKON KALENTERI*
[Fed-puheet, keskuspankkikokoukset, talousluvut päivämäärineen]

━━━━━━━━━━━━━━━━━━━━━━

🎯 *CLAUDEN NÄKYMÄ ENSI VIIKOLLE*
[Lyhyt yhteenveto: mitkä riskit ja mahdollisuudet, mihin kannattaa kiinnittää huomiota]

Pidä raportti tiiviinä mutta informatiivisena. Käytä Telegram Markdown-muotoilua (*lihavointi*, _kursiivi_)."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search"
            }],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Kerää kaikki tekstiosat vastauksesta
        full_response = ""
        for block in msg.content:
            if block.type == "text":
                full_response += block.text
        
        return full_response if full_response else "[Raportin luonti epäonnistui]"
        
    except Exception as e:
        return f"[AI-analyysi epäonnistui: {e}]"


# ═══════════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════════

def send_telegram(message):
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("\n" + "═"*60)
        print(message)
        print("═"*60)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Jaa pitkä viesti osiin (Telegram max 4096 merkkiä)
    for i in range(0, len(message), 4000):
        chunk = message[i:i+4000]
        try:
            requests.post(url, data={
                "chat_id":    chat_id,
                "text":       chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }, timeout=15).raise_for_status()
        except Exception as e:
            print(f"[VIRHE] Telegram: {e}")


# ═══════════════════════════════════════════════════════════════════
#  PÄÄOHJELMA
# ═══════════════════════════════════════════════════════════════════

def main():
    print(f"[{datetime.utcnow().isoformat()}] Viikkokooste käynnistyy...")

    # 1. Hae kurssitiedot
    print("  → Haetaan kurssitiedot Yahoo Financesta...")
    quotes = fetch_all_quotes()
    quotes_text = build_quotes_summary(quotes)
    print(quotes_text)

    # 2. AI kirjoittaa raportin ja hakee uutiset webistä
    print("\n  → Claude kirjoittaa viikkokooste + hakee uutiset...")
    report = ai_weekly_report(quotes_text)

    # 3. Lähetä Telegramiin
    print("  → Lähetetään Telegramiin...")
    send_telegram(report)

    print("  ✓ Viikkokooste lähetetty!")


if __name__ == "__main__":
    main()
