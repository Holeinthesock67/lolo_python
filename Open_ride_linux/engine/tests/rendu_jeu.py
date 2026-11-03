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

RENDERING_DRIVER = "vulkan"
RENDERING_METHOD = "forward_plus"
# Arguments Godot de tous les essais (le jeu n'en passe aucun : Forward+ est le réglage du projet).
GODOT_ARGS = ["--rendering-driver", RENDERING_DRIVER, "--rendering-method", RENDERING_METHOD]
# Ligne d'en-tête de Godot : « Vulkan 1.4.318 - Forward+ - Using Device #0: … »
_FORWARD_PLUS = re.compile(r"^Vulkan [0-9.]+ - Forward\+ - ", re.M)
_FALLBACK = re.compile(r"- Compatibility - |switching to OpenGL", re.M)


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
