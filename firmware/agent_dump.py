"""Dump next + last workout from the same agent."""

import sys

sys.path.insert(0, "/")

import secrets
from net import wifi
from net import cursor_agent


def main():
    print("Connecting WiFi...")
    wifi.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    agent_id = getattr(secrets, "CURSOR_AGENT_ID", None)
    print("Agent:", agent_id)
    snap = cursor_agent.fetch(secrets.CURSOR_API_KEY, agent_id, verbose=True)
    print("NEXT:", snap.get("workout_next"))
    print("LAST:", snap.get("workout_last"))
    try:
        wifi.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    main()
