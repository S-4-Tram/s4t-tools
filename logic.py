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
    FMAX_MAIN_LIFTS,
    FMAX_MACHINE_ACCESSORIES,
    FMAX_ACCESSORIES,
    BRACE_EXERCISES,
    OVERHEAD_EXERCISES,
    STAGE_MAP,
    STAGE_PRESCRIPTIONS,
    STAGE_CUES,
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
    programme_seed: int = 0 # shifts starting position in ranked pools
    block_length: int = 4   # 4 | 6 | 8 week block


# ═══════════════════════════════════════════════════════════════════════════
# EQUIPMENT FILTERING
# ═══════════════════════════════════════════════════════════════════════════

EQUIPMENT_RANK = {"bodyweight": 0, "limited": 1, "full": 2}

# Baseline max exercises per section (applied before competition modifier).
# Sections not listed have no baseline cap.
SECTION_MAX_EXERCISES = {
    "strength": 3,   # 1 main lift + 2 accessories
    "jumps": 2,
    "brace": 3,
    "overhead": 3,
}

# Fixed session section order (overrides programme-type ordering).
SESSION_SECTION_ORDER = ["jumps", "strength", "brace", "overhead"]

# Jump day intent: maps session_number to desired jump_type.
# Exercises matching the day's intent are selected first;
# remaining slots are filled from the rest of the pool.
JUMP_DAY_INTENT = {
    1: "repeated",
    2: "max_output",
    3: "reactive",
}

# Stage-driven jump intent — the default jump progression model.
#
# Session intent is now stage-driven, not fixed. This map determines
# which jump_type (repeated / max_output / reactive) is targeted for
# slot 1 in each session, based on the current block stage.
#
# Early block (establish, build) remains stable — matching the fixed
# baseline to build exposure, movement quality, and consistency across
# all three adaptations before shifting emphasis.
#
# Late block (push, realise) shifts intent to drive adaptation:
#   push    → force output emphasis (2 of 3 sessions target max_output)
#   realise → stiffness emphasis (2 of 3 sessions target reactive)
#
# Stage bias (JUMP_STAGE_BIAS) remains secondary — it only refines
# exercise selection within the chosen intent tier, acting as a
# tie-breaker among exercises of the same jump_type.
#
# Pairing constraints (unilateral exclusion, pattern diversity, contrast
# scoring) remain unchanged and always take priority over both intent
# matching and stage bias.
#
# Falls back to JUMP_DAY_INTENT if stage is None.
JUMP_DAY_INTENT_BY_STAGE = {
    "establish": {1: "repeated",   2: "max_output", 3: "reactive"},
    "build":     {1: "repeated",   2: "max_output", 3: "reactive"},
    "push":      {1: "max_output", 2: "reactive",   3: "max_output"},
    "realise":   {1: "reactive",   2: "max_output",  3: "reactive"},
}

# Biomechanics preference profile per jump day. Scored against exercise
# traits to differentiate exercises within the same intent tier.
JUMP_DAY_PROFILE = {
    1: {"load": "low", "tempo": "explosive"},                     # repeated: bodyweight explosive
    2: {"load": "heavy", "tempo": "explosive"},                   # max_output: loaded explosive
    3: {"contraction_mode": "reactive", "tempo": "fast"},         # reactive: fast stiff contacts
}


def filter_exercises_for_equipment(exercise_pool, equipment):
    """Return the best-matched exercise per equipment-variant slot.

    Uses positional variant grouping: consecutive exercises with
    descending equipment rank are treated as variants of one slot,
    and the best match at or below the available tier is selected.

    Only suitable for sections where exercises are explicitly arranged
    as equipment variant groups (e.g. Barbell → Dumbbell → Bodyweight).
    """
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
        if best is not None:
            selected.append(best)
        i = j
    return selected


def filter_exercises_strict(exercise_pool, equipment):
    """Return all exercises at or below the available equipment tier.

    No variant grouping — every exercise is treated independently.
    Use for sections with a unified pool of independent exercises.
    """
    equip_rank = EQUIPMENT_RANK[equipment]
    return [ex for ex in exercise_pool
            if EQUIPMENT_RANK[ex["equipment"]] <= equip_rank]


# Sections that use strict (non-grouping) equipment filtering.
# All other sections use the positional variant grouping filter.
STRICT_EQUIPMENT_SECTIONS = {"jumps"}


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

