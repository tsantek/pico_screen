"""Cursor Cloud Agents API — same agent: next + last workout."""

import ubinascii

try:
    import ujson as json
except ImportError:
    import json

from net.http import http_get_json
from net.workout import parse_workout

BASE = "https://api.cursor.com/v1"


def _auth_header(api_key):
    token = ubinascii.b2a_base64(("%s:" % api_key).encode()).decode().strip()
    return {"Authorization": "Basic %s" % token}


def _dump(label, obj, limit=500):
    try:
        text = json.dumps(obj)
    except Exception:
        text = str(obj)
    if len(text) > limit:
        text = text[:limit] + "...[trunc %d]" % len(text)
    print("--- %s ---" % label)
    print(text)
    print("--- end %s ---" % label)


def _result_md(run):
    if not run:
        return ""
    st = run.get("status")
    if st in ("RUNNING", "CREATING"):
        return "Working..."
    return (run.get("result") or "")[:2500]


def _get_run(headers, agent_id, run_id):
    if not run_id:
        return None
    return http_get_json(
        "%s/agents/%s/runs/%s" % (BASE, agent_id, run_id), headers=headers
    )


def fetch(api_key, agent_id, last_agent_id=None, verbose=True):
    """
    Same agent, two run fetches:
      1) newest run  → Next workout
      2) previous run → Last workout
    last_agent_id is ignored (kept for call-site compat).
    """
    if not agent_id:
        empty = {"ok": False, "kind": "NONE", "title": "(no agent)", "lines": []}
        return {
            "id": None,
            "name": "?",
            "status": "?",
            "run_status": None,
            "summary": "",
            "workout": empty,
            "workout_next": empty,
            "workout_last": empty,
        }

    headers = _auth_header(api_key)

    print("Agent: loading", agent_id)
    agent = http_get_json("%s/agents/%s" % (BASE, agent_id), headers=headers)
    if verbose:
        _dump("agent GET", agent)
    name = (agent.get("name") or "Agent")[:40]

    print("Runs list (newest first)")
    listed = http_get_json(
        "%s/agents/%s/runs?limit=3" % (BASE, agent_id), headers=headers
    )
    if verbose:
        _dump("runs LIST", listed, limit=400)
    items = listed.get("items") or []

    # Prefer latestRunId as next if list is empty
    next_id = items[0].get("id") if items else agent.get("latestRunId")
    last_id = items[1].get("id") if len(items) > 1 else None

    print("Call 1/2: NEXT run", next_id)
    next_run = _get_run(headers, agent_id, next_id)
    if verbose and next_run:
        _dump("next run", next_run, limit=400)

    print("Call 2/2: LAST run", last_id)
    last_run = _get_run(headers, agent_id, last_id) if last_id else None
    if verbose and last_run:
        _dump("last run", last_run, limit=400)

    workout_next = parse_workout(_result_md(next_run), agent_name=name)
    if last_run:
        workout_last = parse_workout(_result_md(last_run), agent_name=name)
    else:
        workout_last = {
            "ok": False,
            "kind": "NONE",
            "title": "(no previous run)",
            "lines": [],
        }

    if verbose:
        _dump("workout next", workout_next)
        _dump("workout last", workout_last)

    return {
        "id": agent.get("id") or agent_id,
        "name": name,
        "status": agent.get("status") or "?",
        "run_status": next_run.get("status") if next_run else None,
        "summary": workout_next.get("title") or "",
        "url": agent.get("url"),
        "workout": workout_next,
        "workout_next": workout_next,
        "workout_last": workout_last,
    }
