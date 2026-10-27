"""Tests unitaires du schéma et du validateur de thèmes (Lot H7, Format .world v1 §9)."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import jsonschema
import pytest

from openride_compiler.cli import main as cli_main
from openride_compiler.theme import (
    DEFAULT_THEME_DIR,
    DEFAULT_THEME_PATH,
    SCHEMA_PATH,
    check_theme,
    resolve_theme,
)


def _make_png(width: int, height: int) -> bytes:
    """Construit un PNG minimal valide de dimensions (width, height) en pur Python."""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw_scanlines = b"".join(b"\x00" + b"\x00\x00\x00" * width for _ in range(height))
    idat = zlib.compress(raw_scanlines)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _make_jpeg_header(width: int, height: int) -> bytes:
    """Construit un en-tête JPEG minimal avec segment SOF0 (0xFFC0) de dimensions (width, height)."""
    sof0_payload = struct.pack(">BHHB", 8, height, width, 1) + b"\x01\x11\x00"
    sof0_seg = b"\xff\xc0" + struct.pack(">H", len(sof0_payload) + 2) + sof0_payload
    return b"\xff\xd8" + sof0_seg + b"\xff\xd9"


def test_contract_section_9_example_validates_against_schema() -> None:
    """Cas 1 : l'exemple complet de world_format_v1.md §9 est valide selon theme.schema.json."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    example = {
        "version": "1.0",
        "name": "Alpes été",
        "terrain": {
            "grass": {"texture": "textures/grass_albedo.png", "color": "#6f9a4a", "scale_m": 6.0},
            "rock": {"texture": "textures/rock_albedo.png", "color": "#9a9488", "scale_m": 12.0},
            "snow": {"texture": None, "color": "#f2f5f8", "scale_m": 8.0},
            "slope_threshold_deg": 22,
            "snow_line_m": 2200,
            "blend_sharpness": 4.0,
        },
        "road": {"texture": "textures/road_albedo.png", "color": "#4a4a4d", "width_m": 6.0},
        "buildings": {
            "walls": ["#d9c9a3", "#e6d8b8", "#cdb48a"],
            "roofs": ["#a65a3a", "#4d535c"],
        },
        "vegetation": {"treeline_m": 2000, "max_density_per_ha": 400},
        "sky": {"sun_elevation_deg": 40, "fog_density": 0.0008},
    }
    jsonschema.validate(instance=example, schema=schema)


def test_default_theme_passes_without_error_or_warning() -> None:
    """Cas 2 : engine/themes/default/theme.json passe check_theme sans erreur ni avertissement."""
    issues = check_theme(DEFAULT_THEME_DIR)
    assert issues == []


def test_minimal_theme_resolves_to_default(tmp_path: Path) -> None:
    """Cas 3 : un thème minimal est valide et resolve_theme produit le défaut (thème 1.2 depuis P1).

    Un thème 1.0 reste valide : seule sa version diffère du défaut, les clés 1.2 viennent du défaut.
    """
    default_data = json.loads(DEFAULT_THEME_PATH.read_text(encoding="utf-8"))
    for version in ("1.0", default_data["version"]):
        (tmp_path / "theme.json").write_text(f'{{"version": "{version}"}}\n', encoding="utf-8")
        assert check_theme(tmp_path) == []
        assert resolve_theme(tmp_path) == {**default_data, "version": version}


@pytest.mark.parametrize("bad_color", ["vert", "#12345", "#1234567", "#GGGGGG"])
def test_malformed_color_is_error(tmp_path: Path, bad_color: str) -> None:
    """Cas 4 : couleur malformée -> error."""
    theme = {"version": "1.0", "road": {"color": bad_color}}
    (tmp_path / "theme.json").write_text(json.dumps(theme), encoding="utf-8")
    issues = check_theme(tmp_path)
    assert any(i.severity == "error" for i in issues)


