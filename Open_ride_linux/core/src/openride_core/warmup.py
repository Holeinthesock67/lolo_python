"""Échauffement commun avant une course (demande du propriétaire du 21 novembre), module pur.

Une seule règle pour tous les modes de course (Dernier survivant, Grand Prix des objets, épreuves de piste
hors séance libre ; table `RACE_MODES`, et `track.EVENTS[…].race` pour la piste) : après le décor et le
trainer prêts, la séance reste en `READY`, coureurs alignés au départ, et le trainer passe en ERG sur un
profil d'échauffement en watts directs ; à la fin (ou sur Z court, ou la commande `skip_warmup`), le départ
au pédalage habituel s'ouvre. Rien ne compte pendant l'échauffement : ni chrono, ni distance, ni bots.

Profil pour `minutes` de durée (`[depart] echauffement_min`, 0 : pas d'échauffement), hors 2 minutes
d'accélérations : 60 % du temps en montée de 45 % à 70 % de la FTP, 40 % à 70 % ; puis deux fois 20 s à
100 % et 40 s à 55 % (« ouvrir les jambes »). Les cibles passent par `workout.ErgController` (lissage de 2 s,
plancher ERG), comme un entraînement.
"""

from __future__ import annotations

from .workout import Block, ErgController, Workout

RACE_MODES = ("survivor", "grandprix", "track")   # modes de jeu précédés de l'échauffement
OPENERS = 2                                      # accélérations à la fin
OPENER_ON_S, OPENER_OFF_S = 20.0, 40.0
OPENER_ON_FRAC, OPENER_OFF_FRAC = 1.00, 0.55
RAMP_FROM_FRAC, RAMP_TO_FRAC = 0.45, 0.70
RAMP_SHARE = 0.6                                 # part de la montée dans le temps hors accélérations
MIN_MINUTES = 3                                  # en dessous : pas de place pour la montée et les accélérations
MAX_MINUTES = 20
WORKOUT_ID = "echauffement"
WORKOUT_NAME = "Échauffement"


def needed(game_mode: str | None, minutes: int, race: bool = True) -> bool:
    """Vrai si la séance qui part est une course à échauffer (`race` faux : séance libre du vélodrome)."""
    return game_mode in RACE_MODES and race and minutes >= MIN_MINUTES


def profile(minutes: int) -> Workout:
    """Entraînement d'échauffement de `minutes` minutes (MIN_MINUTES à MAX_MINUTES)."""
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not MIN_MINUTES <= minutes <= MAX_MINUTES:
        raise ValueError(f"échauffement : {minutes!r} min refusé ({MIN_MINUTES} à {MAX_MINUTES})")
    openers_s = OPENERS * (OPENER_ON_S + OPENER_OFF_S)
    base_s = minutes * 60.0 - openers_s
    blocks = [Block("warmup", base_s * RAMP_SHARE, RAMP_FROM_FRAC, RAMP_TO_FRAC),
              Block("steady", base_s * (1.0 - RAMP_SHARE), RAMP_TO_FRAC, RAMP_TO_FRAC)]
    for _ in range(OPENERS):
        blocks += [Block("interval_on", OPENER_ON_S, OPENER_ON_FRAC, OPENER_ON_FRAC),
                   Block("interval_off", OPENER_OFF_S, OPENER_OFF_FRAC, OPENER_OFF_FRAC)]
    return Workout(WORKOUT_ID, WORKOUT_NAME, tuple(blocks))


class Warmup:
    """Échauffement en cours : cible ERG, temps restant, prochain changement de cible."""

    def __init__(self, minutes: int, ftp_w: float) -> None:
        self.workout = profile(minutes)
        self.erg = ErgController(self.workout, ftp_w)
        self.elapsed_s = 0.0
        self.skipped = False

    @property
    def total_s(self) -> float:
        return self.workout.duration_s

    @property
    def left_s(self) -> float:
        return max(self.total_s - self.elapsed_s, 0.0)

    @property
    def done(self) -> bool:
        return self.skipped or self.erg.finished or self.left_s <= 0.0

    @property
    def target_w(self) -> int:
        return self.erg.target_w

    def step(self, dt: float) -> bool:
        """Un pas ; vrai quand l'échauffement vient de finir (une seule fois)."""
        if self.done:
            return False
        self.elapsed_s += dt
        self.erg.step(dt)
        return self.done

    def skip(self) -> None:
        """Z court ou `skip_warmup` : départ tout de suite."""
        self.skipped = True

    def to_dict(self) -> dict:
        """Objet `warmup` de `start_wait` (révision 1.32) : cible et suite en watts directs."""
        d = self.erg.to_dict()
        return {"target_w": self.target_w, "left_s": round(self.left_s, 1), "total_s": round(self.total_s, 1),
                "block": d["block_type"], "block_left_s": round(d["block_remaining_s"], 1),
                "next_target_w": d["next_target_w"], "done": self.done}