# ═══════════════════════════════════════════════════════════════════════════
# SESSION BUILDING
# ═══════════════════════════════════════════════════════════════════════════

# Intent bonus added to jump exercises that match the day's jump_type.
# Must be large enough to outweigh biomechanics trait differences but
# still allow biomechanics to break ties between equally-intent-matched exercises.
_JUMP_INTENT_BONUS = 10

# Complementary trait preference for the secondary jump slot.
# For each day, defines which trait values are preferred for slot 2,
# given what slot 1 already provides.
JUMP_SECONDARY_PROFILE = {
    1: {"tempo": "fast", "contraction_mode": "reactive"},     # repeated primary → elastic/cyclic complement
    2: {"load": "low", "tempo": "explosive"},                 # max_output primary → lighter explosive complement (base)
    3: {"load": "low", "tempo": "explosive"},                 # reactive primary → supportive explosive complement
}

# Traits compared for contrast scoring on Day 2 slot 2.
_DAY2_CONTRAST_TRAITS = ("load", "tempo", "contraction_mode")

# Penalty applied when slot 2 shares the same movement pattern as slot 1.
_PATTERN_DUPLICATE_PENALTY = 3

# Stage-based role bias for jump ranking.
# Session intent (JUMP_DAY_INTENT) remains the primary driver of which
# jump_type is selected for each session. Stage bias is secondary — it
# only re-ranks candidates within the intent-matched tier, acting as a
# tie-breaker. With intent bonus = 10 and max stage bias = 3, intent
# always wins the first-order decision.
JUMP_STAGE_BIAS = {
    "establish": {"rfd": 2, "stiffness": 1, "repeatability": 3},
    "build":     {"rfd": 3, "stiffness": 2, "repeatability": 1},
    "push":      {"rfd": 3, "stiffness": 3, "repeatability": 0},
    "realise":   {"rfd": 2, "stiffness": 3, "repeatability": 0},
}


def _is_unilateral(ex):
    """Check if an exercise is unilateral based on its name."""
    name = ex.get("name", "")
    return "SL " in name or "Single Leg" in name


def _get_movement_pattern(ex):
    """Derive the movement pattern category from the exercise name.

    Used to penalise slot 2 candidates that duplicate slot 1's pattern.
    """
    name = ex.get("name", "").lower()
    if any(k in name for k in ("pogo", "ankling", "ankle bounces", "10:5")):
        return "stiffness"
    if any(k in name for k in ("drop", "depth", "snap down", "reactive jump from")):
        return "rebound"
    if any(k in name for k in ("cmj", "countermovement")):
        return "cmj"
    if any(k in name for k in ("broad", "lateral bounds", "lateral split")):
        return "displacement"
    if any(k in name for k in ("box jump", "box jump", "seated")):
        return "box"
    if any(k in name for k in ("squat jump", "pause squat")):
        return "squat_jump"
    if "compass" in name:
        return "compass"
    if "hurdle" in name:
        return "hurdle"
    if "twist" in name:
        return "twist"
    if any(k in name for k in ("tuck", "straight jumps", "split jumps")):
        return "cyclic_vertical"
    if "bounding" in name or "bounds" in name:
        return "bounding"
    if "trap bar" in name:
        return "loaded_pull"
    if "loaded" in name or "weighted" in name:
        return "loaded_push"
    return "other"


def _jump_composite_score(ex, intent, profile, stage=None):
    """Score a jump exercise against intent + day profile + stage bias."""
    traits = ex.get("traits", {})
    bonus = 0
    if intent and traits.get("jump_type") == intent:
        bonus = _JUMP_INTENT_BONUS
    bio = 0
    if profile and traits:
        bio = sum(1 for k, v in profile.items() if traits.get(k) == v)
    stage_bonus = 0
    if stage:
        role = _JUMP_ROLE_MAP.get(traits.get("jump_type"), "")
        stage_bonus = JUMP_STAGE_BIAS.get(stage, {}).get(role, 0)
    return bonus + bio + stage_bonus


