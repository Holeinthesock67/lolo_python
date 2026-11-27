"""Trames réelles du Cyber-Rogue partagées avec les tests de l'engine (revue de code vague 3, lot EC3).

Le fichier `engine/tests/data/rogue_trames_core.json` doit être celui que le core produit aujourd'hui : un
changement du core qui modifie ce qu'il envoie le rend périmé, et les tests de l'engine qui le lisent ne
regardent plus la réalité. Les faits sur lesquels l'engine s'appuie sont aussi écrits ici, en clair.
"""

from __future__ import annotations

import json

import pytest

from openride_core.tools import rogue_trames as tool


@pytest.fixture(scope="module")
def stored() -> dict:
    return json.loads(tool.DEFAULT_OUT.read_text("utf-8"))


@pytest.mark.slow
def test_stored_frames_are_what_the_core_sends_today(stored):
    assert tool.dumps(tool.build()) == tool.dumps(stored), \
        "trames périmées : python -m openride_core.tools.rogue_trames (depuis core/)"


def test_facts_the_engine_relies_on(stored):
    f = {k: m.get("rogue") for k, m in stored["frames"].items()}
    # E10-02 : jamais de longueur de parcours en mode Rogue ; la longueur de la salle vient du message `room`.
    assert all(m["route_length_m"] is None for m in stored["frames"].values())
    assert stored["room"][0]["length_m"] > 0 and stored["room"][0]["room_id"] == f["room"]["room_id"]
    # E10-04, E10-05 : hors salle, écart au Firewall nul, position nulle, pas d'ennemi.
    for k in ("warmup", "corridor", "cooldown", "results"):
        assert f[k]["firewall_gap_m"] == 0.0 and f[k]["s_room"] == 0.0 and f[k]["archetype"] is None, k
    assert f["corridor"]["room_id"] == f["room"]["room_id"]          # couloir : salle finie gardée
    # E10-06 : récupération après contact, écart figé à 0, position remise à 0.
    assert f["recovery_start"]["phase"] == "RECOVERY" and "defeat" in f["recovery_start"]["events"]
    assert f["recovery"]["firewall_gap_m"] == 0.0 and f["recovery"]["s_room"] == 0.0
    # E10-09 : la trame de fin de salle n'a plus d'ennemi et porte déjà la phase suivante.
    assert "room_won" in f["room_end"]["events"] and f["room_end"]["archetype"] is None
    assert f["room_end"]["phase"] == "CORRIDOR" and f["room_end_prev"]["archetype"] is not None
    # E10-03 : pas de bilan pendant RESULTS ; la fin du boss se lit dans la trame d'avant (phase 3).
    assert stored["frames"]["results"]["summary"] is None and stored["frames"]["victory_results"]["summary"] is None
    assert stored["frames"]["finished"]["summary"]["rogue"]["result"] == "defeat"
    assert f["victory_boss_end_prev"]["boss_phase"] == 3 and "room_won" in f["victory_boss_end"]["events"]
    assert "room_won" not in f["boss_end"]["events"]
