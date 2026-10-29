"""Journal de latence d'un appui du Click (lot X7) : notification → événement → envoi à l'engine → Control Point.

Activé par `[log] latence = true` ou `openride-core run --latence` ; sans, aucune ligne et aucun coût hors
d'un test de drapeau. Chaque appui reçoit un identifiant à la notification BLE qui le termine ; chaque
étage écrit une ligne `[latence] id=N etage=notif|evenement|ipc|cp t=…` (heure murale en secondes,
calculée sur l'horloge monotone depuis le démarrage, la même que celle de l'engine sur la même
machine). L'événement relayé à l'engine porte `latence_id` et `latence_t` (contrat IPC, message `input`) ;
l'engine écrit `recu` puis `affiche` (première image dessinée après le changement du HUD).
`openride-core log-report --latence CORE.log ENGINE.log` en fait la statistique.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections import deque
from typing import Any, Iterator

log = logging.getLogger("latence")

CP_WINDOW_S = 2.0   # un appui qui attend une écriture au Control Point l'attend au plus 2 s

_enabled = False
_next_id = 1
_wall0 = time.time()
_mono0 = time.monotonic()
_queues: dict[int, deque] = {}            # fournisseur d'entrées → identifiants dans l'ordre des événements
_current: int | None = None               # appui en cours de traitement par la séance
_waiting_cp: list[tuple[int, float]] = []  # (identifiant, heure) des appuis qui attendent une écriture


def enable(on: bool = True) -> None:
    global _enabled, _wall0, _mono0
    _enabled = on
    _wall0, _mono0 = time.time(), time.monotonic()
    _queues.clear()
    _waiting_cp.clear()


def enabled() -> bool:
    return _enabled


def now() -> float:
    """Heure murale lissée : départ en heure murale, puis horloge monotone (pas de saut NTP)."""
    return _wall0 + (time.monotonic() - _mono0)


def mark(press_id: int | None, stage: str, t: float | None = None) -> None:
    if _enabled and press_id is not None:
        log.info("[latence] id=%d etage=%s t=%.6f", press_id, stage, now() if t is None else t)


def new_press(provider: Any) -> None:
    """Notification BLE qui produit un événement du fournisseur `provider` : nouvel identifiant, étage
    `notif`, rangé dans la file du fournisseur (dans l'ordre de sa file d'événements)."""
    global _next_id
    if not _enabled:
        return
    press_id, _next_id = _next_id, _next_id + 1
    mark(press_id, "notif")
    _queues.setdefault(id(provider), deque()).append(press_id)


@contextlib.contextmanager
def handling(provider: Any) -> Iterator[int | None]:
    """Traitement par la séance d'un événement lu dans la file de `provider` : étage `evenement`."""
    global _current
    q = _queues.get(id(provider)) if _enabled else None
    press_id = q.popleft() if q else None
    mark(press_id, "evenement")
    _current = press_id
    try:
        yield press_id
    finally:
        _current = None


def ipc_fields() -> dict[str, Any]:
    """Champs ajoutés au message `input` de l'appui en cours (étage `ipc`) ; vide sans appui suivi."""
    if _current is None:
        return {}
    t = now()
    mark(_current, "ipc", t)
    return {"latence_id": _current, "latence_t": round(t, 6)}


def expect_cp() -> None:
    """L'appui en cours change la consigne du trainer (braquet, biais ERG) : la prochaine écriture compte."""
    if _current is not None:
        _waiting_cp.append((_current, time.monotonic()))


def cp_written() -> None:
    """Écriture au Control Point : étage `cp` des appuis qui l'attendent depuis moins de CP_WINDOW_S."""
    if not _waiting_cp:
        return
    limit = time.monotonic() - CP_WINDOW_S
    for press_id, since in _waiting_cp:
        if since >= limit:
            mark(press_id, "cp")
    _waiting_cp.clear()
