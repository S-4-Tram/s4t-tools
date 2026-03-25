"""
logic.py
Programme generation logic for the Strength 4 Trampoline system.

Contains constraint application, exercise filtering, session building,
and programme assembly. No input handling, no string formatting beyond
what is needed for structured data.
"""

import re
from dataclasses import dataclass

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


# ═══════════════════════════════════════════════════════════════════════════
# CONSTRAINT MODULE REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

_constraint_modules = []


def register_constraint_module(module):
    """Register a constraint module.

    A module is any object with a method:
        get_constraints(section_key, cfg) -> list[dict]

    Returns a list of constraint dicts. Each dict maps trait names
    to desired values and represents one valid target profile.
    An exercise is scored against each dict separately; best match wins.
    Trait names must match keys used in exercise traits dicts.
    """
    _constraint_modules.append(module)


def resolve_constraints(section_key, cfg):
    """Collect constraint dicts from all registered modules.

    Each module returns a list of constraint dicts. Each dict represents
    one valid target profile. Returns a flat list of all dicts from all modules.
    """
    all_constraints = []
    for module in _constraint_modules:
        constraints = module.get_constraints(section_key, cfg)
        all_constraints.extend(constraints)
    return all_constraints


def apply_exercise_constraints(pool, constraint_list):
    """Sort pool by best trait match across constraint dicts.

    Each exercise is scored against every constraint dict separately.
    Its score is the highest single match (best-fit wins).
    Untagged exercises score 0 (kept, not removed).
    """
    if not constraint_list:
        return pool

    def score_against(traits, constraints):
        return sum(1 for k, v in constraints.items() if traits.get(k) == v)

    def score(ex):
        traits = ex.get("traits")
        if not traits:
            return 0
        return max(score_against(traits, c) for c in constraint_list)

    return sorted(pool, key=score, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════
# PROGRAMME CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ProgrammeConfig:
    """All user inputs bundled into a single object."""
    name: str
    age_group: str          # "junior" | "youth" | "senior"
    athlete_level: str      # "beginner" | "intermediate" | "advanced"
    focus: str              # "force production" | "repeated power" | "injury resilience"
    week: int               # 1–4
    limiting_factor: str    # key from LIMITING_FACTORS or "none"
    equipment: str          # "full" | "limited" | "bodyweight"
    duration: int           # 30 | 45 | 60
    proximity: str          # key from COMPETITION_PROXIMITY
    main_sessions: int      # 1–6
    micro_sessions: int     # 0–5
    version: str            # "athlete" | "coach"


# ═══════════════════════════════════════════════════════════════════════════
# EQUIPMENT FILTERING
# ═══════════════════════════════════════════════════════════════════════════

EQUIPMENT_RANK = {"bodyweight": 0, "limited": 1, "full": 2}

# Baseline max exercises per section (applied before competition modifier).
# Sections not listed have no baseline cap.
SECTION_MAX_EXERCISES = {
    "strength": 4,
    "jumps": 2,
    "overhead": 3,
}

# Sections where the top-ranked exercise is locked into every session.
SECTION_LOCK_TOP = {"strength"}

# Day bias: for sections listed here, exercises matching the given
# contraction_mode values get a small boost on that session_number.
DAY_BIAS = {
    "jumps": {
        2: {"plyometric", "fast_ssc"},
        3: {"reactive", "fast"},
    },
}


def filter_exercises_for_equipment(exercise_pool, equipment):
    """Return the best-matched exercise per equipment-variant slot."""
    equip_rank = EQUIPMENT_RANK[equipment]
    selected = []
    i = 0
    while i < len(exercise_pool):
        group = [exercise_pool[i]]
        j = i + 1
        while j < len(exercise_pool):
            cur_rank = EQUIPMENT_RANK[exercise_pool[j]["equipment"]]
            prev_rank = EQUIPMENT_RANK[exercise_pool[j - 1]["equipment"]]
            if cur_rank < prev_rank:
                group.append(exercise_pool[j])
                j += 1
            else:
                break
        best = None
        for ex in group:
            ex_rank = EQUIPMENT_RANK[ex["equipment"]]
            if ex_rank <= equip_rank:
                if best is None or ex_rank > EQUIPMENT_RANK[best["equipment"]]:
                    best = ex
        if best is None:
            best = group[-1]
        selected.append(best)
        i = j
    return selected


# ═══════════════════════════════════════════════════════════════════════════
# CONSTRAINT APPLICATION
# ═══════════════════════════════════════════════════════════════════════════

def get_sections_for_duration(focus, duration):
    """Return which JOBS sections to include based on session duration."""
    priority = SESSION_PRIORITY[focus]
    if duration == 60:
        count = 4
    elif duration == 45:
        count = 3
    else:
        count = 2
    included = set(priority[:count])
    return [s for s in SESSION_ORDER[focus] if s in included]


def apply_competition_modifier(exercises, proximity):
    """Apply competition proximity constraints to an exercise list."""
    config = COMPETITION_PROXIMITY[proximity]
    result = exercises
    if config["max_exercises_per_section"] is not None:
        result = result[:config["max_exercises_per_section"]]
    if config["exclude_heavy_eccentrics"]:
        result = [ex for ex in result if not ex.get("eccentric_heavy", False)]
        if not result and exercises:
            result = [exercises[0]]
    return result


def apply_volume_modifier(prescription_text, modifier):
    """Reduce set counts in a prescription string by the modifier amount."""
    if modifier >= 0:
        return prescription_text
    match = re.match(r'^(\d+)\s*x\s*', prescription_text)
    if match:
        sets = max(1, int(match.group(1)) + modifier)
        return re.sub(r'^\d+\s*x', f'{sets} x', prescription_text)
    return prescription_text


def get_microdose_schedule(programme_type, limiting_factor, num_sessions):
    """Return the list of microdose focus areas for the week."""
    priorities = list(MICRODOSE_PRIORITIES[programme_type])
    if limiting_factor and limiting_factor != "none":
        lf_focus = LIMITING_FACTORS[limiting_factor]["microdose_priority"]
        if lf_focus in priorities:
            priorities.remove(lf_focus)
        priorities.insert(0, lf_focus)
    return [priorities[i % len(priorities)] for i in range(num_sessions)]


# ═══════════════════════════════════════════════════════════════════════════
# EXERCISE TEXT
# ═══════════════════════════════════════════════════════════════════════════

def get_exercise_text(exercise, week, age_group, version):
    """Return the formatted exercise string for a given week, age, and version."""
    week_idx = min(week - 1, len(exercise["weeks"]) - 1)
    w = exercise["weeks"][week_idx]
    prescription = w["prescription"]
    cue = w["cue"][age_group]
    return f"{exercise['name']}  —  {prescription}\n    → {cue}"


# ═══════════════════════════════════════════════════════════════════════════
# SESSION BUILDING
# ═══════════════════════════════════════════════════════════════════════════

def _apply_day_bias(selected, section_key, session_number):
    """Re-sort exercises by day bias. Matching exercises float to the top,
    non-matching keep their relative order below."""
    bias_config = DAY_BIAS.get(section_key)
    if not bias_config:
        return selected
    target_modes = bias_config.get(session_number)
    if not target_modes:
        return selected
    biased = []
    rest = []
    for ex in selected:
        mode = ex.get("traits", {}).get("contraction_mode")
        if mode and mode in target_modes:
            biased.append(ex)
        else:
            rest.append(ex)
    return biased + rest


def select_exercises_for_section(section_key, cfg, session_number=1):
    """Select and filter exercises for a single JOBS section.

    session_number drives deterministic rotation when a section cap
    is active. Sections in SECTION_LOCK_TOP keep the top-ranked
    exercise in every session, rotating the remaining slots.
    """
    pool = EXERCISE_LIBRARY[cfg.focus][section_key]

    # ── constraint-based reordering (no-op if no modules registered) ──
    constraints = resolve_constraints(section_key, cfg)
    pool = apply_exercise_constraints(pool, constraints)

    selected = filter_exercises_for_equipment(pool, cfg.equipment)

    # ── day bias (light re-sort before cap) ──
    selected = _apply_day_bias(selected, section_key, session_number)

    # ── baseline section cap with session rotation ──
    if section_key in SECTION_MAX_EXERCISES and selected:
        cap = SECTION_MAX_EXERCISES[section_key]
        lock_top = section_key in SECTION_LOCK_TOP

        if lock_top:
            locked = selected[0]
            remainder = selected[1:]
            rotate_cap = cap - 1
            offset = (session_number - 1) * rotate_cap
            rotated = []
            for i in range(rotate_cap):
                if remainder:
                    idx = (offset + i) % len(remainder)
                    rotated.append(remainder[idx])
            selected = [locked] + rotated
        else:
            offset = (session_number - 1) * cap
            rotated = []
            for i in range(cap):
                idx = (offset + i) % len(selected)
                rotated.append(selected[idx])
            selected = rotated

    selected = apply_competition_modifier(selected, cfg.proximity)

    if cfg.limiting_factor and cfg.limiting_factor != "none":
        lf = LIMITING_FACTORS[cfg.limiting_factor]
        if lf["section_bias"] == section_key and section_key in _BONUS_EXERCISES:
            bonus = _BONUS_EXERCISES[section_key]
            if EQUIPMENT_RANK[bonus["equipment"]] <= EQUIPMENT_RANK[cfg.equipment]:
                selected.append(bonus)

    return selected


def build_session_data(day_number, session_number, total_main, cfg):
    """Build the structured data for a main session (no formatting)."""
    sections = get_sections_for_duration(cfg.focus, cfg.duration)
    vol_modifier = COMPETITION_PROXIMITY[cfg.proximity]["volume_modifier"]
    warmup_key = "short" if cfg.duration == 30 else "full"

    session_sections = []
    for section_key in sections:
        exercises = select_exercises_for_section(section_key, cfg, session_number)
        exercise_texts = []
        for ex in exercises:
            text = get_exercise_text(ex, cfg.week, cfg.age_group, cfg.version)
            if vol_modifier < 0:
                week_idx = min(cfg.week - 1, len(ex["weeks"]) - 1)
                orig = ex["weeks"][week_idx]["prescription"]
                mod = apply_volume_modifier(orig, vol_modifier)
                text = text.replace(orig, mod)
            exercise_texts.append(text)
        session_sections.append((section_key, exercise_texts))

    warmup_items = WARMUP[warmup_key]
    cooldown_items = COOLDOWN_SHORT if cfg.duration == 30 else COOLDOWN

    return {
        "day_number": day_number,
        "session_number": session_number,
        "total_main": total_main,
        "sections": session_sections,
        "warmup": warmup_items,
        "cooldown": cooldown_items,
    }


def build_microdose_data(day_number, focus_area, session_number, total_micro, cfg):
    """Build the structured data for a microdose session (no formatting)."""
    session_data = MICRODOSE_SESSIONS[focus_area]
    exercises = session_data.get(cfg.athlete_level, session_data["intermediate"])

    exercise_items = []
    for item in exercises:
        exercise_items.append({
            "prescription": item["prescription"],
            "cue": item["cue"][cfg.age_group],
        })

    return {
        "day_number": day_number,
        "session_number": session_number,
        "total_micro": total_micro,
        "label": session_data["label"],
        "exercises": exercise_items,
    }


def build_programme_data(cfg):
    """Assemble all session data for the full programme."""
    main_session_data = []
    for i in range(1, cfg.main_sessions + 1):
        day = i
        data = build_session_data(day, i, cfg.main_sessions, cfg)
        main_session_data.append(data)

    microdose_areas = get_microdose_schedule(
        cfg.focus, cfg.limiting_factor, cfg.micro_sessions)
    microdose_data = []
    for i in range(1, cfg.micro_sessions + 1):
        day = cfg.main_sessions + i
        focus_area = microdose_areas[i - 1]
        data = build_microdose_data(day, focus_area, i, cfg.micro_sessions, cfg)
        microdose_data.append(data)

    return {
        "main_sessions": main_session_data,
        "microdose_sessions": microdose_data,
    }
