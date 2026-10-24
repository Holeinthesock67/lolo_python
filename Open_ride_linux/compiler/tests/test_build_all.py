"""Tests des sous-commandes `list` et `build-all` du compilateur (Lot I2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import straight_north
from openride_compiler import cli
from openride_compiler.errors import CompileError


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def test_build_all_dry_run_then_real_and_list(
    make_gpx,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Critère 3 : build-all --dry-run n'écrit rien et annonce les 2 compilations, puis build-all et list."""
    gpx_dir = tmp_path / "GPX"
    routes_dir = tmp_path / "routes"
    gpx_dir.mkdir()
    routes_dir.mkdir()

    # 1. GPX déjà compilé et à jour -> ignoré
    gpx_ok = make_gpx("GPX/deja_ok.gpx", *straight_north(length=1000.0))
    assert run("build", gpx_ok, "--out", routes_dir) == 0

    # 2. GPX compilé puis modifié -> outdated
    gpx_mod = make_gpx("GPX/modifie.gpx", *straight_north(length=1000.0))
    assert run("build", gpx_mod, "--out", routes_dir) == 0
    make_gpx("GPX/modifie.gpx", *straight_north(length=1200.0))

    # 3. GPX jamais compilé -> to_compile
    make_gpx("GPX/nouveau.gpx", *straight_north(length=1000.0))
    capsys.readouterr()

    # Dry-run : n'écrit pas nouveau.world, annonce 2 à compiler
    rc_dry = run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes_dir, "--dry-run")
    assert rc_dry == 0
    out_dry = capsys.readouterr().out
    assert "2 à compiler" in out_dry
    assert not (routes_dir / "nouveau.world").exists()

    # Exécution réelle : compile les 2 traces
    rc_build = run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes_dir)
    assert rc_build == 0
    out_build = capsys.readouterr().out
    assert "2 compilé(s)" in out_build
    assert (routes_dir / "nouveau.world").is_dir()

    # List : toutes les traces sont désormais ready
    rc_list = run("list", "--gpx-dir", gpx_dir, "--routes-dir", routes_dir)
    assert rc_list == 0
    out_list = capsys.readouterr().out
    assert "deja-ok" in out_list
    assert "modifie" in out_list
    assert "nouveau" in out_list
    assert "to_compile" not in out_list
    assert "outdated" not in out_list


def test_build_all_invalid_trace_does_not_stop_others(
    make_gpx,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Critère 4 : une trace trop courte (< 500 m) échoue seule ; les autres sont compilées ; code 1."""
    gpx_dir = tmp_path / "GPX"
    routes_dir = tmp_path / "routes"
    gpx_dir.mkdir()
    routes_dir.mkdir()

    make_gpx("GPX/01_valide_a.gpx", *straight_north(length=1000.0))
    make_gpx("GPX/02_trop_courte.gpx", *straight_north(length=300.0))
    make_gpx("GPX/03_valide_b.gpx", *straight_north(length=1000.0))

    rc = run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes_dir)
    assert rc == 1
    captured = capsys.readouterr()
    assert "2 compilé(s)" in captured.out
    assert "1 en erreur" in captured.out
    assert "02_trop_courte.gpx" in captured.err
    assert (routes_dir / "01-valide-a.world").is_dir()
    assert (routes_dir / "03-valide-b.world").is_dir()
    assert not (routes_dir / "02-trop-courte.world").exists()


def test_build_all_default_layers_without_osm(
    make_gpx,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Régression (audit J du 23 octobre) : build-all produit route et terrain par défaut, sans Overpass.

    Après la fusion d'I3, build-all demandait toutes les couches de `LAYERS`, donc OpenStreetMap :
    sans réseau, chaque trace échouait. Les couches OSM restent possibles avec --layers.
    """
    gpx_dir = tmp_path / "GPX"
    routes_dir = tmp_path / "routes"
    gpx_dir.mkdir()
    routes_dir.mkdir()
    make_gpx("GPX/trace.gpx", *straight_north(length=1000.0))

    def no_osm(*args, **kwargs):
        raise AssertionError("build-all ne doit pas interroger Overpass sans --layers OSM")

    monkeypatch.setattr(cli, "make_osm_client", no_osm)
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes_dir) == 0
    assert "1 compilé(s)" in capsys.readouterr().out
    manifest = json.loads((routes_dir / "trace.world" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["layers"]["terrain"]["present"] is True
    assert manifest["layers"]["buildings"]["present"] is False

    # Avec --layers, les couches OSM sont bien demandées (le client Overpass est construit).
    calls: list[bool] = []

    def failing_osm(offline, log=None):
        calls.append(offline)
        raise CompileError("Overpass indisponible (test)")

    make_gpx("GPX/autre.gpx", *straight_north(length=1000.0))
    monkeypatch.setattr(cli, "make_osm_client", failing_osm)
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes_dir,
               "--layers", "route,buildings") == 1
    assert calls == [False]
