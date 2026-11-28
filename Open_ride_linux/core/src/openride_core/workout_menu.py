"""Entraînements créés depuis le menu ERG (lot N16, décision D4 de l'audit IPC du 26 octobre).

Le core reste seul à écrire dans le dossier des entraînements (contrat IPC §4) : l'engine envoie les
paramètres d'un entraînement par intervalles (`create_workout`) ou du QWKcode (`create_workout_qwk`).
L'import de fichiers depuis le menu (`list_imports`, `import_workout`) est retiré depuis la révision
1.15 du contrat (décision du propriétaire du 12 novembre) : un fichier se dépose à la main dans
`~/OpenRide/Workouts/`.

- `build_interval_zwo()` : fichier `.zwo` (Warmup, IntervalsT, Cooldown, en % de la FTP) ; mêmes
  paramètres, même fichier ; nom déjà pris par d'autres réglages : suffixe `_2`, `_3`… (lot O20).
- `create_qwk_workout()` : QWKcode saisi au clavier (lot O21), relu puis écrit en `.qwk`.
- `_store()` : un fichier identique déjà présent n'est pas réécrit, un entraînement différent du même
  nom prend le suffixe `_2`, `_3`…

Module pur (fichiers seulement) : session.py le branche sur l'IPC.
"""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable

from .workout import WORKOUT_SUFFIXES, WorkoutError, parse_workout
from .workout_formats import parse_qwk

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

# Dossiers fouillés pour les traces à importer (`route_import`, lot O23) et les contenus (`contents`),
# relatifs au dossier personnel, avec le nom affiché.
IMPORT_SOURCES: tuple[tuple[str, str], ...] = (
    ("Téléchargements", "Téléchargements"), ("Downloads", "Téléchargements"), ("Bureau", "Bureau"),
    ("Desktop", "Bureau"), ("OpenRide/Import", "OpenRide/Import"), ("", "Dossier personnel"),
)
MAX_IMPORT_CANDIDATES = 30
# Texte QWKcode saisi au clavier (`create_workout_qwk`, lot O21) : la commande tient dans un datagramme
# de 4 096 octets (contrat §2), avec son enveloppe JSON.
MAX_QWK_TEXT_BYTES = 3000
QWK_DEFAULT_STEM = "qwkcode"


# Lot PP8b : base de l'effort d'un entraînement par intervalles : % de la FTP (défaut) ou % de ton meilleur 1 min
# ou 5 min (courbe de puissance des 6 derniers mois, sinon courbe type) ; le `.zwo` reste écrit en % de la FTP.
ON_REFS: dict[str, int | None] = {"ftp": None, "best_60": 60, "best_300": 300}
ON_REF_WORDS = {"best_60": "ton 1 min", "best_300": "ton 5 min"}
CURVE_ON_PCT = (50, 120)   # % du meilleur effort : un 1 min à 120 % de ton record n'est déjà plus tenable


class WorkoutMenuError(Exception):
    """Refus d'une création : `code` est le code d'erreur IPC à renvoyer."""

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


def check_on_ref(args: dict) -> str:
    """Base de l'effort (`on_ref`, lot PP8b) : `ftp` par défaut ; refus `bad_args` d'une base inconnue ou d'un
    pourcentage hors de `CURVE_ON_PCT` pour une base de la courbe."""
    ref = args.get("on_ref", "ftp")
    if ref not in ON_REFS:
        raise WorkoutMenuError("bad_args", "create_workout : « on_ref » vaut " + ", ".join(ON_REFS))
    lo, hi = CURVE_ON_PCT
    pct = args.get("on_pct")
    if ref != "ftp" and (isinstance(pct, bool) or not isinstance(pct, int) or not lo <= pct <= hi):
        raise WorkoutMenuError("bad_args", f"create_workout : « on_pct » de {lo} à {hi} % de {ON_REF_WORDS[ref]}")
    return ref


def curve_interval_params(p: dict[str, int], ref: str, best_w: float, ftp_w: float) -> tuple[dict[str, int], dict]:
    """Paramètres en % de la FTP d'un effort calé sur ton meilleur effort (`best_w`, lot PP8b), et ce qui le
    nomme : {target_w, ref_pct, ref}. Le % de la FTP reste dans les bornes de `INTERVAL_PARAMS`."""
    target_w = best_w * p["on_pct"] / 100.0
    lo, hi = INTERVAL_PARAMS["on_pct"]
    q = dict(p, on_pct=min(max(int(round(100.0 * target_w / ftp_w)), lo), hi))
    return q, {"target_w": int(round(ftp_w * q["on_pct"] / 100.0)), "ref_pct": p["on_pct"], "ref": ref}


