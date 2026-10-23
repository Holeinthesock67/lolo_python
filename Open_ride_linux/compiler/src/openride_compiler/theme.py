"""Validation et résolution des thèmes visuels OpenRide (Lot H7, Format .world v1 §9).

- ``check_theme(theme_dir)`` : valide ``theme.json`` contre ``theme.schema.json`` (erreurs)
  et contrôle les textures ainsi que les clés inconnues (avertissements).
- ``resolve_theme(theme_dir)`` : fusionne récursivement ``theme.json`` avec le thème par
  défaut ``engine/themes/default/theme.json`` (source unique des valeurs par défaut).
"""

from __future__ import annotations

import copy
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "docs" / "contracts" / "world" / "theme.schema.json"
DEFAULT_THEME_DIR = REPO_ROOT / "engine" / "themes" / "default"
DEFAULT_THEME_PATH = DEFAULT_THEME_DIR / "theme.json"

PNG_SIG = b"\x89PNG\r\n\x1a\n"
JPEG_SOF_MARKERS = frozenset({
    0xC0, 0xC1, 0xC2, 0xC3,
    0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB,
    0xCD, 0xCE, 0xCF,
})


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    message: str


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def read_image_dimensions(path: Path) -> tuple[str, int, int] | None:
    """Lit le format ('png' ou 'jpeg') et les dimensions (largeur, hauteur) en pur Python."""
    try:
        data = path.read_bytes()
    except OSError:
        return None

    # PNG : signature 8 octets + longueur (4) + 'IHDR' (4) + width (4) + height (4)
    if len(data) >= 24 and data[:8] == PNG_SIG and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        if width > 0 and height > 0:
            return ("png", width, height)
        return None

    # JPEG : SOI 0xFFD8 puis segments 0xFF <marker> <len:2> ...
    if len(data) >= 4 and data[:2] == b"\xff\xd8":
        idx = 2
        n = len(data)
        while idx < n:
            while idx < n and data[idx] != 0xFF:
                idx += 1
            while idx < n and data[idx] == 0xFF:
                idx += 1
            if idx >= n:
                break
            marker = data[idx]
            idx += 1
            if marker in (0xD8, 0xD9, 0x01) or (0xD0 <= marker <= 0xD7):
                continue
            if idx + 2 > n:
                return None
            seg_len = struct.unpack(">H", data[idx:idx + 2])[0]
            if seg_len < 2 or idx + seg_len > n:
                return None
            if marker in JPEG_SOF_MARKERS:
                if seg_len < 7:
                    return None
                height, width = struct.unpack(">HH", data[idx + 3:idx + 7])
                if width > 0 and height > 0:
                    return ("jpeg", width, height)
                return None
            idx += seg_len
    return None


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_default_theme() -> dict[str, Any]:
    return json.loads(DEFAULT_THEME_PATH.read_text(encoding="utf-8"))


def _warn_unknown_keys(
    data: dict[str, Any],
    reference: dict[str, Any],
    prefix: str,
    issues: list[Issue],
) -> None:
    for key, val in data.items():
        path_key = f"{prefix}.{key}" if prefix else key
        if key not in reference:
            issues.append(Issue("warning", f"clé inconnue ignorée : {path_key}"))
            continue
        ref_val = reference[key]
        if isinstance(val, dict) and isinstance(ref_val, dict):
            _warn_unknown_keys(val, ref_val, path_key, issues)


def _check_texture_field(
    theme_dir: Path,
    field_name: str,
    tex_value: Any,
    issues: list[Issue],
) -> None:
    if tex_value is None or not isinstance(tex_value, str):
        return
    if not tex_value.strip():
        issues.append(Issue("warning", f"{field_name} : chemin de texture vide"))
        return

    tex_path = (theme_dir / tex_value).resolve()
    try:
        tex_path.relative_to(theme_dir.resolve())
    except ValueError:
        issues.append(Issue("warning", f"{field_name} : texture hors du dossier du thème ({tex_value})"))
        return

    if not tex_path.is_file():
        issues.append(
            Issue(
                "warning",
                f"{field_name} : fichier texture absent ({tex_value}), repli sur la couleur unie",
            )
        )
        return

    info = read_image_dimensions(tex_path)
    if info is None:
        issues.append(
            Issue(
                "warning",
                f"{field_name} : fichier texture ({tex_value}) n'est pas un PNG ou JPEG valide",
            )
        )
        return

    _, width, height = info
    if not (_is_power_of_two(width) and _is_power_of_two(height)):
        issues.append(
            Issue(
                "warning",
                f"{field_name} : dimensions {width}x{height} non puissances de 2 ({tex_value})",
            )
        )


def check_theme(theme_dir: Path) -> list[Issue]:
    """Vérifie un dossier de thème et renvoie la liste des erreurs et avertissements."""
    theme_dir = Path(theme_dir)
    issues: list[Issue] = []

    if not theme_dir.is_dir():
        return [Issue("error", f"dossier de thème introuvable : {theme_dir}")]

    theme_file = theme_dir / "theme.json"
    if not theme_file.is_file():
        return [Issue("error", f"theme.json absent dans {theme_dir}")]

    try:
        data = json.loads(theme_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [Issue("error", f"theme.json illisible : {exc}")]

    if not isinstance(data, dict):
        return [Issue("error", "theme.json doit contenir un objet JSON")]

    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        loc = ".".join(str(p) for p in err.absolute_path) or "<racine>"
        issues.append(Issue("error", f"{loc} : {err.message}"))

    default_theme = _load_default_theme()
    _warn_unknown_keys(data, default_theme, "", issues)

    # Contrôle des textures référencées
    terrain = data.get("terrain")
    if isinstance(terrain, dict):
        for layer_name in ("grass", "rock", "snow"):
            layer = terrain.get(layer_name)
            if isinstance(layer, dict) and "texture" in layer:
                _check_texture_field(
                    theme_dir,
                    f"terrain.{layer_name}.texture",
                    layer.get("texture"),
                    issues,
                )

    road = data.get("road")
    if isinstance(road, dict) and "texture" in road:
        _check_texture_field(theme_dir, "road.texture", road.get("texture"), issues)

    return issues


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def resolve_theme(theme_dir: Path) -> dict[str, Any]:
    """Fusionne récursivement theme.json avec engine/themes/default/theme.json."""
    theme_dir = Path(theme_dir)
    issues = check_theme(theme_dir)
    errors = [iss for iss in issues if iss.severity == "error"]
    if errors:
        raise ValueError(f"Thème invalide ({theme_dir}) : {errors[0].message}")

    default_theme = _load_default_theme()
    user_theme = json.loads((theme_dir / "theme.json").read_text(encoding="utf-8"))
    return _deep_merge(default_theme, user_theme)