def rank_jump_pool(selected, session_number, stage=None):
    """Rank jump exercises by intent match + day profile + stage bias.

    Stable sort: ties preserve original pool order.
    If no intent or profile is defined for this session_number, returns
    the pool unchanged (stage bias still applies if provided).
    """
    intent_map = JUMP_DAY_INTENT_BY_STAGE.get(stage, JUMP_DAY_INTENT) if stage else JUMP_DAY_INTENT
    intent = intent_map.get(session_number)
    profile = JUMP_DAY_PROFILE.get(session_number)

    if not intent and not profile and not stage:
        return selected

    return sorted(
        selected,
        key=lambda ex: _jump_composite_score(ex, intent, profile, stage),
        reverse=True,
    )


def _rotate_within_tier(exercises, week, seed=0):
    """Rotate a ranked list by seed + week offset.

    seed shifts the starting position (varies across programmes).
    week advances by 1 within a programme (varies across the block).
    Wraps around when the end is reached.
    """
    if len(exercises) <= 1:
        return exercises
    offset = (seed + week - 1) % len(exercises)
    return exercises[offset:] + exercises[:offset]


def select_jump_pair(pool, session_number, week=1, seed=0, stage=None):
    """Select a primary + complementary jump pair for the session.

    Slot 1 (primary): ranked by intent + day profile + stage bias,
        then offset by seed within the intent-matched tier. The same
        pair is selected for all weeks within a programme (week is not
        used for exercise selection — only for prescription lookup).
    Slot 2 (secondary): ranked by secondary profile from the
        remaining pool (excluding slot 1), offset by seed.

    If only 1 exercise in pool, returns just that exercise.
    If pool is empty, returns empty list.
    """
    if len(pool) <= 1:
        return list(pool)

    intent_map = JUMP_DAY_INTENT_BY_STAGE.get(stage, JUMP_DAY_INTENT) if stage else JUMP_DAY_INTENT
    intent = intent_map.get(session_number)
    profile = JUMP_DAY_PROFILE.get(session_number)
    secondary_profile = JUMP_SECONDARY_PROFILE.get(session_number)

    # Rank the full pool (with stage bias if provided)
    ranked = rank_jump_pool(pool, session_number, stage)

    # Partition into intent-matched and non-matched, preserving rank order
    matched = [ex for ex in ranked
               if ex.get("traits", {}).get("jump_type") == intent]
    unmatched = [ex for ex in ranked
                 if ex.get("traits", {}).get("jump_type") != intent]

    # Slot 1: offset by seed only (stable across the block)
    if matched:
        rotated_matched = _rotate_within_tier(matched, 1, seed)
        primary = rotated_matched[0]
    else:
        rotated_all = _rotate_within_tier(ranked, 1, seed)
        primary = rotated_all[0]

    # Remainder: everything except the selected primary
    remainder = [ex for ex in ranked if ex is not primary]

    # Hard rule: if slot 1 is unilateral, exclude unilateral from slot 2 candidates
    primary_unilateral = _is_unilateral(primary)
    if primary_unilateral:
        bilateral_remainder = [ex for ex in remainder if not _is_unilateral(ex)]
        if bilateral_remainder:
            remainder = bilateral_remainder

    # Slot 2: rank remainder by secondary profile + pattern diversity + contrast.
    primary_traits = primary.get("traits", {})
    primary_pattern = _get_movement_pattern(primary)

    if secondary_profile and remainder:
        def secondary_score(ex):
            traits = ex.get("traits", {})
            if not traits:
                return 0
            # Base: secondary profile match
            base = sum(1 for k, v in secondary_profile.items()
                       if traits.get(k) == v)
            # Day 2 contrast bonus
            contrast = 0
            if session_number == 2:
                for trait_key in _DAY2_CONTRAST_TRAITS:
                    s1_val = primary_traits.get(trait_key)
                    s2_val = traits.get(trait_key)
                    if s1_val and s2_val and s1_val != s2_val:
                        contrast += 1
            # Pattern diversity penalty (soft)
            pattern_penalty = 0
            if _get_movement_pattern(ex) == primary_pattern:
                pattern_penalty = _PATTERN_DUPLICATE_PENALTY
            return base + contrast - pattern_penalty

        remainder = sorted(remainder, key=secondary_score, reverse=True)

    remainder = _rotate_within_tier(remainder, 1, seed)
    secondary = remainder[0] if remainder else None

    result = [primary]
    if secondary:
        result.append(secondary)
    return result


