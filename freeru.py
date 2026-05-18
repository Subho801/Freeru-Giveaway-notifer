import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

WEBHOOK = os.getenv("DISCORD_WEBHOOK")
URL = "https://freeru.cc/games/giveaways/games"
STATE_FILE = "seen_freeru.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

            # Old format support: ["id1", "id2"]
            if isinstance(data, list):
                return {
                    old_id: {
                        "title": old_id,
                        "keys_left": None,
                        "status": "active",
                        "out_notified": False
                    }
                    for old_id in data
                }

            return data

    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def clean_title(title):
    title = re.sub(r"Раздача ключей от игры в Steam\s*-\s*", "", title, flags=re.I)
    title = re.sub(r"Раздача ключей от игры Steam\s*-\s*", "", title, flags=re.I)

    replacements = {
        "Раздача рандомных ключей от игры Steam 2025": "Random Steam Game Keys 2025",
        "Более 20 разных игр": "Over 20 different games",
        "Коллекционные карточки": "Trading Cards",
        "в библиотеку": "Library Bonus",
        "достижения": "Achievements",
    }

    for ru, en in replacements.items():
        title = title.replace(ru, en)

    title = title.replace("!", "").strip()
    title = re.sub(r"\s+", " ", title)

    return title


def get_card_image(card):
    img = card.find("img")

    if img:
        for attr in ["src", "data-src", "data-lazy-src"]:
            src = img.get(attr)
            if src:
                return requests.compat.urljoin(URL, src)

    return None


def get_keys_left(text):
    patterns = [
        r"Keys remaining:\s*(\d+)",
        r"Ключей осталось:\s*(\d+)",
        r"Ключей остал[оьс]+:\s*(\d+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return int(m.group(1))

    return None


def is_active(text):
    return "Active" in text or "Активная" in text


def send_discord(title, keys_left, link, image=None, event_type="started"):
    if event_type == "out":
        embed = {
            "title": f"⛔ {title}",
            "url": link,
            "description": "❌ **Keys ran out!**\n\n[Open Giveaway]({})".format(link),
            "color": 15548997,
            "footer": {
                "text": "Subho's FreeRU Giveaway"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        embed = {
            "title": f"🎁 {title}",
            "url": link,
            "description": f"✅ **Giveaway Started!**\n🔑 **Keys left:** `{keys_left}`\n\n[Claim Giveaway]({link})",
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

    state = load_state()
    current_ids = set()
    posted_started = 0
    posted_out = 0

    headings = soup.find_all("h5")

    for h in headings:
        card = h.find_parent()
        if not card:
            continue

        title_raw = h.get_text(" ", strip=True)
        text = card.get_text(" ", strip=True)

        a = h.find_next("a", href=True)
        if not a:
            continue

        link = requests.compat.urljoin(URL, a["href"])
        giveaway_id = link.rstrip("/").split("/")[-1]
        current_ids.add(giveaway_id)

        title = clean_title(title_raw)
        image = get_card_image(card)
        keys_left = get_keys_left(text)
        active = is_active(text)

        if keys_left is None:
            keys_left = 0

        old = state.get(giveaway_id)

        # New active giveaway notification
        if not old and active and keys_left > 0:
            send_discord(title, keys_left, link, image=image, event_type="started")
            posted_started += 1

            state[giveaway_id] = {
                "title": title,
                "link": link,
                "image": image,
                "keys_left": keys_left,
                "status": "active",
                "out_notified": False
            }

            continue

        # Existing giveaway update
        if old:
            old_keys = old.get("keys_left")

            if old_keys is None:
                old_keys = keys_left

            # Notify once when keys run out
            if old_keys > 0 and keys_left <= 0 and not old.get("out_notified", False):
                send_discord(
                    old.get("title", title),
                    keys_left,
                    old.get("link", link),
                    image=old.get("image") or image,
                    event_type="out"
                )
                posted_out += 1

                old["out_notified"] = True
                old["status"] = "out"

            else:
                old["status"] = "active" if active and keys_left > 0 else "out"

            old["title"] = title
            old["link"] = link
            old["image"] = image or old.get("image")
            old["keys_left"] = keys_left

            state[giveaway_id] = old

    save_state(state)

    print(f"Started posted: {posted_started}")
    print(f"Out-of-keys posted: {posted_out}")

    if posted_started == 0 and posted_out == 0:
        print("No new FreeRU updates.")


if __name__ == "__main__":
    if not WEBHOOK:
        raise RuntimeError("Missing DISCORD_WEBHOOK secret")

    scrape()
