"""Entraînements au format texte de GoldenCheetah : `.erg` (watts) et `.mrc` (% de la FTP), lot O9.

Format (insensible à la casse, fins de ligne Windows acceptées, séparateurs espaces ou tabulations) :

    [COURSE HEADER]
    VERSION = 2
    UNITS = ENGLISH
    DESCRIPTION = Sweet spot 3 x 10
    FILE NAME = sweet_spot.erg
    FTP = 250                    (facultatif, .erg seulement)
    MINUTES WATTS                (.erg)   ou   MINUTES PERCENT   (.mrc)
    [END COURSE HEADER]
    [COURSE DATA]
    0.00    100
    10.00   100
    10.00   200
    [END COURSE DATA]
    [COURSE TEXT]                (facultatif : temps en secondes, texte, durée en secondes)
    60   Accélère !   10
    [END COURSE TEXT]

Les points sont reliés en ligne droite : deux points de même temps font une marche, deux
valeurs différentes une rampe. Chaque segment de durée non nulle devient un bloc `steady`
(valeurs égales) ou `ramp`. Un `.mrc` donne des fractions de la FTP ; un `.erg` des cibles en
watts absolues (`Block.start_w` / `end_w`), sauf avec `relative=True` qui les ramène à la FTP
de l'en-tête. Les autres clés d'en-tête sont ignorées (niveau DEBUG).
"""

from __future__ import annotations

import logging
import math
import re
from itertools import pairwise

from .workout import MAX_POWER_FRAC, Block, Workout, WorkoutError

log = logging.getLogger("workout")

MAX_DURATION_S = 6 * 3600.0
MAX_WATTS = 2000.0             # plage du HomeTrainer (Supported Power Range)
_SECTION_RE = re.compile(r"^\[\s*(end\s+)?course\s+(header|data|text)\s*\]$", re.IGNORECASE)
_SPLIT_RE = re.compile(r"[ \t]+")


def _num(text: str, lineno: int, what: str) -> float:
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        raise WorkoutError(f"ligne {lineno} : {what} n'est pas un nombre ({text!r})") from None
    if not math.isfinite(value):
        raise WorkoutError(f"ligne {lineno} : {what} n'est pas un nombre fini")
    return value


