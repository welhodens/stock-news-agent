"""
╔══════════════════════════════════════════════════════════════════╗
║  OSAKE-UUTISAGENTTI — APLD · TSLA · AMD · ENVX                  ║
║  Seuraa kaikkien neljän yhtiön IR-sivuja joka 15 minuutti        ║
║  Lähettää AI-analyysin Telegramiin kun uusi tiedote ilmestyy     ║
╚══════════════════════════════════════════════════════════════════╝

ASENNUS:
  pip install requests beautifulsoup4 anthropic

YMPÄRISTÖMUUTTUJAT (GitHub Secrets):
  ANTHROPIC_API_KEY
  TELEGRAM_TOKEN
  TELEGRAM_CHAT_ID
"""

import os, json, hashlib, requests
from datetime import datetime
from bs4 import BeautifulSoup
import anthropic

# ═══════════════════════════════════════════════════════════════════
#  YHTIÖT — lisää tai poista tähän listaan
# ═══════════════════════════════════════════════════════════════════

COMPANIES = [
    {
        "name":   "Applied Digital",
        "ticker": "APLD",
        "url":    "https://ir.applieddigital.com/news-events/press-releases",
        "method": "scrape",          # suora HTML-haku
        "selector": "h2",            # otsikot h2-tageissa
        "link_filter": "press-releases/detail",
        "base_url": "https://ir.applieddigital.com",
        "description": "AI/HPC datakeskusyhtiö, rakentaa hyperscaler-kampuksia",
    },
    {
        "name":   "Tesla",
        "ticker": "TSLA",
        "url":    "https://ir.tesla.com/press-releases",
        "method": "scrape",
        "selector": "h2",
        "link_filter": "press-release",
        "base_url": "https://ir.tesla.com",
        "description": "Sähköautot, energia, Robotaxi, Optimus-robotti, FSD",
    },
    {
        "name":   "AMD",
        "ticker": "AMD",
        "url":    "https://ir.amd.com/news-events/press-releases",
        "method": "scrape",
        "selector": "h2",
        "link_filter": "press-releases/detail",
        "base_url": "https://ir.amd.com",
        "description": "CPU/GPU-valmistaja, AI-kiihdyttimet (MI-sarja), kilpailee Nvidian kanssa",
    },
    {
        "name":   "Enovix",
        "ticker": "ENVX",
        # Enovix estää suoran haun — käytetään GlobeNewswire RSS-syötettä
        "url":    "https://www.globenewswire.com/RssFeed/company/enovix",
        "method": "rss",
        "base_url": "https://ir.enovix.com",
        "description": "Piianoodi-akkuteknologia, älypuhelimet ja wearables",
    },
]

STATE_FILE = "news_agent_state.json"

# ═══════════════════════════════════════════════════════════════════
#  PRIORITEETTIAVAINSANAT (kaikille yhtiöille yhteiset)
# ═══════════════════════════════════════════════════════════════════

PRIORITY_KEYWORDS = [
    # Tulokset
    "earnings", "financial results", "quarterly", "revenue", "guidance",
    "profit", "loss", "EPS", "outlook", "forecast",
    # Isot tapahtumat
    "acquisition", "merger", "partnership", "agreement", "contract",
    "billion", "million", "investment", "financing", "offering",
    "CEO", "CFO", "executive", "board", "leadership",
    # Kriittiset
    "recall", "investigation", "SEC", "lawsuit", "bankruptcy",
    "layoff", "restructuring", "restatement", "warning",
    # Yhtiökohtaiset
    "hyperscaler", "gigawatt", "GW", "campus",          # APLD
    "cybertruck", "FSD", "robotaxi", "optimus", "energy",  # TSLA
    "EPYC", "Instinct", "Ryzen", "MI300", "MI400",      # AMD
    "silicon anode", "battery", "smartphone", "ENVX",   # ENVX
]

# ═══════════════════════════════════════════════════════════════════
#  SIVUN HAKU — HTML
# ═══════════════════════════════════════════════════════════════════

