"""Lot B1 : ligne de commande, formats, écriture atomique, verify et info (critères 4, 5, 8 à 10)."""

from __future__ import annotations

import json
import math
import subprocess
import sys

import jsonschema
import pytest

from conftest import WORLD_CONTRACTS, circle, require_core, straight_north
from openride_compiler import cli, writer
from openride_compiler.writer import normalize_name


def run(*argv):
    return cli.main([str(a) for a in argv])


def validator(name):
    schema = json.loads((WORLD_CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


@pytest.fixture
def built(make_gpx, tmp_path):
    gpx = make_gpx("Col d'Essai.gpx", *straight_north())
    out = tmp_path / "routes"
    assert run("build", gpx, "--out", out) == 0
    return out / "col-d-essai.world"


# Critère 8 : formats ------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["straight", "loop", "out_and_back"])
def test_outputs_match_schemas_and_load_in_core(shape, make_gpx, tmp_path):
    load_world = require_core("openride_core.route").load_world

    pts = circle() if shape == "loop" else straight_north()
    gpx = make_gpx("trace.gpx", *pts)
    extra = ["--out-and-back"] if shape == "out_and_back" else []
    assert run("build", gpx, "--out", tmp_path, "--name", shape, *extra) == 0
    world = tmp_path / f"{shape.replace('_', '-')}.world"
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    validator("manifest").validate(manifest)
    validator("route").validate(route)
    if manifest["layers"]["segments"]["present"]:                # couche par défaut avec le core
        validator("segments").validate(json.loads((world / "segments.json").read_text(encoding="utf-8")))

    assert manifest["projection"] == "utm"
    assert manifest["origin"]["utm_zone"] == "32T"
    assert manifest["format_version"] == "1.6"
    assert manifest["layers"]["terrain"]["present"] is True
    assert manifest["layers"]["terrain"]["sources"] == ["synthetic"]
    assert manifest["route"]["alt_source"] in ("gpx", "synthetic")
    assert manifest["source"]["gpx"] == "trace.gpx" and len(manifest["source"]["gpx_sha256"]) == 64
    assert manifest["compiler"]["name"] == "openride-compiler"
    assert manifest["route"]["type"] == route["type"]

    w = load_world(world)
    assert w.route.n == route["n"] and w.route.type == route["type"]
    for s in (0.0, 123.4, w.route.length_m / 2, w.route.length_m):
        p = w.route.sample(s)
        assert math.isfinite(p.x) and math.isfinite(p.grade_pct)


# Critères 4 et 5 par la ligne de commande ----------------------------------------------------

def test_cli_short_trace_code_1(make_gpx, tmp_path, capsys):
    gpx = make_gpx("court.gpx", *straight_north(length=400.0))
    assert run("build", gpx, "--out", tmp_path) == 1
    assert "trace trop courte (400 m < 500 m)" in capsys.readouterr().err
    assert not (tmp_path / "court.world").exists()


def test_cli_missing_altitude_uses_dem(make_gpx, tmp_path, capsys):
    x, z, _ = straight_north()
    gpx = make_gpx("plat.gpx", x, z)
    assert run("build", gpx, "--out", tmp_path, "--layers", "route") == 0
    manifest = json.loads((tmp_path / "plat.world" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["route"]["alt_source"] == "synthetic"
    assert "altitude de la route : synthetic" in capsys.readouterr().err


def test_cli_invalid_gpx_and_usage_code_1(tmp_path):
    bad = tmp_path / "bad.gpx"
    bad.write_text("pas du xml", encoding="utf-8")
    assert run("build", bad, "--out", tmp_path) == 1
    assert run("build", tmp_path / "absent.gpx", "--out", tmp_path) == 1
    with pytest.raises(SystemExit) as exc:
        run("build")
    assert exc.value.code == 1


# Critère 9 : écriture atomique ---------------------------------------------------------------

def test_error_during_write_leaves_nothing(make_gpx, tmp_path, monkeypatch, capsys):
    gpx = make_gpx("essai.gpx", *straight_north())
    real = writer._write_files

    def broken(folder, *args):
        (folder / "route.json").write_text("{", encoding="utf-8")   # écriture à moitié faite
        raise OSError("disque plein (simulé)")

    monkeypatch.setattr(writer, "_write_files", broken)
    assert run("build", gpx, "--out", tmp_path) == 2
    assert "erreur interne" in capsys.readouterr().err
    assert sorted(p.name for p in tmp_path.iterdir()) == ["essai.gpx"]

    monkeypatch.setattr(writer, "_write_files", real)
    assert run("build", gpx, "--out", tmp_path) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["essai.gpx", "essai.world"]


def test_existing_world_needs_force(built, make_gpx, capsys):
    def snapshot():
        return {str(p.relative_to(built)): p.read_bytes() for p in built.rglob("*") if p.is_file()}

    before = snapshot()
    gpx = make_gpx("col-d-essai.gpx", *circle())
    assert run("build", gpx, "--out", built.parent) == 1
    assert "--force" in capsys.readouterr().err
    assert snapshot() == before

    assert run("build", gpx, "--out", built.parent, "--force") == 0
    route = json.loads((built / "route.json").read_text(encoding="utf-8"))
    assert route["type"] == "loop"
    assert sorted(p.name for p in built.parent.iterdir()) == ["col-d-essai.world"]


def test_failed_replace_keeps_old_world(built, make_gpx, monkeypatch):
    before = (built / "route.json").read_bytes()
    gpx = make_gpx("autre.gpx", *circle())

    def broken(folder, *args):
        raise OSError("simulé")

    monkeypatch.setattr(writer, "_write_files", broken)
    assert run("build", gpx, "--out", built.parent, "--name", "col-d-essai", "--force") == 2
    assert (built / "route.json").read_bytes() == before
    assert sorted(p.name for p in built.parent.iterdir()) == ["col-d-essai.world"]


# Critère 10 : verify -------------------------------------------------------------------------

def test_verify_valid(built, capsys):
    assert run("verify", built) == 0
    assert "valide" in capsys.readouterr().out


def test_verify_detects_truncated_array(built, capsys):
    path = built / "route.json"
    route = json.loads(path.read_text(encoding="utf-8"))
    route["grade_pct"] = route["grade_pct"][:-5]
    path.write_text(json.dumps(route), encoding="utf-8")
    assert run("verify", built) == 1
    assert "« grade_pct » a 196 valeurs au lieu de 201" in capsys.readouterr().out


@pytest.mark.parametrize("mutate, expected", [
    (lambda r, m: r.update(length_m=r["length_m"] + 50), "incohérent"),
    (lambda r, m: r.update(type="loop"), "boucle non fermée"),
    (lambda r, m: r["heading_deg"].__setitem__(3, 360.0), "heading_deg"),
    (lambda r, m: r["grade_pct"].__setitem__(3, 31.0), "grade_pct"),
    (lambda r, m: r["lat"].__setitem__(3, "x"), "non numérique"),
    (lambda r, m: m.update(format_version="2.0"), "trop récent"),
    (lambda r, m: m["route"].update(n=12), "désaccord sur n"),
])
def test_verify_detects_problems(built, capsys, mutate, expected):
    rp, mp = built / "route.json", built / "manifest.json"
    route = json.loads(rp.read_text(encoding="utf-8"))
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    mutate(route, manifest)
    rp.write_text(json.dumps(route), encoding="utf-8")
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    assert run("verify", built) == 1
    assert expected in capsys.readouterr().out


def test_verify_missing_files(tmp_path):
    assert run("verify", tmp_path / "absent.world") == 1
    (tmp_path / "vide.world").mkdir()
    assert run("verify", tmp_path / "vide.world") == 1


# info ----------------------------------------------------------------------------------------

def test_info(built, capsys):
    assert run("info", built) == 0
    out = capsys.readouterr().out
    assert "col-d-essai" in out and "2.000 km" in out and "open" in out
    assert "Pente maximale    : 5.0 %" in out
    assert "Dénivelé positif  : 100 m" in out
    assert "Points limités    : 0" in out
    assert "Altitude          : gpx" in out
    assert "Terrain           : " in out and "(synthetic)" in out


def test_info_invalid_world(tmp_path):
    assert run("info", tmp_path) == 1


# Divers --------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw, name", [
    ("Col du Galibier", "col-du-galibier"),
    ("Alpe d'Huez (21 virages)", "alpe-d-huez-21-virages"),
    ("  Éze__Village  ", "eze-village"),
    ("###", "parcours"),
])
def test_normalize_name(raw, name):
    assert normalize_name(raw) == name


def test_module_entry_point(built):
    proc = subprocess.run([sys.executable, "-m", "openride_compiler", "verify", str(built)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
