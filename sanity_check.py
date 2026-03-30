"""
sanity_check.py
Lightweight validation to catch data/config drift early.
"""

from __future__ import annotations

from typing import Iterable

from data import (
    COMPETITION_PROXIMITY,
    EXERCISE_LIBRARY,
    LIMITING_FACTORS,
    MICRODOSE_PRIORITIES,
    MICRODOSE_SESSIONS,
    SESSION_ORDER,
    SESSION_PRIORITY,
    WARMUP,
    COOLDOWN,
    COOLDOWN_SHORT,
    _BONUS_EXERCISES,
)


ALLOWED_EQUIPMENT = {"full", "limited", "bodyweight"}
ALLOWED_SECTIONS = {"strength", "jumps", "brace", "overhead"}
ALLOWED_AGE_GROUPS = {"junior", "youth", "senior"}


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def run_sanity_check(raise_on_error: bool = True) -> list[str]:
    errors: list[str] = []

    # Competition proximity
    for key, cfg in COMPETITION_PROXIMITY.items():
        if "volume_modifier" not in cfg:
            _err(errors, f"COMPETITION_PROXIMITY[{key!r}] missing volume_modifier")
        if "max_exercises_per_section" not in cfg:
            _err(errors, f"COMPETITION_PROXIMITY[{key!r}] missing max_exercises_per_section")
        if "exclude_heavy_eccentrics" not in cfg:
            _err(errors, f"COMPETITION_PROXIMITY[{key!r}] missing exclude_heavy_eccentrics")

    # Programme focus keys
    focus_keys = set(EXERCISE_LIBRARY.keys())
    for mapping_name, mapping in [
        ("SESSION_ORDER", SESSION_ORDER),
        ("SESSION_PRIORITY", SESSION_PRIORITY),
        ("MICRODOSE_PRIORITIES", MICRODOSE_PRIORITIES),
    ]:
        missing = focus_keys - set(mapping.keys())
        extra = set(mapping.keys()) - focus_keys
        for k in sorted(missing):
            _err(errors, f"{mapping_name} missing focus {k!r}")
        for k in sorted(extra):
            _err(errors, f"{mapping_name} has unknown focus {k!r}")

    # Section keys and exercise structure
    for focus, sections in EXERCISE_LIBRARY.items():
        missing_sections = ALLOWED_SECTIONS - set(sections.keys())
        extra_sections = set(sections.keys()) - ALLOWED_SECTIONS
        for s in sorted(missing_sections):
            _err(errors, f"EXERCISE_LIBRARY[{focus!r}] missing section {s!r}")
        for s in sorted(extra_sections):
            _err(errors, f"EXERCISE_LIBRARY[{focus!r}] has unknown section {s!r}")

        for section, pool in sections.items():
            if not isinstance(pool, list) or not pool:
                _err(errors, f"EXERCISE_LIBRARY[{focus!r}][{section!r}] must be a non-empty list")
                continue
            for ex in pool:
                name = ex.get("name")
                equip = ex.get("equipment")
                weeks = ex.get("weeks")
                if not name:
                    _err(errors, f"Exercise missing name in {focus!r}/{section!r}")
                if equip not in ALLOWED_EQUIPMENT:
                    _err(errors, f"Exercise {name!r} has invalid equipment {equip!r} in {focus!r}/{section!r}")
                if not isinstance(weeks, list) or len(weeks) != 4:
                    _err(errors, f"Exercise {name!r} must have 4 weeks in {focus!r}/{section!r}")
                    continue
                for w in weeks:
                    if "prescription" not in w or "cue" not in w:
                        _err(errors, f"Exercise {name!r} week missing prescription/cue in {focus!r}/{section!r}")
                        continue
                    cue = w["cue"]
                    for ag in ALLOWED_AGE_GROUPS:
                        if ag not in cue:
                            _err(errors, f"Exercise {name!r} cue missing {ag!r} in {focus!r}/{section!r}")

    # Limiting factors
    for lf, cfg in LIMITING_FACTORS.items():
        if cfg.get("section_bias") not in ALLOWED_SECTIONS:
            _err(errors, f"LIMITING_FACTORS[{lf!r}] invalid section_bias {cfg.get('section_bias')!r}")
        if cfg.get("microdose_priority") not in MICRODOSE_SESSIONS:
            _err(errors, f"LIMITING_FACTORS[{lf!r}] microdose_priority not in MICRODOSE_SESSIONS")

    # Bonus exercises: section key + structure
    for section, ex in _BONUS_EXERCISES.items():
        if section not in ALLOWED_SECTIONS:
            _err(errors, f"_BONUS_EXERCISES has unknown section {section!r}")
        if ex.get("equipment") not in ALLOWED_EQUIPMENT:
            _err(errors, f"_BONUS_EXERCISES[{section!r}] invalid equipment {ex.get('equipment')!r}")
        weeks = ex.get("weeks")
        if not isinstance(weeks, list) or len(weeks) != 4:
            _err(errors, f"_BONUS_EXERCISES[{section!r}] must have 4 weeks")

    # Warmup/cooldown shape
    for key, items in WARMUP.items():
        if not isinstance(items, list) or not items:
            _err(errors, f"WARMUP[{key!r}] must be a non-empty list")
            continue
        for item in items:
            cue = item.get("cue", {})
            for ag in ALLOWED_AGE_GROUPS:
                if ag not in cue:
                    _err(errors, f"WARMUP[{key!r}] item missing cue for {ag!r}")

    for seq_name, seq in [("COOLDOWN", COOLDOWN), ("COOLDOWN_SHORT", COOLDOWN_SHORT)]:
        if not isinstance(seq, list) or not seq:
            _err(errors, f"{seq_name} must be a non-empty list")

    if raise_on_error and errors:
        raise ValueError("Sanity check failed:\n- " + "\n- ".join(errors))

    return errors


__all__ = ["run_sanity_check"]