def curve_interval_name(q: dict[str, int], meta: dict) -> str:
    """« Intervalles 6 × 1 min à 340 W (95 % de ton 1 min) »."""
    return (f"Intervalles {q['reps']} × {_duration(q['on_s'])} à {meta['target_w']} W "
            f"({meta['ref_pct']} % de {ON_REF_WORDS[meta['ref']]})")


def build_interval_zwo(p: dict[str, int], name: str | None = None) -> str:
    lines = [
        "<workout_file>",
        "  <author>OpenRide</author>",
        f"  <name>{name or interval_name(p)}</name>",
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


def create_interval_workout(workouts_dir: Path, args: Any,
                            best_of: Callable[[int], tuple[float, float]] | None = None) -> dict[str, Any]:
    """Écrit `<dossier>/intervalles_….zwo` ; renvoie {workout_id, name, created} (et `target_w`, lot PP8b).

    Mêmes réglages qu'un fichier existant : rien n'est écrit. Même nom mais réglages différents
    (récupération, échauffement…) : suffixe `_2`, `_3`…, comme à l'import (lot O20) ; aucun
    entraînement n'est remplacé.

    `on_ref` (lot PP8b) : `best_60` ou `best_300`, `on_pct` est un % de ton meilleur 1 min ou 5 min ;
    `best_of(secondes)` rend (meilleur effort en W, FTP en W), lus par la séance sur la courbe du profil."""
    if isinstance(args, dict) and args.get("on_ref", "ftp") != "ftp":
        ref = check_on_ref(args)   # `on_pct` déjà borné à `CURVE_ON_PCT` ; les autres paramètres comme avant
        p = dict(check_interval_params(dict(args, on_pct=100)), on_pct=int(args["on_pct"]))
        if best_of is None:
            raise WorkoutMenuError("bad_args", "create_workout : courbe de puissance indisponible")
        best_w, ftp_w = best_of(int(ON_REFS[ref]))
        q, meta = curve_interval_params(p, ref, best_w, ftp_w)
        name = curve_interval_name(q, meta)
        text = build_interval_zwo(q, name)
        parse_workout(text, interval_id(q))
        workout_id, created = _store(workouts_dir, interval_id(q), ".zwo", text.encode("utf-8"))
        return {"workout_id": workout_id, "name": name, "created": created, "target_w": meta["target_w"]}
    if isinstance(args, dict):
        check_on_ref(args)
    p = check_interval_params(args)
    text = build_interval_zwo(p)
    parse_workout(text, interval_id(p))   # le fichier produit doit rester lisible par le core
    workout_id, created = _store(workouts_dir, interval_id(p), ".zwo", text.encode("utf-8"))
    return {"workout_id": workout_id, "name": interval_name(p), "created": created}


def qwk_stem(name: str) -> str:
    """Nom de fichier tiré du nom de la séance : « Seuil 4 × 5 » donne `seuil_4_5` ; vide : `qwkcode`."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    stem = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")[:40].strip("_")
    return stem or QWK_DEFAULT_STEM


def create_qwk_workout(workouts_dir: Path, args: Any) -> dict[str, Any]:
    """Écrit le QWKcode saisi au clavier dans `<dossier>/<nom>.qwk` (lot O21) ; renvoie {workout_id, name, created}.

    Texte relu par `parse_qwk` avant l'écriture : une erreur (avec son numéro de ligne) donne
    `workout_invalid` et rien n'est écrit. Nom de fichier tiré de la ligne `#` du nom, sans écraser
    un autre entraînement (`_store`)."""
    text = args.get("text") if isinstance(args, dict) else None
    if not isinstance(text, str):
        raise WorkoutMenuError("bad_args", "create_workout_qwk attend « text », une chaîne")
    text = text.replace("\r\n", "\n").strip("\n") + "\n"
    if len(text.encode("utf-8")) > MAX_QWK_TEXT_BYTES:
        raise WorkoutMenuError("bad_args", f"QWKcode trop long (au plus {MAX_QWK_TEXT_BYTES} octets)")
    try:
        workout = parse_qwk(text, QWK_DEFAULT_STEM)
    except WorkoutError as exc:
        raise WorkoutMenuError("workout_invalid", str(exc)) from exc
    name = workout.name if workout.name != QWK_DEFAULT_STEM else "Séance QWKcode"
    workout_id, created = _store(workouts_dir, qwk_stem(workout.name if workout.name != QWK_DEFAULT_STEM else ""),
                                 ".qwk", text.encode("utf-8"))
    return {"workout_id": workout_id, "name": name, "created": created}


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
