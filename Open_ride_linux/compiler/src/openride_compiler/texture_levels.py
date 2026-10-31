"""Niveaux de textures et provenance des images d'un pack de thème (lot P20, Format .world v1 §9).

- ``check_levels`` : chaque niveau de ``texture_levels`` (``{name, max_px, dir}``) existe, a la même liste
  d'images que les autres, et chaque image y est au plus de ``max_px`` et en puissance de 2 (erreurs) ;
- ``check_provenance`` : ``provenance.toml`` (``[[image]]`` : ``file``, ``source`` = ``gemini`` ou ``cc0``,
  ``date``, ``prompt`` ou ``url`` et ``license``, ``tileable``) ; une image ``gen_`` sans entrée est refusée,
  une image ``gemini`` de plus de 1 024 px aussi, une image ``tileable`` dont les bords opposés ne se
  raccordent pas aussi ; pack sans ce fichier : avertissement s'il n'a aucune image ``gen_`` ;
- ``build_levels`` (``theme-pack``) : fabrique les niveaux réduits à partir des images de la racine du pack
  (Pillow nécessaire), raccorde au besoin les images ``tileable`` (``fix_seams``) et écrit ``texture_levels``.

Le chemin d'une image dans un niveau est celui qu'elle a à la racine, sous le dossier du niveau
(``levels/1024/textures/herbe.png`` pour ``textures/herbe.png``).
"""

from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path
from typing import Any

from .errors import CompileError

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
PROVENANCE_FILE = "provenance.toml"
GENERATED_PREFIX = "gen_"
GEMINI_MAX_PX = 1024
SEAM_MAX = 0.08            # écart moyen toléré entre bords opposés d'une image `tileable` (0 à 1)
SEAM_BAND = 0.125          # part de l'image fondue près de chaque bord par `fix_seams`
LEVELS_DIR = "levels"
DEFAULT_LEVELS_PX = (512, 1024, 2048)


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _images_under(root: Path, exclude: Path | None = None) -> list[Path]:
    """Images (png, jpg) sous `root`, en chemins relatifs triés, hors du dossier `exclude`."""
    if not root.is_dir():
        return []
    out = []
    for p in root.rglob("*"):
        if p.suffix.lower() not in IMAGE_SUFFIXES or not p.is_file():
            continue
        if exclude is not None and exclude in p.parents:
            continue
        out.append(p.relative_to(root))
    return sorted(out)


