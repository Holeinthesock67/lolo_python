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

from .workout import MAX_POWER_FRAC, MAX_REPEAT, Block, Workout, WorkoutError

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
    --erg-relative`."""
    lines = ["[COURSE HEADER]", "VERSION = 2", "UNITS = ENGLISH", f"DESCRIPTION = {workout.name}",
             "MINUTES PERCENT", "[END COURSE HEADER]", "[COURSE DATA]"]
    t = 0.0
    for b in workout.blocks:
        a, z = b.profile_fracs(ftp_w)
        a, z = a * 100.0, z * 100.0
        lines.append(f"{t / 60.0:.4f}\t{a:.2f}")
        t += b.duration_s
        lines.append(f"{t / 60.0:.4f}\t{z:.2f}")
    lines.append("[END COURSE DATA]")
    if workout.texts:
        lines.append("[COURSE TEXT]")
        lines += [f"{ts:g}\t{txt}\t{dur:g}" for ts, txt, dur in workout.texts]
        lines.append("[END COURSE TEXT]")
    return "\n".join(lines) + "\n"


# --- QWKcode de GoldenCheetah (`.qwk`, lot O20) ----------------------------------------------
#
# Une ligne par segment, `[Nx] durée@puissance[-puissance] [rdurée@puissance[-puissance]]` :
#     10m@130-220            rampe de 130 à 220 W en 10 min
#     5m@180                 palier
#     4x 5m@280 r3m@140      4 × (5 min à 280 W, 3 min à 140 W)
#     8x 30s@120% r30s@50%   puissances en % de la FTP (suffixe %)
# Durée : nombres suivis de h, m ou s, combinables (`1m30s`, `1.5m`). Puissance en watts, ou en %
# de la FTP avec `%` (`50-75%` : le `%` vaut pour les deux bornes). Lignes vides ignorées ; `#`
# commence un commentaire, et le premier commentaire avant tout segment donne le nom.

_QWK_DUR = r"(?:\d+(?:[.,]\d+)?\s*[hms]\s*)+"
_QWK_POW = r"\d+(?:[.,]\d+)?\s*%?"
_QWK_SEG = rf"({_QWK_DUR})@\s*({_QWK_POW})(?:\s*-\s*({_QWK_POW}))?"
_QWK_LINE_RE = re.compile(rf"^(?:(\d+)\s*x\s*)?{_QWK_SEG}(?:\s*r\s*{_QWK_SEG})?$", re.IGNORECASE)
_QWK_DUR_PART_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*([hms])", re.IGNORECASE)
_QWK_UNIT_S = {"h": 3600.0, "m": 60.0, "s": 1.0}
QWK_SYNTAX = "[Nx] durée@puissance[-puissance] [rdurée@puissance[-puissance]]"


def _qwk_duration(text: str, lineno: int) -> float:
    seconds = sum(float(v.replace(",", ".")) * _QWK_UNIT_S[u.lower()] for v, u in _QWK_DUR_PART_RE.findall(text))
    if seconds <= 0:
        raise WorkoutError(f"ligne {lineno} : durée nulle ({text.strip()!r})")
    return seconds


def _qwk_target(lo: str, hi: str | None, lineno: int) -> tuple[float, float, bool]:
    """(début, fin, en %) ; un `%` sur une borne vaut pour les deux."""
    percent = lo.rstrip().endswith("%") or (hi is not None and hi.rstrip().endswith("%"))
    a = float(lo.rstrip(" %").replace(",", "."))
    z = float(hi.rstrip(" %").replace(",", ".")) if hi is not None else a
    limit = MAX_POWER_FRAC * 100.0 if percent else MAX_WATTS
    for v in (a, z):
        if v > limit:
            unit = "% de la FTP" if percent else "W"
            raise WorkoutError(f"ligne {lineno} : cible {v:g} {unit} au-delà de {limit:g} {unit}")
    return a, z, percent


def _qwk_block(kind: str, duration: float, target: tuple[float, float, bool]) -> Block:
    a, z, percent = target
    if kind == "steady" and a != z:
        kind = "ramp"
    if percent:
        return Block(kind, duration, a / 100.0, z / 100.0)
    return Block(kind, duration, None, None, a, z)


def parse_qwk(text: str, workout_id: str, source: str = "<qwk>") -> Workout:
    """Lit du QWKcode de GoldenCheetah. Lève `WorkoutError` avec le numéro de ligne s'il est invalide."""
    name = ""
    blocks: list[Block] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line, _, comment = raw.partition("#")
        line = line.strip()
        if not line:
            if comment.strip() and not blocks and not name:
                name = comment.strip()
            continue
        m = _QWK_LINE_RE.match(line)
        if not m:
            raise WorkoutError(f"ligne {lineno} : « {line} » ne suit pas la syntaxe {QWK_SYNTAX} "
                               "(exemple : 4x 5m@280 r3m@140)")
        reps_txt, on_dur, on_lo, on_hi, off_dur, off_lo, off_hi = m.groups()
        reps = int(reps_txt) if reps_txt is not None else 1
        if not 1 <= reps <= MAX_REPEAT:
            raise WorkoutError(f"ligne {lineno} : {reps} répétitions (de 1 à {MAX_REPEAT})")
        on = (_qwk_duration(on_dur, lineno), _qwk_target(on_lo, on_hi, lineno))
        off = (_qwk_duration(off_dur, lineno), _qwk_target(off_lo, off_hi, lineno)) if off_dur else None
        interval = reps > 1 or off is not None
        for _ in range(reps):
            blocks.append(_qwk_block("interval_on" if interval else "steady", *on))
            if off is not None:
                blocks.append(_qwk_block("interval_off", *off))
        if sum(b.duration_s for b in blocks) > MAX_DURATION_S:
            raise WorkoutError(f"ligne {lineno} : la séance dépasse la durée maximale de "
                               f"{MAX_DURATION_S / 3600:g} h")
    if not blocks:
        raise WorkoutError(f"aucun segment : écrire une ligne par segment, {QWK_SYNTAX}")
    log.debug("%s : %d blocs lus.", source, len(blocks))
    return Workout(id=workout_id, name=name or workout_id, blocks=tuple(blocks))
