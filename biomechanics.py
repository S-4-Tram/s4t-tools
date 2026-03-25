"""
biomechanics.py
First constraint module for the S4T programme generator.

Returns biomechanics-derived constraint dicts based on joint action
prescriptions. Does not map to JOBS sections — exercises are matched
purely by their tagged traits.

Side-effect free. Register explicitly via:
    from biomechanics import BiomechanicsModule
    from logic import register_constraint_module
    register_constraint_module(BiomechanicsModule())
"""

BIOMECHANICS_CONSTRAINTS = [
    # Hip extension — Glute Max
    {"joint_action": "hip_extension", "rom": "short", "load": "heavy", "tempo": "slow"},

    # Hip flexion — outer range
    {"joint_action": "hip_flexion", "rom_region": "outer", "load": "low",
     "tempo": "explosive", "contraction_mode": "reactive"},
    # Hip flexion — inner range
    {"joint_action": "hip_flexion", "rom": "short", "rom_region": "inner",
     "load": "low", "tempo": "slow", "contraction_mode": "isometric"},

    # Hip adduction — Magnus / Gracilis
    {"joint_action": "hip_adduction", "rom": "mid", "load": "moderate", "tempo": "fast"},
    # Hip adduction — Brevis / Longus
    {"joint_action": "hip_adduction", "load": "bodyweight", "contraction_mode": "isometric"},

    # Hip abduction — Glute Med
    {"joint_action": "hip_abduction", "rom": "short", "load": "heavy", "tempo": "slow"},
    # Hip abduction — Min / Piriformis
    {"joint_action": "hip_abduction", "load": "low", "contraction_mode": "isometric"},

    # Knee extension — VMO / VLO
    {"joint_action": "knee_extension", "rom": "short", "load": "heavy", "tempo": "slow"},

    # Knee flexion — tendon
    {"joint_action": "knee_flexion", "load": "low", "tempo": "explosive",
     "contraction_mode": "reactive"},
    # Knee flexion — muscle
    {"joint_action": "knee_flexion", "rom": "short", "load": "moderate", "tempo": "slow"},

    # Plantar flexion — Soleus (isometric)
    {"joint_action": "plantar_flexion", "load": "heavy", "contraction_mode": "isometric"},
    # Plantar flexion — Soleus (SSC)
    {"joint_action": "plantar_flexion", "contraction_mode": "plyometric"},
    # Plantar flexion — Gastroc / Tib Post
    {"joint_action": "plantar_flexion", "contraction_mode": "slow_ssc"},
    # Plantar flexion — Extensor Group
    {"joint_action": "plantar_flexion", "contraction_mode": "fast_ssc"},

    # Dorsi flexion — Tib Anterior / Flexor
    {"joint_action": "dorsi_flexion", "rom": "short", "load": "low", "tempo": "fast"},

    # Eversion — Peroneus Longus
    {"joint_action": "eversion", "contraction_mode": "plyometric"},
]


class BiomechanicsModule:
    """Returns all biomechanics constraint dicts for any section.

    Does not filter by JOBS section — the scoring system matches
    exercises to constraints via their tagged traits.
    """

    def get_constraints(self, section_key, cfg):
        return BIOMECHANICS_CONSTRAINTS
