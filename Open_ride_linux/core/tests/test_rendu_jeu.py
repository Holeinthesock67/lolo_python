"""Rendu des essais = rendu du jeu (03/11).

Le jeu dessine en Forward+ (``engine/project.godot``) ; les essais qui rendent une image (tests de rendu, bancs,
captures, vitrines, CI) aussi, avec les arguments de ``engine/tests/rendu_jeu.py``. Ce test refuse le retour
d'un lanceur d'essai en Compatibility (OpenGL), moteur qui affichait les couleurs autrement que le jeu.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENGINE = REPO / "engine"
spec = importlib.util.spec_from_file_location("rendu_jeu", ENGINE / "tests" / "rendu_jeu.py")
rendu_jeu = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(rendu_jeu)

COMPAT = re.compile(r"gl_compatibility|--rendering-driver[\"', ]+opengl3")
SOURCES = (".py", ".sh", ".gd", ".yml", ".toml")


def test_projet_en_forward_plus() -> None:
    project = (ENGINE / "project.godot").read_text(encoding="utf-8")
    assert f'renderer/rendering_method="{rendu_jeu.RENDERING_METHOD}"' in project


def test_aucun_essai_en_compatibility() -> None:
    roots = [ENGINE, REPO / "core" / "src", REPO / "scripts", REPO.parent / ".github"]
    bad = []
    for root in roots:
        for f in root.rglob("*"):
            if f.suffix in SOURCES and f.is_file() and f.name != "test_rendu_jeu.py":
                text = f.read_text(encoding="utf-8", errors="replace")
                if COMPAT.search(text):
                    bad.append(str(f.relative_to(REPO.parent)))
    assert bad == [], f"essais en Compatibility (utiliser engine/tests/rendu_jeu.py) : {bad}"


def test_arguments_communs() -> None:
    assert rendu_jeu.godot_cmd(["godot"], True, 800, 600) == ["godot"] + rendu_jeu.GODOT_ARGS
    cmd = rendu_jeu.godot_cmd(["godot"], False, 800, 600)
    assert cmd[:4] == ["xvfb-run", "-a", "-s", "-screen 0 800x600x24"]
    assert cmd[-4:] == ["--rendering-driver", "vulkan", "--rendering-method", "forward_plus"]


def test_journal_forward_plus() -> None:
    ok = "Godot Engine v4.7.2\nVulkan 1.4.318 - Forward+ - Using Device #0: NVIDIA GeForce GTX 1060\n"
    assert rendu_jeu.check_log(ok) is None


def test_journal_repli_opengl_refuse() -> None:
    repli = ("WARNING: Your video card drivers seem not to support the required Vulkan version, switching to OpenGL 3.\n"
             "OpenGL API 4.5 (Core Profile) Mesa 25.2.8 - Compatibility - Using Device: Mesa - llvmpipe\n")
    assert "Compatibility" in (rendu_jeu.check_log(repli) or "")
    assert rendu_jeu.check_log("Godot Engine v4.7.2\n") is not None


# --- Règle des couleurs (engine/shaders/couleur_srgb.gdshaderinc) ---------------------------------------------

INCLUDE = re.compile(r'#include\s+"res://([^"]+)"')


def _shaders() -> dict[str, str]:
    files = list(ENGINE.joinpath("shaders").glob("*.gdshader*")) + list(ENGINE.joinpath("scripts").rglob("*.gdshader*"))
    return {str(f.relative_to(ENGINE)): f.read_text(encoding="utf-8") for f in files if not f.name.endswith(".uid")}


def _uses_rule(name: str, shaders: dict[str, str], seen: set[str] | None = None) -> bool:
    """Le shader inclut couleur_srgb.gdshaderinc, directement ou par un de ses includes."""
    seen = seen or set()
    if name in seen or name not in shaders:
        return False
    seen.add(name)
    for inc in INCLUDE.findall(shaders[name]):
        if inc == "shaders/couleur_srgb.gdshaderinc" or _uses_rule(inc, shaders, seen):
            return True
    return False


def _strip_comments(code: str) -> str:
    return re.sub(r"//[^\n]*", "", code)


def test_couleur_de_sommet_convertie() -> None:
    """Un shader 3D qui lit COLOR.rgb (couleur de sommet ou d'instance, sRGB) suit la règle de couleur_srgb."""
    shaders = _shaders()
    bad = []
    for name, code in shaders.items():
        body = _strip_comments(code)
        if "shader_type canvas_item" in body or "shader_type sky" in body:
            continue   # COLOR y est la sortie de l'écran ou du ciel, pas une couleur écrite
        if "COLOR.rgb" in body and not _uses_rule(name, shaders):
            bad.append(name)
    assert bad == [], f"COLOR.rgb lu sans couleur_srgb.gdshaderinc : {bad}"


def test_une_seule_conversion() -> None:
    """Pas de conversion sRGB maison (pow 2.2, formule par moteur) hors de couleur_srgb.gdshaderinc."""
    bad = [n for n, code in _shaders().items() if n != "shaders/couleur_srgb.gdshaderinc"
           and re.search(r"pow\([^;]*2\.2\)|CURRENT_RENDERER", _strip_comments(code))]
    assert bad == [], f"conversion de couleur hors de couleur_srgb.gdshaderinc : {bad}"


def test_standard_material_couleurs_de_sommet_srgb() -> None:
    """StandardMaterial3D à couleurs de sommet : vertex_color_is_srgb posé sur le même matériau."""
    bad = []
    for f in ENGINE.joinpath("scripts").rglob("*.gd"):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"(\w+)\.vertex_color_use_as_albedo = true", text):
            if f"{m.group(1)}.vertex_color_is_srgb = true" not in text:
                bad.append(f"{f.relative_to(ENGINE)} ({m.group(1)})")
    assert bad == [], f"couleurs de sommet lues comme linéaires : {bad}"