def _deduplicate(exercises):
    """Remove duplicate exercises (by name), preserving order."""
    seen = set()
    result = []
    for ex in exercises:
        if ex["name"] not in seen:
            seen.add(ex["name"])
            result.append(ex)
    return result


def select_exercises_for_section(section_key, cfg, session_number=1, stage=None):
    """Select and filter exercises for a single JOBS section.

    Jumps: uses the jump pair selection system (with optional stage bias).
    Strength: 1 locked main lift + 2 rotating accessories (no duplicates).
    Brace/Overhead: capped selection with day rotation (no duplicates).
    """
    pool = EXERCISE_LIBRARY[cfg.focus][section_key]

    # ── constraint-based reordering (no-op if no modules registered) ──
    constraints = resolve_constraints(section_key, cfg)
    pool = apply_exercise_constraints(pool, constraints)

    if section_key in STRICT_EQUIPMENT_SECTIONS:
        selected = filter_exercises_strict(pool, cfg.equipment)
    else:
        selected = filter_exercises_for_equipment(pool, cfg.equipment)

    # ── deduplicate (prevent same exercise appearing twice in pool) ──
    selected = _deduplicate(selected)

    # ── jump pair selection ──
    if section_key == "jumps":
        selected = select_jump_pair(selected, session_number, cfg.week, cfg.programme_seed, stage)

    # ── strength: 1 locked main lift + 2 rotating accessories ──
    elif section_key == "strength" and selected:
        locked = selected[0]
        remainder = [ex for ex in selected[1:] if ex["name"] != locked["name"]]
        # Rotate accessories by day, selecting 2 unique per session
        offset = (session_number - 1) * 2
        accessories = []
        for i in range(2):
            if remainder:
                idx = (offset + i) % len(remainder)
                if remainder[idx]["name"] not in {a["name"] for a in accessories}:
                    accessories.append(remainder[idx])
        selected = [locked] + accessories

    # ── brace / overhead: capped with day rotation, no duplicates ──
    elif section_key in SECTION_MAX_EXERCISES and selected:
        cap = SECTION_MAX_EXERCISES[section_key]
        offset = (session_number - 1) * cap
        rotated = []
        for i in range(cap):
            if selected:
                idx = (offset + i) % len(selected)
                candidate = selected[idx]
                if candidate["name"] not in {r["name"] for r in rotated}:
                    rotated.append(candidate)
        selected = rotated

    selected = apply_competition_modifier(selected, cfg.proximity)

    if cfg.limiting_factor and cfg.limiting_factor != "none":
        lf = LIMITING_FACTORS[cfg.limiting_factor]
        if lf["section_bias"] == section_key and section_key in _BONUS_EXERCISES:
            bonus = _BONUS_EXERCISES[section_key]
            if EQUIPMENT_RANK[bonus["equipment"]] <= EQUIPMENT_RANK[cfg.equipment]:
                if bonus["name"] not in {ex["name"] for ex in selected}:
                    selected.append(bonus)

    return selected


# ═══════════════════════════════════════════════════════════════════════════
# FMAX STRENGTH SELECTION
# ═══════════════════════════════════════════════════════════════════════════

FMAX_EQUIPMENT_MAP = {
    "full": "full_gym",
    "limited": "partial",
    "bodyweight": "bodyweight",
}

FMAX_EQUIPMENT_RANK = {
    "bodyweight": 0,
    "partial": 1,
    "full_gym": 2,
}

PATTERN_COMPLEMENTS = {
    "squat": ["calf", "hip_extension", "hip_abduction", "hip_adduction"],
    "hinge": ["quad", "calf", "hip_abduction", "hip_adduction"],
    "split_squat": ["calf", "hip_extension", "hip_abduction"],
    "step_up": ["calf", "hip_extension", "hip_abduction"],
    "single_leg_hinge": ["quad", "calf", "hip_abduction"],
    "calf_raise": ["quad", "hamstring", "hip_abduction"],
}

REGION_WEIGHTS = {
    "quad": 5,
    "calf": 5,
    "hamstring": 3,
    "hip_extension": 3,
    "hip_abduction": 2,
    "hip_adduction": 2,
    "hip_flexion": 1,
}


