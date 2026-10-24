"""Lot M7 : traces FIT et TCX lues comme un GPX (`track_formats.read_track`, `build`)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.profile_type import FileType, Manufacturer

from conftest import gpx_text, straight_north, to_latlon
from openride_compiler import cli
from openride_compiler.errors import CompileError
from openride_compiler.track_formats import read_track, sniff_format

T0_MS = 1_761_300_000_000   # 24 octobre 2025, horodatage FIT réaliste


def _trace():
    """Trace de démonstration ; altitudes arrondies à 0,2 m, la résolution d'un FIT (échelle 5),
    pour que le GPX de référence et le FIT portent exactement la même trace."""
    x, z, alt = straight_north()
    lat, lon = to_latlon(x, z)
    return list(lat), list(lon), [round(a * 5) / 5 for a in alt]


def fit_bytes(lat, lon, alt, file_type=FileType.ACTIVITY, enhanced=True) -> bytes:
    b = FitFileBuilder(auto_define=True, min_string_size=50)
    fid = FileIdMessage()
    fid.type = file_type
    fid.manufacturer = Manufacturer.DEVELOPMENT.value
    fid.product = 1
    fid.serial_number = 0x0E0DE007
    fid.time_created = T0_MS
    b.add(fid)
    for k, (a, o, e) in enumerate(zip(lat, lon, alt)):
        m = RecordMessage()
        m.timestamp = T0_MS + 1000 * k
        if a is not None:
            m.position_lat, m.position_long = a, o
        if e is not None:
            if enhanced:
                m.enhanced_altitude = e
            else:
                m.altitude = e
        m.power = 200
        b.add(m)
    return b.build().to_bytes()


def _tcx_point(a, o, e) -> str:
    pos = "" if a is None else (f"<Position><LatitudeDegrees>{a:.10f}</LatitudeDegrees>"
                                f"<LongitudeDegrees>{o:.10f}</LongitudeDegrees></Position>")
    ele = "" if e is None else f"<AltitudeMeters>{e:.4f}</AltitudeMeters>"
    return f"<Trackpoint><Time>2025-10-24T10:00:00Z</Time>{pos}{ele}</Trackpoint>"


TCX_HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n<TrainingCenterDatabase '
            'xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">')


def tcx_activity(lat, lon, alt, laps=1) -> str:
    pts = [_tcx_point(a, o, e) for a, o, e in zip(lat, lon, alt)]
    cut = np.array_split(np.arange(len(pts)), laps)
    body = "".join(f'<Lap StartTime="2025-10-24T10:00:00Z"><Track>'
                   f'{"".join(pts[i] for i in idx)}</Track></Lap>' for idx in cut)
    return (f'{TCX_HEAD}<Activities><Activity Sport="Biking"><Id>2025-10-24T10:00:00Z</Id>'
            f'{body}</Activity></Activities></TrainingCenterDatabase>\n')


def tcx_course(lat, lon, alt) -> str:
    pts = "".join(_tcx_point(a, o, e) for a, o, e in zip(lat, lon, alt))
    return (f'{TCX_HEAD}<Courses><Course><Name>Essai</Name><Lap><TotalTimeSeconds>0</TotalTimeSeconds>'
            f'</Lap><Track>{pts}</Track></Course></Courses></TrainingCenterDatabase>\n')


def _build(path: Path, out: Path) -> dict:
    assert cli.main(["build", str(path), "--out", str(out), "--layers", "route", "--name", "essai"]) == 0
    return json.loads((out / "essai.world" / "route.json").read_text(encoding="utf-8"))


def _assert_close(a, b, path="route"):
    """Même structure ; nombres à 1 cm ou 0,01 % près, bornes comprises (critère 2) : un FIT
    arrondit les positions au semi-cercle (~ 5 mm), et route.json garde 2 décimales."""
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for k in a:
            _assert_close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for k, (u, v) in enumerate(zip(a, b)):
            _assert_close(u, v, f"{path}[{k}]")
    elif isinstance(a, (int, float)) and not isinstance(a, bool):
        if "heading" in path:   # cap plein nord : 0 et 359,99 sont voisins
            b = a + (b - a + 180.0) % 360.0 - 180.0
        assert math.isclose(a, b, rel_tol=1e-4, abs_tol=0.01 + 1e-9), (path, a, b)
    else:
        assert a == b, path


@pytest.fixture
def reference(tmp_path):
    lat, lon, alt = _trace()
    gpx = tmp_path / "ref.gpx"
    gpx.write_text(gpx_text(lat, lon, alt), encoding="utf-8")
    return _build(gpx, tmp_path / "ref")


# Critère 2 : même route.json qu'avec le GPX ------------------------------------------------

def test_fit_gives_same_route_as_gpx(reference, tmp_path):
    path = tmp_path / "sortie.FIT"
    path.write_bytes(fit_bytes(*_trace()))
    _assert_close(reference, _build(path, tmp_path / "fit"))


def test_tcx_gives_same_route_as_gpx(reference, tmp_path):
    path = tmp_path / "sortie.tcx"
    path.write_text(tcx_activity(*_trace()), encoding="utf-8")
    _assert_close(reference, _build(path, tmp_path / "tcx"))


# Lecture FIT ---------------------------------------------------------------------------------

def test_fit_points_in_degrees_with_enhanced_altitude(tmp_path):
    lat, lon, alt = _trace()
    path = tmp_path / "a.fit"
    path.write_bytes(fit_bytes(lat, lon, alt))
    points = read_track(path)
    assert len(points) == len(lat)
    assert points[0].lat == pytest.approx(lat[0], abs=1e-7)
    assert points[-1].lon == pytest.approx(lon[-1], abs=1e-7)
    assert points[10].ele == pytest.approx(alt[10], abs=0.11)


def test_fit_plain_altitude_and_course_file(tmp_path):
    lat, lon, alt = _trace()
    path = tmp_path / "parcours.fit"
    path.write_bytes(fit_bytes(lat, lon, alt, file_type=FileType.COURSE, enhanced=False))
    points = read_track(path)
    assert len(points) == len(lat) and points[5].ele == pytest.approx(alt[5], abs=0.11)


def test_fit_first_30_points_without_position_are_skipped(tmp_path, capsys):
    """Critère 3."""
    lat, lon, alt = _trace()
    lat[:30] = lon[:30] = [None] * 30
    path = tmp_path / "sans-gps-au-depart.fit"
    path.write_bytes(fit_bytes(lat, lon, alt))
    assert len(read_track(path)) == len(alt) - 30
    assert cli.main(["build", str(path), "--out", str(tmp_path), "--layers", "route"]) == 0


def test_fit_without_position(tmp_path, capsys):
    """Critère 4 : home trainer ; code 1, celui des autres erreurs de trace (`EXIT_INPUT`)."""
    n = 200
    path = tmp_path / "home-trainer.fit"
    path.write_bytes(fit_bytes([None] * n, [None] * n, [None] * n))
    with pytest.raises(CompileError, match="aucune position GPS dans ce FIT"):
        read_track(path)
    assert cli.main(["build", str(path), "--out", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "aucune position GPS dans ce FIT" in err and "Traceback" not in err


def test_identical_consecutive_points_are_merged(tmp_path):
    lat, lon, alt = _trace()
    dup = lambda v: [w for w in v[:50] for _ in (0, 1)]   # noqa: E731
    path = tmp_path / "pause.fit"
    path.write_bytes(fit_bytes(dup(lat), dup(lon), dup(alt)))
    assert len(read_track(path)) == 50


def test_corrupt_fit(tmp_path, capsys):
    path = tmp_path / "abime.fit"
    data = fit_bytes(*_trace())
    path.write_bytes(data[:14] + b"\xff" * 40)
    assert cli.main(["build", str(path), "--out", str(tmp_path)]) == 1
    assert "Traceback" not in capsys.readouterr().err


# Critère 5 : format reconnu par le contenu ---------------------------------------------------

def test_fit_extension_holding_a_gpx(tmp_path):
    lat, lon, alt = _trace()
    path = tmp_path / "trompeur.fit"
    path.write_text(gpx_text(lat, lon, alt), encoding="utf-8")
    assert len(read_track(path)) == len(lat)


@pytest.mark.parametrize("kind", ["fit", "tcx", "gpx"])
def test_file_without_extension(tmp_path, kind):
    lat, lon, alt = _trace()
    path = tmp_path / "trace"
    if kind == "fit":
        path.write_bytes(fit_bytes(lat, lon, alt))
    else:
        path.write_text(tcx_course(lat, lon, alt) if kind == "tcx" else gpx_text(lat, lon, alt),
                        encoding="utf-8")
    assert sniff_format(path.read_bytes()) == f".{kind}"
    assert len(read_track(path)) == len(lat)


def test_unknown_content_without_extension(tmp_path, capsys):
    path = tmp_path / "trace"
    path.write_text("ni GPX, ni FIT, ni TCX", encoding="utf-8")
    with pytest.raises(CompileError, match="format inconnu"):
        read_track(path)
    assert cli.main(["build", str(path), "--out", str(tmp_path)]) == 1


# Critère 6 : TCX de parcours et TCX d'activité à deux tours ---------------------------------

def test_tcx_course(tmp_path):
    lat, lon, alt = _trace()
    path = tmp_path / "parcours.TCX"
    path.write_text(tcx_course(lat, lon, alt), encoding="utf-8")
    points = read_track(path)
    assert len(points) == len(lat) and points[3].ele == pytest.approx(alt[3], abs=1e-3)


def test_tcx_two_laps_put_end_to_end(tmp_path):
    lat, lon, alt = _trace()
    path = tmp_path / "deux-tours.tcx"
    path.write_text(tcx_activity(lat, lon, alt, laps=2), encoding="utf-8")
    points = read_track(path)
    assert [p.lat for p in points] == pytest.approx(lat, abs=1e-9)


def test_tcx_trackpoints_without_position_are_skipped(tmp_path):
    lat, lon, alt = _trace()
    lat[:5] = lon[:5] = [None] * 5
    path = tmp_path / "a.tcx"
    path.write_text(tcx_activity(lat, lon, alt), encoding="utf-8")
    assert len(read_track(path)) == len(alt) - 5


def test_tcx_without_trackpoint(tmp_path):
    path = tmp_path / "vide.tcx"
    path.write_text(tcx_activity([], [], []), encoding="utf-8")
    with pytest.raises(CompileError, match="TCX sans point"):
        read_track(path)
