"""
output.py
Output formatting for the Strength 4 Trampoline programme generator.

All string rendering lives here. Takes structured data from logic.py
and a ProgrammeConfig, returns formatted text.
"""

from data import (
    COMPETITION_PROXIMITY,
    LIMITING_FACTORS,
    PROGRAMME_DESCRIPTIONS,
    PROGRAMME_HEADER_ATHLETE,
    PROGRAMME_HEADER_COACH,
    SECTION_LABELS,
    SESSION_RATIONALE,
    WEEK_OVERVIEW,
)
from logic import ProgrammeConfig


# ═══════════════════════════════════════════════════════════════════════════
# SECTION FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def format_header(cfg):
    """Format the programme header block."""
    lines = []
    header = PROGRAMME_HEADER_COACH if cfg.version == "coach" else PROGRAMME_HEADER_ATHLETE
    lines.append(header)

    lines.append(f"\nAthlete        : {cfg.name}")
    lines.append(f"Programme type : {cfg.focus.title()}")
    lines.append(f"Week           : {cfg.week} of 4")
    lines.append(f"Equipment      : {cfg.equipment.title()}")
    lines.append(f"Session length : {cfg.duration} mins")
    if cfg.proximity != "4+ weeks":
        lines.append(f"Competition    : {cfg.proximity.title()}")
    if cfg.limiting_factor and cfg.limiting_factor != "none":
        lines.append(f"Limiting factor: {cfg.limiting_factor.title()}")
    lines.append(f"Main sessions  : {cfg.main_sessions} per week")
    lines.append(f"Microdose      : {cfg.micro_sessions} per week")

    return "\n".join(lines)


def format_week_overview(cfg):
    """Format the week overview block."""
    lines = []
    lines.append(f"\n{'─' * 60}")
    lines.append("WEEK OVERVIEW")
    lines.append(f"{'─' * 60}")

    wo = WEEK_OVERVIEW[cfg.week]
    if cfg.version == "coach":
        lines.append(f"Purpose : {wo['coach']['purpose']}")
        lines.append(f"Focus   : {wo['coach']['focus']}")
        lines.append(f"Load    : {wo['coach']['load']}")
        lines.append(f"Note    : {wo['coach']['note']}")
    else:
        lines.append(wo["athlete"][cfg.age_group])

    lines.append(f"\n{PROGRAMME_DESCRIPTIONS[cfg.focus][cfg.age_group]}")

    comp_note = COMPETITION_PROXIMITY[cfg.proximity]["note"]
    if comp_note:
        lines.append(f"\n{comp_note[cfg.age_group]}")

    if cfg.limiting_factor and cfg.limiting_factor != "none":
        lf_desc = LIMITING_FACTORS[cfg.limiting_factor]["description"][cfg.age_group]
        lines.append(f"\n{lf_desc}")

    return "\n".join(lines)


def format_main_session(session_data, cfg):
    """Format a single main session from structured data."""
    d = session_data
    lines = []

    lines.append(f"\n{'─' * 60}")
    lines.append(f"DAY {d['day_number']}  |  MAIN SESSION {d['session_number']}/{d['total_main']}")
    lines.append(f"{'─' * 60}")

    if cfg.version == "coach":
        lines.append(f"Programme: {cfg.focus.title()}  |  Week {cfg.week}  |  {cfg.equipment.title()} gym")
        lines.append("")
        lines.append("Session rationale:")
        lines.append(SESSION_RATIONALE[cfg.focus][cfg.age_group])
    else:
        lines.append(f"Programme: {cfg.focus.title()}  |  Week {cfg.week}")
        lines.append("")
        lines.append("Why this order:")
        lines.append(SESSION_RATIONALE[cfg.focus][cfg.age_group])

    # Warm-up
    duration_label = "5" if cfg.duration == 30 else "10"
    lines.append(f"\nWARM-UP  ({duration_label} mins)")
    for item in d["warmup"]:
        lines.append(f"  • {item['prescription']} – {item['cue'][cfg.age_group]}")

    # JOBS sections
    for section_key, exercise_texts in d["sections"]:
        label = SECTION_LABELS["coach" if cfg.version == "coach" else "athlete"][section_key]
        lines.append(f"\n{label}")
        for text in exercise_texts:
            lines.append(f"  • {text}")

    # Cool-down
    cooldown_label = "5" if cfg.duration == 30 else "10"
    lines.append(f"\nCOOL-DOWN  ({cooldown_label} mins)")
    for item in d["cooldown"]:
        lines.append(f"  • {item}")

    return "\n".join(lines)


def format_microdose_session(microdose_data, cfg):
    """Format a single microdose session from structured data."""
    d = microdose_data
    lines = []

    lines.append(f"\n{'─' * 60}")
    lines.append(f"DAY {d['day_number']}  |  MICRODOSE {d['session_number']}/{d['total_micro']}  (~15 mins)")
    lines.append(d["label"])
    lines.append(f"{'─' * 60}\n")

    for item in d["exercises"]:
        lines.append(f"  • {item['prescription']}")
        lines.append(f"    → {item['cue']}")

    return "\n".join(lines)


def format_coach_notes(cfg):
    """Format the coach notes block at the end of the programme."""
    lines = []
    lines.append(f"\n\n{'=' * 60}")
    lines.append("  COACH NOTES")
    lines.append(f"{'=' * 60}")

    if cfg.version == "coach":
        lines.append(f"• {WEEK_OVERVIEW[cfg.week]['coach']['note']}")
        lines.append("• Stop any set that no longer meets the movement standard in the cue.")
        lines.append("• Load increases no more than 5% per week. Speed of intent and position are the real metrics.")
        lines.append("• Any tendon pain that persists into the following day must be reported before the next session.")
        lines.append("• Sleep is the primary recovery tool — target 8–9 hours. Hydrate consistently.")
        if cfg.limiting_factor and cfg.limiting_factor != "none":
            lines.append(f"• Limiting factor: {LIMITING_FACTORS[cfg.limiting_factor]['description']['senior']}")
        if cfg.proximity != "4+ weeks":
            lines.append(f"• Competition proximity: {COMPETITION_PROXIMITY[cfg.proximity]['note']['senior']}")
    else:
        lines.append("• If a set doesn't feel right, stop. Don't push through bad reps.")
        lines.append("• Tell your coach about any pain that lasts into the next day.")
        lines.append("• Sleep and hydration are your most important recovery tools.")

    lines.append(f"{'=' * 60}\n")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# FULL PROGRAMME FORMATTER
# ═══════════════════════════════════════════════════════════════════════════

def format_programme(programme_data, cfg):
    """Assemble the full programme text from structured data and config."""
    parts = [
        format_header(cfg),
        format_week_overview(cfg),
    ]

    for session in programme_data["main_sessions"]:
        parts.append(format_main_session(session, cfg))

    for session in programme_data["microdose_sessions"]:
        parts.append(format_microdose_session(session, cfg))

    parts.append(format_coach_notes(cfg))

    return "\n".join(parts)
