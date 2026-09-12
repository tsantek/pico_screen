"""Minimal HTTPS GET for MicroPython (urequests)."""

try:
    import urequests as requests
except ImportError:
    import requests


def http_get(url, headers=None, timeout=30):
    """Return response text. Caller should keep responses small."""
    resp = None
    try:
        try:
            resp = requests.get(url, headers=headers or {}, timeout=timeout)
        except TypeError:
            # Older urequests without timeout=
            resp = requests.get(url, headers=headers or {})
        if resp.status_code != 200:
            raise OSError("HTTP %s for %s" % (resp.status_code, url[:48]))
        text = resp.text
        return text
    finally:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass


def http_get_json(url, headers=None, timeout=30):
    import json

    text = http_get(url, headers=headers, timeout=timeout)
    return json.loads(text)
