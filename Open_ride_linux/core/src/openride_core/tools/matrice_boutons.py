"""Matrice des boutons et des réglages, par mode et par phase de jeu, dans la vraie séance du core (lot X42).

    python -m openride_core.tools.matrice_boutons [--partie boutons|reglages|tout] [--mode sim|erg|rogue|monde|tous]
        [--json] [--md RAPPORT.md]

**Boutons.** Chaque mode (classique SIM, ERG, Cyber-Rogue, monde ouvert) est amené à chacune de ses phases :
prêt, en route, bonus en réserve, bloc FreeRide (palier à 50 W, lot O19), dernier bloc et fin de l'entraînement ERG, échauffement, salle,
couloir, boss, retour au calme et résultats du Cyber-Rogue, carrefour du monde ouvert, pause, bilan. À chaque
phase, la séance est copiée une fois par bouton du Click (les 16 événements, appuis courts, longs et ambigus).
Chaque copie reçoit son appui par le chemin du Click (`_handle_input`) et avance d'une seconde. L'effet relevé
dans le core est comparé à celui que donne le **plan des boutons** de la spécification générale (§7.1), lu
dans le document lui-même et non recopié ici. En séance, la colonne est celle du mode que la séance annonce
(`state.mode`, monde ouvert à part). Hors séance (prêt, pause, bilan), l'écran affiché est un menu de
l'engine : le core doit seulement relayer l'appui, sans rien changer (les menus eux-mêmes : `menu_bench`).
Une case du plan que l'outil ne sait pas lire est signalée comme « case non décrite ».

**Clavier.** Le tableau du clavier du §7.1 est lu à son tour : chaque touche, appui court, entre les deux et
long, doit donner l'événement du Click que donnerait le même appui sur son bouton (décodeur du core, mêmes
seuils). Les tables de `engine/scripts/key_map.gd` sont comparées à ce plan, touche par touche, seuils
compris. Puis, à chaque phase où la séance roule (aucun menu affiché), chaque événement que donne une touche
est envoyé par le chemin du clavier (`input_event`, comme l'engine) et doit avoir l'effet de la case du plan.
Menu affiché (prêt, pause, bilan) : l'engine traite la touche sans le core ; c'est le banc des menus.

**Boîtier gauche.** Il répond (flèches et −), mais OpenRide le redémarre environ une fois par minute (verrou
Zwift, SRS §4.2) : environ 4 s sans boutons. D'où « rien d'indispensable n'est mis sur le seul boîtier gauche » (§7.1). À chaque phase où la séance roule, l'effet de chaque flèche doit aussi être obtenu par
un bouton du boîtier droit, sauf la vue de caméra (confort) ; le décodeur doit lire B comme « − ».

**Réglages.** Chaque réglage du menu (`settings.SETTINGS`) est changé d'un pas à chaque phase : accueil, prêt
en SIM et en ERG, en route, pause, bilan. Règle vérifiée : hors séance, tout réglage est accepté ; en séance,
ceux que l'engine applique tout de suite (`applies = now`) sont acceptés et les autres refusés (`busy`). Un
réglage accepté doit être relu à sa nouvelle valeur et écrit dans `config.toml`. Son effet est ensuite
vérifié dans la séance qui suit (FTP de la cible ERG, masse, difficulté, braquet de départ, bonus, vent),
ou la valeur annoncée à l'engine pour ceux qu'il applique.

Le journal, le FIT et la configuration restent dans un dossier temporaire. Code de sortie : 0 si toutes les
cases passent, 1 sinon, 2 pour un appel invalide.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator
from unittest import mock

from .. import fit_export
from .. import settings as settings_mod
from ..config import Config
from ..free_erg import FreeErg
from ..input_providers import NullProvider
from ..mock_driver import MockDriver
from ..session import CoreSession
from ..zwift_click import (KEYPAD_ALL_RELEASED, KEYPAD_B_BIT, MSG_KEYPAD_STATUS, SHORT_MAX_S, LONG_MIN_S,
                           InputEvent, PressClassifier, parse_click_buttons)

ROOT = Path(__file__).resolve().parents[4]
SPEC = ROOT / "docs" / "SPECIFICATION_GENERALE.md"
STUB_WORLDGEN = ROOT / "core" / "tests" / "data" / "stub_worldgen.py"
DT = 0.1                         # pas de la simulation pour atteindre les phases
AFTER_S = 1.0                    # temps laissé à l'appui pour agir (un pas de run du Cyber-Rogue)
COLUMNS = {"SIM": "Classique SIM", "ERG": "ERG", "ROGUE": "Cyber-Rogue", "MONDE": "Monde ouvert",
           "MENU": "Menus"}
# Lignes du tableau §7.1 : libellé de la ligne → (événement, sens) ; le sens donne le signe des pas.
ROWS = {
    "+ / B (ou −), court": ((InputEvent.PLUS_SHORT, 1), (InputEvent.MINUS_SHORT, -1)),
    "+ / B (ou −), long": ((InputEvent.PLUS_LONG, 1), (InputEvent.MINUS_LONG, -1)),
    "Y court": ((InputEvent.Y_SHORT, 0),),
    "Z court": ((InputEvent.Z_SHORT, 0),),
    "Z long": ((InputEvent.Z_LONG, 0),),
    "A court": ((InputEvent.A_SHORT, 1),),
    "A long": ((InputEvent.A_LONG, 0),),
    "Flèches gauche, droite (boîtier gauche)": ((InputEvent.LEFT_SHORT, -1), (InputEvent.RIGHT_SHORT, 1)),
    "Flèches haut, bas (boîtier gauche)": ((InputEvent.UP_SHORT, 1), (InputEvent.DOWN_SHORT, -1)),
}
# Appui ni court ni long : « entre les deux, rien ne se passe et l'écran le dit » (§7.1, avant le tableau).
UNCLEAR = (InputEvent.PLUS_UNCLEAR, InputEvent.MINUS_UNCLEAR)
UNCLEAR_CELL = "Aucune (appui ni court ni long)"
WORKOUT = """<workout_file><name>Matrice X42</name><sportType>bike</sportType><workout>
<SteadyState Duration="120" Power="0.6"/><FreeRide Duration="60"/><SteadyState Duration="60" Power="0.7"/>
</workout></workout_file>"""
WORLD_START = {"lat": 45.0, "lon": 6.0, "heading_deg": 90, "nav": "ride", "seed": 7}
KEY_MAP = ROOT / "engine" / "scripts" / "key_map.gd"
# Tableau du clavier §7.1 : libellé de la colonne « Bouton du Click » → bouton du décodeur du core.
KEY_BUTTONS = {"+": "PLUS", "− ou B": "MINUS", "A": "A", "Y": "Y", "Z": "Z", "Flèches du boîtier gauche": "ARROWS"}
ARROW_KEYS = {"Flèche gauche": "LEFT", "Flèche droite": "RIGHT", "Flèche haut": "UP", "Flèche bas": "DOWN"}
# Touches de Godot (key_map.gd) → libellé du plan ; l'Entrée du pavé numérique est une Entrée.
GODOT_KEYS = {"KEY_PLUS": "+", "KEY_EQUAL": "=", "KEY_KP_ADD": "+ du pavé numérique", "KEY_MINUS": "−",
              "KEY_KP_SUBTRACT": "− du pavé numérique", "KEY_A": "A", "KEY_Y": "Y", "KEY_Z": "Z",
              "KEY_ESCAPE": "Échap", "KEY_PAGEUP": "Page haut", "KEY_PAGEDOWN": "Page bas", "KEY_ENTER": "Entrée",
              "KEY_KP_ENTER": "Entrée", "KEY_LEFT": "Flèche gauche", "KEY_RIGHT": "Flèche droite",
              "KEY_UP": "Flèche haut", "KEY_DOWN": "Flèche bas"}
HOLDS = {"court": 0.2, "entre les deux": 0.7, "long": 1.2}
LEFT_ONLY = (InputEvent.LEFT_SHORT, InputEvent.RIGHT_SHORT, InputEvent.UP_SHORT, InputEvent.DOWN_SHORT)
RIGHT_UNIT = tuple(ev for ev in InputEvent if ev not in LEFT_ONLY)   # +, A, Y, Z, et − par B


class MatrixError(Exception):
    """Appel invalide ou plan des boutons illisible."""


# --- plan des boutons (§7.1) ----------------------------------------------------------------------------

def read_plan(path: Path = SPEC) -> dict[tuple[InputEvent, str], tuple[str, int]]:
    """Cases du tableau §7.1 : (événement, colonne) → (texte de la case, sens de l'appui)."""
    text = path.read_text("utf-8")
    m = re.search(r"^### 7\.1 .*?$(.*?)^### ", text, re.M | re.S)
    if m is None:
        raise MatrixError(f"section 7.1 introuvable dans {path}")
    lines = [ln for ln in m.group(1).splitlines() if ln.startswith("| ")]
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    if header[0] != "Bouton":
        raise MatrixError(f"tableau du plan des boutons illisible : {header}")
    plan: dict[tuple[InputEvent, str], tuple[str, int]] = {}
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if cells[0] not in ROWS:
            break                    # fin du tableau (le suivant est celui du clavier)
        row = dict(zip(header, cells))
        for ev, sign in ROWS[cells[0]]:
            prev = None
            for key, col in COLUMNS.items():
                cell = row.get(col, "")
                if cell == "idem" and prev is not None:
                    cell = prev
                plan[(ev, key)] = (cell, sign)
                prev = cell
    missing = [r for r in ROWS if not any(k[0] == ROWS[r][0][0] for k in plan)]
    if missing:
        raise MatrixError(f"lignes absentes du plan des boutons : {', '.join(missing)}")
    for ev in UNCLEAR:
        for key in COLUMNS:
            plan[(ev, key)] = (UNCLEAR_CELL, 0)
    return plan


# --- clavier (§7.1, tableau du clavier) ---------------------------------------------------------------------

def click_event(button: str, held_s: float) -> str:
    """Événement que le décodeur du core donne pour un appui de `held_s` secondes sur `button` ("" : aucun)."""
    pc = PressClassifier()
    pc.update(button, True, 0.0)
    ev = pc.update(button, False, held_s)
    return ev.value if ev else ""


def read_keys(path: Path = SPEC) -> dict[str, dict[str, str]]:
    """Touches du tableau du clavier §7.1 : libellé → {durée d'appui : événement attendu}. Une touche double son
    bouton avec les mêmes seuils ; les synonymes de l'appui long et « … vaut Y court » donnent un seul événement."""
    text = path.read_text("utf-8")
    m = re.search(r"^### 7\.1 .*?$(.*?)^### ", text, re.M | re.S)
    rows = [ln for ln in (m.group(1) if m else "").splitlines() if ln.startswith("| ")]
    start = next((i for i, ln in enumerate(rows) if ln.startswith("| Bouton du Click |")), None)
    if start is None:
        raise MatrixError(f"tableau du clavier introuvable au §7.1 de {path}")
    keys: dict[str, dict[str, str]] = {}
    for ln in rows[start + 2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if cells[0] not in KEY_BUTTONS:
            break
        button = KEY_BUTTONS[cells[0]]
        if button == "ARROWS":
            for label, b in ARROW_KEYS.items():
                keys[label] = {d: click_event(b, t) for d, t in HOLDS.items()}
        else:
            for label in (k for k in re.split(r"\s*(?:\(ou |\(|\)|,)\s*", cells[1]) if k):
                keys[label] = {d: click_event(button, t) for d, t in HOLDS.items()}
            for label in (k.strip() for k in cells[2].split(",") if k.strip() not in ("—", "")):
                keys[label] = {d: f"{button}_LONG" for d in HOLDS}
        for syn, letter in re.findall(r"(\S+) vaut (\w) court", cells[3]):
            keys[syn] = {d: f"{letter}_SHORT" for d in HOLDS}
    if not keys:
        raise MatrixError(f"tableau du clavier vide au §7.1 de {path}")
    return keys


def read_key_map(path: Path = KEY_MAP) -> tuple[dict[str, dict[str, str]], tuple[float, float]]:
    """Tables de key_map.gd (MEASURED, FIXED, SHIFT_LONG) et seuils, rejoués comme `event_for`."""
    text = path.read_text("utf-8")

    def table(name: str) -> list[tuple[str, str]]:
        tm = re.search(rf"^const {name} := \{{(.*?)\}}", text, re.M | re.S)
        if tm is None:
            raise MatrixError(f"table {name} introuvable dans {path}")
        return re.findall(r'(KEY_\w+): "(\w+)"', tm.group(1))

    def const(name: str) -> float:
        cm = re.search(rf"^const {name} := ([\d.]+)", text, re.M)
        if cm is None:
            raise MatrixError(f"seuil {name} introuvable dans {path}")
        return float(cm.group(1))
    short_max, long_min = const("SHORT_MAX_S"), const("LONG_MIN_S")
    keys: dict[str, dict[str, str]] = {}
    for k, button in table("MEASURED"):
        keys[GODOT_KEYS.get(k, k)] = {
            d: f"{button}_SHORT" if t < short_max else f"{button}_LONG" if t >= long_min else
            (f"{button}_UNCLEAR" if button in ("PLUS", "MINUS") else "") for d, t in HOLDS.items()}
    for k, ev in table("FIXED"):
        keys[GODOT_KEYS.get(k, k)] = {d: ev for d in HOLDS}
    for k, ev in table("SHIFT_LONG"):
        keys["Maj+" + GODOT_KEYS.get(k, k)] = {d: ev for d in HOLDS}
    return keys, (short_max, long_min)


@dataclass
class KeyCell:
    key: str
    hold: str
    plan: str                    # événement que donne le plan (§7.1), "" : aucun, None : touche absente du plan
    key_map: str | None          # événement que donne key_map.gd, None : touche absente de key_map.gd
    ok: bool
    detail: str = ""


def check_keys(spec: Path = SPEC, key_map: Path = KEY_MAP) -> list[KeyCell]:
    plan = read_keys(spec)
    engine, (short_max, long_min) = read_key_map(key_map)
    cells = [KeyCell("seuils", "court / long", f"{SHORT_MAX_S} / {LONG_MIN_S} s", f"{short_max} / {long_min} s",
                     (short_max, long_min) == (SHORT_MAX_S, LONG_MIN_S), "mêmes seuils que le décodeur du Click")]
    for key in list(plan) + [k for k in engine if k not in plan]:
        for hold in HOLDS:
            want, got = plan.get(key, {}).get(hold), engine.get(key, {}).get(hold)
            detail = ("touche absente du plan" if key not in plan else
                      "touche absente de key_map.gd" if key not in engine else "")
            cells.append(KeyCell(key, hold, want, got, want == got and want is not None, detail))
    return cells


# Effet attendu d'une case, lu dans son texte. `kind` : gear, bias, brake (pas de braquet ou de biais),
# pause, bonus, block, run (bouton reçu par le moteur de run), choice / validate (choix affiché, sinon
# caméra : engine), engine (relais seul : vue de caméra), none (aucun effet).
@dataclass(frozen=True)
class Expect:
    kind: str
    step: float = 0.0
    fallback: str = "engine"     # choix sans choix affiché : vue de caméra (engine) ; « Aucune » sinon


def expect_of(cell: str, sign: int, column: str) -> Expect | None:
    c = cell.lower()
    if c.startswith("comme le mode roulé"):
        return None              # résolu par l'appelant (colonne SIM ou ERG)
    if num := re.match(r"braquet ± (\d+)", c):
        return Expect("gear", sign * int(num.group(1)))
    if num := re.match(r"biais ± (\d+) %", c):
        return Expect("bias", sign * float(num.group(1)))
    if num := re.match(r"vitesse du frein ± (\d+)", c):
        return Expect("brake", sign * int(num.group(1)))
    if c.startswith("pause et reprise"):
        return Expect("pause")
    if c.startswith("bonus"):
        return Expect("bonus")
    if c.startswith("bloc suivant"):
        return Expect("block")
    if c.startswith("attaque") or c.startswith("carte ou relique active"):
        return Expect("run")
    if c.startswith(("couloir ou carte suivant", "couloir ou carte précédent")):
        return Expect("choice", sign)
    if c.startswith("valider le couloir"):
        return Expect("validate")
    if c.startswith("branche suivante") or c.startswith("branche à gauche"):
        return Expect("choice", sign, "engine" if "sinon" in c else "none")
    if c.startswith("valider la branche"):
        return Expect("validate")
    if c.startswith("repère « décrochage »"):
        return Expect("mark")
    if c.startswith(("vue de caméra", "revenir à la vue", "vue suivante")):
        return Expect("engine")
    if c.startswith("aucune"):
        return Expect("none")
    return None


# --- séance et phases -------------------------------------------------------------------------------------

class _NullRecorder:
    """Journal des copies : rien n'est écrit (le vrai reste à la séance d'origine)."""

    failed = False
    path = None

    def __getattr__(self, name: str) -> Callable[..., None]:
        return lambda *a, **k: None


@dataclass
class Phase:
    mode: str                    # SIM, ERG, ROGUE, MONDE
    name: str
    session: CoreSession
    note: str = ""


class Harness:
    """Séances réelles sans trainer ni engine, dans un dossier temporaire ; messages vers l'engine relevés."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.sent: list[dict] = []
        (tmp / "workouts").mkdir(parents=True, exist_ok=True)
        (tmp / "workouts" / "matrice_x42.zwo").write_text(WORKOUT, "utf-8")
        self.n = 0

    def session(self, power: float = 180.0) -> CoreSession:
        self.n += 1
        d = self.tmp / f"s{self.n}"
        cfg = Config()
        cfg.depart.mode = "immediat"   # banc sans engine ni cycliste : départ à la commande start (lot O36)
        cfg.ipc.port_state, cfg.ipc.port_commands = 0, 0
        cfg.open_world.cache_dir = str(d / "cache")
        s = CoreSession(cfg, driver=MockDriver(base_power_w=power, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                        journal_dir=d / "journal", routes_root=d / "routes", workouts_dir=self.tmp / "workouts",
                        records_path=d / "records.json", powerups_path=d / "powerups.toml",
                        profile_path=d / "profile.json", config_path=d / "config.toml")
        self.spy(s)
        s.clock = 1000.0
        return s

    def spy(self, s: CoreSession) -> None:
        s.server.send_raw = lambda m, max_size=None: self.sent.append(m)
        s.server.send_input_event = lambda ev: self.sent.append({"type": "input", "event": ev})
        s.server.send_error = lambda code, msg="", **k: self.sent.append({"type": "error", "code": code, "message": msg})

    def cmd(self, s: CoreSession, name: str, args: dict | None = None) -> None:
        s._on_command(name, args or {}, 1)

    def run(self, s: CoreSession, seconds: float, until: Callable[[], bool] | None = None) -> None:
        for _ in range(int(round(seconds / DT))):
            if until is not None and until():
                return
            s.clock += DT
            s._step(DT, s.clock)
            if s.openworld is not None:
                _sync_world(s)

    def fork(self, s: CoreSession) -> CoreSession:
        """Copie indépendante de la séance (même serveur, journal muet) ; le générateur du monde est partagé."""
        memo: dict[int, Any] = {id(s.server): s.server, id(s.stop_event): s.stop_event, id(s.stats): s.stats}
        if s._rec is not None:
            memo[id(s._rec)] = _NullRecorder()
        if s.openworld is not None:   # générateur et route vivante (fil de préparation) : partagés
            for shared in (s.openworld.client, s.openworld.route, s.route):
                if shared is not None:
                    memo[id(shared)] = shared
        return copy.deepcopy(s, memo)


def _sync_world(s: CoreSession) -> None:
    """Laisse la doublure du générateur répondre (même attente que les tests du lot W9)."""
    ow = s.openworld
    c = ow.client if ow is not None else None
    if c is None or c._proc is None or c.sent == getattr(c, "synced", 0):
        return
    path = ow.folder.parent / f"handled.{c._proc.pid}.json"
    deadline = time.monotonic() + 10.0
    while c.alive and path.exists() and time.monotonic() < deadline:
        try:
            counts = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if counts["handled"] >= c.sent and c.received >= counts["sent"]:
            break
        time.sleep(0.001)
    c.synced = c.sent


def phases_sim(h: Harness) -> Iterator[Phase]:
    s = h.session()
    h.cmd(s, "select_route", {"route_id": "demo"})
    yield Phase("SIM", "prêt", s)
    h.cmd(s, "start")
    h.run(s, 20.0)
    yield Phase("SIM", "en route", s)
    for mode, name in (("erg", "ERG libre"), ("cadence", "ERG à cadence verrouillée")):   # lot O18
        e = h.fork(s)
        h.cmd(e, "set_ride_mode", {"mode": mode})
        yield Phase("SIM", name, e)
        if e.race is not None and mode == "erg":
            b = h.fork(e)
            b.race.powerups.reserve = next(iter(b.race.powerups.table.specs))
            yield Phase("SIM", "ERG libre, bonus en réserve", b)
    if s.race is not None:
        b = h.fork(s)
        b.race.powerups.reserve = next(iter(b.race.powerups.table.specs))
        yield Phase("SIM", "bonus en réserve", b)
    p = h.fork(s)
    h.cmd(p, "pause")
    yield Phase("SIM", "pause", p)
    h.cmd(s, "end_session", {"save": True})
    yield Phase("SIM", "bilan", s)


def phases_erg(h: Harness) -> Iterator[Phase]:
    s = h.session()
    h.cmd(s, "select_workout", {"workout_id": "matrice_x42"})
    h.cmd(s, "select_route", {"route_id": "demo"})
    yield Phase("ERG", "prêt", s)
    h.cmd(s, "start")
    h.run(s, 30.0)
    yield Phase("ERG", "bloc", s)
    p = h.fork(s)
    h.cmd(p, "pause")
    yield Phase("ERG", "pause", p)
    h.run(s, 100.0)
    yield Phase("ERG", "bloc FreeRide", s, "FreeRide du fichier : palier ERG à 50 W, pas de roue libre (lot O19)")
    h.run(s, 60.0)
    yield Phase("ERG", "dernier bloc", s)
    h.run(s, 70.0)
    yield Phase("ERG", "fin de l'entraînement", s, "entraînement fini : parcours libre en mode SIM")
    h.cmd(s, "end_session", {"save": True})
    yield Phase("ERG", "bilan", s)


def phases_rogue(h: Harness) -> Iterator[Phase]:
    from .rogue_sim import PROFILES, Bot

    s = h.session(power=0.0)
    prof = PROFILES["moyen"]
    s.cfg.rider.ftp_w = prof.ftp_w
    h.cmd(s, "start_run", {"objective": "threshold", "duration_min": 30, "seed": 5})
    if s.rogue is None:
        return
    yield Phase("ROGUE", "prêt", s)
    h.cmd(s, "start")
    bot = Bot(s.rogue.engine, prof, 5, body=s.physics)
    seen: set[str] = set()
    wanted = {"WARMUP": ("échauffement", 20.0), "ROOM": ("salle", 60.0), "CORRIDOR": ("couloir", 3.0),
              "BOSS": ("boss", 60.0), "COOLDOWN": ("retour au calme", 10.0), "RESULTS": ("résultats", 1.0)}
    while s.state.session_state == "RUNNING" and s._t_session < 3 * 3600:
        e = s.rogue.engine
        name, after = wanted.get(e.phase, (None, 0.0))
        if name and e.phase not in seen and e.t_phase >= after:
            seen.add(e.phase)
            if e.phase == "CORRIDOR":
                yield Phase("ROGUE", "couloir, aucune carte choisie", s)
                f = h.fork(s)
                for _ in range(2):        # carte du milieu : les flèches peuvent aller des deux côtés
                    f._handle_input(InputEvent.A_SHORT)
                    h.run(f, 1.0)
                yield Phase("ROGUE", "couloir, carte choisie", f)
            else:
                yield Phase("ROGUE", name, s)
            if e.phase == "ROOM":
                p = h.fork(s)
                h.cmd(p, "pause")
                yield Phase("ROGUE", "pause", p)
            if e.phase == "RESULTS":
                break
        power, cadence, buttons, _ = bot.decide()
        while bot.gear != s.rogue.gear:
            s._handle_input(InputEvent.PLUS_SHORT if bot.gear > s.rogue.gear else InputEvent.MINUS_SHORT)
            if bot.gear != s.rogue.gear and s.rogue.gear in (1, s.rogue.balance.gear_max):
                break
        if e.phase not in ("CORRIDOR",):          # couloirs : l'outil garde la main sur les cartes
            for b in sorted(buttons):
                s._handle_input(InputEvent(b))
        elif e.t_phase > 6.0:
            for b in sorted(buttons):
                s._handle_input(InputEvent(b))
        s.driver.base_power_w, s.driver.base_cadence_rpm = power, cadence
        s.clock += 1.0
        s._step(1.0, s.clock)
        bot.gear = s.rogue.gear if s.rogue is not None else bot.gear
    h.run(s, 10.0, until=lambda: s.state.session_state != "RUNNING")
    if s.state.session_state == "RUNNING":
        h.cmd(s, "end_session", {"save": True})
    yield Phase("ROGUE", "bilan", s)


def phases_world(h: Harness) -> Iterator[Phase]:
    if not STUB_WORLDGEN.exists():
        return
    s = h.session(power=0.0)
    s.worldgen_cmd, s.worldgen_args = [sys.executable, str(STUB_WORLDGEN)], []
    try:
        h.cmd(s, "start_open_world", WORLD_START)
        t0 = time.time()
        while s.state.session_state == "LOADING" and time.time() - t0 < 30.0:
            h.run(s, 0.1)
            time.sleep(0.005)
        if s.state.session_state != "READY":
            return
        yield Phase("MONDE", "prêt", s)
        h.cmd(s, "start")
        s.physics.s, s.physics.v = 100.0, 0.0       # carrefour à 500 m : pas encore proposé
        h.run(s, 0.2)
        yield Phase("MONDE", "en route", s)
        s.physics.s, s.physics.v = 350.0, 0.0       # carrefour proposé à 150 m
        h.run(s, 0.2)
        yield Phase("MONDE", "carrefour", s)
        p = h.fork(s)
        h.cmd(p, "pause")
        yield Phase("MONDE", "pause", p)
    finally:
        s._close_open_world(wait=True)


PHASES = {"sim": phases_sim, "erg": phases_erg, "rogue": phases_rogue, "monde": phases_world}


# --- observation et vérification d'un appui ------------------------------------------------------------

def observe(s: CoreSession) -> dict[str, Any]:
    erg = s.erg
    race = s.race
    rg = s.rogue
    o: dict[str, Any] = {
        "séance": s.state.session_state, "mode": s.state.mode, "braquet": s.state.gear,
        "biais": erg.bias_pct if erg else None, "bloc": getattr(erg, "index", None) if erg else None,
        "bonus actif": race.powerups.active if race else None,
        "bonus en réserve": race.powerups.reserve if race else None,
        "repères décrochage": s.dropout_marks,
    }
    if rg is not None:
        e = rg.engine
        o.update({"choix du couloir": getattr(e, "focus", None), "étape du couloir": getattr(e, "stage", None),
                  "cartes": len(getattr(e, "deck", ()) or ()), "porte": getattr(e, "door_pick", None)})
    ow = s.openworld
    if ow is not None:
        j = ow.offered(s.physics.s)
        nxt = (s.state.open_world or {}).get("next") or {}
        jid = j["id"] if j else None
        o.update({"branche": ow._chosen_of(j) if j else None,
                  "branche validée": nxt.get("id") in ow._locked_early if nxt else None})
        o["carrefour proposé"] = jid
    return o


@dataclass
class Cell:
    mode: str
    phase: str
    event: str
    column: str
    plan: str
    ok: bool | None              # None : case non décrite par le plan
    detail: str
    source: str = "Click"        # Click, ou clavier (événement envoyé par `input_event`, comme l'engine)
    effect: str = ""             # effet attendu (Expect.kind ; choix sans choix affiché : celui de repli)


def _changed(a: dict, b: dict, allowed: set[str]) -> list[str]:
    return [f"{k} {a.get(k)!r} → {b.get(k)!r}" for k in sorted(set(a) | set(b))
            if k not in allowed and a.get(k) != b.get(k)]


def press(h: Harness, ph: Phase, ev: InputEvent, keyboard: bool = False
          ) -> tuple[dict, dict, dict, list[dict], list[str]]:
    """Copie de la séance, appui, une seconde ; rend avant, juste après, une seconde après, les messages et
    les boutons reçus par le moteur de run."""
    f = h.fork(ph.session)
    received: list[str] = []
    if f.rogue is not None:
        real = f.rogue.engine.step

        def spy_step(dt, inp, _real=real):
            received.extend(inp.buttons)
            return _real(dt, inp)
        f.rogue.engine.step = spy_step
    before = observe(f)
    n0 = len(h.sent)
    if keyboard:
        h.cmd(f, "input_event", {"event": ev.value})    # touche lue par l'engine, envoyée au core
    else:
        f._handle_input(ev)
    now = observe(f)
    if f.state.session_state == "RUNNING" and f.rogue is not None:
        f.clock += AFTER_S
        f._step(AFTER_S, f.clock)
    later = observe(f)
    return before, now, later, h.sent[n0:], received


def check(h: Harness, ph: Phase, ev: InputEvent, plan: dict, keys: list[str] | None = None) -> Cell:
    running = ph.session.state.session_state == "RUNNING"
    s = ph.session
    # Colonne du mode roulé : monde ouvert, ERG tant qu'un entraînement est en cours (§7.1), sinon le
    # mode que la séance annonce.
    column = ("MONDE" if ph.mode == "MONDE" else "ERG" if s.erg is not None else s.state.mode) if running else "MENU"
    # ERG d'une session libre (lot O18) : colonne ERG, sauf Z, qui garde son rôle de la colonne SIM (§7.1).
    plan_column = "SIM" if running and isinstance(s.erg, FreeErg) and ev in (InputEvent.Z_SHORT, InputEvent.Z_LONG) \
        else column
    text, sign = plan[(ev, plan_column)]
    exp = expect_of(text, sign, column)
    if exp is None and text.lower().startswith("comme le mode roulé"):
        text, sign = plan[(ev, ph.session.state.mode if ph.session.state.mode in ("SIM", "ERG") else "SIM")]
        exp = expect_of(text, sign, column)
    before, now, later, sent, received = press(h, ph, ev, keys is not None)
    relayed = any(m.get("type") == "input" and m.get("event") == ev.value for m in sent)
    errors = [m for m in sent if m.get("type") == "error"]
    source = "Click" if keys is None else "clavier (" + ", ".join(keys) + ")"
    cell = Cell(ph.mode, ph.name, ev.value, COLUMNS[column], text, False, "", source)
    if not running:
        exp = Expect("engine")       # menu de l'engine (prêt, pause, bilan) : relais seul
    if exp is None:
        cell.ok, cell.detail = None, "case non décrite : l'outil ne sait pas quel effet attendre"
        return cell
    shown = before.get("étape du couloir") is not None or before.get("carrefour proposé") is not None
    cell.effect = exp.kind if shown or exp.kind not in ("choice", "validate") else (
        exp.fallback if exp.kind == "choice" else "engine")
    ok, detail = _verify(exp, ev, ph, before, now, later, relayed, received)
    if errors:
        ok, detail = False, f"erreur envoyée à l'engine : {errors[0].get('code')} ; " + detail
    cell.ok, cell.detail = ok, detail
    return cell


def _verify(exp: Expect, ev: InputEvent, ph: Phase, before: dict, now: dict, later: dict, relayed: bool,
            received: list[str]) -> tuple[bool, str]:
    s = ph.session
    if exp.kind == "gear":
        n = s.gearing.n_gears
        want = min(max(before["braquet"] + int(exp.step), 1), n)
        extra = _changed(before, now, {"braquet"})
        return now["braquet"] == want and not extra, f"braquet {before['braquet']} → {now['braquet']} (attendu {want})" + _x(extra)
    if exp.kind == "bias":
        if before["biais"] is None:
            return False, "pas d'entraînement ERG en cours"
        from ..workout import BIAS_MAX_PCT, BIAS_MIN_PCT
        want = min(max(before["biais"] + exp.step, BIAS_MIN_PCT), BIAS_MAX_PCT)
        extra = _changed(before, now, {"biais"})
        return now["biais"] == want and not extra, f"biais {before['biais']} → {now['biais']} % (attendu {want})" + _x(extra)
    if exp.kind == "brake":
        hi = s.rogue.balance.gear_max if s.rogue else 12
        want = min(max(before["braquet"] + int(exp.step), 1), hi)
        extra = _changed(before, now, {"braquet"})
        return now["braquet"] == want and not extra, f"vitesse du frein {before['braquet']} → {now['braquet']} (attendu {want})" + _x(extra)
    if exp.kind == "pause":
        extra = _changed(before, now, {"séance"})
        return now["séance"] == "PAUSED" and not extra, f"séance {before['séance']} → {now['séance']}" + _x(extra)
    if exp.kind == "bonus":
        held = before.get("bonus en réserve")
        if held:
            ok = now["bonus actif"] == held and now["bonus en réserve"] is None
            return ok, f"bonus {held} en réserve → actif {now['bonus actif']}"
        extra = _changed(before, now, set())
        return not extra and relayed, "aucun bonus en réserve : rien ne change" + _x(extra) + _r(relayed)
    if exp.kind == "mark":
        extra = _changed(before, now, {"repères décrochage"})
        ok = now["repères décrochage"] == before["repères décrochage"] + 1 and not extra and relayed
        return ok, (f"repère « décrochage » au journal : {before['repères décrochage']} → "
                    f"{now['repères décrochage']}" + _x(extra) + _r(relayed))
    if exp.kind == "block":
        if before["bloc"] is None:
            return False, "pas d'entraînement ERG en cours"
        ok = now["bloc"] == before["bloc"] + 1 or (now["bloc"] is None and now["mode"] == "SIM")
        return ok, f"bloc {before['bloc']} → {now['bloc']}"
    if exp.kind == "run":
        ok = ev.value in received and relayed
        return ok, ("bouton reçu par le moteur de run" if ev.value in received else "bouton jamais reçu par le moteur de run") + _r(relayed)
    corridor = before.get("étape du couloir") is not None
    junction = before.get("carrefour proposé") is not None
    if exp.kind == "choice" and (corridor or junction):
        key = "choix du couloir" if corridor else "branche"
        a, b = before[key], (later if corridor else now)[key]
        moved = a != b
        return moved and relayed, f"{key} {a!r} → {b!r} (attendu : option {'suivante' if exp.step > 0 else 'précédente'})" + _r(relayed)
    if exp.kind == "validate" and corridor and before["choix du couloir"] is None:
        extra = _changed(before, later, set())
        return not extra and relayed, "aucune option choisie : rien à valider" + _x(extra) + _r(relayed)
    if exp.kind == "validate" and (corridor or junction):
        if corridor:
            ok = later["étape du couloir"] != before["étape du couloir"] or later["cartes"] != before["cartes"]
            return ok, f"étape du couloir {before['étape du couloir']!r} → {later['étape du couloir']!r}, cartes {before['cartes']} → {later['cartes']}"
        return bool(now["branche validée"]), f"branche {before['branche']} validée : {now['branche validée']}"
    # relais seul (vue de caméra, menu de l'engine) ou aucun effet : rien ne doit changer dans le core
    extra = _changed(before, later, set())
    what = "choix sans choix affiché : vue de caméra (engine)" if exp.kind in ("choice", "validate") else (
        "aucun effet" if exp.kind == "none" else "effet côté engine")
    return not extra and relayed, what + _x(extra) + _r(relayed)


def _x(extra: list[str]) -> str:
    return f" ; changé aussi : {', '.join(extra)}" if extra else ""


def _r(relayed: bool) -> str:
    return "" if relayed else " ; appui non relayé à l'engine"


# --- boîtier gauche : secours par le boîtier droit ----------------------------------------------------------

@dataclass
class BackupCell:
    mode: str
    phase: str
    event: str
    effect: str
    ok: bool
    detail: str


def check_backup(mode: str, phase: str, cells: list[Cell]) -> list[BackupCell]:
    """Effet de chaque flèche, en séance, aussi obtenu par un bouton du boîtier droit de la même phase."""
    click = {c.event: c for c in cells if c.source == "Click" and c.column != COLUMNS["MENU"]}
    out = []
    for ev in LEFT_ONLY:
        c = click.get(ev.value)
        if c is None or c.effect in ("", "none"):
            continue                 # menu (banc des menus), case non décrite ou flèche sans effet
        backups = [r.value for r in RIGHT_UNIT if r.value in click and click[r.value].effect == c.effect
                   and click[r.value].ok]
        comfort = c.effect == "engine"   # vue de caméra : confort, jamais indispensable
        out.append(BackupCell(mode, phase, ev.value, c.effect, bool(backups) or comfort,
                              "aussi par " + ", ".join(backups) if backups else
                              "vue de caméra pendant un choix : boîtier gauche et flèches du clavier seulement "
                              "(confort, non indispensable)" if comfort else
                              "effet obtenu seulement par le boîtier gauche"))
    return out


def check_b_is_minus() -> BackupCell:
    """Le décodeur lit B (boîtier droit) comme « − » : trame 0x23, seul le bit de B à 0."""
    mask, varint = KEYPAD_ALL_RELEASED & ~(1 << KEYPAD_B_BIT), b""
    while True:
        byte, mask = mask & 0x7F, mask >> 7
        varint += bytes([byte | (0x80 if mask else 0)])
        if not mask:
            break
    b = parse_click_buttons(bytes([MSG_KEYPAD_STATUS, 0x08]) + varint)
    ok = b is not None and b.minus_pressed and not (b.plus_pressed or b.a_pressed or b.y_pressed or b.z_pressed)
    return BackupCell("décodeur", "trame du Click", "B", "MINUS", ok,
                      "B appuyé lu comme « − »" if ok else f"B appuyé lu comme {b}")


# --- réglages -------------------------------------------------------------------------------------------

@dataclass
class SettingCell:
    phase: str
    key: str
    applies: str
    value: Any
    ok: bool
    detail: str


def setting_phases(h: Harness) -> Iterator[tuple[str, CoreSession]]:
    s = h.session()
    yield "accueil", s
    r = h.fork(s)
    h.cmd(r, "select_route", {"route_id": "demo"})
    yield "prêt (SIM)", r
    e = h.fork(s)
    h.cmd(e, "select_workout", {"workout_id": "matrice_x42"})
    h.cmd(e, "select_route", {"route_id": "demo"})
    yield "prêt (ERG)", e
    run = h.fork(r)
    h.cmd(run, "start")
    h.run(run, 5.0)
    yield "en route", run
    p = h.fork(run)
    h.cmd(p, "pause")
    yield "pause", p
    h.cmd(run, "end_session", {"save": True})
    yield "bilan", run


def _next_session(h: Harness, s: CoreSession) -> CoreSession:
    """Séance suivante après le réglage : celle qui est prête, sinon un parcours, puis le départ."""
    if s.state.session_state != "READY":
        h.cmd(s, "select_route", {"route_id": "demo"})
    h.cmd(s, "start")
    h.run(s, 1.0)
    return s


EFFECTS: dict[str, Callable[[CoreSession, Any], tuple[bool, str]]] = {
    "rider.ftp_w": lambda s, v: (s.server.hello_config.get("ftp_w") == v and (
        s.erg is None or s.erg.ftp_w == v), f"FTP annoncée {s.server.hello_config.get('ftp_w')}"
        + (f", cible ERG calculée sur {s.erg.ftp_w} W" if s.erg is not None else "")),
    "rider.mass_kg": lambda s, v: (abs(s.physics.p.mass_kg - s.cfg.total_mass_kg) < 1e-6 and s.cfg.rider.mass_kg == v,
                                   f"masse de la physique {s.physics.p.mass_kg:.1f} kg"),
    "bike.mass_kg": lambda s, v: (abs(s.physics.p.mass_kg - s.cfg.total_mass_kg) < 1e-6 and s.cfg.bike.mass_kg == v,
                                  f"masse de la physique {s.physics.p.mass_kg:.1f} kg"),
    "trainer.difficulty_pct": lambda s, v: (s.state.difficulty_pct == v, f"difficulté de la séance {s.state.difficulty_pct} %"),
    "gearing.start_gear": lambda s, v: (s.state.gear == v, f"braquet au départ {s.state.gear}"),
    "powerups.mode": lambda s, v: (s.race is None or s.race.powerups_on == (v == "on"),
                                   f"bonus de la course {'actifs' if s.race and s.race.powerups_on else 'coupés'}"),
    **{k: lambda s, v: _wind_effect(s) for k in ("wind.mode", "wind.speed_kmh", "wind.from_deg", "wind.gust_pct")},
}


def _wind_effect(s: CoreSession) -> tuple[bool, str]:
    """Vent de la séance = celui que donne `config.toml` (mode, force, direction, rafales)."""
    from ..wind import WindModel

    want = WindModel.from_config(s.cfg.wind)
    got = s.wind
    sig = lambda w: (w.mode, round(w.base_mps, 3), round(w.from_deg, 1), round(w.gust_frac, 3))   # noqa: E731
    return sig(got) == sig(want), (f"vent de la séance : mode {got.mode}, {got.base_mps * 3.6:.0f} km/h, "
                                   f"{got.from_deg:.0f}°, rafales {got.gust_frac:.0%}")


def check_setting(h: Harness, phase: str, s: CoreSession, st: settings_mod.Setting) -> SettingCell:
    f = h.fork(s)
    cur = settings_mod._value(f.cfg, st)
    new = settings_mod.step(f.cfg, st.key, cur, +1)
    if new == cur:
        new = settings_mod.step(f.cfg, st.key, cur, -1)
    in_session = f.state.session_state in ("RUNNING", "PAUSED")
    want_ok = not in_session or st.applies == "now"
    n0 = len(h.sent)
    h.cmd(f, "set_setting", {"key": st.key, "value": new})
    sent = h.sent[n0:]
    err = next((m for m in sent if m.get("type") == "error"), None)
    accepted = err is None and settings_mod._value(f.cfg, st) == new
    cell = SettingCell(phase, st.key, st.applies, new, False, "")
    if not want_ok:
        cell.ok = err is not None and err.get("code") == "busy" and settings_mod._value(f.cfg, st) == cur
        cell.detail = "refusé en séance (busy)" if cell.ok else f"attendu : refus busy en séance ; reçu {err or 'accepté'}"
        return cell
    if not accepted:
        cell.detail = f"refusé : {err.get('code') if err else '?'} {err.get('message', '') if err else ''}".strip()
        if st.applies == "now" and in_session:
            cell.detail += " (réglage appliqué tout de suite par l'engine : il doit être accepté en séance)"
        return cell
    written = f.config_path is not None and f.config_path.exists() and st.name in f.config_path.read_text("utf-8")
    if not written:
        cell.detail = "accepté mais absent de config.toml"
        return cell
    if st.applies == "now":
        msg = next((m for m in reversed(sent) if m.get("type") == "settings"), None)
        items = {i["key"]: i["value"] for i in (msg or {}).get("items", [])}
        cell.ok = items.get(st.key) == new
        cell.detail = f"annoncé à l'engine : {items.get(st.key)!r}" if msg else "aucun message settings en réponse"
        return cell
    effect = EFFECTS.get(st.key)
    if effect is None:
        cell.ok, cell.detail = True, "accepté, relu et écrit (pas d'effet observable dans le core au départ)"
        return cell
    if in_session:
        cell.ok, cell.detail = True, "accepté"
        return cell
    nxt = _next_session(h, f)
    ok, what = effect(nxt, new)
    cell.ok, cell.detail = ok, f"séance suivante : {what} (attendu {new})"
    return cell


# --- rapport --------------------------------------------------------------------------------------------

@dataclass
class Report:
    cells: list[Cell] = field(default_factory=list)
    settings: list[SettingCell] = field(default_factory=list)
    keys: list[KeyCell] = field(default_factory=list)
    backup: list[BackupCell] = field(default_factory=list)
    phases: list[str] = field(default_factory=list)
    wall_s: float = 0.0

    @property
    def failures(self) -> list[Cell | SettingCell | KeyCell | BackupCell]:
        return [c for c in self.cells if c.ok is False] + [c for c in (*self.settings, *self.keys, *self.backup)
                                                             if not c.ok]

    @property
    def unknown(self) -> list[Cell]:
        return [c for c in self.cells if c.ok is None]

    @property
    def ok(self) -> bool:
        return not self.failures and not self.unknown


def run(part: str = "tout", modes: tuple[str, ...] = tuple(PHASES), spec: Path = SPEC) -> Report:
    if part not in ("boutons", "reglages", "tout"):
        raise MatrixError(f"partie inconnue : {part} (boutons, reglages, tout)")
    for m in modes:
        if m not in PHASES:
            raise MatrixError(f"mode inconnu : {m} ({', '.join(PHASES)})")
    rep = Report()
    t0 = time.perf_counter()
    plan = read_plan(spec) if part != "reglages" else {}
    key_events: dict[InputEvent, list[str]] = {}
    if part != "reglages":
        rep.keys = check_keys(spec)
        rep.backup.append(check_b_is_minus())
        for key, by_hold in read_keys(spec).items():
            for ev in by_hold.values():
                if ev and key not in key_events.setdefault(InputEvent(ev), []):
                    key_events[InputEvent(ev)].append(key)
    with tempfile.TemporaryDirectory(prefix="openride-matrice-") as tmp_s, \
            mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"):
        h = Harness(Path(tmp_s))
        if part in ("boutons", "tout"):
            for m in modes:
                for ph in PHASES[m](h):
                    rep.phases.append(f"{ph.mode} · {ph.name}")
                    cells = [check(h, ph, ev, plan) for ev in InputEvent]
                    if ph.session.state.session_state == "RUNNING":   # aucun menu : la touche passe par le core
                        cells += [check(h, ph, ev, plan, keys) for ev, keys in key_events.items()]
                        rep.backup += check_backup(ph.mode, ph.name, cells)
                    rep.cells += cells
        if part in ("reglages", "tout"):
            for name, s in setting_phases(h):
                for st in settings_mod.SETTINGS:
                    rep.settings.append(check_setting(h, name, s, st))
    rep.wall_s = time.perf_counter() - t0
    return rep


def format_text(rep: Report) -> str:
    out = []
    for c in rep.cells:
        tag = "OK" if c.ok else ("NON DÉCRIT" if c.ok is None else "ÉCHEC")
        if c.ok is not True:
            out.append(f"[{tag}] {c.mode} · {c.phase} · {c.event} par {c.source} (colonne {c.column} : « {c.plan} ») : "
                       f"{c.detail}")
    for k in rep.keys:
        if not k.ok:
            out.append(f"[ÉCHEC] clavier {k.key} ({k.hold}) : plan {k.plan!r}, key_map.gd {k.key_map!r} {k.detail}")
    for b in rep.backup:
        if not b.ok:
            out.append(f"[ÉCHEC] boîtier gauche {b.mode} · {b.phase} · {b.event} ({b.effect}) : {b.detail}")
    for c in rep.settings:
        if not c.ok:
            out.append(f"[ÉCHEC] réglage {c.key} → {c.value!r} · {c.phase} : {c.detail}")
    every = [*rep.cells, *rep.settings, *rep.keys, *rep.backup]
    n_ok = sum(1 for c in every if c.ok)
    n_key = sum(1 for c in rep.cells if c.source != "Click")
    out.append(f"Matrice des boutons et des réglages : {n_ok}/{len(every)} cases conformes ({len(rep.cells) - n_key} "
               f"appuis du Click et {n_key} du clavier sur {len(rep.phases)} phases, {len(rep.keys)} touches du "
               f"plan, {len(rep.backup)} secours du boîtier gauche, {len(rep.settings)} réglages) en {rep.wall_s:.0f} s")
    return "\n".join(out)


def format_md(rep: Report) -> str:
    lines = ["# Matrice des boutons et des réglages (lot X42)", "",
             f"{len(rep.cells)} appuis sur {len(rep.phases)} phases, {len(rep.settings)} réglages.", "",
             "## Boutons", "", "| Mode | Phase | Bouton | Par | Colonne du plan | Case du plan | Résultat | Relevé |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for c in rep.cells:
        res = "OK" if c.ok else ("non décrit" if c.ok is None else "**ÉCHEC**")
        lines.append(f"| {c.mode} | {c.phase} | {c.event} | {c.source} | {c.column} | {c.plan} | {res} | {c.detail} |")
    lines += ["", "## Clavier = plan (§7.1) et key_map.gd", "", "| Touche | Appui | Plan | key_map.gd | Résultat |",
              "| --- | --- | --- | --- | --- |"]
    for k in rep.keys:
        lines.append(f"| {k.key} | {k.hold} | {k.plan or '—'} | {k.key_map or '—'} | "
                     f"{'OK' if k.ok else '**ÉCHEC**'} {k.detail} |")
    lines += ["", "## Boîtier gauche : secours par le boîtier droit", "", "| Mode | Phase | Flèche | Effet | Résultat | Relevé |",
              "| --- | --- | --- | --- | --- | --- |"]
    for b in rep.backup:
        lines.append(f"| {b.mode} | {b.phase} | {b.event} | {b.effect} | {'OK' if b.ok else '**ÉCHEC**'} | {b.detail} |")
    lines += ["", "## Réglages", "", "| Phase | Réglage | Appliqué | Valeur | Résultat | Relevé |",
              "| --- | --- | --- | --- | --- | --- |"]
    for c in rep.settings:
        lines.append(f"| {c.phase} | {c.key} | {c.applies} | {c.value!r} | {'OK' if c.ok else '**ÉCHEC**'} | {c.detail} |")
    return "\n".join(lines) + "\n"


def to_json(rep: Report) -> dict:
    return {"ok": rep.ok, "phases": rep.phases, "wall_s": round(rep.wall_s, 1),
            "boutons": [c.__dict__ for c in rep.cells], "reglages": [c.__dict__ for c in rep.settings],
            "clavier": [c.__dict__ for c in rep.keys], "boitier_gauche": [c.__dict__ for c in rep.backup]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="matrice_boutons", description=__doc__.split("\n\n")[0])
    ap.add_argument("--partie", default="tout", help="boutons, reglages ou tout")
    ap.add_argument("--mode", default="tous", help="sim, erg, rogue, monde ou tous (séparés par des virgules)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--md", type=Path, help="écrit le tableau complet en Markdown")
    a = ap.parse_args(argv)
    modes = tuple(PHASES) if a.mode == "tous" else tuple(m.strip() for m in a.mode.split(","))
    try:
        rep = run(a.partie, modes)
    except MatrixError as exc:
        print(f"Appel invalide : {exc}", file=sys.stderr)
        return 2
    if a.md:
        a.md.write_text(format_md(rep), "utf-8")
    print(json.dumps(to_json(rep), ensure_ascii=False, indent=1) if a.json else format_text(rep))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
