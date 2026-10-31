"""Niveaux de textures et provenance des packs de thème (lot P20) : `theme-pack --levels`, contrôles de
`theme-check` (niveaux, images générées, Gemini ≤ 1 024 px, raccord des images `tileable`), `theme-list`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from openride_compiler.cli import main
from openride_compiler.theme import DEFAULT_THEME_PATH, check_theme
from openride_compiler.theme_packs import list_themes

Image = pytest.importorskip("PIL.Image")


def _png(path: Path, px: int, gradient: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (px, px), (90, 140, 60))
    if gradient:   # dégradé de gauche à droite : bords gauche et droit discordants
        img = Image.linear_gradient("L").rotate(90).resize((px, px)).convert("RGB")
    img.save(path)


def _pack(root: Path, provenance: str | None = None) -> Path:
    theme = json.loads(DEFAULT_THEME_PATH.read_text(encoding="utf-8"))
    theme["name"] = "Niveaux"
    theme["terrain"]["grass"]["texture"] = "textures/herbe.png"
    root.mkdir(parents=True)
    (root / "theme.json").write_text(json.dumps(theme), encoding="utf-8")
    _png(root / "textures" / "herbe.png", 2048)
    if provenance is not None:
        (root / "provenance.toml").write_text(provenance, encoding="utf-8")
    return root


def _errors(theme_dir: Path) -> list[str]:
    return [i.message for i in check_theme(theme_dir) if i.severity == "error"]


CC0 = '''[[image]]
file = "textures/herbe.png"
source = "cc0"
date = "2026-10-30"
url = "https://ambientcg.com/view?id=Grass001"
license = "CC0-1.0"
tileable = false
'''


def test_theme_pack_builds_three_levels_accepted_by_check(tmp_path: Path, capsys) -> None:
    pack = _pack(tmp_path / "pack", CC0)
    assert main(["theme-pack", str(pack), "--levels", "512,1024,2048"]) == 0
    assert "valide" in capsys.readouterr().out
    levels = json.loads((pack / "theme.json").read_text(encoding="utf-8"))["texture_levels"]
    assert [lv["max_px"] for lv in levels] == [512, 1024, 2048]
    for lv in levels:
        with Image.open(pack / lv["dir"] / "textures" / "herbe.png") as im:
            assert im.size == (lv["max_px"], lv["max_px"])
    assert _errors(pack) == []


def test_level_over_max_px_or_with_different_files_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path / "pack", CC0)
    assert main(["theme-pack", str(pack), "--levels", "512,1024"]) == 0
    _png(pack / "levels" / "512" / "textures" / "herbe.png", 1024)
    assert any("plus que 512 px" in e for e in _errors(pack))
    _png(pack / "levels" / "512" / "textures" / "herbe.png", 512)
    _png(pack / "levels" / "1024" / "textures" / "roche.png", 1024)
    assert any("liste d'images différente" in e and "roche.png" in e for e in _errors(pack))


def test_theme_without_levels_is_unchanged(tmp_path: Path) -> None:
    pack = _pack(tmp_path / "pack", CC0)
    issues = check_theme(pack)
    assert issues == []
    assert "texture_levels" not in json.loads((pack / "theme.json").read_text(encoding="utf-8")) \
        or json.loads((pack / "theme.json").read_text(encoding="utf-8"))["texture_levels"] == []


def test_invalid_levels_refused_by_schema(tmp_path: Path) -> None:
    pack = _pack(tmp_path / "pack", CC0)
    theme = json.loads((pack / "theme.json").read_text(encoding="utf-8"))
    for bad in ([{"name": "a", "max_px": 1000, "dir": "x"}], [{"name": "a", "max_px": 512, "dir": "../x"}],
                [{"name": "a", "max_px": 512, "dir": "x"}, {"name": "a", "max_px": 1024, "dir": "y"}]):
        theme["texture_levels"] = bad
        (pack / "theme.json").write_text(json.dumps(theme), encoding="utf-8")
        assert _errors(pack), bad


def test_generated_image_needs_provenance_and_gemini_max_1024(tmp_path: Path) -> None:
    pack = _pack(tmp_path / "pack", CC0)
    _png(pack / "textures" / "gen_panneau_boulangerie_01.png", 1024)
    assert any("gen_panneau_boulangerie_01.png" in e and "sans entrée" in e for e in _errors(pack))
    (pack / "provenance.toml").write_text(CC0 + '''
[[image]]
file = "textures/gen_panneau_boulangerie_01.png"
source = "gemini"
date = "2026-10-30"
prompt = "flat texture, orthographic front view, plain background, bakery sign"
tileable = false
''', encoding="utf-8")
    assert _errors(pack) == []
    _png(pack / "textures" / "gen_panneau_boulangerie_01.png", 2048)
    assert any("Gemini" in e and "2048x2048" in e for e in _errors(pack))


def test_generated_image_without_provenance_file_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path / "pack")
    assert any(i.severity == "warning" and "provenance.toml absent" in i.message for i in check_theme(pack))
    _png(pack / "textures" / "gen_affiche_fete_01.png", 512)
    assert any("provenance.toml absent" in e and "gen_affiche_fete_01.png" in e for e in _errors(pack))


def test_tileable_seam_refused_then_fixed_by_theme_pack(tmp_path: Path) -> None:
    pack = _pack(tmp_path / "pack", CC0.replace("tileable = false", "tileable = true"))
    _png(pack / "textures" / "herbe.png", 256, gradient=True)
    assert any("bords opposés mal raccordés" in e for e in _errors(pack))
    assert main(["theme-pack", str(pack), "--levels", "128,256", "--fix-seams"]) == 0
    assert _errors(pack) == []


def test_theme_pack_refuses_bad_levels(tmp_path: Path) -> None:
    pack = _pack(tmp_path / "pack", CC0)
    assert main(["theme-pack", str(pack), "--levels", "500"]) != 0
    assert main(["theme-pack", str(pack), "--levels", "abc"]) != 0


def test_theme_list_shows_levels(tmp_path: Path) -> None:
    themes = tmp_path / "Themes"
    pack = _pack(themes / "niveaux", CC0)
    assert main(["theme-pack", str(pack), "--levels", "512,1024"]) == 0
    listed = {t["name"]: t for t in list_themes(themes_dir=themes, config_path=tmp_path / "absente.toml")}
    levels = listed["niveaux"]["levels"]
    assert [lv["max_px"] for lv in levels] == [512, 1024]
    assert levels[0]["size_bytes"] > 0 and levels[0]["size_bytes"] < levels[1]["size_bytes"]
