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
    title = re.sub(r"Раздача ключей от игры в Steam\s*-\s*", "", title, flags=re.I)
    title = re.sub(r"Раздача ключей от игры Steam\s*-\s*", "", title, flags=re.I)
    title = re.sub(r"\(.*?\)", "", title)
    title = title.replace("!", "").strip()
    return title

def get_steam_image(title):
    q = title.replace(" ", "+")
    try:
        r = requests.get(
            f"https://store.steampowered.com/api/storesearch/?term={q}&l=english&cc=us",
            headers=HEADERS,
            timeout=20
        )
        data = r.json()
        if data.get("items"):
            appid = data["items"][0]["id"]
            return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
    except Exception:
        pass
    return None

def send_discord(title, keys_left, link):
    image = get_steam_image(title)

    embed = {
        "title": f"🎁 {title}",
        "url": link,
        "description": f"✅ **Available!**\n🔑 **Keys left:** `{keys_left}`\n\n[Claim Giveaway]({link})",
        "color": 5763719,
        "footer": {
            "text": "Subho's FreeRU Giveaway"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if image:
        embed["image"] = {"url": image}

    payload = {"embeds": [embed]}

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