def _build_fmax_category_lookup():
    """Build a name → category lookup from the FMAX accessory data structures.

    For non-machine accessories, category is the FMAX_ACCESSORIES dict key.
    For machine accessories, category is derived from pattern (hip variants)
    or region (quad, hamstring, calf).
    """
    lookup = {}
    for cat, exs in FMAX_ACCESSORIES.items():
        for ex in exs:
            lookup[ex["name"]] = cat
    for ex in FMAX_MACHINE_ACCESSORIES:
        if ex["pattern"] in ("hip_adduction", "hip_abduction"):
            lookup[ex["name"]] = ex["pattern"]
        else:
            lookup[ex["name"]] = ex["region"]
    return lookup


_FMAX_CATEGORY_LOOKUP = _build_fmax_category_lookup()


def _fmax_filter_by_equipment(exercises, equipment):
    """Filter FMAX exercises to those available at the given equipment level."""
    rank = FMAX_EQUIPMENT_RANK[FMAX_EQUIPMENT_MAP[equipment]]
    return [ex for ex in exercises
            if any(FMAX_EQUIPMENT_RANK[el] <= rank for el in ex["equipment_level"])]


def _fmax_build_accessory_pool(equipment):
    """Combine machine and non-machine accessories, filtered by equipment.

    Machine accessories included only at full_gym.
    Non-machine accessories included at all relevant equipment levels.
    """
    rank = FMAX_EQUIPMENT_RANK[FMAX_EQUIPMENT_MAP[equipment]]
    pool = []

    if FMAX_EQUIPMENT_MAP[equipment] == "full_gym":
        pool.extend(FMAX_MACHINE_ACCESSORIES)

    for category, exercises in FMAX_ACCESSORIES.items():
        for ex in exercises:
            if any(FMAX_EQUIPMENT_RANK[el] <= rank for el in ex["equipment_level"]):
                pool.append(ex)

    return pool


def select_fmax_strength(cfg, session_number):
    """Select 1 main lift + 2 accessories for an Fmax strength block.

    Main lift: rotated from FMAX_MAIN_LIFTS, filtered by equipment.
    Accessory 1: different name, region, and pattern from main lift.
        Relaxes constraints gracefully if pool is sparse.
    Accessory 2: from a complement category to the main lift pattern.
        Falls back to remaining pool if no complement match.

    Both accessories sorted by REGION_WEIGHTS (quad/calf bias)
    and rotated deterministically by session_number + programme_seed.
    No duplicate names within the block.
    """
    # ── flatten and filter main lifts ──
    all_mains = []
    for slot, exercises in FMAX_MAIN_LIFTS.items():
        all_mains.extend(exercises)
    mains = _fmax_filter_by_equipment(all_mains, cfg.equipment)
    if not mains:
        return []

    # Sort by region weight (descending), rotate by session + seed
    mains.sort(key=lambda ex: REGION_WEIGHTS.get(ex["region"], 1), reverse=True)
    main_idx = (session_number - 1 + cfg.programme_seed) % len(mains)
    main_lift = mains[main_idx]

    # ── build accessory pool ──
    accessory_pool = _fmax_build_accessory_pool(cfg.equipment)

    # ── accessory 1: different name, region, and pattern from main ──
    acc1_candidates = [
        ex for ex in accessory_pool
        if ex["name"] != main_lift["name"]
        and ex["region"] != main_lift["region"]
        and ex["pattern"] != main_lift["pattern"]
    ]
    # Fallback: relax pattern constraint
    if not acc1_candidates:
        acc1_candidates = [
            ex for ex in accessory_pool
            if ex["name"] != main_lift["name"]
            and ex["region"] != main_lift["region"]
        ]
    # Fallback: relax region constraint
    if not acc1_candidates:
        acc1_candidates = [
            ex for ex in accessory_pool
            if ex["name"] != main_lift["name"]
        ]

    acc1_candidates.sort(
        key=lambda ex: REGION_WEIGHTS.get(
            _FMAX_CATEGORY_LOOKUP.get(ex["name"], ""), 1),
        reverse=True)

    acc1 = None
    if acc1_candidates:
        acc1_idx = (session_number - 1 + cfg.programme_seed) % len(acc1_candidates)
        acc1 = acc1_candidates[acc1_idx]

    # ── accessory 2: complement to main lift pattern, avoid acc1 overlap ──
    complement_cats = PATTERN_COMPLEMENTS.get(main_lift["pattern"], [])
    used_names = {main_lift["name"]}
    if acc1:
        used_names.add(acc1["name"])

    # Preferred: complement category + different region and pattern from acc1
    acc2_candidates = [
        ex for ex in accessory_pool
        if _FMAX_CATEGORY_LOOKUP.get(ex["name"]) in complement_cats
        and ex["name"] not in used_names
        and (acc1 is None or ex["region"] != acc1["region"])
        and (acc1 is None or ex["pattern"] != acc1["pattern"])
    ]
    # Relax: complement category + different region from acc1
    if not acc2_candidates:
        acc2_candidates = [
            ex for ex in accessory_pool
            if _FMAX_CATEGORY_LOOKUP.get(ex["name"]) in complement_cats
            and ex["name"] not in used_names
            and (acc1 is None or ex["region"] != acc1["region"])
        ]
    # Relax: complement category only
    if not acc2_candidates:
        acc2_candidates = [
            ex for ex in accessory_pool
            if _FMAX_CATEGORY_LOOKUP.get(ex["name"]) in complement_cats
            and ex["name"] not in used_names
        ]
    # Fallback: any remaining exercise
    if not acc2_candidates:
        acc2_candidates = [
            ex for ex in accessory_pool
            if ex["name"] not in used_names
        ]

    acc2_candidates.sort(
        key=lambda ex: REGION_WEIGHTS.get(
            _FMAX_CATEGORY_LOOKUP.get(ex["name"], ""), 1),
        reverse=True)

    acc2 = None
    if acc2_candidates:
        acc2_idx = (session_number - 1 + cfg.programme_seed) % len(acc2_candidates)
        acc2 = acc2_candidates[acc2_idx]

    # ── assemble ──
    result = [main_lift]
    if acc1:
        result.append(acc1)
    if acc2:
        result.append(acc2)

    return result


