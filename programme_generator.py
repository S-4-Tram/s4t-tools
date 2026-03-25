"""
programme_generator.py
Entry point for the Strength 4 Trampoline programme generator.

Handles user input collection, wires inputs into a ProgrammeConfig,
delegates to logic.py for programme building and output.py for formatting.
"""

from data import COMPETITION_PROXIMITY, LIMITING_FACTORS
from logic import ProgrammeConfig, build_programme_data, register_constraint_module
from output import format_programme
from biomechanics import BiomechanicsModule

register_constraint_module(BiomechanicsModule())


# ═══════════════════════════════════════════════════════════════════════════
# INPUT HANDLING
# ═══════════════════════════════════════════════════════════════════════════

def get_valid_int(prompt, min_val, max_val):
    """Keep asking until the user enters an integer within the allowed range."""
    while True:
        raw = input(prompt).strip()
        if raw.isdigit():
            value = int(raw)
            if min_val <= value <= max_val:
                return value
        print(f"  Please enter a whole number between {min_val} and {max_val}.")


def get_valid_choice(prompt, options):
    """Present numbered options and return the selected key."""
    keys = list(options) if isinstance(options, dict) else options
    for i, key in enumerate(keys, start=1):
        label = key.title() if isinstance(key, str) else str(key)
        print(f"  {i}. {label}")
    while True:
        raw = input(prompt).strip()
        if raw.isdigit():
            index = int(raw) - 1
            if 0 <= index < len(keys):
                return keys[index]
        print(f"  Please enter a number between 1 and {len(keys)}.")


def get_age_group():
    """Prompt for and return the age group key."""
    print("\nAge group:")
    print("  1. Junior (under 14)")
    print("  2. Youth (14–17)")
    print("  3. Senior (18+)")
    return get_valid_choice("Enter the number: ", ["junior", "youth", "senior"])


def get_athlete_level():
    """Prompt for and return the athlete level key."""
    print("\nAthlete level:")
    return get_valid_choice("Enter the number: ", ["beginner", "intermediate", "advanced"])


def collect_inputs():
    """Run the full input sequence and return a ProgrammeConfig."""
    print("=" * 60)
    print("  TRAMPOLINE S&C — JOBS FRAMEWORK PROGRAMME GENERATOR")
    print("  Strength 4 Trampoline")
    print("=" * 60)
    print()

    # Athlete profile
    name = input("Athlete name: ").strip() or "Athlete"
    age_group = get_age_group()
    athlete_level = get_athlete_level()

    # Programme setup
    print("\nProgramme type:")
    focus = get_valid_choice(
        "Enter the number: ",
        ["force production", "repeated power", "injury resilience"])

    week = get_valid_int("Programme week (1–4): ", 1, 4)

    print("\nPrimary limiting factor:")
    lf_options = ["none"] + list(LIMITING_FACTORS.keys())
    limiting_factor = get_valid_choice("Enter the number: ", lf_options)

    # Session constraints
    print("\nEquipment available:")
    equipment = get_valid_choice(
        "Enter the number: ",
        ["full", "limited", "bodyweight"])

    print("\nSession duration (minutes):")
    duration = get_valid_choice(
        "Enter the number: ",
        [30, 45, 60])

    print("\nCompetition proximity:")
    proximity = get_valid_choice(
        "Enter the number: ",
        list(COMPETITION_PROXIMITY.keys()))

    # Scheduling
    main_sessions = get_valid_int(
        "Number of main sessions this week (1–6): ", 1, 6)
    micro_sessions = get_valid_int(
        "Number of microdose sessions this week (0–5): ", 0, 5)

    # Output
    print("\nOutput version:")
    version = get_valid_choice(
        "Enter the number: ",
        ["athlete", "coach"])

    return ProgrammeConfig(
        name=name,
        age_group=age_group,
        athlete_level=athlete_level,
        focus=focus,
        week=week,
        limiting_factor=limiting_factor,
        equipment=equipment,
        duration=duration,
        proximity=proximity,
        main_sessions=main_sessions,
        micro_sessions=micro_sessions,
        version=version,
    )


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    cfg = collect_inputs()
    programme_data = build_programme_data(cfg)
    programme_text = format_programme(programme_data, cfg)

    print("\n" + programme_text)

    output_file = "weekly_programme.txt"
    with open(output_file, "w") as f:
        f.write(programme_text)
    print(f"Programme saved to: {output_file}")


if __name__ == "__main__":
    main()