def fetch_by_scrape(company):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(company["url"], headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  [{company['ticker']}] Haku epäonnistui: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    articles = []

    for tag in soup.find_all(company["selector"]):
        a = tag.find("a")
        if not a:
            continue
        href = a.get("href", "")
        if company.get("link_filter") and company["link_filter"] not in href:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        if not href.startswith("http"):
            href = company["base_url"] + href
        articles.append({"title": title, "url": href})

    return articles


# ═══════════════════════════════════════════════════════════════════
#  SIVUN HAKU — RSS (Enovix / GlobeNewswire)
# ═══════════════════════════════════════════════════════════════════

def fetch_by_rss(company):
    try:
        r = requests.get(company["url"], timeout=20,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"  [{company['ticker']}] RSS-haku epäonnistui: {e}")
        return []

    soup = BeautifulSoup(r.text, "xml")
    articles = []

    for item in soup.find_all("item"):
        title = item.find("title")
        link  = item.find("link")
        if title and link:
            articles.append({
                "title": title.get_text(strip=True),
                "url":   link.get_text(strip=True),
            })

    return articles[:20]  # vain tuoreimmat 20


# ═══════════════════════════════════════════════════════════════════
#  TILAN HALLINTA
# ═══════════════════════════════════════════════════════════════════

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, "r", encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def get_company_state(state, ticker):
    return state.get(ticker, {"seen_urls": [], "last_check": None})


# ═══════════════════════════════════════════════════════════════════
#  AI-ANALYYSI
# ═══════════════════════════════════════════════════════════════════

def ai_analyze(company, new_articles):
    client = anthropic.Anthropic()

    articles_text = "\n".join(
        [f"- {a['title']}\n  {a['url']}" for a in new_articles]
    )

    prompt = f"""Olet kokenut osakeanalyytikko. Analysoi seuraavat uudet tiedotteet.

Yhtiö: {company['name']} ({company['ticker']}, NASDAQ)
Kuvaus: {company['description']}

Uudet tiedotteet:
{articles_text}

Kirjoita JOKAISESTA tiedotteesta:
1. 📌 Mistä on kyse (1 lause)
2. 💡 Merkitys sijoittajalle (1-2 lausetta)
3. 📈 Vaikutus osakekurssiin: Positiivinen / Negatiivinen / Neutraali + lyhyt perustelu

Pidä vastaus tiiviinä. Kirjoita suomeksi."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        return f"[AI-analyysi epäonnistui: {e}]"


# ═══════════════════════════════════════════════════════════════════
#  PRIORITEETIN TARKISTUS
# ═══════════════════════════════════════════════════════════════════

def is_priority(articles):
    for a in articles:
        text = a["title"].lower()
        if any(kw.lower() in text for kw in PRIORITY_KEYWORDS):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════
#  TELEGRAM-ILMOITUS
# ═══════════════════════════════════════════════════════════════════

def send_telegram(message):
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("\n" + "═"*60)
        print(message)
        print("═"*60 + "\n")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
        try:
            requests.post(url, data={
                "chat_id":    chat_id,
                "text":       chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }, timeout=15).raise_for_status()
        except Exception as e:
            print(f"[VIRHE] Telegram: {e}")


def format_message(company, new_articles, ai_summary):
    now   = datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")
    prio  = is_priority(new_articles)
    emoji = "🔴" if prio else "📰"
    label = "PRIORITEETTIUUTINEN" if prio else "Uusi tiedote"

    lines = [
        f"{emoji} *{label} — {company['name']} ({company['ticker']})*",
        f"_{now} · {len(new_articles)} uutta tiedotetta_",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for a in new_articles:
        tag = " 🔴" if any(kw.lower() in a["title"].lower()
                           for kw in PRIORITY_KEYWORDS) else ""
        lines.append(f"\n*{a['title']}*{tag}")
        lines.append(f"🔗 {a['url']}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "*AI-analyysi:*\n",
        ai_summary,
    ]

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
#  PÄÄOHJELMA
# ═══════════════════════════════════════════════════════════════════

def main():
    print(f"\n[{datetime.utcnow().isoformat()}] Uutisagentti käynnistyy...")
    print(f"Seurataan {len(COMPANIES)} yhtiötä: "
          + ", ".join(c["ticker"] for c in COMPANIES))

    state = load_state()
    found_any = False

    for company in COMPANIES:
        ticker = company["ticker"]
        print(f"\n  → {ticker}: haetaan {company['url']}")

        # Hae uutiset
        if company["method"] == "rss":
            articles = fetch_by_rss(company)
        else:
            articles = fetch_by_scrape(company)

        if not articles:
            print(f"    Ei artikkeleita tai haku epäonnistui.")
            continue

        print(f"    Löydettiin {len(articles)} artikkelia.")

        # Vertaa aiempaan tilaan
        co_state  = get_company_state(state, ticker)
        seen_urls = set(co_state["seen_urls"])
        new       = [a for a in articles if a["url"] not in seen_urls]

        if not new:
            print(f"    Ei uusia tiedotteita.")
        else:
            print(f"    🆕 {len(new)} uutta tiedotetta!")
            for a in new:
                print(f"       • {a['title'][:70]}")

            # AI-analyysi
            print(f"    → Analysoidaan Claudella...")
            summary = ai_analyze(company, new)

            # Lähetä ilmoitus
            msg = format_message(company, new, summary)
            send_telegram(msg)
            found_any = True

        # Päivitä tila
        all_urls = list(seen_urls | {a["url"] for a in articles})
        state[ticker] = {
            "seen_urls":  all_urls[-200:],  # max 200 URL muistissa
            "last_check": datetime.utcnow().isoformat(),
        }

    save_state(state)

    if not found_any:
        print("\n✓ Ei uusia uutisia. Seuraava tarkistus 15 min päästä.")
    else:
        print("\n✓ Ilmoitukset lähetetty!")


if __name__ == "__main__":
    main()
