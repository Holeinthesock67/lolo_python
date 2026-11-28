"""Filet « à l'identique » des modes de jeu (lot IM0, cadrage de l'interface des modes du 22/11, §5.2).

Une séance scriptée et déterministe par cas : trainer simulé à puissance fixe, horloge murale figée et avancée pas
à pas, graines tirées de cette horloge, boutons et commandes joués à des pas donnés. On relève cinq choses :

- `journal` : toutes les lignes du journal de la séance (`.jsonl`) ;
- `trames` : une trame `state` sur dix pas (les parties propres aux modes comprises) ;
- `bilan` : le bilan de fin de séance (`state.summary`) ;
- `trainer` : la suite des consignes envoyées au trainer (pente, puissance ERG, vent), avec leur pas ;
- `messages` : les messages et erreurs envoyés à l'engine, et les fichiers écrits (FIT, records, cote Elo…).

Chaque relevé est réduit à une empreinte SHA-256 de son JSON canonique, comparée à la référence du dépôt
(`core/tests/data/modes_identique.json`). Une refonte de `session.py` (série IM) ne doit en changer aucune.

Bibliothèque partagée par `test_modes_identique.py` et `scripts/modes_identique.py` (référence recalculée,
relevé complet écrit pour comparer deux versions). Aucun fichier écrit hors du dossier donné.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

REFERENCE = Path(__file__).resolve().parent / "data" / "modes_identique.json"
RELEVES = ("journal", "trames", "bilan", "trainer", "messages")
DT = 0.02
FRAME_EVERY = 10                       # une trame relevée tous les 10 pas (5 par seconde)
T0_WALL = 1_790_000_000.0              # 2026-09-21 13:33:20 UTC
POWER_W = 250.0                        # FTP fictive du profil d'essai, jamais une valeur réelle
PYTHON_MIN = (3, 13)                   # mêmes octets en 3.13 et 3.14 ; 3.11 diffère (pickle du Rogue, un arrondi)
SEED_WITHOUT_SEED = 1234               # graine donnée aux `random.Random()` créés sans graine


class _FrozenDatetime(_dt.datetime):
    """`datetime.now()` et `today()` lus sur l'horloge figée du banc (dates des records, du profil…)."""

    clock: list[float] = [T0_WALL]

    @classmethod
    def now(cls, tz=None):  # noqa: D102
        return _dt.datetime.fromtimestamp(cls.clock[0], tz)

    @classmethod
    def today(cls):  # noqa: D102
        return _dt.datetime.fromtimestamp(cls.clock[0])


class _FrozenDate(_dt.date):
    clock: list[float] = [T0_WALL]

    @classmethod
    def today(cls):  # noqa: D102
        return _dt.date.fromtimestamp(cls.clock[0])


class _SeededRandom(random.Random):
    """`random.Random()` sans graine (bonus en réserve du mode classique, graine d'une run) : graine fixe."""

    def __init__(self, x: Any = None) -> None:
        super().__init__(SEED_WITHOUT_SEED if x is None else x)


@contextlib.contextmanager
def _patched(obj: Any, name: str, value: Any) -> Iterator[None]:
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


