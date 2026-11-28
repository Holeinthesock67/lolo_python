"""Départ d'une séance au pédalage (lot O36), module pur.

Après la commande `start`, la séance reste en `READY` tant que le départ n'est pas « ouvert » ; le
chrono, la distance, l'ERG, les bots et le journal ne partent qu'à l'ouverture. Trois étapes, dans
l'ordre, chacune vérifiée à chaque pas de la boucle :

1. `decor` : l'engine a dit son décor du départ prêt (commande `scene_ready` avec le parcours en
   cours, contrat IPC révision 1.5) ; au plus `attente_decor_s` secondes, pour un engine qui ne
   l'envoie pas (ancien engine, séance sans engine) ; au plus ATTENTE_ENGINE_S si un engine s'est relié pendant
   l'attente (préparation des graphismes du premier lancement, lot PG1) ;
2. `trainer` : le trainer donne des mesures ;
3. `echauffement` (course seulement, `warmup.py`) : échauffement sur place en ERG, jusqu'au bout ou à Z ;
   gardé si le trainer décroche un moment (l'étape retombe, l'échauffement reprend où il en était) ;
4. `pedalage` : `duree_s` secondes de pédalage cumulées à au moins `cadence_rpm` tr/min ou
   `POWER_W` W (la cadence du trainer arrive en retard, la puissance tout de suite) ; un à-coup sous le seuil de moins de
   `TOLERANCE_S` secondes ne remet pas le compte à zéro, au-delà il redescend aussi vite qu'il monte.

Le décor et le trainer peuvent revenir en arrière (engine relancé, trainer perdu) : l'étape
retombe, le compte du pédalage repart de zéro. Le mode `immediat` ouvre le départ tout de suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PHASES = ("decor", "trainer", "echauffement", "pedalage")
# Attente du décor quand un engine s'est montré pendant l'attente (lot PG1, banc j26r2) : au premier lancement, la
# préparation des graphismes (une minute ou plus, pilote froid) passe avant le parcours ; `attente_decor_s` (60 s)
# coupait la préparation et la séance partait sans décor. Un engine présent finit par dire son décor prêt.
ATTENTE_ENGINE_S = 300.0
POWER_W = 40.0        # pédalage reconnu à la puissance, même quand la cadence est encore basse
TOLERANCE_S = 2.0     # à-coup toléré sous le seuil sans perdre le compte


@dataclass
class StartGate:
    cadence_rpm: float = 30.0
    duree_s: float = 1.0
    attente_decor_s: float = 60.0
    immediate: bool = False
    warmup: Any = None       # `warmup.Warmup` d'une course, None sinon

    def __post_init__(self) -> None:
        self.waited_s = 0.0      # depuis la commande start
        self.held_s = 0.0        # pédalage cumulé
        self._below_s = 0.0      # à-coup en cours sous le seuil
        self.phase = "open" if self.immediate else "decor"
        self.decor_timeout = False
        self.engine_seen = False   # un engine relié pendant l'attente : ATTENTE_ENGINE_S au lieu d'attente_decor_s

    @property
    def open(self) -> bool:
        return self.phase == "open"

    @property
    def warming(self) -> bool:
        """Échauffement prévu et pas encore fini (ni passé)."""
        return self.warmup is not None and not self.warmup.done

    def pedalling(self, cadence_rpm: float | None, power_w: float | None) -> bool:
        # La cadence du trainer arrive plusieurs secondes après les premiers coups de pédale, la puissance
        # tout de suite (journaux du 15 novembre) : l'une ou l'autre suffit.
        return (cadence_rpm is not None and cadence_rpm >= self.cadence_rpm) \
            or (power_w is not None and power_w >= POWER_W)

    @property
    def decor_limit_s(self) -> float:
        """Attente maximale du décor : `attente_decor_s`, portée à ATTENTE_ENGINE_S si un engine s'est relié pendant
        l'attente (préparation des graphismes au premier lancement) ; 0 (départ sans décor voulu) reste 0."""
        if self.engine_seen and self.attente_decor_s > 0:
            return max(self.attente_decor_s, ATTENTE_ENGINE_S)
        return self.attente_decor_s

    def update(self, dt: float, *, scene_ready: bool, trainer_connected: bool,
               cadence_rpm: float | None, power_w: float | None, engine_connected: bool = False) -> bool:
        """Un pas de `dt` secondes ; renvoie vrai quand le départ s'ouvre (une seule fois). `engine_connected` :
        engine relié à ce pas (un battement manqué pendant une image de plusieurs secondes ne l'oublie pas)."""
        if self.open:
            return False
        self.waited_s += dt
        self.engine_seen = self.engine_seen or engine_connected
        if not scene_ready and self.waited_s >= self.decor_limit_s:
            self.decor_timeout = True
        if not (scene_ready or self.decor_timeout):
            self._reset("decor")
            return False
        if not trainer_connected:
            self._reset("trainer")
            return False
        if self.warming:
            self.phase = "echauffement"
            self.warmup.step(dt)
            if not self.warmup.done:
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
        out = {"phase": self.phase, "cadence_rpm": int(round(self.cadence_rpm)),
               "hold_s": round(self.duree_s, 1), "held_s": round(min(self.held_s, self.duree_s), 1),
               "waited_s": round(self.waited_s, 1)}
        if self.warmup is not None:   # révision 1.33 : échauffement d'une course (`warmup.py`)
            out["warmup"] = self.warmup.to_dict()
        return out