@pytest.mark.parametrize(
    "payload",
    [
        {"version": "1.0", "terrain": {"grass": {"scale_m": 0}}},
        {"version": "1.0", "terrain": {"grass": {"scale_m": -5}}},
        {"version": "1.0", "terrain": {"slope_threshold_deg": 120}},
        {"version": "1.0", "road": {"width_m": 0}},
        {"version": "1.0", "sky": {"fog_density": -0.1}},
    ],
)
def test_numeric_bounds_violation_is_error(tmp_path: Path, payload: dict) -> None:
    """Cas 5 : scale_m <= 0, slope_threshold_deg > 90, etc. -> error."""
    (tmp_path / "theme.json").write_text(json.dumps(payload), encoding="utf-8")
    issues = check_theme(tmp_path)
    assert any(i.severity == "error" for i in issues)


def test_unsupported_major_version_is_error(tmp_path: Path) -> None:
    """Cas 6 : version "2.0" -> error."""
    (tmp_path / "theme.json").write_text('{"version": "2.0"}', encoding="utf-8")
    issues = check_theme(tmp_path)
    assert any(i.severity == "error" for i in issues)


def test_missing_texture_is_warning_not_error(tmp_path: Path) -> None:
    """Cas 7 : texture référencée mais fichier absent -> warning (pas error)."""
    theme = {
        "version": "1.0",
        "terrain": {"grass": {"texture": "textures/absent.png", "color": "#6f9a4a"}},
    }
    (tmp_path / "theme.json").write_text(json.dumps(theme), encoding="utf-8")
    issues = check_theme(tmp_path)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    assert errors == []
    assert len(warnings) == 1
    assert "absent.png" in warnings[0].message


def test_png_and_jpeg_dimensions_validation(tmp_path: Path) -> None:
    """Cas 8 : PNG 100x100 -> warning ; PNG 64x64 et JPEG 128x128 -> aucun warning."""
    tex_dir = tmp_path / "textures"
    tex_dir.mkdir()

    # 100x100 (non puissance de 2) -> warning
    (tex_dir / "bad.png").write_bytes(_make_png(100, 100))
    theme_bad = {"version": "1.0", "road": {"texture": "textures/bad.png"}}
    (tmp_path / "theme.json").write_text(json.dumps(theme_bad), encoding="utf-8")
    issues_bad = check_theme(tmp_path)
    assert [i for i in issues_bad if i.severity == "error"] == []
    assert len([i for i in issues_bad if i.severity == "warning"]) == 1
    assert "100x100" in issues_bad[0].message

    # 64x64 PNG et 128x128 JPEG -> aucun warning
    (tex_dir / "ok.png").write_bytes(_make_png(64, 64))
    (tex_dir / "ok.jpg").write_bytes(_make_jpeg_header(128, 128))
    theme_ok = {
        "version": "1.0",
        "road": {"texture": "textures/ok.png"},
        "terrain": {"grass": {"texture": "textures/ok.jpg"}},
    }
    (tmp_path / "theme.json").write_text(json.dumps(theme_ok), encoding="utf-8")
    assert check_theme(tmp_path) == []


def test_unknown_key_emits_warning(tmp_path: Path) -> None:
    """Clé inconnue : tolérée par le schéma mais signalée en warning."""
    theme = {"version": "1.0", "custom_future_field": True}
    (tmp_path / "theme.json").write_text(json.dumps(theme), encoding="utf-8")
    issues = check_theme(tmp_path)
    assert [i for i in issues if i.severity == "error"] == []
    assert any(i.severity == "warning" and "custom_future_field" in i.message for i in issues)


def test_cli_theme_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Cas 9 : CLI openride-compiler theme-check renvoie 0 sur default, 1 sur un thème invalide."""
    rc_ok = cli_main(["theme-check", str(DEFAULT_THEME_DIR)])
    assert rc_ok == 0
    assert "valide" in capsys.readouterr().out

    (tmp_path / "theme.json").write_text('{"version": "2.0"}', encoding="utf-8")
    rc_err = cli_main(["theme-check", str(tmp_path)])
    assert rc_err == 1
    assert "erreur" in capsys.readouterr().out
