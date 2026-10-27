"""Lot O5 : traces FIT, TCX et archives Garmin déposées dans le dossier des traces.

Toutes les traces sont fabriquées par les tests (aucun fichier d'activité réel dans le dépôt).
"""

from __future__ import annotations

import gzip
import io
import zipfile
from pathlib import Path

import pytest

from conftest import gpx_text, straight_north, to_latlon
from openride_compiler import cli
from openride_compiler.errors import CompileError
from openride_compiler.track_formats import MAX_UNPACKED_BYTES, read_track, scan_tracks, track_stem
from test_track_formats import fit_bytes, tcx_activity


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def trace(length: float):
    x, z, alt = straight_north(length=length)
    lat, lon = to_latlon(x, z)
    return list(lat), list(lon), [round(a * 5) / 5 for a in alt]


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def dirs(tmp_path):
    gpx_dir, routes = tmp_path / "GPX", tmp_path / "routes"
    gpx_dir.mkdir()
    routes.mkdir()
    return gpx_dir, routes


def deposit_four(gpx_dir: Path) -> None:
    """Critère 2 : a.gpx, b.fit, c.tcx.gz, d.zip (contenant un FIT), longueurs différentes."""
    (gpx_dir / "a.gpx").write_text(gpx_text(*trace(900.0)), encoding="utf-8")
    (gpx_dir / "b.fit").write_bytes(fit_bytes(*trace(1000.0)))
    (gpx_dir / "c.tcx.gz").write_bytes(gzip.compress(tcx_activity(*trace(1100.0)).encode()))
    (gpx_dir / "d.zip").write_bytes(zip_bytes({"activite_123.fit": fit_bytes(*trace(1200.0))}))


@pytest.mark.parametrize("name, expected", [
    ("col.gpx", ("col", 0)), ("COL.FIT", ("COL", 1)), ("x.fit.gz", ("x", 2)), ("y.TCX", ("y", 3)),
    ("z.tcx.GZ", ("z", 4)), ("export.zip", ("export", 5)), ("notes.txt", None), (".gpx", None),
    ("a.gpx.gz", None), ("b.gz", None),
])
def test_track_stem(name, expected):
    assert track_stem(name) == expected


def test_four_formats_listed_built_then_up_to_date(dirs, capsys):
    gpx_dir, routes = dirs
    deposit_four(gpx_dir)
    entries = {e.id: e for e in cli._catalog_entries(routes, gpx_dir)}
    assert {k: e.status for k, e in entries.items() if k != "demo"} == \
        {"a": "to_compile", "b": "to_compile", "c": "to_compile", "d": "to_compile"}
    assert entries["c"].name == "c" and entries["d"].gpx_path == gpx_dir / "d.zip"
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--layers", "route") == 0
    assert "4 compilé(s)" in capsys.readouterr().out
    assert sorted(p.name for p in routes.iterdir()) == ["a.world", "b.world", "c.world", "d.world"]
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--layers", "route") == 0
    assert "0 compilé(s)" in capsys.readouterr().out
    assert run("list", "--gpx-dir", gpx_dir, "--routes-dir", routes) == 0
    out = capsys.readouterr().out
    assert out.count("ready") == 5 and "c.tcx.gz" in out and "d.zip" in out


def test_manifest_keeps_the_deposited_file(dirs):
    import hashlib
    import json

    gpx_dir, routes = dirs
    deposit_four(gpx_dir)
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--layers", "route") == 0
    src = json.loads((routes / "d.world" / "manifest.json").read_text(encoding="utf-8"))["source"]
    assert src["gpx"] == "d.zip"
    assert src["gpx_sha256"] == hashlib.sha256((gpx_dir / "d.zip").read_bytes()).hexdigest()


def test_modified_fit_is_outdated_and_rebuilt_alone(dirs, capsys):
    """Critère 3."""
    gpx_dir, routes = dirs
    deposit_four(gpx_dir)
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--layers", "route") == 0
    (gpx_dir / "b.fit").write_bytes(fit_bytes(*trace(1300.0)))
    statuses = {e.id: e.status for e in cli._catalog_entries(routes, gpx_dir)}
    assert statuses["b"] == "outdated" and statuses["a"] == statuses["d"] == "ready"
    capsys.readouterr()
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--layers", "route") == 0
    assert "1 compilé(s)" in capsys.readouterr().out


