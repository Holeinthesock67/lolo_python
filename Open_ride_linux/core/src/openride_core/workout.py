"""Entraînements structurés ERG (SRS §6) : lecture des fichiers `.zwo`, `.erg` et `.mrc` et calcul de la cible.

- `load_workout` lit un `.zwo` (XML ouvert de Zwift) et le déplie en blocs simples ;
  les intervalles `IntervalsT` deviennent des paires `interval_on` / `interval_off`.
  Les `.erg` (cibles en watts) et `.mrc` (cibles en % de la FTP) de GoldenCheetah sont lus par
  `workout_formats.parse_erg` (lot O9) : un bloc `steady` ou `ramp` par segment ; les blocs
  d'un `.erg` portent des cibles absolues (`start_w`, `end_w`) que la FTP ne change pas.
- `list_workouts` liste un dossier pour le futur menu : un fichier invalide y figure avec son
  erreur et n'est pas sélectionnable.
- `ErgController` donne, à chaque pas de 50 Hz, la cible de puissance en watts et l'objet `erg`
  du contrat IPC (§3).

Arrondi : la cible est arrondie au watt par `round()` de Python, qui arrondit les demis au pair
(237,5 W donne 238 W, 212,5 W donne 212 W).
Pendant un bloc `freeride`, il n'y a pas de cible : `target_w` vaut 0 et le core repasse en SIM.
Les métadonnées `author`, `sportType` et `tags` sont notées au niveau DEBUG ; les autres balises
inconnues (`textevent`, …) donnent un avertissement. Un `sportType` autre que `bike` est refusé.
"""

from __future__ import annotations

import logging
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("workout")

MAX_POWER_FRAC = 3.0
MAX_REPEAT = 100                    # borne de Repeat (IntervalsT) : un fichier aberrant ne doit pas épuiser la mémoire
SMOOTH_S = 2.0                      # lissage des changements de bloc (SRS §6)
BIAS_DEFAULT_PCT = 100
BIAS_STEP_PCT = 2
BIAS_MIN_PCT, BIAS_MAX_PCT = 80, 120
WORKOUT_ID_RE = re.compile(r"^[^/\\.][^/\\]*$")   # un nom de fichier simple, sans dossier
# Extensions lues, par priorité : en cas de conflit de nom (`x.zwo` et `x.erg`), la première gagne.
WORKOUT_SUFFIXES = (".zwo", ".erg", ".mrc")

# Attributs lus pour chaque balise de bloc (noms en minuscules).
_BLOCK_ATTRS: dict[str, set[str]] = {
    "warmup": {"duration", "powerlow", "powerhigh"},
    "cooldown": {"duration", "powerlow", "powerhigh"},
    "ramp": {"duration", "powerlow", "powerhigh"},
    "steadystate": {"duration", "power"},
    "intervalst": {"repeat", "onduration", "offduration", "onpower", "offpower"},
    "freeride": {"duration"},
}
# Métadonnées courantes des fichiers Zwift : sans effet sur la cible, notées au niveau DEBUG seulement.
_META_TAGS = {"author", "sporttype", "tags"}


class WorkoutError(Exception):
    """Fichier d'entraînement invalide ; le message est lisible par l'utilisateur."""


