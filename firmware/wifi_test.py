"""Minimal WiFi smoke test."""

import secrets
from net.wifi import connect

print("Starting WiFi test...")
connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
print("SUCCESS")