def levels_of(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Niveaux bien formés du thème, du plus petit au plus grand (le schéma refuse les autres)."""
    raw = data.get("texture_levels")
    if not isinstance(raw, list):
        return []
    ok = [lv for lv in raw if isinstance(lv, dict) and isinstance(lv.get("dir"), str)
          and isinstance(lv.get("max_px"), int) and isinstance(lv.get("name"), str)]
    return sorted(ok, key=lambda lv: lv["max_px"])


def check_levels(theme_dir: Path, data: dict[str, Any], issues: list[Any], issue_cls: Any) -> None:
    """Contrôle des niveaux (erreurs) : dossier présent, même liste d'images, côté ≤ max_px, puissance de 2."""
    from .theme import read_image_dimensions

    levels = levels_of(data)
    for key in ("name", "max_px"):
        values = [lv[key] for lv in levels]
        if len(set(values)) != len(values):
            issues.append(issue_cls("error", f"texture_levels : {key} en double"))
    reference: tuple[str, list[Path]] | None = None
    for lv in levels:
        d = (theme_dir / lv["dir"]).resolve()
        if not d.is_relative_to(theme_dir.resolve()) or not d.is_dir():
            issues.append(issue_cls("error", f"texture_levels « {lv['name']} » : dossier {lv['dir']} absent"))
            continue
        files = _images_under(d)
        if reference is None:
            reference = (lv["name"], files)
        elif files != reference[1]:
            missing = sorted(set(map(str, reference[1])) ^ set(map(str, files)))
            issues.append(issue_cls("error", f"texture_levels « {lv['name']} » : liste d'images différente de "
                                             f"celle de « {reference[0]} » ({', '.join(missing[:5])})"))
        for rel in files:
            info = read_image_dimensions(d / rel)
            if info is None:
                issues.append(issue_cls("error", f"texture_levels « {lv['name']} » : {rel} n'est pas un PNG ou JPEG valide"))
                continue
            _, w, h = info
            if max(w, h) > lv["max_px"]:
                issues.append(issue_cls("error", f"texture_levels « {lv['name']} » : {rel} fait {w}x{h}, "
                                                 f"plus que {lv['max_px']} px"))
            elif not (_is_power_of_two(w) and _is_power_of_two(h)):
                issues.append(issue_cls("error", f"texture_levels « {lv['name']} » : {rel} fait {w}x{h}, "
                                                 "pas en puissances de 2"))


def read_provenance(theme_dir: Path) -> dict[str, dict[str, Any]] | None:
    """Entrées de `provenance.toml` par chemin d'image ; None sans fichier ; CompileError s'il est illisible."""
    path = theme_dir / PROVENANCE_FILE
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CompileError(f"{PROVENANCE_FILE} illisible : {exc}") from exc
    entries = data.get("image", [])
    if not isinstance(entries, list):
        raise CompileError(f"{PROVENANCE_FILE} : [[image]] attendu")
    return {str(e.get("file", "")): e for e in entries if isinstance(e, dict)}


def _pack_images(theme_dir: Path, data: dict[str, Any]) -> list[tuple[Path, str]]:
    """Toutes les images du pack : (chemin complet, chemin de référence) ; une copie de niveau a pour
    référence son chemin à la racine."""
    out: list[tuple[Path, str]] = []
    level_dirs = [(theme_dir / lv["dir"]).resolve() for lv in levels_of(data)]
    for rel in _images_under(theme_dir):
        full = (theme_dir / rel).resolve()
        ref = rel.as_posix()
        for d in level_dirs:
            if d in full.parents:
                ref = full.relative_to(d).as_posix()
                break
        out.append((full, ref))
    return out


def _pillow() -> Any:
    try:
        from PIL import Image
    except ImportError:
        return None
    return Image


def seam_error(path: Path) -> float | None:
    """Écart moyen (0 à 1) entre la première et la dernière colonne, puis ligne, de l'image ; None sans Pillow."""
    image_mod = _pillow()
    if image_mod is None:
        return None
    import numpy as np

    with image_mod.open(path) as im:
        a = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    return float((np.abs(a[:, 0] - a[:, -1]).mean() + np.abs(a[0] - a[-1]).mean()) / 2.0)


def check_provenance(theme_dir: Path, data: dict[str, Any], issues: list[Any], issue_cls: Any) -> None:
    """Contrôle de `provenance.toml` (règles du lot P20, décision du propriétaire du 26 octobre)."""
    from .theme import read_image_dimensions

    images = _pack_images(theme_dir, data)
    try:
        prov = read_provenance(theme_dir)
    except CompileError as exc:
        issues.append(issue_cls("error", str(exc)))
        return
    generated = [ref for _, ref in images if Path(ref).name.startswith(GENERATED_PREFIX)]
    if prov is None:
        if generated:
            issues.append(issue_cls("error", f"{PROVENANCE_FILE} absent : images générées sans provenance "
                                             f"({', '.join(sorted(set(generated))[:5])})"))
        elif images:
            issues.append(issue_cls("warning", f"{PROVENANCE_FILE} absent : provenance des images non déclarée"))
        return
    seam_skipped = False
    for full, ref in images:
        entry = prov.get(ref)
        if entry is None:
            if Path(ref).name.startswith(GENERATED_PREFIX):
                issues.append(issue_cls("error", f"{ref} : image générée sans entrée dans {PROVENANCE_FILE}"))
            continue
        source = entry.get("source")
        if source not in ("gemini", "cc0"):
            issues.append(issue_cls("error", f"{ref} : source « {source} » inconnue (gemini ou cc0)"))
        if source == "gemini":
            info = read_image_dimensions(full)
            if info is not None and max(info[1], info[2]) > GEMINI_MAX_PX:
                issues.append(issue_cls("error", f"{ref} : image Gemini de {info[1]}x{info[2]}, "
                                                 f"plus que {GEMINI_MAX_PX} px"))
        if entry.get("tileable") is True:
            err = seam_error(full)
            if err is None:
                seam_skipped = True
            elif err > SEAM_MAX:
                issues.append(issue_cls("error", f"{ref} : bords opposés mal raccordés (écart {err:.2f}, "
                                                 f"au plus {SEAM_MAX}) ; theme-pack --fix-seams les fond"))
    if seam_skipped:
        issues.append(issue_cls("warning", "raccord des images tileable non contrôlé : Pillow absent"))


def fix_seams(path: Path) -> None:
    """Fond chaque bord avec le bord opposé sur SEAM_BAND de l'image : bords opposés identiques."""
    image_mod = _pillow()
    if image_mod is None:
        raise CompileError("--fix-seams demande Pillow (pip install Pillow)")
    import numpy as np

    with image_mod.open(path) as im:
        mode = im.mode
        a = np.asarray(im.convert("RGBA"), dtype=np.float32)
    for axis in (1, 0):
        n = a.shape[axis]
        band = max(1, int(n * SEAM_BAND))
        b = a.copy()
        for i in range(band):
            w = 0.5 * (1.0 - i / band)       # 0,5 au bord : les deux bords prennent la même moyenne
            near = np.take(a, i, axis=axis)
            far = np.take(a, n - 1 - i, axis=axis)
            idx_near = [slice(None)] * 3
            idx_far = [slice(None)] * 3
            idx_near[axis] = i
            idx_far[axis] = n - 1 - i
            b[tuple(idx_near)] = (1.0 - w) * near + w * far
            b[tuple(idx_far)] = (1.0 - w) * far + w * near
        a = b
    out = image_mod.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), "RGBA")
    if mode != "RGBA":
        out = out.convert("RGB" if path.suffix.lower() in (".jpg", ".jpeg") else mode)
    _save(out, path)


