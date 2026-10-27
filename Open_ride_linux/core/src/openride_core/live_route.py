"""Route engagée d'un monde ouvert, lue par parties de 1 km (lot W9, `world_format_v1.md` §13).

`LiveRoute` a la même interface de lecture que `Route` (`grade_at`, `sample`, `length_m`, `wrap`,
`is_loop`). Le générateur prolonge et réécrit la route pendant la séance ; le core la relit quand un
message `revision` arrive. La lecture des fichiers et la construction de la nouvelle table se font
dans un fil ; la table est remplacée d'un coup sous verrou, si bien que la boucle à 50 Hz ne lit
jamais le disque et n'attend jamais plus qu'un échange de référence.

`base_m` est la distance déjà parcourue avant le début de la route actuelle : après une relance du
générateur (plantage), la nouvelle route repart d'un point du terrain et la distance du cycliste
continue de croître.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .route import ROUTE_FIELDS, Route, RouteSample, WorldError

log = logging.getLogger("live_route")

PART_M = 1000.0


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorldError("route_invalid", f"{path.name} illisible : {exc}") from exc
    if not isinstance(data, dict):
        raise WorldError("route_invalid", f"{path.name} n'est pas un objet JSON")
    return data


def read_live(folder: Path) -> dict[str, Any]:
    """`live.json` : état courant du monde vivant."""
    return _read_json(folder / "live.json")


def read_junctions(folder: Path) -> list[dict[str, Any]]:
    """Carrefours à venir (`junctions.json`) ; liste vide si le fichier n'existe pas encore."""
    path = folder / "junctions.json"
    if not path.is_file():
        return []
    items = _read_json(path).get("junctions")
    return [j for j in items if isinstance(j, dict)] if isinstance(items, list) else []


def assemble(parts: list[dict[str, Any]]) -> Route:
    """Route unique à partir des parties (bord partagé : le premier point des parties suivantes est sauté)."""
    if not parts:
        raise WorldError("route_invalid", "aucune partie de route")
    cols: dict[str, list[float]] = {k: [] for k in ROUTE_FIELDS}
    for k, part in enumerate(parts):
        for name in ROUTE_FIELDS:
            try:
                col = part[name]
            except (KeyError, TypeError) as exc:
                raise WorldError("route_invalid", f"partie {k} : colonne « {name} » absente") from exc
            cols[name].extend(col if k == 0 else col[1:])
    first, last = parts[0], parts[-1]
    try:
        length = float(last["s0_m"]) + float(last["length_m"]) - float(first["s0_m"])
        ds = float(first["ds_m"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WorldError("route_invalid", f"partie de route incomplète : {exc}") from exc
    return Route({"n": len(cols["lat"]), "ds_m": ds, "length_m": length, "type": "open", **cols})


class LiveRoute:
    """Route engagée d'une séance en monde ouvert (mêmes lectures que `Route`)."""

    def __init__(self, folder: Path, base_m: float = 0.0,
                 on_error: Callable[[str], None] | None = None) -> None:
        self.folder = Path(folder)
        self.base_m = base_m
        self._on_error = on_error
        self._lock = threading.Lock()
        self._route: Route | None = None
        self._parts: dict[int, dict[str, Any]] = {}
        self._junctions: list[dict[str, Any]] = []
        self.revision = 0
        self._worker: threading.Thread | None = None
        self._pending: tuple[int, int] | None = None   # (rev, première partie à relire) demandée pendant un chargement
        self.load_seconds = 0.0

    # --- lecture à 50 Hz ------------------------------------------------------------------

    def _current(self) -> Route:
        with self._lock:
            route = self._route
        if route is None:
            raise WorldError("route_invalid", "route du monde ouvert pas encore chargée")
        return route

    @property
    def junctions(self) -> list[dict[str, Any]]:
        """Carrefours à venir de la dernière révision chargée (`s_m` dans le repère de la route, sans `base_m`)."""
        with self._lock:
            return self._junctions

    @property
    def ready(self) -> bool:
        return self._route is not None

    @property
    def length_m(self) -> float:
        return self.base_m + self._current().length_m

    @property
    def is_loop(self) -> bool:
        return False

    @property
    def type(self) -> str:
        return "open"

    def wrap(self, s: float) -> float:
        return min(max(s, 0.0), self.length_m)

    def grade_at(self, s: float) -> float:
        """Pente en s ; au-delà de la route connue, celle du dernier point."""
        return self._current().grade_at(s - self.base_m)

    def sample(self, s: float) -> RouteSample:
        return self._current().sample(s - self.base_m)

    def known_ahead_m(self, s: float) -> float:
        """Distance de route connue devant `s`."""
        return self.length_m - s

    # --- révisions -----------------------------------------------------------------------

    def load(self) -> None:
        """Premier chargement, dans le fil appelant (préparation de la séance, avant `RUNNING`)."""
        live = read_live(self.folder)
        self._reload(int(live.get("revision", 0)), 0)

    def apply_revision(self, rev: int, changed_from_part: int = 0) -> None:
        """Charge la révision `rev` dans un fil et remplace la table d'un coup.

        Une demande qui arrive pendant un chargement est mémorisée : le fil la traite ensuite, en
        relisant à partir de la plus petite partie changée depuis.
        """
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                first = min(changed_from_part, self._pending[1]) if self._pending else changed_from_part
                self._pending = (rev, first)
                return
            self._worker = threading.Thread(target=self._work, args=(rev, changed_from_part),
                                            name="live-route", daemon=True)
            self._worker.start()

    def _work(self, rev: int, first: int) -> None:
        while True:
            try:
                self._reload(rev, first)
            except WorldError as exc:
                log.warning("Révision %d de la route non chargée : %s", rev, exc)
                if self._on_error:
                    self._on_error(str(exc))
            with self._lock:
                nxt, self._pending = self._pending, None
                if nxt is None:
                    self._worker = None
                    return
            rev, first = nxt

    def _reload(self, rev: int, first: int) -> None:
        t0 = time.perf_counter()
        live = read_live(self.folder)
        n_parts = int(live.get("route", {}).get("parts", 0))
        if n_parts < 1:
            raise WorldError("route_invalid", "live.json sans partie de route")
        parts = {k: v for k, v in self._parts.items() if k < min(first, n_parts)}
        for k in range(min(first, n_parts), n_parts):
            parts[k] = _read_json(self.folder / "route" / f"part_{k}.json")
        route = assemble([parts[k] for k in range(n_parts)])
        junctions = read_junctions(self.folder)
        with self._lock:
            self._parts = parts
            self._route = route
            self._junctions = junctions
            self.revision = max(rev, int(live.get("revision", rev)))
        self.load_seconds = time.perf_counter() - t0

    def wait(self, timeout: float = 5.0) -> bool:
        """Attend la fin du chargement en cours (tests) ; vrai si aucun chargement ne reste."""
        worker = self._worker
        if worker is not None:
            worker.join(timeout)
        return self._worker is None
