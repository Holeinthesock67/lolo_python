"""Tour visuel guidé (lot X21) : points automatiques sur un parcours fabriqué, liste de points, planche.
Sans Godot : seules les fonctions pures de `engine/tests/tour_visuel.py` sont appelées."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ENGINE_TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
sys.path.insert(0, str(ENGINE_TESTS))

import tour_visuel as tv  # noqa: E402

DS = 10.0


def _write_world(root: Path, alt: list[float], biome: bool = False) -> Path:
    """Parcours droit vers −z : x = 0, z = −s ; couches bâtiments, végétation et eau autour."""
    w = root / "fab.world"
    n = len(alt)
    route = {"version": "1.0", "ds_m": DS, "n": n, "length_m": (n - 1) * DS, "type": "open",
             "x": [0.0] * n, "z": [-i * DS for i in range(n)], "alt_m": alt, "grade_pct": [0.0] * n}
    layers = {"biome": {"present": biome}}
    (w / "buildings").mkdir(parents=True)
    (w / "vegetation").mkdir()
    (w / "water").mkdir()
    (w / "manifest.json").write_text(json.dumps({"name": "fab", "layers": layers}), encoding="utf-8")
    (w / "route.json").write_text(json.dumps(route), encoding="utf-8")

    def square(cx: float, cz: float, r: float = 5.0) -> list:
        return [[cx - r, cz - r], [cx + r, cz - r], [cx + r, cz + r], [cx - r, cz + r]]

    # Un hameau de 2 maisons à 1 000 m, un village de 6 à 4 000 m.
    houses = [square(20.0, -1000.0), square(-20.0, -1010.0)] + [square(25.0 + 12 * k, -4000.0 - 8 * k) for k in range(6)]
    (w / "buildings" / "chunk_0.json").write_text(json.dumps(
        {"buildings": [{"id": f"b{k}", "outer": o} for k, o in enumerate(houses)]}), encoding="utf-8")
    (w / "vegetation" / "chunk_0.json").write_text(json.dumps({"areas": [
        {"id": "w1", "kind": "wood", "outer": square(60.0, -2200.0, 30.0)},
        {"id": "m1", "kind": "meadow", "outer": square(10.0, -200.0, 30.0)}]}), encoding="utf-8")
    (w / "water" / "chunk_0.json").write_text(json.dumps({"lines": [
        {"id": "r1", "kind": "river", "points": [[120.0, -3300.0, 0.0], [90.0, -3400.0, 0.0]]}]}), encoding="utf-8")
    if biome:
        # Tuile proche (0, −1) : prairie au nord (z > −500), forêt de montagne au sud.
        weights_a = [255 if (j * 1000.0 / 16) - 1000.0 > -500.0 else 0 for j in range(17) for _ in range(17)]
        weights_b = [255 - v for v in weights_a]
        (w / "biome" / "near").mkdir(parents=True)
        (w / "biome" / "near" / "tile_0_-1.json").write_text(json.dumps(
            {"grid": 17, "biomes": ["temperate_plain", "mountain_forest"], "weights": [weights_a, weights_b]}),
            encoding="utf-8")
    return w


def _profile() -> list[float]:
    """0–1 500 m plat, 1 500–2 500 m à 5 %, 2 500–3 500 m à 10 %, puis plat jusqu'à 5 000 m."""
    alt, a = [], 100.0
    for i in range(501):
        s = i * DS
        alt.append(a)
        a += DS * (0.05 if 1500 <= s < 2500 else 0.10 if 2500 <= s < 3500 else 0.0)
    return alt