def _save(image: Any, path: Path) -> None:
    if path.suffix.lower() in (".jpg", ".jpeg"):
        image.convert("RGB").save(path, quality=92)
    else:
        image.save(path)


def build_levels(theme_dir: Path, sizes: tuple[int, ...] = DEFAULT_LEVELS_PX,
                 seams: bool = False) -> list[dict[str, Any]]:
    """Fabrique `levels/<px>/` pour chaque côté de `sizes` à partir des images de la racine du pack (jamais
    agrandies), écrit `texture_levels` dans `theme.json` et renvoie les niveaux. `seams` : images `tileable`
    de `provenance.toml` raccordées d'abord (à la racine)."""
    image_mod = _pillow()
    if image_mod is None:
        raise CompileError("theme-pack demande Pillow (pip install Pillow)")
    theme_file = theme_dir / "theme.json"
    if not theme_file.is_file():
        raise CompileError(f"theme.json absent dans {theme_dir}")
    if not sizes or any(not _is_power_of_two(px) or not 64 <= px <= 8192 for px in sizes):
        raise CompileError(f"niveaux invalides : {', '.join(map(str, sizes))} (puissances de 2 de 64 à 8 192)")
    data = json.loads(theme_file.read_text(encoding="utf-8"))
    sources = _images_under(theme_dir, exclude=(theme_dir / LEVELS_DIR))
    if not sources:
        raise CompileError(f"aucune image à la racine de {theme_dir}")
    if seams:
        prov = read_provenance(theme_dir) or {}
        for rel in sources:
            if prov.get(rel.as_posix(), {}).get("tileable") is True:
                fix_seams(theme_dir / rel)
    shutil.rmtree(theme_dir / LEVELS_DIR, ignore_errors=True)
    levels = []
    for px in sorted(set(sizes)):
        level_dir = theme_dir / LEVELS_DIR / str(px)
        for rel in sources:
            dest = level_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with image_mod.open(theme_dir / rel) as im:
                w, h = im.size
                scale = min(1.0, px / max(w, h))
                size = (_pow2_floor(max(1, int(w * scale))), _pow2_floor(max(1, int(h * scale))))
                out = im.resize(size, image_mod.Resampling.LANCZOS) if size != (w, h) else im.copy()
            _save(out, dest)
        levels.append({"name": f"{px} px", "max_px": px, "dir": f"{LEVELS_DIR}/{px}"})
    data["texture_levels"] = levels
    theme_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return levels


def _pow2_floor(n: int) -> int:
    return 1 << (n.bit_length() - 1)


def level_sizes(theme_dir: Path, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Pour `theme-list` : [{name, max_px, size_bytes}] de chaque niveau."""
    out = []
    for lv in levels_of(data):
        d = theme_dir / lv["dir"]
        size = sum(p.stat().st_size for p in d.rglob("*") if p.is_file()) if d.is_dir() else 0
        out.append({"name": lv["name"], "max_px": lv["max_px"], "size_bytes": size})
    return out
