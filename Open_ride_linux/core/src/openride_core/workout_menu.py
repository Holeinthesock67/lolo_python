"""Entraînements créés ou importés depuis le menu ERG (lot N16, décision D4 de l'audit IPC du 26 octobre).

Le core reste seul à écrire dans le dossier des entraînements (contrat IPC §4) : l'engine envoie les
paramètres d'un entraînement par intervalles (`create_workout`) ou choisit un fichier dans la liste
que le core lui a donnée (`list_imports`, puis `import_workout`).

- `build_interval_zwo()` : fichier `.zwo` (Warmup, IntervalsT, Cooldown, en % de la FTP) ; mêmes
  paramètres, même fichier ; nom déjà pris par d'autres réglages : suffixe `_2`, `_3`… (lot O20).
- `import_candidates()` : fichiers `.zwo`, `.erg`, `.mrc` et `.qwk` des dossiers habituels, sans
  sous-dossiers, les plus récents d'abord (30 au plus).
- `import_file()` : copie validée (le core relit le fichier avant de l'écrire) ; un fichier identique
  déjà importé n'est pas recopié, un entraînement différent du même nom prend le suffixe `_2`, `_3`…

Module pur (fichiers seulement) : session.py le branche sur l'IPC.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from .workout import WORKOUT_SUFFIXES, WorkoutError, load_workout, parse_workout

# Bornes des paramètres de `create_workout` (mêmes que l'écran « Créer un entraînement » de l'engine).
INTERVAL_PARAMS: dict[str, tuple[int, int]] = {
    "warmup_min": (0, 30),
    "reps": (1, 20),
    "on_s": (15, 1200),
    "on_pct": (50, 200),
    "off_s": (15, 1200),
    "off_pct": (30, 100),
    "cooldown_min": (0, 30),
}

# Dossiers proposés à l'import, relatifs au dossier personnel, avec le nom affiché.
IMPORT_SOURCES: tuple[tuple[str, str], ...] = (
    ("Téléchargements", "Téléchargements"), ("Downloads", "Téléchargements"), ("Bureau", "Bureau"),
    ("Desktop", "Bureau"), ("OpenRide/Import", "OpenRide/Import"), ("", "Dossier personnel"),
)
MAX_IMPORT_CANDIDATES = 30
MAX_IMPORT_BYTES = 1_000_000   # un entraînement fait quelques kilo-octets


class WorkoutMenuError(Exception):
    """Refus d'une création ou d'un import : `code` est le code d'erreur IPC à renvoyer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def check_interval_params(args: Any) -> dict[str, int]:
    """Paramètres entiers dans leurs bornes ; sinon `bad_args`."""
    if not isinstance(args, dict):
        raise WorkoutMenuError("bad_args", "create_workout attend un objet de paramètres")
    out: dict[str, int] = {}
    for key, (lo, hi) in INTERVAL_PARAMS.items():
        val = args.get(key)
        if isinstance(val, bool) or not isinstance(val, int) or not lo <= val <= hi:
            raise WorkoutMenuError("bad_args", f"create_workout : « {key} » doit être un entier de {lo} à {hi}")
        out[key] = val
    return out


def _duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    if m == 0:
        return f"{s} s"
    return f"{m} min" if s == 0 else f"{m} min {s} s"


def interval_id(p: dict[str, int]) -> str:
    return f"intervalles_{p['reps']}x{p['on_s']}s_{p['on_pct']}"


def interval_name(p: dict[str, int]) -> str:
    return f"Intervalles {p['reps']} × {_duration(p['on_s'])} à {p['on_pct']} %"


def build_interval_zwo(p: dict[str, int]) -> str:
    lines = [
        "<workout_file>",
        "  <author>OpenRide</author>",
        f"  <name>{interval_name(p)}</name>",
        "  <description>Créé dans le menu d'OpenRide.</description>",
        "  <sportType>bike</sportType>",
        "  <workout>",
    ]
    if p["warmup_min"] > 0:
        lines.append(f'    <Warmup Duration="{p["warmup_min"] * 60}" PowerLow="0.50" PowerHigh="0.75"/>')
    lines.append(f'    <IntervalsT Repeat="{p["reps"]}" OnDuration="{p["on_s"]}" OffDuration="{p["off_s"]}" '
                 f'OnPower="{p["on_pct"] / 100:.2f}" OffPower="{p["off_pct"] / 100:.2f}"/>')
    if p["cooldown_min"] > 0:
        lines.append(f'    <Cooldown Duration="{p["cooldown_min"] * 60}" PowerLow="0.65" PowerHigh="0.45"/>')
    lines += ["  </workout>", "</workout_file>", ""]
    return "\n".join(lines)


