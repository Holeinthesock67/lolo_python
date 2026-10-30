"""Fuzz des lecteurs d'entraînements `.zwo`, `.erg` et `.mrc` (lot X26).

Fichiers valides générés puis abîmés (octets tronqués, morceaux supprimés ou dupliqués, nombres hors
bornes, balises et entités insérées, encodages). Propriété : la lecture rend un entraînement valide ou
lève `WorkoutError`, jamais une autre exception, en moins de 2 s. 200 exemples par lecteur
(`--hypothesis-profile=long` : 5 000, sur le PC).
"""

from __future__ import annotations

import math
import time

import pytest

pytest.importorskip("hypothesis")   # extra dev

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from openride_core.workout import Workout, WorkoutError, load_workout, parse_workout
from openride_core.workout_formats import parse_erg

pytestmark = pytest.mark.fuzz

MAX_S = 2.0
NUMBERS = ["", "-1", "0", "1e309", "-1e309", "nan", "inf", "1e18", "abc", "0x10", "1,5", "٣", " 7 ", "1_000"]
INSERTS = ["<", ">", "&", "&amp;", "&lol;", "]]>", "<!--", "\x00", "\ufeff", "é", "\n", "\t", "[COURSE DATA]",
           "[END COURSE DATA]", "[COURSE TEXT]", "=", '"', "<SteadyState/>", "<workout>", "</workout_file>"]


@st.composite
def zwo_texts(draw) -> str:
    blocks = draw(st.lists(st.sampled_from([
        '<Warmup Duration="{d}" PowerLow="0.4" PowerHigh="0.7"/>',
        '<SteadyState Duration="{d}" Power="{p}"/>',
        '<IntervalsT Repeat="{r}" OnDuration="{d}" OffDuration="60" OnPower="1.1" OffPower="0.5"/>',
        '<Ramp Duration="{d}" PowerLow="0.6" PowerHigh="0.9"/>',
        '<FreeRide Duration="{d}"/>',
        '<Cooldown Duration="{d}" PowerLow="0.7" PowerHigh="0.4"/>',
    ]), min_size=1, max_size=8))
    body = "".join(b.format(d=draw(st.integers(1, 3600)), p=draw(st.floats(0.3, 1.5)).__round__(2),
                            r=draw(st.integers(1, 10))) for b in blocks)
    return ('<?xml version="1.0" encoding="UTF-8"?><workout_file><author>essai</author><name>Essai</name>'
            f'<description>fuzz</description><sportType>bike</sportType><workout>{body}</workout></workout_file>')


@st.composite
def erg_texts(draw, percent: bool) -> str:
    n = draw(st.integers(2, 12))
    t = 0.0
    rows = []
    for _ in range(n):
        rows.append(f"{t:.2f}\t{draw(st.integers(40, 150) if percent else st.integers(50, 600))}")
        t += draw(st.floats(0.0, 20.0))
    unit = "MINUTES PERCENT" if percent else "MINUTES WATTS"
    head = "" if percent else "FTP = 250\n"
    return (f"[COURSE HEADER]\nVERSION = 2\nUNITS = ENGLISH\nDESCRIPTION = essai\n{head}{unit}\n[END COURSE HEADER]\n"
            "[COURSE DATA]\n" + "\n".join(rows) + "\n[END COURSE DATA]\n"
            "[COURSE TEXT]\n60 Allez 5\n[END COURSE TEXT]\n")


@st.composite
def damaged(draw, text: str) -> str:
    """Une à trois retouches au hasard d'un texte valide."""
    for _ in range(draw(st.integers(1, 3))):
        n = len(text)
        kind = draw(st.sampled_from(["tronque", "supprime", "duplique", "nombre", "insere", "balise"]))
        i = draw(st.integers(0, n))
        j = draw(st.integers(i, min(n, i + 80)))
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
                while e < len(text) and (text[e].isdigit() or text[e] == "."):
                    e += 1
                text = text[:k] + draw(st.sampled_from(NUMBERS)) + text[e:]
        elif kind == "insere":
            text = text[:i] + draw(st.sampled_from(INSERTS) | st.text(max_size=20)) + text[i:]
        else:
            tags = [k for k, c in enumerate(text) if c == "<"]
            if tags:
                k = draw(st.sampled_from(tags))
                e = text.find(">", k)
                text = text[:k] + text[e + 1:] if e > 0 else text[:k]
    return text


