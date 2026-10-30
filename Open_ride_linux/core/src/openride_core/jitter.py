"""Gigue de la boucle du core (lot X17) : écart de chaque pas de physique à sa période, retard des trames `state`.

Critère de la série W : gigue de la boucle à 50 Hz sous 5 ms (p99) pendant la génération du monde.
`JitterMeter` range chaque écart dans un histogramme fixe (pas de 0,05 ms jusqu'à 100 ms, puis une case
« au-delà ») : coût constant, aucune liste qui grandit. La séance écrit toutes les 60 s une ligne
`Gigue : physique p50 … p99 … max … ms ; state p99 … max … ms (N pas)` pour la minute écoulée, et à la fin
la même ligne pour la séance entière (`Gigue (séance entière) : …`), lues par `log_report --gigue`.

Physique : |intervalle entre deux pas − 20 ms|. Trames `state` : retard de l'envoi sur son échéance fixe
de 33,3 ms ; elles partent sur un pas de physique, le retard reste donc sous 20 ms par construction.
"""

from __future__ import annotations

BIN_MS = 0.05
N_BINS = 2000            # 100 ms ; au-delà, la dernière case


class JitterMeter:
    def __init__(self) -> None:
        self.counts = [0] * (N_BINS + 1)
        self.n = 0
        self.max_ms = 0.0
        self._last: float | None = None

    def add(self, dev_ms: float) -> None:
        dev_ms = abs(dev_ms)
        self.counts[min(int(dev_ms / BIN_MS), N_BINS)] += 1
        self.n += 1
        if dev_ms > self.max_ms:
            self.max_ms = dev_ms

    def interval(self, t: float, period_s: float) -> None:
        """Pas à l'instant `t` (s) : compte l'écart de l'intervalle depuis le pas précédent à `period_s`."""
        if self._last is not None:
            self.add((t - self._last - period_s) * 1000.0)
        self._last = t

    def percentile(self, q: float) -> float:
        """Borne haute de la case qui contient le quantile `q` (précision BIN_MS), bornée par le maximum ;
        le maximum pour la case « au-delà »."""
        if self.n == 0:
            return 0.0
        rank = q * self.n
        seen = 0
        for i, c in enumerate(self.counts):
            seen += c
            if seen >= rank and c:
                return self.max_ms if i == N_BINS else min((i + 1) * BIN_MS, self.max_ms)
        return self.max_ms

    def merge(self, other: "JitterMeter") -> None:
        self.counts = [a + b for a, b in zip(self.counts, other.counts)]
        self.n += other.n
        self.max_ms = max(self.max_ms, other.max_ms)

    def clear(self) -> None:
        """Remet les comptes à zéro ; garde l'instant du dernier pas (l'intervalle suivant reste juste)."""
        self.counts = [0] * (N_BINS + 1)
        self.n = 0
        self.max_ms = 0.0


def line(physics: JitterMeter, state: JitterMeter, whole: bool = False) -> str:
    """Ligne du journal ; format lu par `tools/log_report.py`."""
    return ("Gigue%s : physique p50 %.2f p99 %.2f max %.2f ms ; state p99 %.2f max %.2f ms (%d pas)"
            % (" (séance entière)" if whole else "", physics.percentile(0.50), physics.percentile(0.99),
               physics.max_ms, state.percentile(0.99), state.max_ms, physics.n))
