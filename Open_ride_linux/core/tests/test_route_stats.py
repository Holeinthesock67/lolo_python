"""Fiches des parcours (lot O15) : fiche calculée, fiche saisie, tri et filtres du catalogue."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from openride_core import catalog, route_stats as rs
from openride_core.catalog import RouteEntry


def route_from(alt: list[float], ds: float = 10.0) -> dict:
    n = len(alt)
    return {"n": n, "ds_m": ds, "length_m": (n - 1) * ds, "alt_m": alt}


def col_then_flat() -> dict:
    """Montée de 10 km à 7 % puis 5 km de plat (critère d'acceptation 2 du cahier O15)."""
    climb = [100.0 + 0.07 * i * 10.0 for i in range(1001)]
    return route_from(climb + [climb[-1]] * 500)


def test_col_then_flat_sheet() -> None:
    st = rs.compute_stats(col_then_flat())
    assert st["distance_m"] == pytest.approx(15000.0)
    assert st["gain_m"] == pytest.approx(700.0, abs=1.0)
    assert st["loss_m"] == pytest.approx(0.0, abs=1.0)
    assert (st["alt_min_m"], st["alt_max_m"]) == (pytest.approx(100.0), pytest.approx(800.0))
    assert st["max_grade_pct"] == pytest.approx(7.0, abs=0.1)
    main = st["main_climb"]
    assert st["climbs"] == 1
    assert main["start_m"] == pytest.approx(0.0)
    assert main["length_m"] == pytest.approx(10000.0, abs=10.0)
    assert main["gain_m"] == pytest.approx(700.0, abs=1.0)
    assert main["avg_grade_pct"] == pytest.approx(7.0, abs=0.05)
    assert main["category"] == "1"                     # 10 000 m × 7 % = 70 000
    assert st["difficulty"] == 4
    # 10 km à 7 % à 200 W pour 84 kg : environ 11 km/h (55 min) ; puis 5 km de plat vers 33 km/h.
    assert 3500 <= st["duration_200w_s"] <= 4000
    assert st["durations_s"]["200"] == st["duration_200w_s"]


def test_noise_is_not_counted_as_climbing() -> None:
    rng = random.Random(7)
    st = rs.compute_stats(route_from([200.0 + rng.uniform(-0.4, 0.4) for _ in range(2001)]))
    assert st["gain_m"] < 1.0 and st["climbs"] == 0 and st["main_climb"] is None
    assert st["difficulty"] == 1


def test_max_grade_uses_100_m_window() -> None:
    alt = [0.0] * 200 + [0.0 + 1.5 * i for i in range(1, 11)] + [15.0] * 200   # 15 m sur 100 m
    assert rs.compute_stats(route_from(alt))["max_grade_pct"] == pytest.approx(15.0, abs=0.1)


def test_descent_and_two_climbs_main_is_biggest() -> None:
    up1 = [100.0 + 0.05 * i * 10 for i in range(201)]           # 2 km à 5 % : 100 m
    down = [up1[-1] - 0.05 * i * 10 for i in range(1, 201)]      # redescente de 100 m
    up2 = [down[-1] + 0.08 * i * 10 for i in range(1, 401)]      # 4 km à 8 % : 320 m
    st = rs.compute_stats(route_from(up1 + down + up2))
    assert st["climbs"] == 2
    assert st["main_climb"]["gain_m"] == pytest.approx(320.0, abs=1.0)
    assert st["main_climb"]["start_m"] == pytest.approx(4000.0, abs=10.0)
    assert st["main_climb"]["category"] == "2"                  # 4 000 × 8 = 32 000
    assert st["loss_m"] == pytest.approx(100.0, abs=1.0)


@pytest.mark.parametrize("length,grade,expected", [
    (1000, 5, None), (2000, 4, "4"), (3000, 6, "3"), (5000, 7, "2"), (10000, 7, "1"), (12000, 7, "HC")])
def test_category_scale(length, grade, expected) -> None:
    assert rs.category(length, grade) == expected


def test_duration_interpolation_and_order() -> None:
    st = rs.compute_stats(col_then_flat())
    assert rs.duration_at(st, 250) < rs.duration_at(st, 200) < rs.duration_at(st, 150)
    mid = rs.duration_at(st, 212.5)
    assert rs.duration_at(st, 225) < mid < rs.duration_at(st, 200)
    assert rs.duration_at(st, 50) == st["durations_s"]["100"]    # bornée hors du tableau
    assert rs.duration_at(None, 200) is None


def test_library_sheet(tmp_path: Path) -> None:
    side = tmp_path / "col.toml"
    side.write_text('name = "Col d\'essai"\nregion = "Vosges du Nord"\ntags = ["Col", "classique", "col"]\n'
                    'credits = "trace synthétique"\n', encoding="utf-8")
    assert rs.load_library(side) == {"name": "Col d'essai", "region": "Vosges du Nord",
                                     "tags": ["classique", "col"], "credits": "trace synthétique"}


@pytest.mark.parametrize("text,needle", [
    ('region = "45.123, 6.456"', "coordonnées"),
    ('region = "45°07 N"', "coordonnées"),
    ('tags = ["col", "pas bon !"]', "étiquette invalide"),
    ('tags = "col"', "liste"),
    ('auteur = "x"', "inconnue"),
    ('name = ""', "non vide"),
    ('name = "x', "TOML invalide"),
])
def test_library_sheet_refused(tmp_path: Path, text: str, needle: str) -> None:
    side = tmp_path / "col.toml"
    side.write_text(text + "\n", encoding="utf-8")
    with pytest.raises(rs.LibraryError, match=needle):
        rs.load_library(side)


def entry(rid: str, km: float | None, gain: float | None = None, tags=(), status="ready",
          region: str | None = None) -> RouteEntry:
    st = None
    if km is not None:
        alt = [100.0 + (gain or 0.0) * i / 100 for i in range(101)]
        st = rs.compute_stats(route_from(alt, ds=km * 10.0))
    lib = {"tags": sorted(tags)} if tags else None
    if region:
        lib = {**(lib or {}), "region": region}
    return RouteEntry(rid, rid, status, km * 1000 if km else None, "open", False, None, stats=st, library=lib)


def test_query_sort_and_filters() -> None:
    entries = [entry("plat", 30, 0, tags=["plat"]), entry("petit-col", 12, 400, tags=["col"], region="Vosges"),
               entry("grand-col", 25, 1500, tags=["col", "classique"]), entry("nouveau", None, status="to_compile",
                                                                              tags=["col"])]
    ids = lambda es: [e.id for e in es]   # noqa: E731
    assert ids(catalog.query(entries, sort="deniv")) == ["plat", "petit-col", "grand-col", "nouveau"]
    assert ids(catalog.query(entries, sort="deniv", reverse=True)) == ["grand-col", "petit-col", "plat", "nouveau"]
    assert ids(catalog.query(entries, sort="deniv", filters={"tag": "col"})) == ["petit-col", "grand-col", "nouveau"]
    assert ids(catalog.query(entries, filters={"min_km": 10, "max_km": 26})) == ["petit-col", "grand-col"]
    assert ids(catalog.query(entries, filters={"region": "vosges"})) == ["petit-col"]
    assert ids(catalog.query(entries, filters={"status": "to_compile"})) == ["nouveau"]
    assert ids(catalog.query(entries, filters={"max_difficulty": 3})) == ["plat", "petit-col"]
    assert ids(catalog.query(entries, sort="duree")) == ["petit-col", "plat", "grand-col", "nouveau"]
    with pytest.raises(ValueError):
        catalog.query(entries, sort="inconnu")


def write_world(root: Path, rid: str, route: dict, manifest_extra: dict | None = None) -> Path:
    wdir = root / f"{rid}.world"
    wdir.mkdir(parents=True)
    route = {**route, "type": "open"}
    n = route["n"]
    for key in ("lat", "lon", "x", "z", "grade_pct", "heading_deg"):
        route.setdefault(key, [0.0] * n)
    route["z"] = [-i * route["ds_m"] for i in range(n)]
    (wdir / "route.json").write_text(json.dumps(route), encoding="utf-8")
    manifest = {"format": "openride-world", "format_version": "1.1", "name": rid,
                "origin": {"lat": 45.0, "lon": 6.0, "alt_m": route["alt_m"][0], "utm_zone": "32T"},
                "projection": "utm",
                "route": {"present": True, "version": "1.0", "file": "route.json", "length_m": route["length_m"],
                          "ds_m": route["ds_m"], "n": n, "type": "open"},
                "layers": {"terrain": {"present": False}}, **(manifest_extra or {})}
    (wdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return wdir


def test_old_world_gets_sheet_recomputed(tmp_path: Path, caplog) -> None:
    write_world(tmp_path / "routes", "ancien", col_then_flat())
    entries = catalog.list_routes(tmp_path / "routes", tmp_path / "GPX")
    old = next(e for e in entries if e.id == "ancien")
    assert old.status == "ready"
    assert old.stats == rs.compute_stats(col_then_flat())
    assert not [r for r in caplog.records if r.levelname == "WARNING"]


def test_manifest_sheet_and_library_are_read(tmp_path: Path) -> None:
    stored = {**rs.compute_stats(col_then_flat()), "gain_m": 1234.0}
    write_world(tmp_path / "routes", "neuf", col_then_flat(),
                {"stats": stored, "library": {"name": "Neuf", "tags": ["col"]}})
    e = next(e for e in catalog.list_routes(tmp_path / "routes", tmp_path / "GPX") if e.id == "neuf")
    assert e.stats["gain_m"] == 1234.0 and e.library == {"name": "Neuf", "tags": ["col"]}
    write_world(tmp_path / "r2", "vieux", col_then_flat(), {"stats": {**stored, "version": 0}})
    e = next(e for e in catalog.list_routes(tmp_path / "r2", tmp_path / "GPX") if e.id == "vieux")
    assert e.stats["gain_m"] == pytest.approx(700.0, abs=1.0)    # version ancienne : recalculée


def test_pack_subfolder_tracks_and_sidecars(tmp_path: Path, caplog) -> None:
    gpx = tmp_path / "GPX"
    (gpx / "mon-pack").mkdir(parents=True)
    (gpx / "mon-pack" / "Col A.gpx").write_text("<gpx/>", encoding="utf-8")
    (gpx / "mon-pack" / "Col A.toml").write_text('tags = ["col"]\n', encoding="utf-8")
    (gpx / "mon-pack" / "pack.toml").write_text('name = "Mon pack"\n', encoding="utf-8")
    (gpx / "plat.gpx").write_text("<gpx/>", encoding="utf-8")
    (gpx / "plat.toml").write_text('region = "1.234, 5.678"\n', encoding="utf-8")   # refusée
    (gpx / ".cache").mkdir()
    (gpx / ".cache" / "x.gpx").write_text("<gpx/>", encoding="utf-8")
    entries = {e.id: e for e in catalog.list_routes(tmp_path / "routes", gpx)}
    assert set(entries) == {"demo", "col-a", "plat"}
    assert entries["col-a"].status == "to_compile" and entries["col-a"].library == {"tags": ["col"]}
    assert entries["plat"].library is None
    assert any("fiche de parcours ignorée" in r.getMessage() for r in caplog.records)