@dataclass(frozen=True)
class Block:
    type: str                  # warmup, steady, interval_on, interval_off, ramp, cooldown, freeride
    duration_s: float
    start_frac: float | None   # None pour freeride et pour un bloc en watts absolus
    end_frac: float | None
    start_w: float | None = None   # cibles absolues en watts (`.erg`, lot O9), sans la FTP
    end_w: float | None = None

    @property
    def absolute(self) -> bool:
        return self.start_w is not None and self.end_w is not None

    @property
    def free(self) -> bool:
        """Bloc sans cible (roue libre)."""
        return not self.absolute and (self.start_frac is None or self.end_frac is None)

    def frac_at(self, t: float) -> float | None:
        """Fraction de la FTP à t secondes du début du bloc (linéaire dans une rampe) ; None en
        roue libre et pour un bloc en watts absolus."""
        if self.start_frac is None or self.end_frac is None:
            return None
        u = min(max(t / self.duration_s, 0.0), 1.0)
        return self.start_frac + (self.end_frac - self.start_frac) * u

    def watts_at(self, t: float, ftp_w: float) -> float | None:
        """Cible en watts à t secondes du début du bloc, sans biais (None en roue libre)."""
        if self.absolute:
            u = min(max(t / self.duration_s, 0.0), 1.0)
            return self.start_w + (self.end_w - self.start_w) * u
        frac = self.frac_at(t)
        return None if frac is None else ftp_w * frac

    def profile_fracs(self, ftp_w: float) -> tuple[float | None, float | None]:
        """(début, fin) en fraction de la FTP, pour le profil affiché (watts absolus ramenés à la FTP)."""
        if self.absolute:
            return self.start_w / ftp_w, self.end_w / ftp_w
        return self.start_frac, self.end_frac


@dataclass(frozen=True)
class Workout:
    id: str
    name: str
    blocks: tuple[Block, ...]
    description: str = ""
    # Messages `[COURSE TEXT]` d'un `.erg` / `.mrc` : (temps en s, texte, durée en s), pour un
    # affichage futur (lot O9) ; vide pour un `.zwo`.
    texts: tuple[tuple[float, str, float], ...] = ()

    @property
    def duration_s(self) -> float:
        return sum(b.duration_s for b in self.blocks)


@dataclass(frozen=True)
class WorkoutInfo:
    """Entrée du menu des entraînements : profil des blocs, ou erreur si le fichier est invalide."""
    id: str
    name: str
    duration_s: float
    profile: tuple[Block, ...]
    error: str | None = None

    @property
    def selectable(self) -> bool:
        return self.error is None


# --- lecture ------------------------------------------------------------------------------

class _Reader:
    """Lecture d'un fichier ; les avertissements ne sont émis qu'une fois par nom."""

    def __init__(self, source: str) -> None:
        self.source = source
        self._warned: set[str] = set()

    def warn(self, what: str, name: str) -> None:
        key = f"{what}:{name}"
        if key not in self._warned:
            self._warned.add(key)
            log.warning("%s : %s inconnu « %s » ignoré.", self.source, what, name)

    def attrs(self, el: ET.Element, tag: str) -> dict[str, str]:
        out = {k.lower(): v for k, v in el.attrib.items()}
        for key in out:
            if key not in _BLOCK_ATTRS[tag]:
                self.warn("attribut", f"{el.tag}.{key}")
        return out

    def number(self, attrs: dict[str, str], key: str, tag: str) -> float:
        if key not in attrs:
            raise WorkoutError(f"bloc {tag} sans attribut {key}")
        try:
            value = float(attrs[key])
        except ValueError:
            raise WorkoutError(f"bloc {tag} : {key} n'est pas un nombre ({attrs[key]!r})") from None
        if not math.isfinite(value):
            raise WorkoutError(f"bloc {tag} : {key} n'est pas un nombre fini")
        return value

    def duration(self, attrs: dict[str, str], key: str, tag: str) -> float:
        value = self.number(attrs, key, tag)
        if value <= 0:
            raise WorkoutError(f"bloc {tag} : durée {key} nulle ou négative ({value:g})")
        return value

    def power(self, attrs: dict[str, str], key: str, tag: str) -> float:
        value = self.number(attrs, key, tag)
        if not 0.0 <= value <= MAX_POWER_FRAC:
            raise WorkoutError(f"bloc {tag} : puissance {key} = {value:g} hors de 0 à {MAX_POWER_FRAC:g}")
        return value

    def blocks(self, el: ET.Element, tag: str) -> list[Block]:
        for child in el:
            self.warn("balise", child.tag)   # textevent, etc. à l'intérieur d'un bloc
        a = self.attrs(el, tag)
        if tag in ("warmup", "cooldown", "ramp"):
            return [Block(tag, self.duration(a, "duration", tag),
                          self.power(a, "powerlow", tag), self.power(a, "powerhigh", tag))]
        if tag == "steadystate":
            p = self.power(a, "power", tag)
            return [Block("steady", self.duration(a, "duration", tag), p, p)]
        if tag == "freeride":
            return [Block("freeride", self.duration(a, "duration", tag), None, None)]
        # intervalst
        repeat = self.number(a, "repeat", tag)
        if repeat < 1 or repeat != int(repeat):
            raise WorkoutError(f"bloc {tag} : Repeat doit être un entier positif ({repeat:g})")
        if repeat > MAX_REPEAT:
            raise WorkoutError(f"bloc {tag} : Repeat = {repeat:g} dépasse {MAX_REPEAT}")
        on_d, off_d = self.duration(a, "onduration", tag), self.duration(a, "offduration", tag)
        on_p, off_p = self.power(a, "onpower", tag), self.power(a, "offpower", tag)
        out: list[Block] = []
        for _ in range(int(repeat)):
            out += [Block("interval_on", on_d, on_p, on_p), Block("interval_off", off_d, off_p, off_p)]
        return out


