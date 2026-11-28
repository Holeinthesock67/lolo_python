"""Lot IM0 : filet « à l'identique » des modes de jeu (cadrage de l'interface des modes du 22/11, §4 et §5.2).

Chaque séance scriptée de `identique_scenarios.py` (session libre, Course, Grand Prix, Dernier survivant, WTF,
piste, Cyber-Rogue, refus, fins forcées) est rejouée et ses relevés (journal, trames, bilan, consignes du trainer,
messages et fichiers) comparés, empreinte par empreinte, à la référence `core/tests/data/modes_identique.json`.

Une PR de la série IM (refonte de `session.py`) ne doit changer **aucune** empreinte. Une PR qui change exprès un
comportement de mode recalcule la référence et le dit dans sa description :

    python3 scripts/modes_identique.py --maj                 # depuis Open_ride_linux/, référence réécrite
    python3 scripts/modes_identique.py --releve DOSSIER     # relevés complets en JSON, pour comparer deux versions
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import identique  # noqa: E402
from identique_scenarios import SCENARIOS  # noqa: E402

REFERENCE = identique.load_reference()
PORT0 = 7600
# Référence calculée en Python 3.14 (PC et CI) ; 3.13 donne les mêmes octets. En 3.11, l'instantané `pickle` du
# Cyber-Rogue et un arrondi d'une trame changent : la comparaison y est sautée (le reste de la suite y tourne).
SAME_BYTES = sys.version_info[:2] >= identique.PYTHON_MIN


def test_reference_covers_every_scenario() -> None:
    assert sorted(REFERENCE.get("scenarios", {})) == sorted(SCENARIOS), \
        "référence à recalculer : python3 scripts/modes_identique.py --maj"
    for name, fp in REFERENCE["scenarios"].items():
        assert sorted(fp) == sorted(identique.RELEVES), name


@pytest.mark.slow
@pytest.mark.skipif(not SAME_BYTES, reason="empreintes de référence calculées en Python 3.13 et plus (3.14 en CI)")
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_identique(name: str, tmp_path: Path) -> None:
    root = tmp_path / "banc"
    rel = identique.play(name, root, port=PORT0 + 40 * sorted(SCENARIOS).index(name))
    got = identique.fingerprint(rel, root)
    want = REFERENCE.get("scenarios", {}).get(name)
    if got != want:
        dump = tmp_path / f"{name}.json"
        dump.write_bytes(identique.canonical(rel, root))
        changed = [k for k in identique.RELEVES if not want or got[k] != want.get(k)]
        pytest.fail(f"« {name} » n'est plus à l'identique : {', '.join(changed)} ; relevé complet dans {dump}.\n"
                    "Changement voulu : python3 scripts/modes_identique.py --maj, et le dire dans la PR.")


def test_scenarios_are_meaningful(tmp_path: Path) -> None:
    """Garde du filet lui-même (rapide) : la session libre roule, le journal et le trainer sont bien relevés."""
    root = tmp_path / "banc"
    rel = identique.play("refus", root, port=PORT0 - 40)
    errors = [m for m in rel["messages"]["engine"] if m[1] == "error"]
    texts = {m[3] for m in errors}
    assert "Le mode WTF se joue en SIM seulement." in texts
    assert "Pas de demi-tour pendant une épreuve de piste." in texts
    assert "Le Dernier survivant compose lui-même ses adversaires." in texts
    assert rel["journal"] and rel["trainer"] and rel["trames"]
    assert str(root) not in identique.canonical(rel, root).decode("utf-8")
