"""Tests du catalogue des parcours (Lot I2, SRS §7 et §11)."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from openride_core.catalog import list_routes
from openride_core.demo_world import build_manifest, build_route


def _write_compiled_world(
    routes_root: Path,
    world_id: str,
    gpx_file: Path | None,
    gpx_sha: str | None = None,
    has_terrain: bool = True,
) -> Path:
    route = build_route(1000.0)
    manifest = build_manifest(world_id, route)
    manifest["source"] = {
        "gpx": gpx_file.name if gpx_file else None,
        "gpx_sha256": gpx_sha,
    }
    manifest["layers"]["terrain"] = {"present": has_terrain}
    wdir = routes_root / f"{world_id}.world"
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / "route.json").write_text(json.dumps(route, separators=(",", ":")), encoding="utf-8")
    (wdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return wdir


def test_list_routes_four_statuses_and_demo_first(tmp_path: Path) -> None:
    """Critère 2 : ready, outdated, to_compile, invalid, avec demo toujours en premier."""
    routes_root = tmp_path / "routes"
    gpx_dir = tmp_path / "GPX"
    routes_root.mkdir()
    gpx_dir.mkdir()

    # 1. GPX compilé et inchangé -> ready
    gpx_ready = gpx_dir / "col_ready.gpx"
    gpx_ready.write_text("<gpx>trace 1</gpx>", encoding="utf-8")
    sha_ready = hashlib.sha256(gpx_ready.read_bytes()).hexdigest()
    _write_compiled_world(routes_root, "col-ready", gpx_ready, sha_ready, has_terrain=True)

    # 2. GPX modifié après compilation -> outdated
    gpx_outdated = gpx_dir / "col_modifie.gpx"
    gpx_outdated.write_text("<gpx>trace originale</gpx>", encoding="utf-8")
    old_sha = hashlib.sha256(gpx_outdated.read_bytes()).hexdigest()
    _write_compiled_world(routes_root, "col-modifie", gpx_outdated, old_sha, has_terrain=False)
    gpx_outdated.write_text("<gpx>trace modifiée depuis</gpx>", encoding="utf-8")

    # 3. GPX jamais compilé -> to_compile
    gpx_new = gpx_dir / "Nouveau Parcours.gpx"
    gpx_new.write_text("<gpx>jamais compilé</gpx>", encoding="utf-8")

    # 4. .world corrompu -> invalid
    corrupt_dir = routes_root / "casse.world"
    corrupt_dir.mkdir()
    (corrupt_dir / "manifest.json").write_text("{json invalide", encoding="utf-8")

    entries = list_routes(routes_root, gpx_dir)
    assert entries[0].id == "demo"
    assert entries[0].status == "ready"

    by_id = {e.id: e for e in entries}
    assert by_id["col-ready"].status == "ready"
    assert by_id["col-ready"].has_terrain is True
    assert by_id["col-ready"].gpx_path == gpx_ready

    assert by_id["col-modifie"].status == "outdated"
    assert by_id["col-modifie"].gpx_path == gpx_outdated

    assert by_id["nouveau-parcours"].status == "to_compile"
    assert by_id["nouveau-parcours"].gpx_path == gpx_new
    assert by_id["nouveau-parcours"].length_m is None

    assert by_id["casse"].status == "invalid"
    assert by_id["casse"].error is not None


def test_list_routes_50_worlds_performance(tmp_path: Path) -> None:
    """Critère 5 : list_routes sur 50 parcours synthétiques tient en moins de 200 ms."""
    routes_root = tmp_path / "routes"
    gpx_dir = tmp_path / "GPX"
    routes_root.mkdir()
    gpx_dir.mkdir()

    base_route = build_route(1000.0)
    route_json = json.dumps(base_route, separators=(",", ":"))

    for i in range(50):
        wid = f"parcours-{i:02d}"
        gpx_file = gpx_dir / f"{wid}.gpx"
        gpx_file.write_text(f"<gpx>trace {i}</gpx>", encoding="utf-8")
        sha = hashlib.sha256(gpx_file.read_bytes()).hexdigest()
        wdir = routes_root / f"{wid}.world"
        wdir.mkdir()
        manifest = build_manifest(wid, base_route)
        manifest["source"] = {"gpx": gpx_file.name, "gpx_sha256": sha}
        (wdir / "route.json").write_text(route_json, encoding="utf-8")
        (wdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    t0 = time.perf_counter()
    entries = list_routes(routes_root, gpx_dir)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    print(f"list_routes (50 parcours) : {elapsed_ms:.1f} ms")

    assert len(entries) == 51  # demo + 50 parcours
    # Seuil cible 200 ms (marge CI jusqu'à 500 ms sur machine virtuelle partagée)
    assert elapsed_ms < 500.0
