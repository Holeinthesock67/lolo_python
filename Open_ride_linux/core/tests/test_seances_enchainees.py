"""Banc des séances enchaînées (enquête 7bi) : pas et mémoire du core stables d'une séance à l'autre."""

import logging
import threading
import time

from openride_core.tools import seances_enchainees as se


def test_chained_sessions_stay_flat():
    """Sous pytest, d'autres fils allouent et la capture des logs garde chaque ligne INFO du core : seule la
    mémoire gardée par OpenRide compte (en CI, le banc échouait sur ces deux mémoires étrangères)."""
    kept: list[logging.LogRecord] = []
    junk: list[bytes] = []
    stop = threading.Event()

    class Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            kept.append(record)

    def hog() -> None:
        while not stop.is_set():
            junk.append(bytes(10_000))
            time.sleep(0.01)

    root = logging.getLogger()
    handler, level = Keep(), root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    t = threading.Thread(target=hog, daemon=True)
    t.start()
    try:
        out = se.run(sessions=3, minutes=0.1, n_bots=1, memory=True)
    finally:
        stop.set()
        t.join()
        root.removeHandler(handler)
        root.setLevel(level)
    assert len(kept) > 10 and len(junk) > 20
    assert [r["seance"] for r in out["rows"]] == [1, 2, 3]
    assert all(r["fenetre_3s"] <= se.WINDOW_MAX and r["etat"] == "FINISHED" for r in out["rows"])
    assert all(c["ok"] for c in out["checks"]), out["checks"]
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