# ═══════════════════════════════════════════════════════════════════════════
# BRACE SELECTION
# ═══════════════════════════════════════════════════════════════════════════

def select_brace(cfg, session_number):
    """Select 2 brace exercises: 1 lateral + 1 anterior or posterior.

    Lateral is always selected first.
    Second exercise biased ~70/30 toward anterior over posterior.
    Deterministic rotation using session_number + programme_seed.
    """
    lateral = _fmax_filter_by_equipment(BRACE_EXERCISES["lateral"], cfg.equipment)
    anterior = _fmax_filter_by_equipment(BRACE_EXERCISES["anterior"], cfg.equipment)
    posterior = _fmax_filter_by_equipment(BRACE_EXERCISES["posterior"], cfg.equipment)

    if not lateral:
        return []

    lat_idx = (session_number - 1 + cfg.programme_seed) % len(lateral)
    lat_pick = lateral[lat_idx]

    # Bias ~70/30 toward anterior: use 7 of every 10 sessions for anterior
    rotation = (session_number - 1 + cfg.programme_seed) % 10
    if rotation < 7 and anterior:
        second_pool = anterior
    elif posterior:
        second_pool = posterior
    else:
        second_pool = anterior or posterior

    if not second_pool:
        return [lat_pick]

    sec_idx = (session_number - 1 + cfg.programme_seed) % len(second_pool)
    sec_pick = second_pool[sec_idx]

    return [lat_pick, sec_pick]


# ═══════════════════════════════════════════════════════════════════════════
# OVERHEAD SELECTION
# ═══════════════════════════════════════════════════════════════════════════

def select_overhead(cfg, session_number):
    """Select 2 overhead exercises: 1 stability + 1 strength, scapular, or integrated.

    Stability is always selected first.
    Second exercise: ~60% strength, ~20% scapular, ~20% integrated.
    Selected stability exercise excluded from second pool.
    Dynamic retained in data but not in default rotation.
    Deterministic rotation using session_number + programme_seed.
    """
    stability = _fmax_filter_by_equipment(OVERHEAD_EXERCISES["stability"], cfg.equipment)
    strength = _fmax_filter_by_equipment(OVERHEAD_EXERCISES["strength"], cfg.equipment)
    scapular = _fmax_filter_by_equipment(OVERHEAD_EXERCISES["scapular"], cfg.equipment)
    integrated = _fmax_filter_by_equipment(OVERHEAD_EXERCISES["integrated"], cfg.equipment)

    if not stability:
        return []

    stab_idx = (session_number - 1 + cfg.programme_seed) % len(stability)
    stab_pick = stability[stab_idx]

    # 60% strength / 20% scapular / 20% integrated
    rotation = (session_number - 1 + cfg.programme_seed) % 5
    if rotation < 3 and strength:
        second_pool = strength
    elif rotation == 3 and scapular:
        second_pool = scapular
    elif rotation == 4 and integrated:
        second_pool = integrated
    elif strength:
        second_pool = strength
    elif scapular:
        second_pool = scapular
    elif integrated:
        second_pool = integrated
    else:
        return [stab_pick]

    second_pool = [ex for ex in second_pool if ex["name"] != stab_pick["name"]]

    if not second_pool:
        return [stab_pick]

    sec_idx = (session_number - 1 + cfg.programme_seed) % len(second_pool)
    sec_pick = second_pool[sec_idx]

    return [stab_pick, sec_pick]


