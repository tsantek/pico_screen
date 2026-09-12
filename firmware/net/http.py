"""Minimal HTTPS helpers for MicroPython (urequests)."""

try:
    import urequests as requests
except ImportError:
    import requests

try:
    import ujson as json
except ImportError:
    import json


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
    text = http_get(url, headers=headers, timeout=timeout)
    return json.loads(text)


def http_post_json(url, body, headers=None, timeout=60):
    """POST JSON body; return parsed JSON. Accepts 200/201/202."""
    resp = None
    hdrs = dict(headers or {})
    hdrs["Content-Type"] = "application/json"
    data = json.dumps(body)
    try:
        try:
            resp = requests.post(url, data=data, headers=hdrs, timeout=timeout)
        except TypeError:
            resp = requests.post(url, data=data, headers=hdrs)
        code = resp.status_code
        if code not in (200, 201, 202):
            raise OSError("HTTP %s POST %s" % (code, url[:48]))
        text = resp.text
        return json.loads(text) if text else {}
    finally:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass
