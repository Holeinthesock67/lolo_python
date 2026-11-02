"""Départ d'une séance au pédalage (lot O36), module pur.

Après la commande `start`, la séance reste en `READY` tant que le départ n'est pas « ouvert » ; le
chrono, la distance, l'ERG, les bots et le journal ne partent qu'à l'ouverture. Trois étapes, dans
l'ordre, chacune vérifiée à chaque pas de la boucle :

1. `decor` : l'engine a dit son décor du départ prêt (commande `scene_ready` avec le parcours en
   cours, contrat IPC révision 1.5) ; au plus `attente_decor_s` secondes, pour un engine qui ne
   l'envoie pas (ancien engine, séance sans engine) ;
2. `trainer` : le trainer donne des mesures ;
3. `pedalage` : `duree_s` secondes de pédalage cumulées à au moins `cadence_rpm` tr/min (ou
   `POWER_W` W quand le trainer ne donne pas la cadence) ; un à-coup sous le seuil de moins de
   `TOLERANCE_S` secondes ne remet pas le compte à zéro, au-delà il redescend aussi vite qu'il monte.

Le décor et le trainer peuvent revenir en arrière (engine relancé, trainer perdu) : l'étape
retombe, le compte du pédalage repart de zéro. Le mode `immediat` ouvre le départ tout de suite.
"""

from __future__ import annotations

from dataclasses import dataclass

PHASES = ("decor", "trainer", "pedalage")
POWER_W = 40.0        # pédalage reconnu à la puissance quand la cadence manque
TOLERANCE_S = 2.0     # à-coup toléré sous le seuil sans perdre le compte


@dataclass
class StartGate:
    cadence_rpm: float = 30.0
    duree_s: float = 3.0
    attente_decor_s: float = 60.0
    immediate: bool = False

    def __post_init__(self) -> None:
        self.waited_s = 0.0      # depuis la commande start
        self.held_s = 0.0        # pédalage cumulé
        self._below_s = 0.0      # à-coup en cours sous le seuil
        self.phase = "open" if self.immediate else "decor"
        self.decor_timeout = False

    @property
    def open(self) -> bool:
        return self.phase == "open"

    def pedalling(self, cadence_rpm: float | None, power_w: float | None) -> bool:
        if cadence_rpm is not None and cadence_rpm > 0.0:
            return cadence_rpm >= self.cadence_rpm
        return power_w is not None and power_w >= POWER_W

    def update(self, dt: float, *, scene_ready: bool, trainer_connected: bool,
               cadence_rpm: float | None, power_w: float | None) -> bool:
        """Un pas de `dt` secondes ; renvoie vrai quand le départ s'ouvre (une seule fois)."""
        if self.open:
            return False
        self.waited_s += dt
        if not scene_ready and self.waited_s >= self.attente_decor_s:
            self.decor_timeout = True
        if not (scene_ready or self.decor_timeout):
            self._reset("decor")
            return False
        if not trainer_connected:
            self._reset("trainer")
            return False
        self.phase = "pedalage"
        if self.pedalling(cadence_rpm, power_w):
            self._below_s = 0.0
            self.held_s += dt
        else:
            self._below_s += dt
            if self._below_s > TOLERANCE_S:
                self.held_s = max(0.0, self.held_s - dt)
        if self.held_s >= self.duree_s:
            self.phase = "open"
            return True
        return False

    def _reset(self, phase: str) -> None:
        self.phase = phase
        self.held_s = self._below_s = 0.0

    def to_dict(self) -> dict:
        """Objet `start_wait` de la trame `state` (révision 1.5, lot O36)."""
        return {"phase": self.phase, "cadence_rpm": int(round(self.cadence_rpm)),
                "hold_s": round(self.duree_s, 1), "held_s": round(min(self.held_s, self.duree_s), 1),
                "waited_s": round(self.waited_s, 1)}