# ── overhead role lookup (maps exercise name → overhead category) ──

def _build_overhead_role_lookup():
    lookup = {}
    for role in OVERHEAD_EXERCISES:
        for ex in OVERHEAD_EXERCISES[role]:
            lookup[ex["name"]] = role
    return lookup


_OVERHEAD_ROLE_LOOKUP = _build_overhead_role_lookup()


# ═══════════════════════════════════════════════════════════════════════════
# STAGE-BASED PROGRESSION
# ═══════════════════════════════════════════════════════════════════════════

def get_stage(block_length, current_week):
    """Map current week to training stage based on block length."""
    week_map = STAGE_MAP[block_length]
    clamped = min(current_week, block_length)
    return week_map[clamped]


def get_prescription(section, role, stage):
    """Look up the prescription string for a section/role/stage combination."""
    return STAGE_PRESCRIPTIONS[section][role][stage]


def get_cue(section, role, stage):
    """Look up the coaching cue for a section/role/stage combination."""
    return STAGE_CUES[section][role][stage]


def _build_exercise_item(name, prescription, cue, video=None, **meta):
    """Build a structured exercise item (data only, no display text).

    Core fields: name, prescription, cue, video.
    Additional metadata passed via **meta is merged into the item.
    """
    item = {
        "name": name,
        "prescription": prescription,
        "cue": cue,
        "video": video,
    }
    item.update(meta)
    return item


# ═══════════════════════════════════════════════════════════════════════════
# DISPLAY FORMATTING
# ═══════════════════════════════════════════════════════════════════════════

def format_exercise(section_key, exercise_item):
    """Format a structured exercise item for visible output.

    Jumps:                  Name  —  prescription\\n    → cue
    Strength/Brace/Overhead: Name  —  prescription
    """
    name = exercise_item["name"]
    rx = exercise_item["prescription"]
    cue = exercise_item.get("cue", "")

    if section_key == "jumps" and cue:
        return f"{name}  —  {rx}\n    → {cue}"
    return f"{name}  —  {rx}"