def parse_erg(text: str, workout_id: str, source: str = "<erg>", *, percent: bool = False,
              relative: bool = False) -> Workout:
    """Lit un `.erg` (`percent=False`) ou un `.mrc` (`percent=True`).

    `relative` (`.erg` seulement) : cibles converties en % de la clé `FTP` de l'en-tête.
    Lève `WorkoutError` avec le numéro de ligne si le fichier est invalide.
    """
    section: str | None = None
    seen: set[str] = set()
    header: dict[str, str] = {}
    units_line: tuple[int, str] | None = None
    points: list[tuple[float, float, int]] = []
    texts: list[tuple[float, str, float]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        m = _SECTION_RE.match(line)
        if m:
            name = m.group(2).lower()
            if m.group(1):
                if section != name:
                    raise WorkoutError(f"ligne {lineno} : [END COURSE {name.upper()}] sans début")
                section = None
            else:
                if section is not None:
                    raise WorkoutError(f"ligne {lineno} : section [COURSE {section.upper()}] non fermée")
                section = name
                seen.add(name)
            continue
        if section == "header":
            if "=" in line:
                key, _, value = line.partition("=")
                header[key.strip().upper()] = value.strip()
            else:
                units_line = (lineno, line.upper())
        elif section == "data":
            parts = _SPLIT_RE.split(line)
            if len(parts) < 2:
                raise WorkoutError(f"ligne {lineno} : deux colonnes attendues (minutes et "
                                   f"{'pourcentage' if percent else 'watts'}), lu {line!r}")
            minutes = _num(parts[0], lineno, "le temps")
            value = _num(parts[1], lineno, "la cible")
            if minutes < 0:
                raise WorkoutError(f"ligne {lineno} : temps négatif ({minutes:g} min)")
            if value < 0:
                raise WorkoutError(f"ligne {lineno} : cible négative ({value:g})")
            if points and minutes < points[-1][0]:
                raise WorkoutError(f"ligne {lineno} : temps décroissant ({minutes:g} min après "
                                   f"{points[-1][0]:g} min)")
            if minutes * 60.0 > MAX_DURATION_S:
                raise WorkoutError(f"ligne {lineno} : {minutes:g} min dépasse la durée maximale de "
                                   f"{MAX_DURATION_S / 3600:g} h")
            points.append((minutes, value, lineno))
        elif section == "text":
            parts = _SPLIT_RE.split(line)
            t_s = _num(parts[0], lineno, "le temps du message")
            dur = 10.0
            body = parts[1:]
            if len(body) >= 2:
                try:
                    last = float(body[-1].replace(",", "."))
                except ValueError:
                    last = None        # dernier mot du message, pas une durée
                if last is not None:
                    if not math.isfinite(last) or last <= 0:
                        raise WorkoutError(f"ligne {lineno} : durée du message invalide ({body[-1]!r})")
                    dur = last
                    body = body[:-1]
            texts.append((t_s, " ".join(body), dur))
        else:
            raise WorkoutError(f"ligne {lineno} : texte hors de toute section ({line!r})")
    if section is not None:
        raise WorkoutError(f"fin du fichier : section [COURSE {section.upper()}] non fermée")
    if "data" not in seen:
        raise WorkoutError("section [COURSE DATA] absente")
    if len(points) < 2:
        raise WorkoutError("[COURSE DATA] : au moins deux points attendus")
    for key in header:
        if key not in ("DESCRIPTION", "FTP", "FILE NAME"):
            log.debug("%s : clé d'en-tête « %s » ignorée.", source, key)
    if units_line is not None:
        lineno, units = units_line
        expected = "PERCENT" if percent else "WATTS"
        if expected not in units:
            raise WorkoutError(f"ligne {lineno} : colonnes « {units} » alors qu'un "
                               f"{'.mrc' if percent else '.erg'} attend MINUTES {expected}")

    ftp_header: float | None = None
    if "FTP" in header and not percent:
        ftp_header = _num(header["FTP"], 0, "la FTP de l'en-tête")
        if ftp_header <= 0:
            raise WorkoutError(f"FTP de l'en-tête nulle ou négative ({ftp_header:g})")
    if relative and not percent and ftp_header is None:
        raise WorkoutError("conversion en % de la FTP impossible : clé FTP absente de l'en-tête")

    def check(value: float, lineno: int) -> None:
        if percent or relative:
            frac = value / 100.0 if percent else value / ftp_header
            if frac > MAX_POWER_FRAC:
                raise WorkoutError(f"ligne {lineno} : cible {frac * 100:.0f} % de la FTP au-delà de "
                                   f"{MAX_POWER_FRAC * 100:.0f} %")
        elif value > MAX_WATTS:
            raise WorkoutError(f"ligne {lineno} : cible {value:g} W au-delà de {MAX_WATTS:g} W")

    blocks: list[Block] = []
    for (m0, v0, l0), (m1, v1, l1) in pairwise(points):
        check(v0, l0)
        check(v1, l1)
        duration = (m1 - m0) * 60.0
        if duration <= 1e-9:
            continue                   # marche : deux points au même temps
        kind = "steady" if v0 == v1 else "ramp"
        if percent:
            blocks.append(Block(kind, duration, v0 / 100.0, v1 / 100.0))
        elif relative:
            blocks.append(Block(kind, duration, v0 / ftp_header, v1 / ftp_header))
        else:
            blocks.append(Block(kind, duration, None, None, float(v0), float(v1)))
    if not blocks:
        raise WorkoutError("[COURSE DATA] : durée totale nulle")
    name = header.get("DESCRIPTION") or workout_id
    return Workout(id=workout_id, name=name, blocks=tuple(blocks), description=header.get("DESCRIPTION", ""),
                   texts=tuple(texts))


def to_mrc(workout: Workout, ftp_w: float) -> str:
    """Texte `.mrc` d'un entraînement (cibles absolues ramenées à `ftp_w`), pour `workouts install
    --erg-relative`. Les roues libres sont écrites à 0 %."""
    lines = ["[COURSE HEADER]", "VERSION = 2", "UNITS = ENGLISH", f"DESCRIPTION = {workout.name}",
             "MINUTES PERCENT", "[END COURSE HEADER]", "[COURSE DATA]"]
    t = 0.0
    for b in workout.blocks:
        a, z = b.profile_fracs(ftp_w)
        a, z = (a or 0.0) * 100.0, (z or 0.0) * 100.0
        lines.append(f"{t / 60.0:.4f}\t{a:.2f}")
        t += b.duration_s
        lines.append(f"{t / 60.0:.4f}\t{z:.2f}")
    lines.append("[END COURSE DATA]")
    if workout.texts:
        lines.append("[COURSE TEXT]")
        lines += [f"{ts:g}\t{txt}\t{dur:g}" for ts, txt, dur in workout.texts]
        lines.append("[END COURSE TEXT]")
    return "\n".join(lines) + "\n"
