"""Cursor Cloud Agents API — prompt for NEXT/LAST workout, or read runs."""

import time
import ubinascii

try:
    import ujson as json
except ImportError:
    import json

from net.http import http_get_json, http_post_json
from net.workout import parse_workout

BASE = "https://api.cursor.com/v1"

# Fixed desk-dashboard template. Agent must answer in this shape.
STATUS_PROMPT = """You are updating a Pico e-ink desk dashboard.

Using this agent's conversation / plan context, report:
1) NEXT planned workout
2) LAST completed workout

Reply with ONLY the markdown below. ASCII only. No extra commentary.
KIND must be one of: RUN GYM BIKE SWIM
Use - for unknown fields.
For SWIM fill Distance/Stroke; leave Run pace/Walk/Incline as -
For BIKE fill Pace as km/h or watts; leave Walk/Incline as -
For GYM fill Pattern as sets focus; leave Run pace/Walk/Incline as -
For RUN fill Pattern/Run pace/Walk/Incline as needed

## NEXT
KIND: RUN
TITLE: short title under 40 chars
Duration: e.g. 2:30-2:45 or 45:00
Pattern: e.g. 25/5 run/walk or -
Distance: e.g. 2000m or 7.5 km or -
Stroke: e.g. freestyle or -   (SWIM only; else -)
Run pace: e.g. 7.0-8.0 km/h or -
Walk: e.g. 5.0-5.5 km/h or -
Incline: e.g. 1-2% or -
Avg HR: e.g. 120-135 or -
Soft max: e.g. 145 or -
Fuel: e.g. TW + gel + water or -

## LAST
KIND: BIKE
TITLE: short title under 40 chars
Duration: e.g. 45:00
Pattern: -
Distance: -
Stroke: -
Run pace: -
Walk: -
Incline: -
Avg HR: e.g. 105
Soft max: e.g. 116
Fuel: -
"""


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


def _empty(title):
    return {"ok": False, "kind": "NONE", "title": title, "lines": []}


def _result_md(run):
    if not run:
        return ""
    st = run.get("status")
    if st in ("RUNNING", "CREATING"):
        return "Working..."
    return (run.get("result") or "")[:3500]


def _get_run(headers, agent_id, run_id):
    if not run_id:
        return None
    return http_get_json(
        "%s/agents/%s/runs/%s" % (BASE, agent_id, run_id), headers=headers
    )


def _split_next_last(md):
    """Split templated ## NEXT / ## LAST markdown into two bodies."""
    text = md or ""
    upper = text.upper()
    i_next = upper.find("## NEXT")
    i_last = upper.find("## LAST")
    if i_next < 0 and i_last < 0:
        return text, ""
    if i_next >= 0 and i_last >= 0:
        if i_next < i_last:
            next_body = text[i_next:i_last].strip()
            last_body = text[i_last:].strip()
        else:
            last_body = text[i_last:i_next].strip()
            next_body = text[i_next:].strip()
        return next_body, last_body
    if i_next >= 0:
        return text[i_next:].strip(), ""
    return "", text[i_last:].strip()


def _parse_kind_title(section, agent_name):
    """Prefer KIND:/TITLE: lines from template; else parse_workout."""
    kind = None
    title = None
    for line in (section or "").split("\n"):
        s = line.strip()
        low = s.lower()
        if low.startswith("kind:"):
            kind = s.split(":", 1)[1].strip().upper()
            if kind not in ("RUN", "GYM", "BIKE", "SWIM"):
                kind = None
        elif low.startswith("title:"):
            title = s.split(":", 1)[1].strip()[:40]
    card = parse_workout(section, agent_name=agent_name)
    if kind:
        card["kind"] = kind
        card["ok"] = True
    if title:
        from net.workout import _ascii_fold

        card["title"] = _ascii_fold(title)
        card["ok"] = True
    return card


def create_status_run(headers, agent_id, prompt_text):
    body = {"prompt": {"text": prompt_text}}
    print("Agent: POST status run...")
    created = http_post_json(
        "%s/agents/%s/runs" % (BASE, agent_id), body, headers=headers, timeout=60
    )
    _dump("create run", created, limit=300)
    # API may return {id, ...} or {run: {id, ...}}
    run_id = created.get("id")
    if not run_id and isinstance(created.get("run"), dict):
        run_id = created["run"].get("id")
    if not run_id:
        raise OSError("create run: no id")
    return run_id


def wait_run(headers, agent_id, run_id, poll_s=8, timeout_s=240):
    """Poll until FINISHED / ERROR / CANCELLED / EXPIRED or timeout."""
    deadline = time.time() + timeout_s
    last_st = None
    while time.time() < deadline:
        run = _get_run(headers, agent_id, run_id)
        st = (run or {}).get("status")
        if st != last_st:
            print("Agent run status:", st)
            last_st = st
        if st == "FINISHED":
            return run
        if st in ("ERROR", "CANCELLED", "EXPIRED"):
            raise OSError("agent run %s" % st)
        time.sleep(poll_s)
    raise OSError("agent run timeout after %ss" % timeout_s)