def format_session(session_data):
    """Format a full session's exercise items for visible output.

    Returns the same structure with exercise dicts replaced by display strings.
    """
    formatted_sections = []
    for section_key, exercises in session_data["sections"]:
        texts = [format_exercise(section_key, ex) for ex in exercises]
        formatted_sections.append((section_key, texts))

    return {
        **session_data,
        "sections": formatted_sections,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SESSION BUILDING
# ═══════════════════════════════════════════════════════════════════════════
#
# Progression model across sections:
#
# Jumps use stage-driven selection — the primary intent (which jump_type
# is targeted) changes across the block via JUMP_DAY_INTENT_BY_STAGE.
# This reflects the need for varied SSC exposure: different stages
# emphasise repeatability, force output, or stiffness to drive
# adaptation through stimulus variation.
#
# Strength, Brace, and Overhead use stable exercise selection within a
# block — the same exercises are selected for a given session_number +
# programme_seed regardless of stage. Progression in these sections
# comes from prescription and cue changes (STAGE_PRESCRIPTIONS,
# STAGE_CUES), not exercise variation. This reflects the need for
# repetition: strength, trunk stiffness, and overhead control develop
# through consistent practice of the same movement patterns under
# progressively greater demand.
#
# This distinction is intentional. Exercise variation drives jump
# adaptation. Exercise consistency drives strength, brace, and
# overhead adaptation.

_JUMP_ROLE_MAP = {
    "max_output": "rfd",
    "reactive": "stiffness",
    "repeated": "repeatability",
}


def build_session_data(day_number, session_number, total_main, cfg):
    """Build the structured data for a main session.

    Routes each JOBS section to the appropriate selector and prescription path:
    - Jumps: existing exercise library + week-based cues
    - Strength: FMAX selection + stage-based prescriptions
    - Brace: brace selection + subtype prescriptions (iso/dynamic)
    - Overhead: overhead selection + role prescriptions
    """
    available = set(get_sections_for_duration(cfg.focus, cfg.duration))
    sections = [s for s in SESSION_SECTION_ORDER if s in available]
    vol_modifier = COMPETITION_PROXIMITY[cfg.proximity]["volume_modifier"]
    warmup_key = "short" if cfg.duration == 30 else "full"
    stage = get_stage(cfg.block_length, cfg.week)

    session_sections = []
    for section_key in sections:

        if section_key == "jumps":
            # ── jumps: existing selection + week-based data ──
            exercises = select_exercises_for_section(section_key, cfg, session_number, stage)
            exercise_texts = []
            for ex in exercises:
                week_idx = min(cfg.week - 1, len(ex["weeks"]) - 1)
                w = ex["weeks"][week_idx]
                rx = w["prescription"]
                cue = w["cue"][cfg.age_group]
                if vol_modifier < 0:
                    rx = apply_volume_modifier(rx, vol_modifier)
                exercise_texts.append(_build_exercise_item(
                    ex["name"], rx, cue, ex.get("video"),
                    section="jumps",
                    role=_JUMP_ROLE_MAP.get(
                        ex.get("traits", {}).get("jump_type")),
                    equipment=ex.get("equipment"),
                    eccentric_heavy=ex.get("eccentric_heavy"),
                ))

        elif section_key == "strength":
            # ── strength: FMAX selection + stage prescriptions ──
            exercises = select_fmax_strength(cfg, session_number)
            exercise_texts = []
            for i, ex in enumerate(exercises):
                role = "main_lift" if i == 0 else "accessory"
                rx = get_prescription("strength", role, stage)
                cue = get_cue("strength", role, stage)
                exercise_texts.append(_build_exercise_item(
                    ex["name"], rx, cue, ex.get("video"),
                    section="strength",
                    role=role,
                    pattern=ex.get("pattern"),
                    region=ex.get("region"),
                    laterality=ex.get("laterality"),
                    equipment_type=ex.get("equipment_type"),
                    equipment_level=ex.get("equipment_level"),
                ))

        elif section_key == "brace":
            # ── brace: subtype-based prescriptions (iso / dynamic) ──
            exercises = select_brace(cfg, session_number)
            exercise_texts = []
            for ex in exercises:
                rx = get_prescription("brace", ex["subtype"], stage)
                cue = get_cue("brace", ex["subtype"], stage)
                exercise_texts.append(_build_exercise_item(
                    ex["name"], rx, cue, ex.get("video"),
                    section="brace",
                    role=ex["subtype"],
                    requires_support=ex.get("requires_support"),
                    equipment_type=ex.get("equipment_type"),
                    equipment_level=ex.get("equipment_level"),
                ))

        elif section_key == "overhead":
            # ── overhead: role-based prescriptions ──
            exercises = select_overhead(cfg, session_number)
            exercise_texts = []
            for ex in exercises:
                role = _OVERHEAD_ROLE_LOOKUP[ex["name"]]
                rx = get_prescription("overhead", role, stage)
                cue = get_cue("overhead", role, stage)
                exercise_texts.append(_build_exercise_item(
                    ex["name"], rx, cue, ex.get("video"),
                    section="overhead",
                    role=role,
                    pattern=ex.get("pattern"),
                    region=ex.get("region"),
                    laterality=ex.get("laterality"),
                    equipment_type=ex.get("equipment_type"),
                    equipment_level=ex.get("equipment_level"),
                    requires_support=ex.get("requires_support"),
                ))

        else:
            continue

        session_sections.append((section_key, exercise_texts))

    warmup_items = WARMUP[warmup_key]
    cooldown_items = COOLDOWN_SHORT if cfg.duration == 30 else COOLDOWN

    return {
        "day_number": day_number,
        "session_number": session_number,
        "total_main": total_main,
        "stage": stage,
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
