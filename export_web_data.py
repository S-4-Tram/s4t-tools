"""
export_web_data.py

Exports the Python single-source-of-truth programme data (from data.py)
into a web-friendly JSON file consumed by index.html.
"""

from __future__ import annotations

import json
from pathlib import Path

import data as pydata


WEB_EXPORT_KEYS = [
    "PROGRAMME_DESCRIPTIONS",
    "SESSION_ORDER",
    "SESSION_PRIORITY",
    "SESSION_RATIONALE",
    "SECTION_LABELS",
    "WEEK_OVERVIEW",
    "COMPETITION_PROXIMITY",
    "LIMITING_FACTORS",
    "MICRODOSE_PRIORITIES",
    "EXERCISE_LIBRARY",
    "MICRODOSE_SESSIONS",
    "WARMUP",
    "COOLDOWN",
    "COOLDOWN_SHORT",
    "_BONUS_EXERCISES",
    "PROGRAMME_HEADER_ATHLETE",
    "PROGRAMME_HEADER_COACH",
]


def build_payload() -> dict:
    payload = {}
    for key in WEB_EXPORT_KEYS:
        payload[key] = getattr(pydata, key)
    payload["_export_version"] = 1
    return payload


def main() -> None:
    out_path = Path(__file__).with_name("web_data.json")
    payload = build_payload()
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

