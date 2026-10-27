"""Route engagée du monde ouvert (lot W9) : parties de 1 km, révisions, lecture sans attente."""

import json
import threading
import time
from pathlib import Path

import pytest

from openride_core.demo_world import build_route
from openride_core.live_route import LiveRoute, assemble, read_junctions
from openride_core.route import Route, WorldError

COLUMNS = ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg")


def split(route: dict, part_m: float = 1000.0) -> list[dict]:
    """Découpe une route en parties de 1 km au bord partagé (même règle que `split_parts` du générateur)."""
    ds = route["ds_m"]
    s = [i * ds for i in range(route["n"] - 1)] + [route["length_m"]]
    parts = []
    k = 0
    while True:
        lo, hi = k * part_m, (k + 1) * part_m
        idx = [i for i, v in enumerate(s) if lo - 1e-6 <= v <= hi + 1e-6]
        if len(idx) < 2:
            break
        parts.append({"version": "1.0", "ds_m": ds, "n": len(idx), "length_m": s[idx[-1]] - s[idx[0]],
                      "type": "open", "s0_m": lo, **{c: [route[c][i] for i in idx] for c in COLUMNS}})
        if s[idx[-1]] >= s[-1] - 1e-6:
            break
        k += 1
    return parts


def write_session(folder: Path, parts: list[dict], revision: int = 1, junctions: list | None = None) -> None:
    (folder / "route").mkdir(parents=True, exist_ok=True)
    for k, p in enumerate(parts):
        (folder / "route" / f"part_{k}.json").write_text(json.dumps(p), encoding="utf-8")
    (folder / "junctions.json").write_text(json.dumps(
        {"version": "1.0", "revision": revision, "junctions": junctions or []}), encoding="utf-8")
    (folder / "live.json").write_text(json.dumps(
        {"version": "1.0", "revision": revision,
         "route": {"parts": len(parts), "length_m": sum(p["length_m"] for p in parts), "changed_from_part": 0},
         "tiles": {"near": [], "far": []}, "layer_tiles": [], "status": "ok"}), encoding="utf-8")


def test_parts_assemble_to_the_same_route_as_the_whole(tmp_path):
    whole = build_route(3456.0)
    reference = Route(whole)
    write_session(tmp_path, split(whole))
    live = LiveRoute(tmp_path)
    live.load()
    assert live.length_m == pytest.approx(3456.0, abs=1e-9) and not live.is_loop
    for s in [0.0, 5.0, 999.0, 1000.0, 1001.3, 1999.99, 2000.0, 3000.0, 3455.0, 3456.0, 5000.0, -3.0]:
        a, b = live.sample(s), reference.sample(s)
        for field in ("x", "y", "z", "lat", "lon", "alt_m", "grade_pct", "heading_deg"):
            assert getattr(a, field) == pytest.approx(getattr(b, field), abs=1e-9), (s, field)
        assert live.grade_at(s) == pytest.approx(reference.grade_at(s), abs=1e-9)


def test_beyond_known_route_keeps_last_grade_and_reports_missing_road(tmp_path):
    whole = build_route(2500.0)
    write_session(tmp_path, split(whole))
    live = LiveRoute(tmp_path)
    live.load()
    last = Route(whole).grade_pct[-1]
    assert live.grade_at(2600.0) == pytest.approx(last)
    assert live.known_ahead_m(2000.0) == pytest.approx(500.0)
    assert live.known_ahead_m(2600.0) == pytest.approx(-100.0)    # négatif : route manquante
    assert live.wrap(9999.0) == pytest.approx(2500.0)


def test_base_shifts_the_route_after_a_restart(tmp_path):
    whole = build_route(2000.0)
    write_session(tmp_path, split(whole))
    live = LiveRoute(tmp_path, base_m=700.0)
    live.load()
    ref = Route(whole)
    assert live.length_m == pytest.approx(2700.0)
    assert live.grade_at(700.0 + 300.0) == pytest.approx(ref.grade_at(300.0), abs=1e-9)
    assert live.sample(700.0 + 1200.0).x == pytest.approx(ref.sample(1200.0).x, abs=1e-9)
    assert live.known_ahead_m(2000.0) == pytest.approx(700.0)


