"""Banc des séances enchaînées (enquête 7bi) : pas et mémoire du core stables d'une séance à l'autre."""

from openride_core.tools import seances_enchainees as se


def test_chained_sessions_stay_flat():
    out = se.run(sessions=3, minutes=0.25, n_bots=1, memory=True)
    assert [r["seance"] for r in out["rows"]] == [1, 2, 3]
    assert all(r["fenetre_3s"] <= se.WINDOW_MAX and r["etat"] == "FINISHED" for r in out["rows"])
    assert all(c["ok"] for c in out["checks"]), out["checks"]
    assert "ÉCHEC" not in se.format_text(out)


def test_checks_flag_a_growing_step_and_window():
    rows = [{"seance": 1, "pas_moyen_ms": 0.1, "pas_p99_ms": 0.2, "fenetre_3s": 150, "etat": "FINISHED"},
            {"seance": 2, "pas_moyen_ms": 1.0, "pas_p99_ms": 2.0, "fenetre_3s": 30150, "etat": "FINISHED"}]
    ok = [c["ok"] for c in se.checks(rows, 10.0)]
    assert ok == [False, False, True]


def test_main_rejects_a_single_session(capsys):
    assert se.main(["--seances", "1"]) == 2


def test_memory_ignores_other_threads():
    """Sous pytest, d'autres fils allouent pendant le banc : seule la mémoire gardée par OpenRide compte."""
    import threading
    import time

    junk: list[bytes] = []
    stop = threading.Event()

    def hog() -> None:
        while not stop.is_set():
            junk.append(bytes(10_000))
            time.sleep(0.001)

    t = threading.Thread(target=hog, daemon=True)
    t.start()
    try:
        out = se.run(sessions=2, minutes=0.25, n_bots=0, memory=True)
    finally:
        stop.set()
        t.join()
    assert len(junk) > 100
    assert all(c["ok"] for c in out["checks"]), out["checks"]
