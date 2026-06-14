"""
╔══════════════════════════════════════════════════════════════════╗
║  GEOPOLIITTINEN UUTISHÄLYTYS                                     ║
║  Seuraa isoja kriisejä jotka vaikuttavat markkinoihin            ║
║  Tarkistaa joka 15 min — hälyttää vain isoista tapahtumista      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, json, requests, hashlib
from datetime import datetime
import anthropic

STATE_FILE = "geopolitical_state.json"

# RSS-syötteet geopoliittisille uutisille
NEWS_FEEDS = [
    {
        "name": "Reuters World",
        "url":  "https://feeds.reuters.com/reuters/worldNews",
    },
    {
        "name": "BBC World",
        "url":  "https://feeds.bbci.co.uk/news/world/rss.xml",
    },
    {
        "name": "Bloomberg Markets",
        "url":  "https://feeds.bloomberg.com/markets/news.rss",
    },
]

# Avainsanat jotka laukaisevat tarkemman AI-arvion
TRIGGER_KEYWORDS = [
    # Sota ja konfliktit
    "war", "conflict", "attack", "missile", "strike", "invasion",
    "troops", "military", "nuclear", "nato", "ceasefire",
    # Pakotteet ja kauppa
    "sanction", "tariff", "trade war", "embargo", "ban", "restriction",
    "export control", "chip ban",
    # Energia ja resurssit
    "oil", "gas", "opec", "pipeline", "energy crisis", "shortage",
    # Talouskriisit
    "crisis", "recession", "default", "crash", "collapse", "panic",
    "bank run", "contagion", "systemic",
    # Geopoliittiset alueet
    "china", "russia", "iran", "north korea", "taiwan", "ukraine",
    "middle east", "israel", "saudi",
    # Keskuspankit ja politiikka
    "fed", "federal reserve", "powell", "rate hike", "rate cut",
    "ecb", "inflation", "stagflation",
]

def fetch_rss_headlines(feed):
    """Hakee RSS-syötteen otsikot."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(feed["url"], headers=headers, timeout=15)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "xml")
        items = []
        for item in soup.find_all("item")[:20]:
            title = item.find("title")
            link  = item.find("link")
            desc  = item.find("description")
            if title:
                items.append({
                    "title": title.get_text(strip=True),
                    "url":   link.get_text(strip=True) if link else "",
                    "desc":  desc.get_text(strip=True)[:200] if desc else "",
                    "source": feed["name"],
                })
        return items
    except Exception as e:
        print(f"  RSS haku epäonnistui ({feed['name']}): {e}")
        return []

def has_trigger_keyword(text):
    """Tarkistaa löytyykö tekstistä laukaisevat avainsanat."""
    text_low = text.lower()
    found = [kw for kw in TRIGGER_KEYWORDS if kw in text_low]
    return found

def ai_evaluate_significance(headlines):
    """Claude arvioi onko uutinen tarpeeksi merkittävä lähettääkseen hälytyksen."""
    client = anthropic.Anthropic()

    headlines_text = "\n".join([
        f"- [{h['source']}] {h['title']}\n  {h['desc']}"
        for h in headlines[:15]
    ])

    prompt = f"""Olet geopoliittinen riskianalyytikko. Analysoi seuraavat uutisotsikot sijoittajan näkökulmasta.

Uutiset:
{headlines_text}

Tehtäväsi:
1. Arvioi onko joukossa MERKITTÄVIÄ tapahtumia jotka voivat liikuttaa markkinoita yli 1%
2. Jos löydät merkittävän tapahtuman, kirjoita lyhyt hälytys

Vastaa JSON-muodossa:
{{
  "alert_needed": true/false,
  "severity": "HIGH/MEDIUM/LOW",
  "headline": "Lyhyt otsikko suomeksi",
  "analysis": "2-3 lausetta suomeksi: mitä tapahtui ja miten vaikuttaa markkinoihin",
  "affected_assets": ["lista vaikutetuista omaisuusluokista tai osakkeista"]
}}

Lähetä hälytys VAIN jos tapahtuma on oikeasti merkittävä — älä hälytä rutiiniuutisista."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text
        # Puhdista JSON
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"  AI-arvio epäonnistui: {e}")
    return {"alert_needed": False}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return {"seen_hashes": [], "last_alert": ""}

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

def main():
    print(f"[{datetime.utcnow().isoformat()}] Geopoliittinen seuranta...")
    state = load_state()
    seen  = set(state.get("seen_hashes", []))

    # Kerää kaikki otsikot kaikista syötteistä
    all_headlines = []
    for feed in NEWS_FEEDS:
        headlines = fetch_rss_headlines(feed)
        all_headlines.extend(headlines)
        print(f"  {feed['name']}: {len(headlines)} otsikkoa")

    # Suodata uudet otsikot joissa on avainsanoja
    triggered = []
    for h in all_headlines:
        h_hash = hashlib.md5(h["title"].encode()).hexdigest()
        if h_hash in seen:
            continue
        keywords = has_trigger_keyword(h["title"] + " " + h["desc"])
        if keywords:
            triggered.append(h)
            seen.add(h_hash)

    print(f"  Uusia laukaisevia otsikoita: {len(triggered)}")

    if triggered:
        print("  → Lähetetään AI-arviolle...")
        result = ai_evaluate_significance(triggered)

        if result.get("alert_needed"):
            severity = result.get("severity", "MEDIUM")
            emoji = "🔴" if severity == "HIGH" else "🟡"

            affected = ", ".join(result.get("affected_assets", []))
            msg = (
                f"{emoji} *GEOPOLIITTINEN HÄLYTYS*\n"
                f"_{datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC_\n\n"
                f"*{result.get('headline', '')}*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{result.get('analysis', '')}\n\n"
                f"📊 *Vaikuttaa:* {affected}"
            )
            send_telegram(msg)
            print(f"  🚨 Hälytys lähetetty! ({severity})")
        else:
            print("  Ei merkittäviä tapahtumia.")
    else:
        print("  Ei uusia laukaisevia otsikoita.")

    # Pidä maksimissaan 500 hashia muistissa
    state["seen_hashes"] = list(seen)[-500:]
    save_state(state)
    print("✓ Geopoliittinen seuranta valmis!")

if __name__ == "__main__":
    main()
