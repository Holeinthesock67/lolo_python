"""Fuzz des lecteurs de traces GPX, TCX et FIT, nus ou en `.gz` / `.zip` (lot X26).

Traces valides générées puis abîmées (octets tronqués, retournés, supprimés ou dupliqués, nombres hors
bornes, balises et entités insérées). Propriété : la lecture rend des points valides ou lève
`CompileError`, jamais une autre exception, en moins de 2 s. 200 exemples par lecteur
(`--hypothesis-profile=long` : 5 000, sur le PC).
"""

from __future__ import annotations

import gzip
import io
import math
import time
import zipfile

import pytest

pytest.importorskip("hypothesis")   # extra dev

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from openride_compiler.errors import CompileError
from openride_compiler.gpx import parse_gpx
from openride_compiler.track_formats import parse_fit, parse_tcx, read_track
from test_track_formats import fit_bytes

pytestmark = pytest.mark.fuzz

MAX_S = 2.0
NUMBERS = ["", "-1", "0", "1e309", "-1e309", "nan", "inf", "91", "-181", "1e18", "abc", "1,5", " 7 "]
INSERTS = ["<", ">", "&", "&amp;", "&lol;", "]]>", "<!--", "\x00", "\ufeff", "é", "\n", "<trkpt>", "</gpx>",
           '<trkpt lat="1">', "<Position/>", "<Trackpoint>", 'lat="', "<ele>"]
FUZZ = settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])


@st.composite
def points(draw):
    n = draw(st.integers(1, 30))
    lat0, lon0 = draw(st.floats(-80, 80)), draw(st.floats(-170, 170))
    return [(lat0 + k * 1e-4, lon0 + k * 1e-4, draw(st.one_of(st.none(), st.floats(-100, 4000)))) for k in range(n)]


def gpx_of(pts) -> str:
    body = "".join(f'<trkpt lat="{a:.7f}" lon="{o:.7f}">{"" if e is None else f"<ele>{e:.1f}</ele>"}</trkpt>'
                   for a, o, e in pts)
    return ('<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="fuzz" '
            f'xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>{body}</trkseg></trk></gpx>')


def tcx_of(pts) -> str:
    body = "".join(f"<Trackpoint><Time>2025-10-24T10:00:00Z</Time><Position><LatitudeDegrees>{a:.7f}</LatitudeDegrees>"
                   f"<LongitudeDegrees>{o:.7f}</LongitudeDegrees></Position>"
                   f"{'' if e is None else f'<AltitudeMeters>{e:.1f}</AltitudeMeters>'}</Trackpoint>" for a, o, e in pts)
    return ('<?xml version="1.0" encoding="UTF-8"?><TrainingCenterDatabase '
            'xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"><Activities><Activity Sport="Biking">'
            f"<Lap><Track>{body}</Track></Lap></Activity></Activities></TrainingCenterDatabase>")


@st.composite
def damaged_text(draw, text: str) -> str:
    for _ in range(draw(st.integers(1, 3))):
        n = len(text)
        kind = draw(st.sampled_from(["tronque", "supprime", "duplique", "nombre", "insere"]))
        i = draw(st.integers(0, n))
        j = draw(st.integers(i, min(n, i + 120)))
        if kind == "tronque":
            text = text[:i]
        elif kind == "supprime":
            text = text[:i] + text[j:]
        elif kind == "duplique":
            text = text[:j] + text[i:j] * draw(st.integers(1, 50)) + text[j:]
        elif kind == "nombre":
            digits = [k for k, c in enumerate(text) if c.isdigit()]
            if digits:
                k = draw(st.sampled_from(digits))
                e = k
                while e < len(text) and (text[e].isdigit() or text[e] in ".-"):
                    e += 1
                text = text[:k] + draw(st.sampled_from(NUMBERS)) + text[e:]
        else:
            text = text[:i] + draw(st.sampled_from(INSERTS) | st.text(max_size=20)) + text[i:]
    return text


@st.composite
def damaged_bytes(draw, data: bytes) -> bytes:
    for _ in range(draw(st.integers(1, 4))):
        n = len(data)
        kind = draw(st.sampled_from(["tronque", "retourne", "supprime", "duplique", "insere"]))
        i = draw(st.integers(0, max(n - 1, 0)))
        j = draw(st.integers(i, min(n, i + 64)))
        if kind == "tronque":
            data = data[:i]
        elif kind == "retourne" and n:
            data = data[:i] + bytes([data[i] ^ draw(st.integers(1, 255))]) + data[i + 1:]
        elif kind == "supprime":
            data = data[:i] + data[j:]
        elif kind == "duplique":
            data = data[:j] + data[i:j] * draw(st.integers(1, 20)) + data[j:]
        else:
            data = data[:i] + draw(st.binary(max_size=16)) + data[i:]
    return data


