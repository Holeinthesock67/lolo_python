"""Frein lâché par le trainer : une seule règle pour le pilote et le rapport des décrochages (lot FR1).

Le 29 octobre, le trainer a lâché son frein en plein effort : 449 W puis 0 W en 2 s, à 73 tr/min
constants et 31 km/h, sans erreur ni statut. Le pilote (`ftms_driver.py`) le détecte en direct et
reprend le contrôle ; l'outil `tools/decrochages.py` le relit après la séance. Les deux lisent ici la
même définition.

Le piège : la cadence annoncée par le trainer est en retard d'environ 1 s sur la puissance. Quand le
cycliste arrête de pédaler, la puissance tombe tout de suite à 0 W mais l'ancienne cadence reste
affichée encore une seconde : un simple arrêt (fin de salle du Cyber-Rogue, fin d'épreuve au
vélodrome, 14 et 15 novembre) ressemble alors exactement à un frein lâché. D'où la règle :

- **chute** : la puissance passe sous `STOP_W` moins de `DROP_WINDOW_S` après le dernier relevé à
  `DROP_MIN_W` ou plus ; le niveau d'avant est la médiane des `DROP_WINDOW_S` qui précèdent ce relevé,
  au moins `DROP_MIN_W` ; le volant roule encore (`MIN_KMH`) ; consigne qui demande un effort (pas un
  bloc ERG à 0 W) ;
- **pédales qui tournent encore** : pendant `CONFIRM_S` après la chute, **chaque** relevé reste sous
  `STOP_W` avec une cadence d'au moins `PEDALS_MIN_RPM` **et** d'au moins `PEDALS_KEPT_FRAC` de la
  cadence au moment de la chute, sur au moins `CONFIRM_MIN_SAMPLES` relevés (le trainer n'en envoie
  qu'un par seconde au repos) ; sans assez de relevés au bout de `CONFIRM_MAX_S`, rien n'est conclu.
  Une chute n'est jugée qu'une fois : la suivante attend que la puissance repasse à `DROP_MIN_W`.
  `CONFIRM_S` vaut deux fois le retard connu de la cadence : un arrêt de pédalage a tout le temps de
  se voir ;
- **frein revenu** : après la reprise du contrôle, une puissance d'au moins `BACK_W` revenue en moins
  de `BACK_WINDOW_S` ne compte que si les pédales n'ont jamais cessé de tourner entre-temps. Un
  cycliste qui s'arrête puis repart ne prouve rien contre le trainer ;
- une reprise du contrôle au plus toutes les `COOLDOWN_S`.

Module pur, sans entrées-sorties : `BrakeWatch.step` reçoit chaque relevé et rend les événements.
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass

DROP_MIN_W = 150.0          # niveau d'avant la chute (médiane), même seuil que les chutes du rapport
STOP_W = 10.0               # puissance « nulle »
DROP_WINDOW_S = 3.0         # chute en 3 s au plus
PEDALS_MIN_RPM = 40.0       # pédales qui tournent
PEDALS_KEPT_FRAC = 0.75     # … sans perdre plus du quart de la cadence de la chute
CONFIRM_S = 2.0             # durée de la preuve (deux fois le retard de la cadence)
CONFIRM_MIN_SAMPLES = 2     # relevés après la chute, au moins
CONFIRM_MAX_S = 4.0         # sans assez de relevés après ce délai : rien n'est conclu
MIN_KMH = 15.0              # volant qui roule encore à la chute
COOLDOWN_S = 10.0           # une reprise du contrôle au plus toutes les 10 s
BACK_W = 50.0               # puissance revenue après la reprise : le frein est revenu
BACK_WINDOW_S = 15.0
HISTORY_S = 2 * DROP_WINDOW_S


def pedals_kept(cadence_at_drop: float, cadences: list[float]) -> bool:
    """Vrai si toutes les cadences montrent des pédales qui tournent encore comme à la chute."""
    floor = max(PEDALS_MIN_RPM, PEDALS_KEPT_FRAC * cadence_at_drop)
    return bool(cadences) and all(c >= floor for c in cadences)


@dataclass
class BrakeEvent:
    """Événement rendu par `BrakeWatch.step` : `brake_loss`, `power_back`, `power_not_back` ou
    `rider_stopped` (le cycliste a cessé de pédaler après la reprise : plus de preuve à attendre)."""
    kind: str
    from_w: float = 0.0
    to_w: float = 0.0
    cadence_rpm: float = 0.0
    speed_kmh: float | None = None
    after_s: float = 0.0
    power_w: float = 0.0


@dataclass
class _Drop:
    t: float
    from_w: float
    to_w: float
    cadence_rpm: float
    speed_kmh: float | None
    samples: int = 0


class BrakeWatch:
    """Suit les relevés du trainer et dit quand le frein a vraiment lâché (règle du module)."""

    def __init__(self) -> None:
        self._history: deque[tuple[float, float]] = deque()
        self._drop: _Drop | None = None
        self._lost_at: float | None = None
        self._last_loss_at = float("-inf")
        self._armed = False   # une seule chute jugée par effort : il faut repasser à DROP_MIN_W pour en juger une autre
        self.losses = 0

    @property
    def lost_at(self) -> float | None:
        """Instant de la dernière reprise du contrôle dont on attend encore le retour du frein."""
        return self._lost_at

    def step(self, now: float, power_w: float, cadence_rpm: float, speed_kmh: float | None,
             loaded: bool) -> list[BrakeEvent]:
        """Un relevé du trainer ; `loaded` : la consigne demande un effort (faux pour un bloc ERG à 0 W)."""
        events: list[BrakeEvent] = []
        self._history.append((now, power_w))
        if power_w >= DROP_MIN_W:
            self._armed = True
        while self._history and self._history[0][0] < now - HISTORY_S:
            self._history.popleft()
        self._follow_loss(now, power_w, cadence_rpm, events)
        self._follow_drop(now, power_w, cadence_rpm, speed_kmh, loaded, events)
        return events

    def _follow_loss(self, now: float, power_w: float, cadence_rpm: float, events: list[BrakeEvent]) -> None:
        if self._lost_at is None:
            return
        after = now - self._lost_at
        if cadence_rpm < PEDALS_MIN_RPM:
            events.append(BrakeEvent("rider_stopped", cadence_rpm=cadence_rpm, after_s=after))
            self._lost_at = None
        elif power_w >= BACK_W:
            events.append(BrakeEvent("power_back", after_s=after, power_w=power_w))
            self._lost_at = None
        elif after > BACK_WINDOW_S:
            events.append(BrakeEvent("power_not_back", after_s=BACK_WINDOW_S))
            self._lost_at = None

    def _follow_drop(self, now: float, power_w: float, cadence_rpm: float, speed_kmh: float | None,
                     loaded: bool, events: list[BrakeEvent]) -> None:
        drop = self._drop
        if drop is not None:
            if not (power_w < STOP_W and loaded and pedals_kept(drop.cadence_rpm, [cadence_rpm])):
                self._drop = None          # puissance revenue, ou les pédales ralentissent : pas le frein
                return
            drop.samples += 1
            waited = now - drop.t
            if waited >= CONFIRM_S and drop.samples >= CONFIRM_MIN_SAMPLES:
                self._drop = None
                self._last_loss_at = self._lost_at = now
                self.losses += 1
                events.append(BrakeEvent("brake_loss", drop.from_w, drop.to_w, drop.cadence_rpm, drop.speed_kmh))
            elif waited > CONFIRM_MAX_S:
                self._drop = None          # trop peu de relevés pour trancher : jamais « trainer » sans preuve
            return
        if not (self._armed and power_w < STOP_W and loaded and cadence_rpm >= PEDALS_MIN_RPM):
            return
        if speed_kmh is not None and speed_kmh < MIN_KMH:
            return
        if now - self._last_loss_at < COOLDOWN_S:
            return
        from_w = self._level_before(now)
        if from_w is not None:
            self._armed = False   # une cadence qui fond ne relance pas la preuve à chaque relevé
            self._drop = _Drop(now, from_w, power_w, cadence_rpm, speed_kmh)

    def _level_before(self, now: float) -> float | None:
        """Niveau d'avant la chute : médiane des 3 s qui précèdent le dernier relevé chargé, s'il est récent."""
        loaded_at = next((t for t, p in reversed(self._history) if p >= DROP_MIN_W and t < now), None)
        if loaded_at is None or now - loaded_at > DROP_WINDOW_S:
            return None
        level = statistics.median(p for t, p in self._history if loaded_at - DROP_WINDOW_S <= t <= loaded_at)
        return level if level >= DROP_MIN_W else None