def test_revision_extends_and_rewrites_from_the_changed_part(tmp_path):
    whole = build_route(3000.0)
    parts = split(whole)
    write_session(tmp_path, parts[:2], revision=1)
    live = LiveRoute(tmp_path)
    live.load()
    assert live.length_m == pytest.approx(2000.0) and live.revision == 1
    # Révision 2 : la partie 1 est réécrite (autre branche) et une partie s'ajoute.
    other = build_route(3000.0, origin_alt=900.0)
    new_parts = parts[:1] + split(other)[1:]
    write_session(tmp_path, new_parts, revision=2)
    live.apply_revision(2, changed_from_part=1)
    assert live.wait(5.0) and live.revision == 2
    assert live.length_m == pytest.approx(3000.0)
    a = live.sample(500.0)                      # partie 0 : inchangée
    assert a.alt_m == pytest.approx(Route(whole).sample(500.0).alt_m, abs=1e-9)
    b = live.sample(1500.0)                     # partie 1 : réécrite
    assert b.alt_m == pytest.approx(Route(other).sample(1500.0).alt_m, abs=1e-9)


def test_requests_during_loading_are_coalesced(tmp_path):
    whole = build_route(4000.0)
    parts = split(whole)
    write_session(tmp_path, parts[:2], revision=1)
    live = LiveRoute(tmp_path)
    live.load()
    write_session(tmp_path, parts[:3], revision=2)
    live.apply_revision(2, 2)
    write_session(tmp_path, parts[:4], revision=3)
    live.apply_revision(3, 3)
    assert live.wait(5.0)
    for _ in range(100):               # la dernière demande est traitée par le même fil, peu après
        if live.revision == 3:
            break
        time.sleep(0.02)
    assert live.revision == 3 and live.length_m == pytest.approx(4000.0)


def test_broken_revision_keeps_the_previous_route(tmp_path):
    whole = build_route(2000.0)
    write_session(tmp_path, split(whole), revision=1)
    errors = []
    live = LiveRoute(tmp_path, on_error=errors.append)
    live.load()
    (tmp_path / "route" / "part_1.json").write_text("{pas du json", encoding="utf-8")
    live.apply_revision(2, 1)
    assert live.wait(5.0)
    assert live.revision == 1 and live.length_m == pytest.approx(2000.0) and errors
    with pytest.raises(WorldError):
        LiveRoute(tmp_path / "absent").load()


def test_junctions_follow_the_loaded_revision(tmp_path):
    whole = build_route(2000.0)
    j = {"id": "j1", "s_m": 900.0, "lock_s_m": 870.0, "default": 0, "chosen": 0, "locked": False, "branches": []}
    write_session(tmp_path, split(whole), junctions=[j])
    live = LiveRoute(tmp_path)
    assert live.junctions == []
    live.load()
    assert [x["id"] for x in live.junctions] == ["j1"]
    assert read_junctions(tmp_path / "absent") == []


def test_reading_never_waits_for_a_revision(tmp_path):
    """Critère 2 : la boucle à 50 Hz ne lit pas le disque ; un chargement en cours ne la retient pas (< 1 ms)."""
    whole = build_route(20_000.0)
    parts = split(whole)
    write_session(tmp_path, parts[:10], revision=1)
    live = LiveRoute(tmp_path)
    live.load()
    worst = 0.0
    for attempt in range(3):          # une machine chargée peut dépasser 1 ms une fois sur un pas isolé
        write_session(tmp_path, parts[:10 + attempt + 1], revision=2 + attempt)
        live.apply_revision(2 + attempt, 9 + attempt)
        worst = 0.0
        for i in range(1000):
            t0 = time.perf_counter()
            live.grade_at(i * 3.7)
            worst = max(worst, time.perf_counter() - t0)
        live.wait(5.0)
        if worst < 0.001:
            break
    assert worst < 0.001, f"lecture la plus lente : {worst * 1000:.2f} ms"
    assert live.revision >= 2


def test_swap_is_atomic_for_concurrent_readers(tmp_path):
    whole = build_route(6000.0)
    parts = split(whole)
    write_session(tmp_path, parts[:3], revision=1)
    live = LiveRoute(tmp_path)
    live.load()
    stop = threading.Event()
    bad = []

    def reader():
        while not stop.is_set():
            try:
                n = live.length_m
                live.sample(min(n, 2500.0))
                live.grade_at(100.0)
            except Exception as exc:  # noqa: BLE001
                bad.append(exc)

    t = threading.Thread(target=reader)
    t.start()
    for k in range(4, 7):
        write_session(tmp_path, parts[:k], revision=k)
        live.apply_revision(k, k - 1)
        live.wait(5.0)
    stop.set()
    t.join()
    assert not bad
