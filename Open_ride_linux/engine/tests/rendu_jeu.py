"""Rendu des essais = rendu du jeu.

Le jeu dessine en Forward+ sur Vulkan (``engine/project.godot``). Les tests, bancs et captures dessinent avec le
même moteur de rendu, sur l'écran réel (``--native``) comme sous Xvfb (au cloud et en CI : Vulkan logiciel de
Mesa, paquet ``mesa-vulkan-drivers``). Avant le 03/11, les essais sous Xvfb passaient en Compatibility (OpenGL) :
ciel de secours, pas de SSAO, de lueur ni de brouillard volumétrique, et surtout couleurs de sommet converties de
sRGB en linéaire par ce seul moteur ; le gravier, juste au cloud, sortait pâle et bleuté sur le PC.

Godot repasse en silence sur OpenGL quand Vulkan manque : ``check_log`` refuse alors l'essai au lieu de
laisser passer des captures qui ne ressemblent pas au jeu.
"""
from __future__ import annotations

import re
from pathlib import Path

RENDERING_DRIVER = "vulkan"
RENDERING_METHOD = "forward_plus"
# Arguments Godot de tous les essais (le jeu n'en passe aucun : Forward+ est le réglage du projet).
GODOT_ARGS = ["--rendering-driver", RENDERING_DRIVER, "--rendering-method", RENDERING_METHOD]
# Ligne d'en-tête de Godot : « Vulkan 1.4.318 - Forward+ - Using Device #0: … »
_FORWARD_PLUS = re.compile(r"^Vulkan [0-9.]+ - Forward\+ - ", re.M)
_FALLBACK = re.compile(r"- Compatibility - |switching to OpenGL", re.M)
# Vulkan logiciel de Mesa (cloud, CI) : la scène complète tourne à 1 à 3 images/s, contre 60 sur le PC.
_SOFTWARE = re.compile(r"^Vulkan [0-9.]+ - Forward\+ - .*llvmpipe", re.M)
SOFTWARE_SLOWDOWN = 10.0
# Pilote Vulkan logiciel de Mesa (lavapipe, rendu llvmpipe) : celui de la CI, qui a fait les références xvfb/ des
# tests graphiques. Sous Xvfb, le PC prendrait sinon la carte NVIDIA (SSIM 0,959 à 0,966 sur main, 8/11).
LAVAPIPE_ICD_DIRS = ("/usr/share/vulkan/icd.d", "/usr/local/share/vulkan/icd.d", "/etc/vulkan/icd.d")


def xvfb_cmd(cmd: list[str], width: int, height: int) -> list[str]:
    """``cmd`` (Godot et ses arguments avant ``--``) lancé sous Xvfb, avec le moteur de rendu du jeu."""
    return ["xvfb-run", "-a", "-s", f"-screen 0 {width}x{height}x24"] + cmd + GODOT_ARGS


def godot_cmd(cmd: list[str], native: bool, width: int, height: int) -> list[str]:
    """Écran réel (``native``) ou Xvfb ; dans les deux cas le moteur de rendu du jeu."""
    return cmd + GODOT_ARGS if native else xvfb_cmd(cmd, width, height)


def check_log(text: str) -> str | None:
    """None si Godot a bien rendu en Forward+ ; sinon la raison (repli OpenGL, ligne absente)."""
    if _FALLBACK.search(text):
        return "Godot est repassé en Compatibility (OpenGL) : Vulkan absent (installer mesa-vulkan-drivers)"
    if not _FORWARD_PLUS.search(text):
        return "ligne « Vulkan … - Forward+ - » absente du journal de Godot"
    return None


def software_vulkan_env() -> dict[str, str] | None:
    """Variables d'environnement qui imposent lavapipe à Vulkan (Godot ne voit alors que llvmpipe) ; None si le
    pilote manque (paquet mesa-vulkan-drivers)."""
    for d in LAVAPIPE_ICD_DIRS:
        for icd in sorted(Path(d).glob("lvp_icd*.json")):
            return {"VK_DRIVER_FILES": str(icd), "VK_ICD_FILENAMES": str(icd)}
    return None


def is_software(text: str) -> bool:
    """Vrai si le journal de Godot montre un rendu Forward+ sur Vulkan logiciel (llvmpipe)."""
    return bool(_SOFTWARE.search(text))


def slowdown(text: str) -> float:
    """Facteur des attentes d'un essai : SOFTWARE_SLOWDOWN sous Vulkan logiciel (llvmpipe), 1 sur un vrai GPU."""
    return SOFTWARE_SLOWDOWN if is_software(text) else 1.0