def _write(path: Path, data: bytes) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except OSError as exc:
        raise WorkoutMenuError("workout_write_failed", f"écriture impossible : {exc}") from exc


def create_interval_workout(workouts_dir: Path, args: Any) -> dict[str, Any]:
    """Écrit `<dossier>/intervalles_….zwo` ; renvoie {workout_id, name, created}.

    Mêmes réglages qu'un fichier existant : rien n'est écrit. Même nom mais réglages différents
    (récupération, échauffement…) : suffixe `_2`, `_3`…, comme à l'import (lot O20) ; aucun
    entraînement n'est remplacé."""
    p = check_interval_params(args)
    text = build_interval_zwo(p)
    parse_workout(text, interval_id(p))   # le fichier produit doit rester lisible par le core
    workout_id, created = _store(workouts_dir, interval_id(p), ".zwo", text.encode("utf-8"))
    return {"workout_id": workout_id, "name": interval_name(p), "created": created}


def _store(workouts_dir: Path, stem: str, suffix: str, data: bytes) -> tuple[str, bool]:
    """Range `data` sous `<stem><suffix>` sans écraser un autre entraînement : contenu identique
    déjà présent, rien n'est écrit ; nom pris, suffixe `_2`, `_3`… Renvoie (identifiant, écrit)."""
    digest = hashlib.sha256(data).digest()
    taken = _ids_taken(workouts_dir)
    workout_id, n = stem, 1
    while True:
        target = workouts_dir / f"{workout_id}{suffix}"
        if target.is_file() and hashlib.sha256(target.read_bytes()).digest() == digest:
            return workout_id, False
        if workout_id not in taken:
            break
        n += 1
        workout_id = f"{stem}_{n}"
    _write(workouts_dir / f"{workout_id}{suffix}", data)
    return workout_id, True


def _ids_taken(workouts_dir: Path) -> set[str]:
    if not workouts_dir.is_dir():
        return set()
    return {f.stem for f in workouts_dir.iterdir() if f.suffix.lower() in WORKOUT_SUFFIXES}


def import_candidates(home: Path, workouts_dir: Path) -> list[dict[str, Any]]:
    """Fichiers importables : [{path, file, source, imported}], les plus récents d'abord."""
    found: list[tuple[float, dict[str, Any]]] = []
    seen: set[Path] = set()
    taken = _ids_taken(workouts_dir)
    for rel, label in IMPORT_SOURCES:
        directory = home / rel if rel else home
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for f in entries:
            if f.suffix.lower() not in WORKOUT_SUFFIXES or f in seen or not f.is_file():
                continue
            seen.add(f)
            found.append((f.stat().st_mtime, {"path": str(f), "file": f.name, "source": label,
                                               "imported": f.stem in taken}))
    found.sort(key=lambda t: (-t[0], t[1]["file"]))
    return [item for _, item in found[:MAX_IMPORT_CANDIDATES]]


def import_file(src: Path, workouts_dir: Path) -> dict[str, Any]:
    """Copie validée de `src` ; renvoie {workout_id, name, created}."""
    suffix = src.suffix.lower()
    if suffix not in WORKOUT_SUFFIXES:
        raise WorkoutMenuError("workout_invalid", f"{src.name} : format inconnu")
    try:
        if src.stat().st_size > MAX_IMPORT_BYTES:
            raise WorkoutMenuError("workout_invalid", f"{src.name} : fichier trop gros")
        data = src.read_bytes()
        workout = load_workout(src)
    except OSError as exc:
        raise WorkoutMenuError("workout_invalid", f"{src.name} illisible : {exc}") from exc
    except WorkoutError as exc:
        raise WorkoutMenuError("workout_invalid", str(exc)) from exc
    workout_id, created = _store(workouts_dir, src.stem, suffix, data)
    return {"workout_id": workout_id, "name": workout.name, "created": created}
