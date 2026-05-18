import os, json, re, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

WEBHOOK = os.getenv("DISCORD_WEBHOOK")
URL = "https://freeru.cc/games/giveaways/games"
SEEN_FILE = "seen_freeru.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def load_seen():
    if os.path.exists(SEEN_FILE):
        return set(json.load(open(SEEN_FILE, "r", encoding="utf-8")))
    return set()

def save_seen(seen):
    json.dump(sorted(seen), open(SEEN_FILE, "w", encoding="utf-8"), indent=2)

def clean_title(title):
    title = title.replace("Раздача ключей от игры в Steam -", "")
    title = title.replace("Раздача ключей от игры Steam -", "")
    title = title.replace("Раздача", "Giveaway")
    return title.strip(" !")

def send_discord(title, keys_left, link):
    embed = {
        "title": f"🎁 {title}",
        "url": link,
        "description": f"✅ **Available!**\n🔑 **Keys left:** `{keys_left}`",
        "color": 5763719,
        "footer": {
            "text": "Megumin's FreeRU Giveaway"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    payload = {
        "content": "",
        "embeds": [embed]
    }

    r = requests.post(WEBHOOK, json=payload, timeout=20)
    r.raise_for_status()

def scrape():
    html = requests.get(URL, headers=HEADERS, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    seen = load_seen()
    new_seen = set(seen)
    posted = 0

    headings = soup.find_all("h5")

    for h in headings:
        title_raw = h.get_text(" ", strip=True)
        block_text = h.find_parent().get_text(" ", strip=True)

        if "Активная" not in block_text:
            continue

        m = re.search(r"Ключей остал[оьс]+:\s*(\d+)", block_text)
        if not m:
            continue

        keys_left = int(m.group(1))
        if keys_left <= 0:
            continue

        a = h.find_next("a", href=True)
        if not a:
            continue

        link = requests.compat.urljoin(URL, a["href"])
        giveaway_id = link.split("/")[-1]

        if giveaway_id in seen:
            continue

        title = clean_title(title_raw)
        send_discord(title, keys_left, link)

        new_seen.add(giveaway_id)
        posted += 1

    save_seen(new_seen)

    if posted == 0:
        print("No new FreeRU giveaways.")
    else:
        print(f"Posted {posted} new FreeRU giveaway(s).")

if __name__ == "__main__":
    if not WEBHOOK:
        raise RuntimeError("Missing DISCORD_WEBHOOK secret")
    scrape()
