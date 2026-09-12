"""Preview: 10h weather, next/last workout, no goals."""

from drivers.epd_7in5_b import EPD_7in5_B
from net.workout import parse_workout
from ui import dashboard

NEXT_MD = """## Sub — LONG **2:30–2:45** (traka, 25/5)
| Nagib | **1–2%** |
| Run | **7.0–8.0 km/h** |
| Hod | **5.0–5.5 km/h** |
| Avg HR | **120–135** |
| Soft max | **145** |
| Cilj | **2:30** min · **2:45** max |
Tailwind gel Waffle Voda
"""

LAST_MD = """## Easy bike **45 min**
| Avg HR | **110–125** |
| Soft max | **135** |
| Cilj | **45 min**
"""


def main():
    next_w = parse_workout(NEXT_MD, "Profil trkaca")
    last_w = parse_workout(LAST_MD, "Profil trkaca")
    print("Next:", next_w.get("kind"), next_w.get("title"))
    print("Last:", last_w.get("kind"), last_w.get("title"))
    hourly = []
    for i, h in enumerate(range(18, 28)):
        hourly.append(
            {
                "hour": h % 24,
                "temp": 96 - i * 2,
                "icon": "sun" if i < 4 else "partly",
                "precip": 0,
            }
        )
    model = {
        "date_str": "FRI, SEP 12, 2026",
        "updated_str": "as of 18:00",
        "hour": 18,
        "minute": 0,
        "battery_pct": 87,
        "offline": False,
        "temp_unit": "F",
        "calendar": {
            "today": [
                {"start": "09:00", "end": "09:30", "title": "Standup"},
                {"start": "15:00", "end": "16:00", "title": "Ship board"},
                {"start": "18:30", "end": "19:30", "title": "Run club"},
            ],
            "tomorrow": [
                {"start": "10:00", "title": "Doctor"},
                {"start": "14:00", "title": "Deep work"},
            ],
        },
        "weather": {
            "current": {"temp": 96, "label": "Clear", "icon": "sun", "wind": 8, "wind_dir": "NW"},
            "today": {"high": 98, "low": 78, "label": "Clear", "icon": "sun", "precip": 5},
            "hourly": hourly,
        },
        "agent": {
            "name": "Profil trkaca",
            "status": "IDLE",
            "run_status": "FINISHED",
            "workout": next_w,
            "workout_next": next_w,
            "workout_last": last_w,
        },
    }
    print("Drawing...")
    epd = EPD_7in5_B()
    dashboard.draw(epd, model)
    epd.display()
    print("Done.")


if __name__ == "__main__":
    main()