def test_auto_points_find_climbs_village_wood_water(tmp_path: Path) -> None:
    pts = tv.auto_points(tv.load_world(_write_world(tmp_path, _profile())))
    by_id = {p["id"]: p for p in pts}
    assert [p["s"] for p in pts] == sorted(p["s"] for p in pts)
    assert by_id["depart"]["s"] == 30.0 and by_id["arrivee"]["s"] == 4940.0
    assert 1600 <= by_id["montee_5"]["s"] <= 2400 and "5.0 %" in by_id["montee_5"]["label"]
    assert 2600 <= by_id["montee_10"]["s"] <= 3400 and "10.0 %" in by_id["montee_10"]["label"]
    assert "Plat" in by_id["depart"]["label"]   # plat dès le départ : point fusionné
    assert abs(by_id["village"]["s"] - 4020) <= 60 and "6 bâtiment(s)" in by_id["village"]["label"]
    assert abs(by_id["foret"]["s"] - 2200) <= 30
    assert 3290 <= by_id["eau"]["s"] <= 3410
    assert all(p["camera"] == "subjective" for p in pts)
    assert all(b["s"] - a["s"] >= tv.MIN_GAP_M for a, b in zip(pts, pts[1:]))


def test_flat_route_gets_no_invented_climb(tmp_path: Path) -> None:
    pts = tv.auto_points(tv.load_world(_write_world(tmp_path, [100.0] * 301)))
    ids = {p["id"] for p in pts}
    assert "montee_5" not in ids and "montee_10" not in ids


def test_close_points_are_merged_with_both_reasons(tmp_path: Path) -> None:
    pts = tv.auto_points(tv.load_world(_write_world(tmp_path, [100.0] * 301)))
    first = pts[0]
    assert first["id"] == "depart" and "Départ ; Plat" in first["label"]
    assert not any(p["id"] == "plat" for p in pts)


def test_biome_frontier_point(tmp_path: Path) -> None:
    pts = tv.auto_points(tv.load_world(_write_world(tmp_path, _profile(), biome=True)))
    frontier = [p for p in pts if "Frontière de biome" in p["label"]]
    assert len(frontier) == 1 and abs(frontier[0]["s"] - 500) <= 60
    assert "temperate_plain → mountain_forest" in frontier[0]["label"]


def test_demo_tour_is_valid() -> None:
    doc = json.loads((tv.TOURS_DIR / "demo.json").read_text(encoding="utf-8"))
    pts = tv.validate_tour(doc, "demo.json")
    assert {p["camera"] for p in pts} == set(tv.CAMERAS)
    assert any(p.get("weather", {}).get("kind") == "rain" for p in pts)


@pytest.mark.parametrize("doc, msg", [
    ({"points": [{"s": -1}]}, "distance"),
    ({"points": [{"s": 10, "camera": "drone"}]}, "camera"),
    ({"points": [{"s": 10, "heure": 18}]}, "inconnue"),
    ({"points": [{"s": 10, "weather": "pluie"}]}, "weather"),
    ({"pts": []}, "points"),
])
def test_bad_tour_is_named(doc: dict, msg: str) -> None:
    with pytest.raises(tv.TourError, match=msg):
        tv.validate_tour(doc)


def test_board_has_one_card_per_point_and_keeps_verdicts(tmp_path: Path) -> None:
    pts = [{"id": "village", "s": 4020.0, "camera": "subjective", "label": "Village", "file": "01_village.png",
            "mesures": {"triangles": 500000, "draw_calls": 107, "pending": 0, "particles": 0}},
           {"id": "pluie", "s": 2200.0, "camera": "side", "label": "Pluie", "weather": {"kind": "rain"},
            "file": "", "mesures": {}}]
    page = tv.write_board(tmp_path, "Tour visuel : fab (low)", pts).read_text(encoding="utf-8")
    assert page.count('class="card"') == 2
    assert '<img src="01_village.png"' in page and "pas de capture" in page
    assert "triangles 500000 · appels de dessin 107" in page and "tuiles en attente" not in page
    assert page.count('type="radio"') == 6 and "localStorage" in page and "Exporter en JSON" in page
    assert "météo {&quot;kind&quot;: &quot;rain&quot;}" in page
