"""Libellés français des exercices Garmin (catégorie + nom exact)."""

CATEGORIES = {
    "BENCH_PRESS": "Développé couché", "SHOULDER_PRESS": "Développé épaules", "PUSH_UP": "Pompes",
    "PULL_UP": "Tirage vertical / tractions", "ROW": "Rowing", "LATERAL_RAISE": "Élévations latérales",
    "DEADLIFT": "Soulevé de terre", "SQUAT": "Squat", "LUNGE": "Fentes", "HIP_RAISE": "Pont / hip thrust",
    "CURL": "Curl biceps", "TRICEPS_EXTENSION": "Extension triceps", "FLYE": "Écarté", "SHRUG": "Haussements",
    "CALF_RAISE": "Mollets", "SIT_UP": "Abdominaux", "CRUNCH": "Crunch", "CORE": "Gainage", "PLANK": "Planche",
    "LEG_CURL": "Leg curl", "LEG_RAISE": "Relevés de jambes", "PLYO": "Pliométrie", "CARDIO": "Cardio",
    "BANDED_EXERCISES": "Exercice à l'élastique", "HIP_STABILITY": "Stabilité de hanche",
    "CHOP": "Rotation (chop)", "CARRY": "Porté", "OLYMPIC_LIFT": "Haltérophilie", "UNKNOWN": "Non identifié",
}

NAMES = {  # noms exacts utiles du programme
    "INCLINE_DUMBBELL_BENCH_PRESS": "Développé incliné aux haltères",
    "NEUTRAL_GRIP_DUMBBELL_BENCH_PRESS": "Développé couché haltères, prise neutre",
    "LAT_PULLDOWN": "Tirage vertical à la poulie", "PULL_UP": "Tractions", "NEUTRAL_GRIP_PULL_UP": "Tractions prise neutre",
    "TRICEPS_PRESSDOWN": "Triceps à la poulie", "DUMBBELL_HAMMER_CURL": "Curl marteau", "DUMBBELL_BICEPS_CURL": "Curl haltères",
    "FACE_PULL": "Face-pull", "RING_ROW": "Rowing aux anneaux", "SEATED_CABLE_ROW": "Rowing poulie assis",
    "BENT_OVER_ROW_WITH_DUMBELL": "Rowing haltère buste penché", "ROMANIAN_DEADLIFT": "Soulevé de terre roumain",
    "SINGLE_LEG_RDL_CIRCUIT": "RDL sur une jambe", "STRAIGHT_LEG_DEADLIFT": "Soulevé de terre jambes tendues",
    "BARBELL_DEADLIFT": "Soulevé de terre barre", "HAMSTRING_CURLS": "Leg curl (élastique / poulie)",
    "DUMBBELL_BULGARIAN_SPLIT_SQUAT": "Bulgarian split squat", "GOBLET_SQUAT": "Goblet squat",
    "HANGING_KNEE_RAISE": "Relevés de genoux suspendu", "DUMBBELL_FLYE": "Écarté haltères",
    "INCLINE_DUMBBELL_FLYE": "Écarté incliné haltères", "UPRIGHT_ROW": "Tirage menton", "BENCH_DIP": "Dips sur banc",
    "HAND_RELEASE_PUSH_UP": "Pompes mains décollées", "GLUTE_BRIDGE": "Pont fessier", "KETTLEBELL_SWING": "Swing kettlebell",
    "BOX_JUMP": "Box jump", "JUMP_ROPE": "Corde à sauter", "CABLE_CORE_PRESS": "Pallof press",
}


def label(category, name):
    if name and name in NAMES:
        return NAMES[name]
    cat = CATEGORIES.get(category or "UNKNOWN", (category or "Non identifié").replace("_", " ").capitalize())
    if name:
        return f"{cat} ({name.replace('_', ' ').lower()})"
    return cat


def confirmed(probability, wkt_step, category=None):
    """Série saisie ou confirmée (entraînement programmé ou corrigée dans Garmin Connect).
    Une série « UNKNOWN » n'est jamais confirmée : la montre n'a pas reconnu l'exercice."""
    if category in (None, "UNKNOWN"):
        return False
    return wkt_step is not None or (probability or 0) >= 99
