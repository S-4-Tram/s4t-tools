# S4T Programme Generator — System State

Last updated: 2026-03-26

## Architecture Overview

```
ProgrammeConfig
  ├── programme_seed        Jumps only — shifts starting position in ranked tiers
  ├── week                  1–4, advances within block (all sections)
  ├── focus                 force production / repeated power / injury resilience
  ├── equipment             bodyweight / limited / full
  ├── duration              30 / 45 / 60 min
  ├── proximity             competition proximity modifiers
  ├── limiting_factor       biases one section + microdose priority
  └── name / age_group / athlete_level / version
```

## File Structure

| File | Purpose |
|---|---|
| `programme_generator.py` | CLI entry point, input collection, biomechanics module registration |
| `logic.py` | All selection, scoring, rotation, and programme assembly logic |
| `data.py` | Exercise pools, prescriptions, constants, warmup/cooldown |
| `biomechanics.py` | First constraint module (joint action prescriptions) |
| `exercise_database.py` | Master exercise database by joint action (131 exercises, 15 joint actions) |
| `output.py` | Text formatting for programme output |
| `index.html` | Web interface (not yet synced with Python changes) |

## Sections and Selection Logic

### JUMPS (fully implemented)
- **Pool:** 50 exercises, unified across programme types
- **Equipment filtering:** Strict (no variant grouping)
- **Selection:** Intent-weighted pair selection (slot 1 primary + slot 2 complementary)
- **Day intent:** Day 1 = repeated, Day 3 = max_output, Day 5 = reactive
- **Scoring:** intent_bonus (10) + day profile match + Day 2 contrast scoring
- **Constraints:** Unilateral hard rule (no two unilateral per session), movement pattern diversity penalty
- **Rotation:** programme_seed shifts starting position; stable within 4-week block
- **Prescriptions:** All 50 exercises fully prescribed (4 weeks, 3 age tiers)
- **Classifications:**
  - jump_type: max_output (21), repeated (9), reactive (20)
  - contraction_mode: ssc (21), reactive (21), concentric (7), loaded_push (1)
  - equipment: bodyweight (32), limited (12), full (6)

### STRENGTH (basic implementation)
- **Pool:** Per programme type (_FP_STRENGTH, _RP_STRENGTH, _IR_STRENGTH)
- **Equipment filtering:** Variant grouping (original system)
- **Selection:** 1 locked main lift + 2 rotating accessories
- **Main lift:** Top-ranked exercise, locked across all sessions
- **Main lift progression:** Programme-level (MAIN_LIFT_PROGRESSION), not exercise-level
- **Accessory rotation:** Day-based offset, no seed
- **Uniqueness:** Enforced (no duplicates within session)
- **Known limitation:** RP and IR pools are too small for meaningful accessory rotation

### BRACE (minimal implementation)
- **Pool:** Per programme type (3 exercises FP, 2 RP, 3 IR)
- **Selection:** Capped at 3, day rotation, no duplicates
- **Known limitation:** Pools too small for day-to-day variation

### OVERHEAD (minimal implementation)
- **Pool:** Per programme type (9 exercises FP, 2 RP, 3 IR)
- **Selection:** Capped at 3, day rotation, no duplicates
- **Known limitation:** RP and IR pools too small

### MICRODOSE
- **System:** Separate from JOBS sections
- **Selection:** Focus area scheduling (ankle/knee/hip/trunk/shoulder)
- **Prioritisation:** Programme type + limiting factor
- **Tiering:** Beginner/intermediate/advanced exercise counts

## Constraint System

### Scaffold
- Module registry (`register_constraint_module`)
- `resolve_constraints(section_key, cfg)` → list of constraint dicts
- `apply_exercise_constraints(pool, constraint_list)` → sorted pool (best match first)
- Scoring: best single match across all constraint dicts

### Biomechanics Module
- 16 constraint dicts covering 9 joint actions
- Returns all constraints for any section (joint-action based, not JOBS-mapped)
- Trait vocabulary: joint_action, rom, rom_region, load, tempo, contraction_mode

### Jump-Specific Scoring
- `JUMP_DAY_INTENT` — maps session number to jump_type
- `JUMP_DAY_PROFILE` — biomechanics preferences per day
- `JUMP_SECONDARY_PROFILE` — slot 2 base preferences
- `_DAY2_CONTRAST_TRAITS` — contrast scoring on Day 2
- `_PATTERN_DUPLICATE_PENALTY` — soft penalty for same movement pattern
- `_is_unilateral()` — hard constraint enforcement
- `_get_movement_pattern()` — pattern classification for diversity

## Session Structure

Fixed order for all programme types:
1. Jumps (2 exercises)
2. Strength (1 main lift + 2 accessories)
3. Brace (2–3 exercises)
4. Overhead (2–3 exercises)

## Progression Model

### Within a block (W1–W4)
- Main lift: programme-level progression (volume → intensity → peak)
- Accessories: exercise-level progression (per exercise weeks[] array)
- Jumps: exercise-level progression (stable exercises, advancing prescriptions)

### Across programmes
- `programme_seed` varies jump selections (Jumps only)
- Seed 0 = default starting position
- Different seeds = different exercise pairs, same quality

## Exercise Database (exercise_database.py)

Master database organised by joint action. Not yet integrated as runtime source — EXERCISE_LIBRARY in data.py remains the active system.

| Joint action | Exercises |
|---|---|
| hip_extension | 15 |
| hip_adduction | 13 |
| hip_abduction | 11 |
| hip_flexion | 12 |
| knee_extension | 8 |
| knee_flexion | 10 |
| plantar_flexion | 22 |
| dorsi_flexion | 4 |
| inversion | 3 |
| eversion | 6 |
| foot | 7 |
| overhead | 6 |
| upper_push | 6 |
| upper_pull | 3 |
| trunk | 5 |

Plus: HAMSTRING_CURL_CONTINUUM (reference structure)

## Known Gaps / Next Steps

1. **Strength/Brace/Overhead pools need expansion** — RP and IR programme types have too few exercises for meaningful selection. Need the same treatment as Jumps (unified or expanded pools).
2. **Web interface (index.html) is behind** — does not reflect any of the constraint system, unified jump pool, or selection logic changes.
3. **Difficulty/complexity layer** — not yet implemented. Programme_seed currently represents variation only, not athlete progression. Future: training age, phase, and history should influence seed calculation.
4. **Exercise database → EXERCISE_LIBRARY migration** — exercise_database.py has 131 exercises with metadata but no prescriptions. A mapping layer is needed to feed these into the runtime system.
5. **Brace section needs intent system** — similar to how Jumps has day intent, Brace could benefit from day-specific emphasis (e.g., anti-extension vs anti-rotation vs lateral stability).
6. **Landing drills** — `_LANDING_DRILLS` (2 exercises) kept separate from Jumps. May need their own section or integration path.
