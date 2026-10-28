"""Cohérence entre les événements du core du Cyber-Rogue et les sons de l'engine (lot R18) :
chaque événement émis par le core a un son, sauf ceux de la liste explicite ci-dessous."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "core/src/openride_core/rogue"
MODEL = (ROOT / "engine/scripts/rogue/rogue_sound_model.gd").read_text()
SYNTH = (ROOT / "engine/scripts/rogue/rogue_sound_synth.gd").read_text()

# Événements sans son propre : le contact du Firewall est porté par le ronflement en boucle.
SANS_SON = {"firewall_contact"}


def _core_events() -> set[str]:
    found: set[str] = set()
    for path in SRC.glob("*.py"):
        found |= set(re.findall(r'events?\.(?:append|add)\(\s*"([a-z_]+)"', path.read_text()))
    return found


def _event_sounds() -> dict[str, str]:
    block = MODEL.split("const EVENT_SOUNDS := {", 1)[1].split("}", 1)[0]
    return dict(re.findall(r'"([a-z_]+)":\s*"([a-z_]+)"', block))


def test_every_core_event_has_a_sound():
    sounds = _event_sounds()
    missing = sorted(_core_events() - SANS_SON - set(sounds))
    assert missing == [], f"événements du core sans son : {missing}"


def test_every_event_sound_is_synthesized():
    for event, sound in _event_sounds().items():
        assert f'"{sound}"' in SYNTH, f"son {sound} (événement {event}) absent de la synthèse"