def check_result(fn, *args) -> None:
    t0 = time.monotonic()
    try:
        w = fn(*args)
    except WorkoutError:
        w = None
    assert time.monotonic() - t0 < MAX_S, "lecture trop lente"
    if w is None:
        return
    assert isinstance(w, Workout) and w.blocks
    for b in w.blocks:
        assert math.isfinite(b.duration_s) and b.duration_s > 0, b
        for v in (b.start_frac, b.end_frac, b.start_w, b.end_w):
            assert v is None or (math.isfinite(v) and v >= 0), b
    for t_s, _text, dur in w.texts:
        assert math.isfinite(t_s) and math.isfinite(dur), (t_s, dur)


FUZZ = settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])


@FUZZ
@given(st.data())
def test_zwo(data):
    check_result(parse_workout, data.draw(damaged(data.draw(zwo_texts()))), "fuzz")


@FUZZ
@given(st.data())
def test_erg(data):
    check_result(lambda t: parse_erg(t, "fuzz", relative=data.draw(st.booleans())),
                 data.draw(damaged(data.draw(erg_texts(False)))))


@FUZZ
@given(st.data())
def test_mrc(data):
    check_result(lambda t: parse_erg(t, "fuzz", percent=True), data.draw(damaged(data.draw(erg_texts(True)))))


@FUZZ
@given(st.data(), st.sampled_from([".zwo", ".erg", ".mrc"]), st.sampled_from(["utf-8", "utf-8-sig", "latin-1", "utf-16"]))
def test_files_and_encodings(tmp_path_factory, data, suffix, encoding):
    text = data.draw(zwo_texts() if suffix == ".zwo" else erg_texts(suffix == ".mrc"))
    raw = data.draw(damaged(text)).encode(encoding, errors="replace")
    if data.draw(st.booleans()):
        raw = raw[: data.draw(st.integers(0, len(raw)))]
    path = tmp_path_factory.mktemp("fuzz") / f"essai{suffix}"
    path.write_bytes(raw)
    check_result(load_workout, path)


# --- XML : aucune entité externe ni expansion ---------------------------------------------------------

BILLION_LAUGHS = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
                  + "".join(f'<!ENTITY lol{i} "{("&lol" + (str(i - 1) if i > 1 else "") + ";") * 10}">' for i in range(1, 10))
                  + ']><workout_file><name>&lol9;</name><workout><SteadyState Duration="60" Power="0.5"/></workout>'
                  '</workout_file>')


def test_billion_laughs_refused():
    t0 = time.monotonic()
    with pytest.raises(WorkoutError):
        parse_workout(BILLION_LAUGHS, "bombe")
    assert time.monotonic() - t0 < MAX_S


def test_external_entity_not_read(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("CONFIDENTIEL", encoding="utf-8")
    text = (f'<?xml version="1.0"?><!DOCTYPE w [<!ENTITY x SYSTEM "file://{secret}">]>'
            '<workout_file><name>&x;</name><workout><SteadyState Duration="60" Power="0.5"/></workout></workout_file>')
    try:
        w = parse_workout(text, "externe")
    except WorkoutError:
        return
    assert "CONFIDENTIEL" not in w.name


# --- défauts trouvés par le fuzz (non-régression) ------------------------------------------------------

ERG_TEXT_1E309 = ("[COURSE HEADER]\nFTP = 250\nMINUTES WATTS\n[END COURSE HEADER]\n[COURSE DATA]\n0.00\t50\n10.00\t50\n"
                  "[END COURSE DATA]\n[COURSE TEXT]\n60 Allez {}\n[END COURSE TEXT]\n")


@pytest.mark.parametrize("dur", ["1e309", "nan", "-5", "0"])
def test_erg_text_duration_1e309(dur):
    """Fuzz du 28 octobre : `60 Allez 1e309` donnait un message de durée infinie."""
    with pytest.raises(WorkoutError, match="durée du message invalide"):
        parse_erg(ERG_TEXT_1E309.format(dur), "fuzz")
    assert parse_erg(ERG_TEXT_1E309.format("5"), "fuzz").texts == ((60.0, "Allez", 5.0),)
    assert parse_erg(ERG_TEXT_1E309.format("tous"), "fuzz").texts == ((60.0, "Allez tous", 10.0),)


def test_zwo_unknown_encoding_utf__1(tmp_path):
    """Encodage déclaré inconnu (défaut des GPX et TCX, fuzz du 28 octobre) : le .zwo est décodé avant
    l'analyse XML, la déclaration est ignorée."""
    path = tmp_path / "essai.zwo"
    path.write_bytes(b'<?xml version="1.0" encoding="UTF--1"?><workout_file><workout>'
                     b'<SteadyState Duration="60" Power="0.5"/></workout></workout_file>')
    assert len(load_workout(path).blocks) == 1