def check_points(fn, *args) -> None:
    t0 = time.monotonic()
    try:
        pts = fn(*args)
    except CompileError:
        pts = None
    assert time.monotonic() - t0 < MAX_S, "lecture trop lente"
    if pts is None:
        return
    assert pts
    for p in pts:
        assert math.isfinite(p.lat) and math.isfinite(p.lon) and -90 <= p.lat <= 90 and -180 <= p.lon <= 180, p
        assert p.ele is None or math.isfinite(p.ele), p


@FUZZ
@given(st.data())
def test_gpx(data):
    check_points(parse_gpx, data.draw(damaged_text(gpx_of(data.draw(points())))).encode("utf-8", "replace"))


@FUZZ
@given(st.data())
def test_tcx(data):
    check_points(parse_tcx, data.draw(damaged_text(tcx_of(data.draw(points())))).encode("utf-8", "replace"))


_FIT = fit_bytes([45.0 + k * 1e-4 for k in range(20)], [6.0 + k * 1e-4 for k in range(20)],
                 [300.0 + k for k in range(20)])


@FUZZ
@given(st.data())
def test_fit(data):
    check_points(parse_fit, data.draw(damaged_bytes(_FIT)))


def _pack(kind: str, name: str, raw: bytes) -> bytes:
    if kind == "gz":
        return gzip.compress(raw)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, raw)
    return buf.getvalue()


@FUZZ
@given(st.data(), st.sampled_from(["gpx", "tcx", "fit"]), st.sampled_from(["", "gz", "zip"]))
def test_read_track_files(tmp_path_factory, data, fmt, pack):
    pts = data.draw(points())
    raw = _FIT if fmt == "fit" else (gpx_of(pts) if fmt == "gpx" else tcx_of(pts)).encode("utf-8")
    if pack:
        raw = _pack(pack, f"trace.{fmt}", raw)
    raw = data.draw(damaged_bytes(raw)) if data.draw(st.booleans()) else raw
    path = tmp_path_factory.mktemp("fuzz") / f"trace.{fmt}{'.' + pack if pack else ''}"
    path.write_bytes(raw)
    check_points(read_track, path)


# --- XML : aucune entité externe ni expansion ---------------------------------------------------------

def _laughs(root_open: str, point: str, root_close: str) -> bytes:
    ents = "".join(f'<!ENTITY lol{i} "{("&lol" + (str(i - 1) if i > 1 else "") + ";") * 10}">' for i in range(1, 10))
    return (f'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY lol "lol">{ents}]>{root_open}{point}{root_close}').encode()


@pytest.mark.parametrize("parse,doc", [
    (parse_gpx, _laughs("<gpx><trk><trkseg>", '<trkpt lat="1" lon="1"><name>&lol9;</name></trkpt>', "</trkseg></trk></gpx>")),
    (parse_tcx, _laughs("<TrainingCenterDatabase>", "<Trackpoint><Notes>&lol9;</Notes><Position><LatitudeDegrees>1"
                        "</LatitudeDegrees><LongitudeDegrees>1</LongitudeDegrees></Position></Trackpoint>",
                        "</TrainingCenterDatabase>")),
])
def test_billion_laughs_refused(parse, doc):
    t0 = time.monotonic()
    with pytest.raises(CompileError):
        parse(doc)
    assert time.monotonic() - t0 < MAX_S


def test_external_entity_not_read(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("45.5", encoding="utf-8")
    doc = (f'<?xml version="1.0"?><!DOCTYPE g [<!ENTITY x SYSTEM "file://{secret}">]>'
           '<gpx><trk><trkseg><trkpt lat="1" lon="1"><ele>&x;</ele></trkpt></trkseg></trk></gpx>').encode()
    try:
        pts = parse_gpx(doc)
    except CompileError:
        return
    assert pts[0].ele is None


# --- défauts trouvés par le fuzz (non-régression) ------------------------------------------------------

def test_zip_without_first_byte(tmp_path):
    """Fuzz du 28 octobre : un .zip privé de son premier octet levait ValueError (« negative seek value »)."""
    raw = _pack("zip", "trace.gpx", gpx_of([(45.0, 6.0, 300.0)]).encode())[1:]
    path = tmp_path / "trace.gpx.zip"
    path.write_bytes(raw)
    with pytest.raises(CompileError, match="archive .zip corrompue"):
        read_track(path)


@pytest.mark.parametrize("parse,doc", [
    (parse_gpx, '<?xml version="1.0" encoding="UTF--1"?><gpx/>'),
    (parse_tcx, '<?xml version="1.0" encoding="UTF--1"?><TrainingCenterDatabase/>'),
])
def test_unknown_xml_encoding_utf__1(parse, doc):
    """Fuzz du 28 octobre : `encoding="UTF--1"` levait LookupError."""
    with pytest.raises(CompileError, match="illisible"):
        parse(doc.encode())