@contextlib.contextmanager
def frozen_world(root: Path) -> Iterator[list[float]]:
    """Horloge murale figée (`time.time`, `strftime`, `localtime`, `datetime.now`, `date.today`) en UTC,
    `random.Random()` sans graine fixé (`SEED_WITHOUT_SEED`), profil de joueur neuf sous `root`, fichiers du joueur sous `root`. Rend la liste `[t]` de l'horloge."""
    import os

    from openride_core import classic, config, fit_export, powerups, profile, profiles, records, session

    wall = [T0_WALL]
    _FrozenDatetime.clock = wall
    _FrozenDate.clock = wall
    real_strftime, real_localtime = time.strftime, time.localtime
    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    root.mkdir(parents=True, exist_ok=True)
    patches = [
        (time, "time", lambda: wall[0]),
        (random, "Random", _SeededRandom),
        (time, "strftime", lambda fmt, t=None: real_strftime(fmt, real_localtime(wall[0]) if t is None else t)),
        (time, "localtime", lambda t=None: real_localtime(wall[0] if t is None else t)),
        (session, "datetime", _FrozenDatetime), (session, "date", _FrozenDate),
        (classic, "datetime", _FrozenDatetime),
        (config, "DEPART_MODE_DEFAULT", "immediat"),
        (fit_export, "ACTIVITIES_DIR", root / "act"),
        (profile, "PROFILE_PATH", root / "profile.json"),
        (records, "RECORDS_FILE", root / "records.json"),
        (powerups, "POWERUPS_FILE", root / "powerups.toml"),
    ]
    old_active = profiles._active
    with contextlib.ExitStack() as stack:
        for obj, name, value in patches:
            stack.enter_context(_patched(obj, name, value))
        ctx = profiles.create("Banc", base=root / "Profils", today=_dt.date(2026, 1, 1))
        profiles.activate(ctx)
        try:
            yield wall
        finally:
            profiles.activate(old_active)
            if old_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old_tz
            time.tzset()


def _recording_driver(log: list, step: list[int]):
    from openride_core.mock_driver import MockDriver

    class RecordingDriver(MockDriver):
        """Trainer simulé à puissance fixe qui note chaque consigne reçue, avec le pas."""

        def set_target_power(self, watts: float) -> bool:
            log.append([step[0], "erg", watts])
            return super().set_target_power(watts)

        def set_sim_grade(self, grade_pct: float, immediate: bool = False) -> bool:
            log.append([step[0], "sim", grade_pct, immediate])
            return super().set_sim_grade(grade_pct, immediate)

        def set_wind(self, wind_mps: float) -> None:
            log.append([step[0], "wind", wind_mps])
            super().set_wind(wind_mps)

    return RecordingDriver(base_power_w=POWER_W, ramp_amplitude_w=0.0)


