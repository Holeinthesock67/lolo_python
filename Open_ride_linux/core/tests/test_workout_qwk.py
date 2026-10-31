"""Lot O20 : QWKcode de GoldenCheetah (`.qwk`) lu par `workout_formats.parse_qwk`."""

from __future__ import annotations

from pathlib import Path

import pytest

from openride_core.workout import ERG_MIN_W, ErgController, WorkoutError, load_workout
from openride_core.workout_formats import parse_qwk

SEANCE = """# Séance seuil
10m@130-220
5m@180
4x 5m@280 r3m@140
10m@130
"""


def test_example_session_from_goldencheetah():
    w = parse_qwk(SEANCE, "seuil")
    assert w.name == "Séance seuil"
    assert w.duration_s == pytest.approx(600 + 300 + 4 * 480 + 600)
    kinds = [b.type for b in w.blocks]
    assert kinds == ["ramp", "steady"] + ["interval_on", "interval_off"] * 4 + ["steady"]
    ramp = w.blocks[0]
    assert ramp.absolute and (ramp.start_w, ramp.end_w) == (130, 220)
    assert (w.blocks[2].start_w, w.blocks[3].start_w) == (280, 140)


@pytest.mark.parametrize("line, durations, targets", [
    ("3x 20m@250 r5m@150", [1200, 300] * 3, [(250, 250), (150, 150)] * 3),
    ("8x30s@380r30s@130", [30, 30] * 8, [(380, 380), (130, 130)] * 8),
    ("1m30s@200", [90], [(200, 200)]),
    ("1.5m@200", [90], [(200, 200)]),
    ("1h@150", [3600], [(150, 150)]),
    ("2x 1m@300", [60, 60], [(300, 300)] * 2),
    ("5m@200 r2m@100-80", [300, 120], [(200, 200), (100, 80)]),
    ("10M@120 - 220", [600], [(120, 220)]),
])
def test_watts(line, durations, targets):
    w = parse_qwk(line, "x")
    assert [b.duration_s for b in w.blocks] == durations
    assert [(b.start_w, b.end_w) for b in w.blocks] == targets


def test_percent_of_ftp():
    w = parse_qwk("10m@50-75%\n4x 3m@115% r3m@50%", "x")
    warm = w.blocks[0]
    assert not warm.absolute and (warm.start_frac, warm.end_frac) == (0.5, 0.75)
    assert w.blocks[1].start_frac == pytest.approx(1.15) and w.blocks[2].start_frac == pytest.approx(0.5)
    erg = ErgController(w, 200.0)
    assert erg.target_w == 100


def test_name_comments_and_blank_lines():
    w = parse_qwk("\n# Nom\n\n5m@200   # palier\n# fin\n", "id")
    assert w.name == "Nom" and len(w.blocks) == 1
    assert parse_qwk("5m@200\n# trop tard pour un nom\n", "id").name == "id"


def test_low_watts_follow_erg_floor():
    erg = ErgController(parse_qwk("5m@20", "x"), 250.0)
    assert erg.target_w == ERG_MIN_W


@pytest.mark.parametrize("text, message", [
    ("4x 5m280", "ligne 1 : « 4x 5m280 » ne suit pas la syntaxe"),
    ("5m@200\n20@200", "ligne 2"),
    ("0m@200", "durée nulle"),
    ("0x 5m@200", "0 répétitions"),
    ("101x 1m@200", "101 répétitions"),
    ("5m@2500", "2500 W au-delà"),
    ("5m@350%", "350 % de la FTP au-delà"),
    ("7x 1h@200", "durée maximale"),
    ("# seulement un nom\n", "aucun segment"),
    ("5m@200 r", "ne suit pas la syntaxe"),
])
def test_errors_name_the_line(text, message):
    with pytest.raises(WorkoutError, match=message):
        parse_qwk(text, "x")


def test_load_qwk_file(tmp_path: Path):
    path = tmp_path / "seuil.qwk"
    path.write_bytes(SEANCE.encode("utf-8-sig"))   # BOM accepté, comme les .erg
    w = load_workout(path)
    assert w.id == "seuil" and w.name == "Séance seuil"
