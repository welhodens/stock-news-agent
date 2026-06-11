"""
╔══════════════════════════════════════════════════════════════════╗
║  VIX-HÄLYTYS + SEC SISÄPIIRIOSTOT                               ║
║  VIX: hälyttää jos yli 25 tai nousee yli 20% päivässä           ║
║  SEC: seuraa Form 4 sisäpiiri-ilmoituksia APLD/TSLA/AMD/ENVX    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, json, requests
from datetime import datetime
from bs4 import BeautifulSoup
import anthropic

VIX_THRESHOLD      = 25.0   # Absoluuttinen taso
VIX_MOVE_THRESHOLD = 20.0   # Päivämuutos %

TICKERS = ["APLD", "TSLA", "AMD", "ENVX"]

STATE_FILE = "vix_sec_state.json"

# ═══════════════════════════════════════════════════════════════════
#  VIX-HÄLYTYS
# ═══════════════════════════════════════════════════════════════════

def fetch_vix():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, params={"interval": "1d", "range": "2d"},
                        headers=headers, timeout=15)
        meta    = r.json()["chart"]["result"][0]["meta"]
        current = meta.get("regularMarketPrice", 0)
        prev    = meta.get("chartPreviousClose", current)
        change  = ((current - prev) / prev * 100) if prev else 0
        return {"vix": current, "change": change, "prev": prev}
    except Exception as e:
        print(f"VIX haku epäonnistui: {e}")
        return None

def ai_vix_analysis(vix_data):
    client = anthropic.Anthropic()
    prompt = f"""VIX (pelkoindeksi) on nyt {vix_data['vix']:.1f} (muutos: {vix_data['change']:+.1f}% päivässä).

Käytä web-hakua selvittääksesi miksi VIX on noussut näin korkealle.
Kirjoita SUOMEKSI 3-4 lausetta: mitä VIX-taso tarkoittaa, mikä aiheutti nousun, 
mitä sijoittajan tulisi harkita."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        return "".join(b.text for b in msg.content if hasattr(b, "text"))
    except Exception as e:
        return f"[Analyysi epäonnistui: {e}]"

# ═══════════════════════════════════════════════════════════════════
#  SEC SISÄPIIRI-ILMOITUKSET (Form 4)
# ═══════════════════════════════════════════════════════════════════

def fetch_sec_form4(ticker):
    """Hakee tuoreimmat Form 4 -ilmoitukset SEC EDGAR:sta."""
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}&type=4&dateb=&owner=include&count=5&search_text="
    headers = {
        "User-Agent": "StockMonitor contact@example.com",
        "Accept": "text/html"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        filings = []
        table = soup.find("table", class_="tableFile2")
        if not table:
            return []
            
        for row in table.find_all("tr")[1:6]:
            cols = row.find_all("td")
            if len(cols) >= 4:
                filing_type = cols[0].get_text(strip=True)
                date        = cols[3].get_text(strip=True)
                link_tag    = cols[1].find("a")
                link        = "https://www.sec.gov" + link_tag["href"] if link_tag else ""
                
                if filing_type == "4":
                    filings.append({
                        "type": filing_type,
                        "date": date,
                        "url":  link,
                    })
        return filings
    except Exception as e:
        print(f"SEC haku epäonnistui ({ticker}): {e}")
        return []

def ai_sec_analysis(ticker, filings):
    client = anthropic.Anthropic()
    filings_text = "\n".join([f"- Form 4, päivätty {f['date']}: {f['url']}" for f in filings])
    
    prompt = f"""Seuraavat uudet sisäpiiri-ilmoitukset (Form 4) on jätetty SEC:lle yhtiölle {ticker}:

{filings_text}

Käytä web-hakua hakemaan lisätietoja näistä ilmoituksista.
Kirjoita SUOMEKSI lyhyt analyysi (2-3 lausetta): 
- Ostaako vai myyvätkö johtohenkilöt osakkeita?
- Mitä tämä yleensä signaloi?
- Mikä on merkitys sijoittajalle?"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        return "".join(b.text for b in msg.content if hasattr(b, "text"))
    except Exception as e:
        return f"[Analyysi epäonnistui: {e}]"

# ═══════════════════════════════════════════════════════════════════
#  TILA & TELEGRAM
# ═══════════════════════════════════════════════════════════════════

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return {"vix_alerted": False, "date": "", "seen_sec": {}}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2)

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

# ═══════════════════════════════════════════════════════════════════
#  PÄÄOHJELMA
# ═══════════════════════════════════════════════════════════════════

def main():
    print(f"[{datetime.utcnow().isoformat()}] VIX + SEC tarkistus...")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    state = load_state()

    if state.get("date") != today:
        state = {"vix_alerted": False, "date": today, "seen_sec": state.get("seen_sec", {})}

    # ── VIX-tarkistus ──────────────────────────────────────────────
    vix_data = fetch_vix()
    if vix_data:
        vix = vix_data["vix"]
        chg = vix_data["change"]
        print(f"  VIX: {vix:.1f} ({chg:+.1f}%)")

        should_alert = (
            (vix >= VIX_THRESHOLD and not state["vix_alerted"]) or
            (abs(chg) >= VIX_MOVE_THRESHOLD)
        )

        if should_alert:
            print(f"  🚨 VIX-HÄLYTYS!")
            analysis = ai_vix_analysis(vix_data)
            level = "🔴 KORKEA" if vix >= 30 else "🟡 KOHOLLA"
            msg = (
                f"⚠️ *VIX-HÄLYTYS* — Markkinapelko kasvaa\n"
                f"_{datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC_\n\n"
                f"*VIX: {vix:.1f}* {level} (muutos: {chg:+.1f}%)\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"*AI-analyysi:*\n{analysis}"
            )
            send_telegram(msg)
            state["vix_alerted"] = True

    # ── SEC Form 4 tarkistus ────────────────────────────────────────
    for ticker in TICKERS:
        print(f"  SEC {ticker}...")
        filings = fetch_sec_form4(ticker)
        
        seen = set(state["seen_sec"].get(ticker, []))
        new_filings = [f for f in filings if f["url"] not in seen]

        if new_filings:
            print(f"  🆕 {ticker}: {len(new_filings)} uutta SEC Form 4!")
            analysis = ai_sec_analysis(ticker, new_filings)

            msg = (
                f"📋 *SEC SISÄPIIRI-ILMOITUS — {ticker}*\n"
                f"_{datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC_\n\n"
                f"*{len(new_filings)} uutta Form 4 -ilmoitusta*\n\n"
            )
            for f in new_filings:
                msg += f"🔗 {f['url']}\n"
            msg += f"\n━━━━━━━━━━━━━━━━━━━━━━\n*AI-analyysi:*\n{analysis}"
            send_telegram(msg)

            state["seen_sec"][ticker] = list(seen | {f["url"] for f in new_filings})

    save_state(state)
    print("✓ VIX + SEC tarkistus valmis!")

if __name__ == "__main__":
    main()
