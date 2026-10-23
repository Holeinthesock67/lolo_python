"""Lot B1 : lecture GPX 1.0 et 1.1, espaces de noms et extensions ignorés."""

from __future__ import annotations

import pytest

from openride_compiler.errors import CompileError
from openride_compiler.gpx import parse_gpx


def test_gpx_11_multiple_tracks_and_segments_in_order():
    data = b"""<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <wpt lat="1" lon="1"><ele>9</ele></wpt>
  <rte><rtept lat="9" lon="9"/></rte>
  <trk><trkseg>
    <trkpt lat="45.0" lon="6.0"><ele>100</ele><time>2026-10-23T10:00:00Z</time>
      <extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>140</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions>
    </trkpt>
    <trkpt lat="45.001" lon="6.0"><ele>101.5</ele></trkpt>
  </trkseg><trkseg>
    <trkpt lat="45.002" lon="6.0"><ele>102</ele></trkpt>
  </trkseg></trk>
  <trk><trkseg><trkpt lat="45.003" lon="6.0"></trkpt></trkseg></trk>
</gpx>"""
    pts = parse_gpx(data)
    assert [p.lat for p in pts] == [45.0, 45.001, 45.002, 45.003]
    assert [p.ele for p in pts] == [100.0, 101.5, 102.0, None]


def test_gpx_10_routes_when_no_track():
    data = b"""<gpx version="1.0" xmlns="http://www.topografix.com/GPX/1/0">
  <rte><rtept lat="45.0" lon="6.0"><ele>5</ele></rtept><rtept lat="45.1" lon="6.1"><ele>6</ele></rtept></rte>
</gpx>"""
    pts = parse_gpx(data)
    assert [(p.lat, p.lon, p.ele) for p in pts] == [(45.0, 6.0, 5.0), (45.1, 6.1, 6.0)]


def test_no_namespace():
    pts = parse_gpx(b'<gpx><trk><trkseg><trkpt lat="1" lon="2"><ele>3</ele></trkpt></trkseg></trk></gpx>')
    assert pts[0].lat == 1.0 and pts[0].lon == 2.0 and pts[0].ele == 3.0


@pytest.mark.parametrize("data", [
    b"pas du xml",
    b"<gpx></gpx>",
    b'<gpx><trk><trkseg><trkpt lat="abc" lon="2"/></trkseg></trk></gpx>',
    b'<gpx><trk><trkseg><trkpt lat="95" lon="2"/></trkseg></trk></gpx>',
])
def test_invalid_gpx(data):
    with pytest.raises(CompileError):
        parse_gpx(data)


def test_bad_elevation_counts_as_missing():
    pts = parse_gpx(b'<gpx><trk><trkseg><trkpt lat="1" lon="2"><ele>n/a</ele></trkpt></trkseg></trk></gpx>')
    assert pts[0].ele is None
