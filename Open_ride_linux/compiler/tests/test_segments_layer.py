"""Lot T3 : couche `segments` du `.world` (format 1.3, §8 bis), fichier `<parcours>.segments.toml`."""

from __future__ import annotations

import json

import jsonschema
import pytest

import numpy as np

from conftest import ORIGIN, WORLD_CONTRACTS, require_core, straight_north
from openride_compiler import cli
from openride_compiler import segments_layer as SEG
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.errors import CompileError


def climb_dem(x, z):
    """MNT : 2 km à 5 % vers le nord, puis plat."""
    return 1000.0 + 0.05 * np.minimum(-np.asarray(z, dtype=float), 2000.0) + 0.0 * np.asarray(x, dtype=float)


@pytest.fixture(autouse=True)
def climb_then_flat_dem(monkeypatch):
    monkeypatch.setattr(cli, "make_provider", lambda offline, log=None: SyntheticProvider(*ORIGIN, climb_dem))


def run(*argv):
    return cli.main([str(a) for a in argv])


def seg_validator():
    schema = json.loads((WORLD_CONTRACTS / "segments.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def read(world):
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    segs = json.loads((world / "segments.json").read_text(encoding="utf-8"))
    return manifest, segs


def climb_then_flat(make_gpx, name="col.gpx"):
    """2 km à 5 % puis 3 km de plat : une montée et un sprint proposés."""
    x, z, _ = straight_north(length=5000.0)
    return make_gpx(name, x, z, climb_dem(x, z))


def test_build_writes_detected_segments(make_gpx, tmp_path):
    core = require_core("openride_core.segments")
    gpx = climb_then_flat(make_gpx)
    assert run("build", gpx, "--out", tmp_path / "routes", "--layers", "route,segments") == 0
    world = tmp_path / "routes" / "col.world"
    manifest, layer = read(world)
    seg_validator().validate(layer)
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    expected = [s.to_dict() for s in core.detect_segments(SEG.route_profile(core, route))]
    assert layer["segments"] == expected
    assert [s["type"] for s in expected] == ["climb", "sprint"]
    assert manifest["layers"]["segments"] == {"present": True, "version": "1.0", "file": "segments.json",
                                              "count": 2, "manual_count": 0}
    assert manifest["format_version"] == "1.6"
    assert run("verify", world) == 0


def test_manual_file_add_then_replace(make_gpx, tmp_path):
    require_core("openride_core.segments")
    gpx = climb_then_flat(make_gpx)
    side = gpx.with_name("col.segments.toml")
    side.write_text('[[segment]]\ntype = "sprint"\nstart_km = 4.2\nend_km = 4.6\n'
                    'name = "Sprint du village"\n', encoding="utf-8")
    out = tmp_path / "routes"
    assert run("build", gpx, "--out", out, "--layers", "route,segments") == 0
    manifest, layer = read(out / "col.world")
    kinds = [(s["type"], s["source"]) for s in layer["segments"]]
    assert kinds == [("climb", "auto"), ("sprint", "manual")]     # le sprint auto chevauché disparaît
    assert layer["segments"][1]["name"] == "Sprint du village"
    assert manifest["layers"]["segments"]["manual_count"] == 1

    side.write_text('mode = "replace"\n[[segment]]\ntype = "climb"\nstart_km = 0.5\nend_km = 1.5\n',
                    encoding="utf-8")
    assert run("build", gpx, "--out", out, "--layers", "route,segments", "--force") == 0
    _, layer = read(out / "col.world")
    assert [(s["id"], s["source"], s["s_start"], s["s_end"]) for s in layer["segments"]] == [
        ("mclimb1", "manual", 500.0, 1500.0)]

    side.write_text('auto_sprints = false\n', encoding="utf-8")
    assert run("build", gpx, "--out", out, "--layers", "route,segments", "--force") == 0
    _, layer = read(out / "col.world")
    assert [s["type"] for s in layer["segments"]] == ["climb"]


@pytest.mark.parametrize("content, message", [
    ("mode = ", "fichier illisible"),
    ('couleur = "rouge"\n', "clé inconnue couleur"),
    ('mode = "fusion"\n', "mode 'fusion' inconnu"),
    ('[[segment]]\ntype = "sprint"\nstart_km = 1.0\nend_km = 1.2\n'
     '[[segment]]\ntype = "descente"\nstart_km = 2.0\nend_km = 3.0\n', "segment 2 : type 'descente' inconnu"),
    ('[[segment]]\ntype = "climb"\nstart_km = 4.0\nend_km = 9.0\n', "segment 1 : 4.0–9.0 km hors du parcours"),
    ('[[segment]]\ntype = "climb"\nstart_km = 2.0\nend_km = 2.0\n', "segment 1 : 2.0–2.0 km hors du parcours"),
    ('[[segment]]\ntype = "climb"\nstart_km = 1.0\n', "segment 1 : end_km manquant"),
    ('[[segment]]\ntype = "climb"\nstart_km = 1.0\nend_km = 2.0\npente = 5\n', "segment 1 : clé inconnue pente"),
])
def test_invalid_manual_files_are_refused(content, message, make_gpx, tmp_path, capsys):
    require_core("openride_core.segments")
    gpx = climb_then_flat(make_gpx)
    gpx.with_name("col.segments.toml").write_text(content, encoding="utf-8")
    assert run("build", gpx, "--out", tmp_path / "routes", "--layers", "route,segments") == 1
    err = capsys.readouterr().err
    assert "col.segments.toml" in err and message in err
    assert not (tmp_path / "routes" / "col.world").exists()


def test_add_layer_on_utm_and_synthetic_routes_without_network(make_gpx, tmp_path):
    require_core("openride_core.segments")
    demo_world = require_core("openride_core.demo_world")
    gpx = climb_then_flat(make_gpx)
    out = tmp_path / "routes"
    assert run("build", gpx, "--out", out, "--layers", "route") == 0
    world = out / "col.world"
    assert json.loads((world / "manifest.json").read_text())["layers"]["segments"] == {"present": False}
    (tmp_path / "col.segments.toml").unlink(missing_ok=True)
    assert run("add-layer", world, "segments") == 0
    manifest, layer = read(world)
    assert manifest["layers"]["segments"]["count"] == len(layer["segments"]) == 2
    assert run("verify", world) == 0

    # Fichier manuel de la trace source, cherché à côté du .world
    (out / "col.segments.toml").write_text('mode = "replace"\n', encoding="utf-8")
    assert run("add-layer", world, "segments") == 0
    assert read(world)[1]["segments"] == []

    # Parcours synthétique (projection locale) : accepté
    synth = demo_world.write_world(tmp_path / "synth", "essai", 6000.0)
    (synth / "segments.json").unlink()
    assert run("add-layer", synth, "segments", "--manual", tmp_path / "absent.segments.toml") == 1
    assert run("add-layer", synth, "segments") == 0
    assert run("verify", synth) == 0
    seg_validator().validate(read(synth)[1])


def test_without_core_build_warns_and_add_layer_fails(make_gpx, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(SEG, "core_segments", lambda: None)
    gpx = climb_then_flat(make_gpx)
    out = tmp_path / "routes"
    assert run("build", gpx, "--out", out) == 0                    # couches par défaut
    err = capsys.readouterr().err
    assert "core OpenRide non installé, couche segments omise" in err
    world = out / "col.world"
    assert not (world / "segments.json").exists()
    assert json.loads((world / "manifest.json").read_text())["layers"]["segments"] == {"present": False}
    assert run("verify", world) == 0
    assert run("add-layer", world, "segments") == 1
    assert "le core OpenRide (openride_core) n'est pas installé" in capsys.readouterr().err
    with pytest.raises(CompileError):
        SEG.build_segments({"n": 2, "ds_m": 10.0, "length_m": 10.0, "alt_m": [0, 0], "grade_pct": [0, 0]})


def _tampered(world, change):
    manifest, layer = read(world)
    change(layer["segments"])
    (world / "segments.json").write_text(json.dumps(layer), encoding="utf-8")
    manifest["layers"]["segments"]["count"] = len(layer["segments"])
    (world / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.parametrize("change, message", [
    (lambda segs: segs[1].update(s_end=9000.0), "hors du parcours"),
    (lambda segs: segs[1].update(id=segs[0]["id"]), "identifiant en double"),
    (lambda segs: segs[0].update(type="descente"), "type inconnu"),
    (lambda segs: segs[0].update(category="5"), "catégorie inconnue"),
    (lambda segs: segs[1].update(s_start=4000.0, s_end=3000.0), "doit être inférieur"),
])
def test_verify_refuses_bad_segments(change, message, make_gpx, tmp_path, capsys):
    require_core("openride_core.segments")
    gpx = climb_then_flat(make_gpx)
    assert run("build", gpx, "--out", tmp_path, "--layers", "route,segments") == 0
    world = tmp_path / "col.world"
    _tampered(world, change)
    assert run("verify", world) == 1
    assert message in capsys.readouterr().out


def test_verify_checks_count_and_info_summarizes(make_gpx, tmp_path, capsys):
    require_core("openride_core.segments")
    gpx = climb_then_flat(make_gpx)
    assert run("build", gpx, "--out", tmp_path, "--layers", "route,segments") == 0
    world = tmp_path / "col.world"
    capsys.readouterr()
    assert run("info", world) == 0
    assert "Segments          : 1 montée(s) (cat. 4 : 1), 1 sprint(s)" in capsys.readouterr().out
    manifest, _ = read(world)
    manifest["layers"]["segments"]["count"] = 5
    (world / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert run("verify", world) == 1
    assert "manifeste count = 5, fichier : 2" in capsys.readouterr().out


def test_build_all_reads_the_manual_file_of_each_track(make_gpx, tmp_path):
    require_core("openride_core.segments")
    gpx_dir, routes = tmp_path / "GPX", tmp_path / "routes"
    gpx_dir.mkdir()
    climb_then_flat(make_gpx, "GPX/avec.gpx")
    climb_then_flat(make_gpx, "GPX/sans.gpx")
    (gpx_dir / "avec.segments.toml").write_text('mode = "replace"\n', encoding="utf-8")
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--layers", "route,segments") == 0
    assert read(routes / "avec.world")[1]["segments"] == []
    assert len(read(routes / "sans.world")[1]["segments"]) == 2