def parse_workout(text: str, workout_id: str, source: str = "<zwo>") -> Workout:
    """Lit le contenu XML d'un `.zwo`. Lève `WorkoutError` si le fichier est invalide."""
    reader = _Reader(source)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise WorkoutError(f"XML mal formé : {exc}") from None
    if root.tag.lower() != "workout_file":
        raise WorkoutError(f"racine <{root.tag}> au lieu de <workout_file>")
    name, description, workout_el = workout_id, "", None
    for child in root:
        tag = child.tag.lower()
        if tag == "name":
            name = (child.text or "").strip() or workout_id
        elif tag == "description":
            description = (child.text or "").strip()
        elif tag == "workout":
            workout_el = child
        elif tag in _META_TAGS:
            if tag == "sporttype" and (child.text or "").strip().lower() not in ("", "bike"):
                raise WorkoutError(f"entraînement de type « {child.text.strip()} », pas de vélo")
            log.debug("%s : métadonnée « %s » ignorée.", source, child.tag)
        else:
            reader.warn("balise", child.tag)
    if workout_el is None:
        raise WorkoutError("balise <workout> absente")
    blocks: list[Block] = []
    for el in workout_el:
        tag = el.tag.lower()
        if tag in _BLOCK_ATTRS:
            blocks += reader.blocks(el, tag)
        else:
            reader.warn("balise", el.tag)
    if not blocks:
        raise WorkoutError("aucun bloc reconnu")
    return Workout(id=workout_id, name=name, blocks=tuple(blocks), description=description)


def load_workout(path: Path, erg_relative: bool = False) -> Workout:
    """Lit un fichier `.zwo`, `.erg` ou `.mrc` ; son identifiant est le nom du fichier sans extension.

    `erg_relative` : un `.erg` est converti en % de la FTP de son en-tête (`FTP = …`).
    """
    suffix = path.suffix.lower()
    if suffix not in WORKOUT_SUFFIXES:
        raise WorkoutError(f"{path.name} : format inconnu (attendu {', '.join(WORKOUT_SUFFIXES)})")
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8") if suffix == ".zwo" else _decode_text(raw)
    except (OSError, UnicodeDecodeError) as exc:
        raise WorkoutError(f"lecture impossible de {path.name} : {exc}") from None
    if suffix == ".zwo":
        return parse_workout(text, path.stem, source=path.name)
    from .workout_formats import parse_erg
    return parse_erg(text, path.stem, source=path.name, percent=suffix == ".mrc", relative=erg_relative)