def fetch_via_prompt(
    api_key,
    agent_id,
    prompt_text=None,
    poll_s=8,
    timeout_s=240,
    verbose=True,
):
    """POST templated status prompt, wait, parse ## NEXT / ## LAST."""
    headers = _auth_header(api_key)
    prompt = prompt_text or STATUS_PROMPT

    agent = http_get_json("%s/agents/%s" % (BASE, agent_id), headers=headers)
    if verbose:
        _dump("agent GET", agent, limit=300)
    name = (agent.get("name") or "Agent")[:40]

    run_id = create_status_run(headers, agent_id, prompt)
    run = wait_run(headers, agent_id, run_id, poll_s=poll_s, timeout_s=timeout_s)
    if verbose:
        _dump("status run", run, limit=600)

    md = _result_md(run)
    next_md, last_md = _split_next_last(md)
    workout_next = _parse_kind_title(next_md, name)
    if last_md:
        workout_last = _parse_kind_title(last_md, name)
    else:
        workout_last = _empty("(no LAST section)")

    if verbose:
        _dump("workout next", workout_next)
        _dump("workout last", workout_last)

    return {
        "id": agent.get("id") or agent_id,
        "name": name,
        "status": agent.get("status") or "?",
        "run_status": run.get("status") if run else None,
        "summary": workout_next.get("title") or "",
        "url": agent.get("url"),
        "workout": workout_next,
        "workout_next": workout_next,
        "workout_last": workout_last,
        "source": "prompt",
    }


def fetch_via_runs(api_key, agent_id, verbose=True):
    """Read-only: prefer newest FINISHED run; split ## NEXT / ## LAST if present."""
    headers = _auth_header(api_key)

    print("Agent: loading runs", agent_id)
    agent = http_get_json("%s/agents/%s" % (BASE, agent_id), headers=headers)
    if verbose:
        _dump("agent GET", agent)
    name = (agent.get("name") or "Agent")[:40]

    print("Runs list (newest first)")
    listed = http_get_json(
        "%s/agents/%s/runs?limit=5" % (BASE, agent_id), headers=headers
    )
    if verbose:
        _dump("runs LIST", listed, limit=400)
    items = listed.get("items") or []

    # Skip in-progress runs for display
    finished = [it for it in items if it.get("status") == "FINISHED"]
    if not finished and agent.get("latestRunId"):
        finished = [{"id": agent.get("latestRunId")}]

    primary_id = finished[0].get("id") if finished else None
    prev_id = finished[1].get("id") if len(finished) > 1 else None

    print("Primary FINISHED run", primary_id)
    primary = _get_run(headers, agent_id, primary_id) if primary_id else None
    if verbose and primary:
        _dump("primary run", primary, limit=500)

    md = _result_md(primary)
    if md and ("## NEXT" in md.upper() or "## LAST" in md.upper()):
        next_md, last_md = _split_next_last(md)
        workout_next = _parse_kind_title(next_md, name)
        workout_last = (
            _parse_kind_title(last_md, name) if last_md else _empty("(no LAST section)")
        )
        source = "runs-template"
    else:
        workout_next = parse_workout(md, agent_name=name)
        prev = _get_run(headers, agent_id, prev_id) if prev_id else None
        if verbose and prev:
            _dump("prev run", prev, limit=400)
        workout_last = (
            parse_workout(_result_md(prev), agent_name=name)
            if prev
            else _empty("(no previous run)")
        )
        source = "runs"

    if verbose:
        _dump("workout next", workout_next)
        _dump("workout last", workout_last)

    return {
        "id": agent.get("id") or agent_id,
        "name": name,
        "status": agent.get("status") or "?",
        "run_status": primary.get("status") if primary else None,
        "summary": workout_next.get("title") or "",
        "url": agent.get("url"),
        "workout": workout_next,
        "workout_next": workout_next,
        "workout_last": workout_last,
        "source": source,
    }


def fetch(
    api_key,
    agent_id,
    last_agent_id=None,
    verbose=True,
    prompt_on_refresh=False,
    prompt_text=None,
    poll_s=8,
    timeout_s=240,
):
    """
    prompt_on_refresh=True → POST templated status, wait, parse NEXT/LAST.
    Else → read newest + previous runs (no new agent work).
    last_agent_id ignored (compat).
    """
    if not agent_id:
        empty = _empty("(no agent)")
        return {
            "id": None,
            "name": "?",
            "status": "?",
            "run_status": None,
            "summary": "",
            "workout": empty,
            "workout_next": empty,
            "workout_last": empty,
            "source": "none",
        }

    if prompt_on_refresh:
        try:
            return fetch_via_prompt(
                api_key,
                agent_id,
                prompt_text=prompt_text,
                poll_s=poll_s,
                timeout_s=timeout_s,
                verbose=verbose,
            )
        except Exception as e:
            print("Prompt refresh failed (%s) — falling back to runs list" % e)

    return fetch_via_runs(api_key, agent_id, verbose=verbose)
