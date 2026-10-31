"""Banc des séances enchaînées (enquête 7bi) : pas et mémoire du core stables d'une séance à l'autre."""

import json
import subprocess
import sys

from openride_core.tools import seances_enchainees as se


def test_chained_sessions_stay_flat():
    """Le banc tourne dans son propre processus, comme sur le PC : sous pytest, d'autres tests laissent des
    gestionnaires de logs et des fils qui allouent, ce qui faussait la mémoire mesurée en CI."""
    r = subprocess.run([sys.executable, "-m", "openride_core.tools.seances_enchainees", "--seances", "3",
                        "--minutes", "0.1", "--bots", "1", "--json"], capture_output=True, text=True, timeout=600)
    out = json.loads(r.stdout)
    assert r.returncode == 0, out["checks"]
    assert [x["seance"] for x in out["rows"]] == [1, 2, 3]
    assert all(x["fenetre_3s"] <= se.WINDOW_MAX and x["etat"] == "FINISHED" for x in out["rows"])
    assert "ÉCHEC" not in se.format_text(out)


def test_checks_flag_a_growing_step_window_and_memory():
    rows = [{"seance": 1, "pas_moyen_ms": 0.1, "pas_p99_ms": 0.2, "fenetre_3s": 150, "etat": "FINISHED",
             "memoire_mo": 2.0},
            {"seance": 2, "pas_moyen_ms": 1.0, "pas_p99_ms": 2.0, "fenetre_3s": 30150, "etat": "FINISHED",
             "memoire_mo": 5.4}]
    assert [c["ok"] for c in se.checks(rows, 10.0)] == [False, False, True, False]
    rows[1].update(pas_moyen_ms=0.1, fenetre_3s=150, memoire_mo=2.004)
    assert all(c["ok"] for c in se.checks(rows, 0.1))


def test_main_rejects_a_single_session():
    assert se.main(["--seances", "1"]) == 2
