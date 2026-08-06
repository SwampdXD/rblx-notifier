"""
Roblox -> Discord "user came online" notifier (single-run, for GitHub Actions).

This script checks presence ONCE and exits. It's meant to be triggered
repeatedly (e.g. every 5 minutes) by a GitHub Actions schedule, which means
it needs your PC on for exactly zero minutes.

It remembers the last known status in last_status.json so it can detect
"they just came online" across separate runs.
"""

import requests
import json
import os
from datetime import datetime
from pathlib import Path

# ---------------- CONFIG ----------------
ROBLOX_USER_ID = 980356263
STATE_FILE = Path(__file__).parent / "last_status.json"
# Webhook URL comes from an environment variable (set as a GitHub secret,
# see setup instructions) rather than being hardcoded in the file.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
# -----------------------------------------

PRESENCE_LABELS = {
    0: "Offline",
    1: "Online (Website)",
    2: "In a Game",
    3: "In Studio",
}


def get_username(user_id):
    try:
        resp = requests.get(f"https://users.roblox.com/v1/users/{user_id}")
        resp.raise_for_status()
        return resp.json().get("name", str(user_id))
    except Exception:
        return str(user_id)


def get_presence(user_id):
    url = "https://presence.roblox.com/v1/presence/users"
    resp = requests.post(url, json={"userIds": [user_id]})
    resp.raise_for_status()
    presences = resp.json()["userPresences"]
    return presences[0] if presences else None


def send_discord_notification(username, presence_type):
    if not DISCORD_WEBHOOK_URL:
        print("No DISCORD_WEBHOOK_URL set, skipping notification.")
        return
    status_text = PRESENCE_LABELS.get(presence_type, "Online")
    payload = {
        "content": f"🟢 **{username}** just came online! ({status_text}) — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    }
    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if resp.status_code not in (200, 204):
        print(f"Failed to send webhook: {resp.status_code} {resp.text}")


def load_last_status():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text()).get("status", 0)
        except Exception:
            return 0
    return 0


def save_last_status(status):
    STATE_FILE.write_text(json.dumps({"status": status}))


def main():
    username = get_username(ROBLOX_USER_ID)
    presence = get_presence(ROBLOX_USER_ID)

    if presence is None:
        print(f"No presence data returned for {username} ({ROBLOX_USER_ID})")
        return

    presence_type = presence["userPresenceType"]
    last_status = load_last_status()

    was_offline = last_status == 0
    now_online = presence_type != 0

    label = PRESENCE_LABELS.get(presence_type, "Unknown")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {username}: {label}")

    if was_offline and now_online:
        print(f"{username} just came online -> sending Discord notification")
        send_discord_notification(username, presence_type)

    save_last_status(presence_type)


if __name__ == "__main__":
    main()