def test_same_id_gives_one_route_and_a_conflict(dirs, capsys):
    """Critère 4 : col.gpx gagne sur col.fit et COL.tcx.gz."""
    gpx_dir, routes = dirs
    (gpx_dir / "col.fit").write_bytes(fit_bytes(*trace(1000.0)))
    (gpx_dir / "col.gpx").write_text(gpx_text(*trace(900.0)), encoding="utf-8")
    (gpx_dir / "COL.tcx.gz").write_bytes(gzip.compress(tcx_activity(*trace(800.0)).encode()))
    kept, conflicts = scan_tracks(gpx_dir)
    assert kept == [gpx_dir / "col.gpx"]
    assert conflicts == [(gpx_dir / "col.fit", gpx_dir / "col.gpx"), (gpx_dir / "COL.tcx.gz", gpx_dir / "col.gpx")]
    assert [e.id for e in cli._catalog_entries(routes, gpx_dir)] == ["demo", "col"]
    capsys.readouterr()
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--layers", "route") == 0
    captured = capsys.readouterr()
    assert "1 compilé(s)" in captured.out
    assert "conflit : col.fit ignoré, même parcours que col.gpx" in captured.err


def test_bad_archives_do_not_stop_the_others(dirs, capsys, monkeypatch):
    """Critère 5 : messages clairs, les autres traces compilées, code non nul."""
    gpx_dir, routes = dirs
    (gpx_dir / "bon.fit").write_bytes(fit_bytes(*trace(1000.0)))
    (gpx_dir / "casse.zip").write_bytes(b"PK\x03\x04 pas une archive")
    (gpx_dir / "vide.zip").write_bytes(zip_bytes({"lisez-moi.txt": b"rien"}))
    (gpx_dir / "gros.fit.gz").write_bytes(gzip.compress(b"\0" * 4096))
    monkeypatch.setattr("openride_compiler.track_formats.MAX_UNPACKED_BYTES", 1024)
    capsys.readouterr()
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--layers", "route") == 1
    captured = capsys.readouterr()
    assert "1 compilé(s)" in captured.out and "3 en erreur" in captured.out
    assert "casse.zip : archive .zip corrompue" in captured.err
    assert "vide.zip : archive sans trace .fit, .tcx ou .gpx" in captured.err
    assert "gros.fit.gz : archive trop grosse" in captured.err
    assert (routes / "bon.world").is_dir()


@pytest.mark.parametrize("name, data, message", [
    ("x.fit.gz", b"\x1f\x8b\x08\x00 tronque", "archive .gz corrompue"),
    ("x.zip", zip_bytes({}), "archive sans trace"),
])
def test_read_track_errors(tmp_path, name, data, message):
    (tmp_path / name).write_bytes(data)
    with pytest.raises(CompileError, match=message):
        read_track(tmp_path / name)


def test_zip_reads_first_track_and_lists_the_others(tmp_path):
    lat, lon, alt = trace(500.0)
    other = trace(700.0)
    (tmp_path / "export.zip").write_bytes(zip_bytes({
        "b_tour.tcx": tcx_activity(*other).encode(),
        "a_sortie.FIT": fit_bytes(lat, lon, alt),
        "notes.txt": b"x",
    }))
    notes: list[str] = []
    points = read_track(tmp_path / "export.zip", notes)
    assert len(points) == len(lat) and points[0].lat == pytest.approx(lat[0], abs=1e-6)
    assert notes == ["export.zip : a_sortie.FIT lu, ignoré(s) : b_tour.tcx"]


def test_zip_declared_too_big(tmp_path, monkeypatch):
    monkeypatch.setattr("openride_compiler.track_formats.MAX_UNPACKED_BYTES", 100)
    (tmp_path / "e.zip").write_bytes(zip_bytes({"s.gpx": gpx_text(*trace(300.0)).encode()}))
    with pytest.raises(CompileError, match="trop gros"):
        read_track(tmp_path / "e.zip")


def test_build_accepts_archives_on_the_command_line(tmp_path):
    src = tmp_path / "Ma Sortie.tcx.gz"
    src.write_bytes(gzip.compress(tcx_activity(*trace(600.0)).encode()))
    assert run("build", src, "--out", tmp_path / "routes", "--layers", "route") == 0
    assert (tmp_path / "routes" / "ma-sortie.world").is_dir()


def test_no_real_activity_file_in_the_repository():
    """Critère 6 : aucun FIT, TCX, GPX ou archive d'activité versionné hors des fichiers d'essai connus."""
    import subprocess

    repo = Path(__file__).resolve().parents[2]
    try:
        out = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git indisponible")
    tracked = [f for f in out.splitlines() if track_stem(Path(f).name) is not None]
    assert not [f for f in tracked if not f.endswith(".gpx")], tracked