@dataclass
class Banc:
    """Une séance scriptée : `cmd`, `press`, `run`, puis `releve()`."""

    root: Path
    wall: list[float]
    port: int
    configure: Callable[[Any], None] | None = None
    routes: Path | None = None
    trainer: list = field(default_factory=list)
    frames: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    step_no: list[int] = field(default_factory=lambda: [0])

    def __post_init__(self) -> None:
        from openride_core.config import Config
        from openride_core.input_providers import NullProvider
        from openride_core.session import CoreSession

        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = self.port, self.port + 1
        if self.configure:
            self.configure(cfg)
        routes = self.routes or self.root / "routes"
        workouts = self.root / "Workouts"
        workouts.mkdir(parents=True, exist_ok=True)
        s = CoreSession(cfg, driver=_recording_driver(self.trainer, self.step_no), inputs=[NullProvider()],
                        journal_dir=self.root / "journal", routes_root=routes, workouts_dir=workouts,
                        records_path=self.root / "records.json", powerups_path=self.root / "powerups.toml",
                        wtf_path=self.root / "wtf.toml", grandprix_path=self.root / "grandprix.toml",
                        config_path=self.root / "config.toml")
        msgs = self.messages
        s.server.send_raw = lambda m, max_size=None: msgs.append([self.step_no[0], "raw", m])
        s.server.send_error = lambda code, text: msgs.append([self.step_no[0], "error", code, text])
        s.server.send_input_event = lambda ev: msgs.append([self.step_no[0], "input", ev])
        self.s = s

    # --- script ---------------------------------------------------------------------------------------

    def cmd(self, name: str, args: dict | None = None) -> None:
        """Commande de l'engine (`_on_command`), numérotée dans l'ordre."""
        self.messages.append([self.step_no[0], "cmd", name, args or {}])
        self.s._on_command(name, args or {}, len(self.messages))

    def press(self, event: str) -> None:
        """Appui du Click (`InputEvent`), comme `_drain_inputs`."""
        from openride_core.zwift_click import InputEvent

        self.messages.append([self.step_no[0], "press", event])
        self.s._handle_input(InputEvent(event))

    def run(self, seconds: float, until: Callable[[Any], bool] | None = None, power_w: float | None = None,
            end_at_arrival: bool = True, dt: float = DT, each: Callable[[Any], None] | None = None) -> None:
        """Avance de `seconds` (pas de 20 ms, ou `dt`) tant que la séance roule ; arrivée de course : fin
        enregistrée (« Y puis A maintenu », lot RT2). `each(session)` est appelé avant chaque pas (puissance du
        cycliste qui suit une cible)."""
        s = self.s
        if power_w is not None:
            s.driver.base_power_w = power_w
        for _ in range(int(round(seconds / dt))):
            st = s.state.session_state
            if st not in ("RUNNING", "PAUSED", "READY"):
                return
            if until is not None and until(s):
                return
            if end_at_arrival and st == "RUNNING" and s.state.arrival is not None \
                    and s.state.arrival.get("kind") != "workout":
                self.cmd("end_session", {"save": True})
                return
            if each is not None:
                each(s)
            self.wall[0] += dt
            self.step_no[0] += 1
            s._safe_step(dt, self.wall[0])
            if self.step_no[0] % FRAME_EVERY == 0:
                s._fill_mode_frames(self.wall[0])
                self.frames.append(s.state.to_dict())

    # --- relevé ---------------------------------------------------------------------------------------

    def files(self) -> dict[str, str]:
        """Empreinte des fichiers écrits par la séance, hors parcours et journal (relevés à part)."""
        out: dict[str, str] = {}
        skip = {"routes", "journal", "Workouts"}
        for p in sorted(self.root.rglob("*")):
            rel = p.relative_to(self.root)
            if p.is_file() and rel.parts[0] not in skip and ".verrou" not in rel.name:
                out[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    def releve(self) -> dict[str, Any]:
        journal: list[Any] = []
        for p in sorted((self.root / "journal").glob("**/*.jsonl")):
            journal.append(p.name)
            journal.extend(json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip())
        return {"journal": journal, "trames": self.frames, "bilan": self.s.state.summary,
                "trainer": self.trainer, "messages": {"engine": self.messages, "fichiers": self.files()}}


def canonical(obj: Any, root: Path) -> bytes:
    """JSON canonique (clés triées, flottants en `repr`), chemins du dossier de travail remplacés."""
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return text.replace(str(root), "<TMP>").encode("utf-8")


def fingerprint(rel: dict[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    out = {}
    for key in RELEVES:
        value = rel[key]
        n = len(value) if isinstance(value, (list, dict)) else (0 if value is None else 1)
        out[key] = {"n": n, "sha256": hashlib.sha256(canonical(value, root)).hexdigest()}
    return out


def load_reference(path: Path = REFERENCE) -> dict[str, Any]:
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return {}


def play(name: str, root: Path, port: int = 7600) -> dict[str, Any]:
    """Joue le scénario `name` dans `root` (dossier neuf) et rend son relevé complet (bancs mis bout à bout)."""
    from identique_scenarios import SCENARIOS, prepare_routes

    with frozen_world(root) as wall:
        prepare_routes(root / "routes")
        ports = iter(range(port, port + 40, 2))

        def make(configure: Callable[[Any], None] | None = None, continue_from: Banc | None = None) -> Banc:
            if continue_from is not None:   # core relancé : même dossier, même horloge, mêmes relevés
                c = continue_from
                return Banc(root, wall, next(ports), configure, trainer=c.trainer, frames=c.frames,
                            messages=c.messages, step_no=c.step_no)
            return Banc(root, wall, next(ports), configure)

        bancs = SCENARIOS[name](make)
        rel = bancs[-1].releve()
        return rel
