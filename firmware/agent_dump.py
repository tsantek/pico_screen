"""Dump NEXT + LAST workouts (optional live status prompt)."""

import sys

sys.path.insert(0, "/")

import secrets
from net import wifi
from net import cursor_agent


def main():
    print("Connecting WiFi...")
    wifi.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    agent_id = getattr(secrets, "CURSOR_AGENT_ID", None)
    prompt_on = bool(getattr(secrets, "AGENT_PROMPT_ON_REFRESH", True))
    print("Agent:", agent_id, "prompt_on_refresh=", prompt_on)
    snap = cursor_agent.fetch(
        secrets.CURSOR_API_KEY,
        agent_id,
        verbose=True,
        prompt_on_refresh=prompt_on,
        prompt_text=getattr(secrets, "AGENT_STATUS_PROMPT", None),
        poll_s=int(getattr(secrets, "AGENT_POLL_SECONDS", 8)),
        timeout_s=int(getattr(secrets, "AGENT_POLL_TIMEOUT", 240)),
    )
    print("SOURCE:", snap.get("source"))
    print("NEXT:", snap.get("workout_next"))
    print("LAST:", snap.get("workout_last"))
    try:
        wifi.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    main()