def _decode_text(raw: bytes) -> str:
    """Fichiers texte de GoldenCheetah : UTF-8 (avec ou sans BOM), sinon Latin-1 (exports Windows)."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _workout_files(directory: Path) -> dict[str, list[Path]]:
    """Fichiers d'entraînement par identifiant, dans l'ordre de priorité des extensions."""
    found: dict[str, list[Path]] = {}
    for p in directory.iterdir():
        if p.suffix.lower() in WORKOUT_SUFFIXES and p.is_file():
            found.setdefault(p.stem, []).append(p)
    for paths in found.values():
        paths.sort(key=lambda p: WORKOUT_SUFFIXES.index(p.suffix.lower()))
    return found


def _chosen(workout_id: str, paths: list[Path]) -> Path:
    if len(paths) > 1:
        log.warning("Entraînement « %s » en plusieurs formats (%s) : %s retenu.", workout_id,
                    ", ".join(p.name for p in paths), paths[0].name)
    return paths[0]


def list_workouts(directory: Path) -> list[WorkoutInfo]:
    """Entraînements d'un dossier (`~/OpenRide/Workouts/`), triés par identifiant.

    `.zwo`, `.erg` et `.mrc` ; un même identifiant en plusieurs formats est signalé une fois
    au journal et le `.zwo` gagne (puis `.erg`, puis `.mrc`).
    """
    if not directory.is_dir():
        return []
    out: list[WorkoutInfo] = []
    files = _workout_files(directory)
    for path in (_chosen(wid, files[wid]) for wid in sorted(files)):
        try:
            w = load_workout(path)
        except WorkoutError as exc:
            out.append(WorkoutInfo(path.stem, path.stem, 0.0, (), str(exc)))
        else:
            out.append(WorkoutInfo(w.id, w.name, w.duration_s, w.blocks))
    return out


def workout_path(directory: Path, workout_id: str) -> Path:
    """Chemin de `<dossier>/<workout_id>.zwo` (ou `.erg`, `.mrc`, dans cet ordre de priorité) ;
    refuse un identifiant qui sortirait du dossier."""
    if not WORKOUT_ID_RE.match(workout_id):
        raise WorkoutError(f"identifiant d'entraînement invalide : {workout_id!r}")
    paths = _workout_files(directory).get(workout_id, []) if directory.is_dir() else []
    if not paths:
        raise WorkoutError(f"entraînement « {workout_id} » introuvable dans {directory}")
    return _chosen(workout_id, paths)


# --- contrôleur ERG -----------------------------------------------------------------------

class ErgController:
    """Cible de puissance d'un entraînement, avancée par pas de temps (SRS §6, §4.4).

    - Cible = FTP × fraction × biais / 100, arrondie au watt ; pour un bloc en watts absolus
      (`.erg`, lot O9) : watts × biais / 100, quelle que soit la FTP.
    - À chaque changement de bloc, la cible sans biais passe linéairement de l'ancienne valeur à
      la nouvelle en 2 s ; le biais s'applique sans lissage. Après un bloc `freeride` (sans cible),
      le bloc suivant démarre directement à sa cible.
    - Pause ERG : le temps du bloc et le lissage s'arrêtent.

    Entrées refusées (`ValueError`, constat R3 de la vérification du 24 octobre) : FTP ≤ 0 ou
    non finie, `dt` négatif, infini ou NaN (`dt == 0` reste permis). La session ne peut pas en
    produire : sa FTP vient de `rider.ftp_w`, bornée à 50–600 W par la validation de la
    configuration, et son `dt` d'une horloge monotone (`time.monotonic`, borné par `MAX_STEP_S`).
    Le contrôle protège un futur appelant (outils, tests).
    """

    def __init__(self, workout: Workout, ftp_w: float) -> None:
        if not (math.isfinite(ftp_w) and ftp_w > 0):
            raise ValueError(f"FTP invalide : {ftp_w!r} W (attendu un nombre fini > 0)")
        self.workout = workout
        self.ftp_w = ftp_w
        self.index = 0
        self.t_block = 0.0
        self.bias_pct = BIAS_DEFAULT_PCT
        self.paused = False
        self.finished = False
        self._from_w: float | None = None   # début du lissage en cours, en watts sans biais (None : aucun)
        self._smooth_t = 0.0

    @property
    def block(self) -> Block:
        return self.workout.blocks[self.index]

    @property
    def is_freeride(self) -> bool:
        return self.block.free

    @property
    def target_active(self) -> bool:
        """Vrai quand le trainer doit recevoir une cible ERG (ni roue libre, ni pause, ni fin)."""
        return not (self.finished or self.paused or self.is_freeride)

    def base_w(self) -> float | None:
        """Cible en cours en watts, lissage compris, sans biais (None en roue libre)."""
        w = self.block.watts_at(self.t_block, self.ftp_w)
        if w is None or self._from_w is None or self._smooth_t >= SMOOTH_S:
            return w
        return self._from_w + (w - self._from_w) * (self._smooth_t / SMOOTH_S)

    def fraction(self) -> float | None:
        """Fraction de la FTP en cours, lissage compris (None en roue libre)."""
        w = self.base_w()
        return None if w is None else w / self.ftp_w

    def _watts(self, base_w: float | None) -> int | None:
        if base_w is None:
            return None
        return round(base_w * self.bias_pct / 100.0)

    @property
    def target_w(self) -> int:
        """Cible lissée en watts, biais compris ; 0 en roue libre."""
        return self._watts(self.base_w()) or 0

    @property
    def next_target_w(self) -> int | None:
        if self.index + 1 >= len(self.workout.blocks):
            return None
        return self._watts(self.workout.blocks[self.index + 1].watts_at(0.0, self.ftp_w))

    def _enter(self, index: int, carry_s: float = 0.0) -> None:
        if index >= len(self.workout.blocks):
            self.finished = True
            self.t_block = self.block.duration_s
            return
        self._from_w = self.base_w()
        self._smooth_t = carry_s
        self.index, self.t_block = index, carry_s

    def step(self, dt: float) -> None:
        """Avance le temps de l'entraînement de dt secondes (rien en pause ou après la fin)."""
        if not (math.isfinite(dt) and dt >= 0):
            raise ValueError(f"pas de temps invalide : {dt!r} s (attendu un nombre fini ≥ 0)")
        if self.finished or self.paused:
            return
        self.t_block += dt
        self._smooth_t += dt
        while not self.finished and self.t_block >= self.block.duration_s:
            carry = self.t_block - self.block.duration_s
            self.t_block = self.block.duration_s   # fraction de fin de bloc pour le lissage
            self._enter(self.index + 1, carry)

    def skip(self) -> None:
        """Passe au début du bloc suivant (lissage de 2 s) ; au dernier bloc, termine."""
        self.goto(self.index + 1)

    def goto(self, index: int) -> None:
        """Passe au début du bloc `index` (à partir de 0, lissage de 2 s) ; au-delà du dernier,
        termine. Sert à la fin de la rampe du test de FTP (lot O10), qui saute au retour au calme."""
        if not self.finished:
            self._enter(index)

    def change_bias(self, steps: int) -> None:
        self.bias_pct = min(max(self.bias_pct + steps * BIAS_STEP_PCT, BIAS_MIN_PCT), BIAS_MAX_PCT)

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def to_dict(self) -> dict[str, Any]:
        """Objet `erg` du contrat IPC §3."""
        b = self.block
        return {
            "workout_name": self.workout.name,
            "block_index": self.index + 1,
            "block_count": len(self.workout.blocks),
            "block_type": b.type,
            "block_remaining_s": round(max(b.duration_s - self.t_block, 0.0), 2),
            "block_total_s": b.duration_s,
            "target_w": self.target_w,
            "next_target_w": self.next_target_w,
            "bias_pct": self.bias_pct,
            "paused": self.paused,
        }
