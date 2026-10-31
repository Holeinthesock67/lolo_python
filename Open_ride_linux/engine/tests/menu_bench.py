#!/usr/bin/env python3
"""Banc des menus : scénarios déclaratifs joués au Click simulé, au clavier et à la souris, de bout en bout.

Usage :
    menu_bench.py [--godot CHEMIN] [--scenario NOM|FICHIER.json]... [--voies click,clavier,souris] [--rotation]
                  [--native] [--out DOSSIER] [--captures echecs|ecrans] [--keep] [--list]

Chaque scénario (`engine/tests/menu_scenarios/*.json`) est joué une fois par voie d'entrée, avec un vrai core
sur Bluetooth simulé (`--trainer sim --input sim --hr sim`, sans `--autostart` : le core démarre en IDLE,
comme depuis l'icône du bureau) et la vraie scène Godot (`--test-mode`), sous Xvfb ou dans une fenêtre
(`--native`). `--rotation` ne joue chaque scénario que sur une voie, à tour de rôle (intégration continue). Le core et l'engine ont un HOME temporaire et des ports UDP libres : rien n'est écrit dans le
vrai dossier personnel.

Voies d'entrée (un seul tableau bouton → geste, `GESTES`, d'après la spécification générale §7.1,
`key_map.gd` et `menu_view.gd`) :
- `click` : appui sur le bouton du Zwift Click V2 simulé (fichier de commandes du monde simulé,
  `control_file`) ; tout le chemin réel : notifications Bluetooth, `PressClassifier`, relais du core, engine ;
- `clavier` : touche appuyée puis relâchée après la durée de l'appui, par `Input.parse_input_event` (message
  de test `key`) : même chemin qu'une vraie touche (`_unhandled_input`, `key_map.gd`) ;
- `souris` : molette (+ et −), clic droit (Y) et clic gauche sur l'élément (A maintenu), message de test
  `mouse` ; un événement sans geste de souris (A court, Z, flèches, appuis longs) passe par le clavier et
  le rapport le compte (« repli clavier »).

Étapes d'un scénario (liste `etapes`, jouées dans l'ordre ; `voies` sur une étape la réserve à ces voies) :
- gestes : `appui` (événement ou liste : PLUS_SHORT, A_LONG, Y_SHORT…), `choisir` (identifiant d'un élément
  de l'écran : focus dessus puis A maintenu ; à la souris, clic sur sa rangée), `aller` (focus seulement),
  `touche` (+ `maj`, `duree_ms`), `souris` (+ `element` ou `point`), `click` (+ `duree_s`) : gestes bruts ;
- vérifications, attendues jusqu'à `delai` secondes (5 par défaut) : `ecran` (identifiant, ou liste des
  écrans permis ; + `monde` (menu du monde ouvert affiché ou non, ou son écran : globe, search, map, setup),
  `titre`, `groupe`,
  `contient` et `absent` : textes cherchés dans la ligne d'état, les éléments « libellé — détail », les pastilles
  des appareils et la carte de détail ; `focus`, `elements`, `statut`, `edition`), `menu_cache`, `config` ({clé: valeur} de
  config.toml, `null` : absente), `journal` (`core` ou `engine`) + `motif`, `fichier` (chemin ou motif
  glob dans le HOME, ex. OpenRide/Activities/*.fit) + `existe`, `sortie` (code de sortie de l'engine) ; dans `config`, la valeur "*" veut dire « présente » ;
- autres : `commande` (+ `args`), `attendre` (secondes), `capture` (nom), `relancer` (core et engine
  arrêtés proprement puis relancés sur le même HOME : persistance des réglages).

En-tête d'un scénario : `description`, `voies` (défaut : les trois), `appareils` (`prets` ou `unilateral`),
`config` ({clé: valeur} écrite dans config.toml avant le lancement), `entrainement` (vrai : `erg_court.zwo`
dans ~/OpenRide/Workouts), `telechargements` ({fichier: nom de l'entraînement} dans ~/Téléchargements), `plans`
(vrai : plans de référence de `core/plans/` installés dans ~/OpenRide/Plans), `fichiers` ({chemin dans le
HOME: contenu}, texte ou objet JSON, posés avant le lancement : records, profil…).

Rapport dans `--out` : `rapport.html` (tableau scénario × voie, vérifications, captures), `resultats.json`
et `resume.txt`. Une capture est prise à chaque échec, avec l'état du menu. Code de sortie : 0 si toutes les
vérifications passent, 1 sinon, 2 si Godot ou xvfb-run manque.
"""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import os
import re
import shutil
import signal
import socket
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent
REPO = ENGINE_DIR.parent
SCENARIOS_DIR = TESTS_DIR / "menu_scenarios"
sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(REPO / "core" / "src"))

from openride_core.launcher import build_supervisor  # noqa: E402
from e2e_check import free_udp_ports, now  # noqa: E402
from sim_bench import ERG_SHORT_ZWO, BenchProc, Report  # noqa: E402

VOIES = ("click", "clavier", "souris")
MAX_FAILURES = 5   # au-delà, le passage s'arrête : les échecs suivants ne seraient que des conséquences
# Après le hello_ack, l'engine peut rester plusieurs secondes sans traiter ses messages (premières images, shaders
# compilés sur une vraie carte : GTX 1060 du PC, 31 octobre). Le banc attend sa première réponse avant la première
# vérification, en redemandant l'état : sinon « écran home : engine sans réponse » sur le PC, jamais dans le cloud.
ENGINE_READY_S = 60.0
ENGINE_READY_ASK_S = 3.0   # délai de chaque demande d'état pendant cette attente
COURT_S, LONG_S, FLOU_S = 0.15, 1.1, 0.7

# Un seul tableau bouton → geste : événement du Click -> (bouton du Click V2 simulé, durée en s),
# (touche Godot, Maj, durée en ms), geste de souris (None : pas de geste, repli au clavier). « − » au Click : bouton
# B du boîtier droit, qui marche aussi avec un seul boîtier relié (le gauche se tait sans déblocage Zwift).
GESTES: dict[str, dict[str, Any]] = {
    "PLUS_SHORT": {"click": ("+", COURT_S), "clavier": ("Plus", False, 150), "souris": "wheel_down"},
    "PLUS_LONG": {"click": ("+", LONG_S), "clavier": ("Plus", False, 1100), "souris": None},
    "PLUS_UNCLEAR": {"click": ("+", FLOU_S), "clavier": ("Plus", False, 700), "souris": None},
    "MINUS_SHORT": {"click": ("B", COURT_S), "clavier": ("Minus", False, 150), "souris": "wheel_up"},
    "MINUS_LONG": {"click": ("B", LONG_S), "clavier": ("Minus", False, 1100), "souris": None},
    "MINUS_UNCLEAR": {"click": ("B", FLOU_S), "clavier": ("Minus", False, 700), "souris": None},
    "A_SHORT": {"click": ("A", COURT_S), "clavier": ("A", False, 150), "souris": None},
    "A_LONG": {"click": ("A", LONG_S), "clavier": ("A", False, 1100), "souris": "click"},
    "Y_SHORT": {"click": ("Y", COURT_S), "clavier": ("Y", False, 150), "souris": "right"},
    "Z_SHORT": {"click": ("Z", COURT_S), "clavier": ("Z", False, 150), "souris": None},
    "Z_LONG": {"click": ("Z", LONG_S), "clavier": ("Z", False, 1100), "souris": None},
    "LEFT_SHORT": {"click": ("LEFT", COURT_S), "clavier": ("Left", False, 150), "souris": None},
    "RIGHT_SHORT": {"click": ("RIGHT", COURT_S), "clavier": ("Right", False, 150), "souris": None},
    "UP_SHORT": {"click": ("UP", COURT_S), "clavier": ("Up", False, 150), "souris": None},
    "DOWN_SHORT": {"click": ("DOWN", COURT_S), "clavier": ("Down", False, 150), "souris": None},
}

READY = {"trainer": {"appear_at": 0.3, "connect_delay_s": 0.3},
         "click": {"appear_at": 0.5, "connect_delay_s": 0.3},
         "hr": {"appear_at": 0.5, "connect_delay_s": 0.2}, "events": []}
# Boîtier « − » qui n'apparaît jamais : un seul boîtier relié (unilatéral).
UNILATERAL = {**READY, "click": {"appear_at": 0.5, "connect_delay_s": 0.3, "minus": {"appear_at": 100000}}}
APPAREILS = {"prets": READY, "unilateral": UNILATERAL}
# Réglages de départ du banc (le scénario peut les changer) : rendu léger sous Xvfb, fenêtre et non plein écran.
BASE_CONFIG = {"render.quality": "low", "render.display": "windowed"}

STEP_KEYS = {"appui", "choisir", "aller", "touche", "maj", "duree_ms", "souris", "element", "point", "click",
             "duree_s", "ecran", "monde", "titre", "groupe", "contient", "absent", "focus", "elements", "statut", "edition",
             "menu_cache", "config", "journal", "motif", "fichier", "existe", "sortie", "commande", "args",
             "attendre", "capture", "relancer", "delai", "voies", "note"}
HEAD_KEYS = {"description", "voies", "appareils", "config", "entrainement", "telechargements", "plans", "fichiers", "etapes"}


def descendants(pid: int) -> list[int]:
    """Processus descendants de `pid` (lus dans /proc), les plus profonds d'abord."""
    children: dict[int, list[int]] = {}
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        children.setdefault(int(fields[1]), []).append(int(stat.parent.name))
    out: list[int] = []
    todo = [pid]
    while todo:
        for child in children.get(todo.pop(), []):
            out.append(child)
            todo.append(child)
    return out[::-1]


class ScenarioError(Exception):
    """Scénario illisible ; le message dit où."""


def load_scenario(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ScenarioError(f"{path.name} : lecture impossible : {exc}") from None
    unknown = set(doc) - HEAD_KEYS
    if unknown:
        raise ScenarioError(f"{path.name} : clés inconnues {sorted(unknown)}")
    if doc.get("appareils", "prets") not in APPAREILS:
        raise ScenarioError(f"{path.name} : appareils {doc['appareils']!r} inconnus ({', '.join(APPAREILS)})")
    for v in doc.get("voies", VOIES):
        if v not in VOIES:
            raise ScenarioError(f"{path.name} : voie {v!r} inconnue")
    for i, step in enumerate(doc.get("etapes", [])):
        unknown = set(step) - STEP_KEYS
        if unknown:
            raise ScenarioError(f"{path.name}, étape {i + 1} : clés inconnues {sorted(unknown)}")
        evs = step.get("appui", [])
        for ev in [evs] if isinstance(evs, str) else evs:
            if ev not in GESTES:
                raise ScenarioError(f"{path.name}, étape {i + 1} : événement {ev!r} inconnu")
    return doc


def scenarios() -> dict[str, Path]:
    return {p.stem: p for p in sorted(SCENARIOS_DIR.glob("*.json"))}


def toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)


def config_text(values: dict[str, Any]) -> str:
    sections: dict[str, list[str]] = {}
    for key, v in values.items():
        section, name = key.rsplit(".", 1)
        sections.setdefault(section, []).append(f"{name} = {toml_value(v)}")
    return "".join(f"\n[{s}]\n" + "\n".join(lines) + "\n" for s, lines in sections.items())


def config_get(data: dict[str, Any], key: str) -> Any:
    node: Any = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


class Run:
    """Un scénario joué sur une voie : core et engine lancés, gestes, vérifications et captures."""

    def __init__(self, args: argparse.Namespace, name: str, doc: dict[str, Any], voie: str, out: Path) -> None:
        self.args, self.name, self.doc, self.voie, self.out = args, name, doc, voie, out
        self.report = Report()
        self.shots: list[dict[str, Any]] = []
        self.replis = 0
        self.state_port = self.cmd_port = 0
        self.engine: BenchProc | None = None
        self.core: BenchProc | None = None
        self.tmp = self.home = self.config = self.control = self.routes = Path()
        self._req = 0
        self.last: dict[str, Any] = {}
        self.duration_s = 0.0

    # --- dialogue avec l'engine -------------------------------------------------------------

    def _send(self, msg: dict[str, Any]) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(json.dumps(msg).encode(), ("127.0.0.1", self.state_port))

    def state(self, timeout: float = 10.0) -> dict[str, Any]:
        """État des menus (message de test `menu_state`) ; {} si l'engine ne répond pas."""
        assert self.engine is not None
        self._req += 1
        req = f"{self.voie}-{self._req}"
        t = now()
        self._send({"type": "_test", "action": "menu_state", "req": req})
        got = self.engine.wait_for(r"\[test\] menu_state (\{.*\"req\":\"" + re.escape(req) + r"\".*\})$", timeout, after=t)
        self.last = json.loads(got[1].group(1)) if got else {}
        return self.last

    def capture(self, tag: str, why: str = "") -> dict[str, Any]:
        assert self.engine is not None
        path = (self.out / f"{len(self.shots):02d}_{tag}.png").resolve()
        t = now()
        self._send({"type": "_test", "action": "screenshot", "path": str(path), "tag": tag})
        ok = self.engine.wait_for(r"\[test\] screenshot \{", 8.0, after=t) is not None
        st = self.state()
        info = {"tag": tag, "file": path.name if ok else "", "why": why, "screen": st.get("screen", ""),
                "title": st.get("title", ""), "rows": [r["text"] for r in st.get("rows", [])], "hint": st.get("hint", "")}
        self.shots.append(info)
        return info

    def check(self, ok: bool, label: str, measure: str) -> bool:
        self.report.check(ok, label, measure)
        if not ok and self.engine is not None and self.engine.p.poll() is None:
            self.capture(f"echec_{len(self.shots):02d}", f"{label} : {measure}")
        return ok

    # --- gestes ----------------------------------------------------------------------------

    def _received(self, ev: str, t: float, hold_s: float, menu_shown: bool) -> bool:
        """Attend la ligne de l'engine qui prouve que le geste est arrivé (bip, appui ambigu, souris)."""
        assert self.engine is not None
        if not menu_shown and ev == "Y_SHORT":
            return True   # Y en séance : pause demandée par le core, sans relais à l'engine
        pattern = r"Appui ambigu : " + ev if ev.endswith("_UNCLEAR") else r"(Bip|Souris) : " + ev
        got = self.engine.wait_for(pattern, hold_s + 10.0, after=t)
        return got is not None or self.check(False, f"{ev} reçu par l'engine ({self.voie})", f"aucune ligne « {pattern} »")

    def gesture(self, ev: str) -> bool:
        """Joue l'événement `ev` par la voie du passage (repli au clavier sans geste de souris)."""
        assert self.engine is not None
        g = GESTES[ev]
        menu_shown = bool(self.last.get("visible", True))
        voie = self.voie
        if voie == "souris" and (g["souris"] is None or not menu_shown):
            voie = "clavier"
            self.replis += 1
        t = now()
        if voie == "click":
            button, hold = g["click"]
            with self.control.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"action": "press", "button": button, "duration_s": hold}) + "\n")
        elif voie == "clavier":
            key, shift, hold_ms = g["clavier"]
            hold = hold_ms / 1000.0
            self._send({"type": "_test", "action": "key", "key": key, "shift": shift, "hold_ms": hold_ms})
        else:
            hold = 0.0
            item = self.last.get("focus_id", "") if g["souris"] == "click" else ""
            self._send({"type": "_test", "action": "mouse", "kind": g["souris"], "item": item})
            if g["souris"] == "click":
                got = self.engine.wait_for(r"Souris : clic sur|\[test\] mouse hidden", 10.0, after=t)
                self.state()
                return (got is not None and "clic sur" in got[1].group(0)) or self.check(
                    False, f"A_LONG à la souris : clic sur « {item} »", got[1].group(0) if got else "sans réponse")
        ok = self._received(ev, t, hold, menu_shown)
        self.state()
        return ok

    def move_focus(self, item: str) -> bool:
        """Focus sur l'élément `item` par appuis courts sur + ou − (le plus court chemin, la liste boucle)."""
        for _ in range(40):
            st = self.state()
            if st.get("focus_id") == item:
                return True
            items = [it for it in st.get("items", []) if it["enabled"]]
            ids = [it["id"] for it in items]
            if item not in ids or st.get("focus_id") not in ids:
                return False
            fi, ti, n = ids.index(st["focus_id"]), ids.index(item), len(ids)
            if not self.gesture("PLUS_SHORT" if (ti - fi) % n <= (fi - ti) % n else "MINUS_SHORT"):
                return False
        return False

    def choose(self, item: str) -> bool:
        assert self.engine is not None
        st = self.state()
        if self.voie == "souris" and any(r["id"] == item for r in st.get("rows", [])):
            t = now()
            self._send({"type": "_test", "action": "mouse", "kind": "click", "item": item})
            got = self.engine.wait_for(r"Souris : clic sur " + re.escape(item) + r"$", 10.0, after=t)
            self.state()
            return got is not None
        return self.move_focus(item) and self.gesture("A_LONG")

    # --- vérifications ---------------------------------------------------------------------

    def _screen_ok(self, st: dict[str, Any], step: dict[str, Any]) -> list[str]:
        """Écarts entre l'état `st` et ce qu'attend l'étape (liste vide : tout va)."""
        bad = []
        if not st:
            return ["engine sans réponse"]
        text = " | ".join([st.get("status", "")] + [f"{it['label']} — {it['detail']}" if it["detail"] else it["label"]
                                                     for it in st.get("items", [])] + [st.get("devices", ""), st.get("card", "")]
                         + [st.get("world_menu", {}).get(k, "") for k in ("body", "help", "hint")])
        if "menu_cache" in step:
            if st.get("visible") == bool(step["menu_cache"]):
                bad.append(f"menu {'visible' if st.get('visible') else 'caché'}")
            return bad
        if "ecran" in step:
            if not st.get("visible") and not st.get("world_menu", {}).get("visible"):
                bad.append("menu caché")
            if st.get("screen") not in ([step["ecran"]] if isinstance(step["ecran"], str) else step["ecran"]):
                bad.append(f"écran « {st.get('screen')} »")
        if "monde" in step:
            world = st.get("world_menu", {})
            if bool(world.get("visible")) != bool(step["monde"]):
                bad.append(f"menu du monde ouvert {'affiché' if world.get('visible') else 'fermé'}")
            elif isinstance(step["monde"], str) and world.get("state") != step["monde"]:
                bad.append(f"monde ouvert : écran « {world.get('state')} »")
        if "titre" in step and st.get("title") != step["titre"]:
            bad.append(f"titre « {st.get('title')} »")
        if "groupe" in step and st.get("group") != step["groupe"]:
            bad.append(f"groupe « {st.get('group')} »")
        if "focus" in step and st.get("focus_id") != step["focus"]:
            bad.append(f"focus sur « {st.get('focus_id')} »")
        if "edition" in step and bool(st.get("editing")) != bool(step["edition"]):
            bad.append(f"édition {st.get('editing')}")
        if "statut" in step and not re.search(step["statut"], st.get("status", "")):
            bad.append(f"ligne d'état « {st.get('status')} »")
        ids = [it["id"] for it in st.get("items", [])]
        for want in step.get("elements", []):
            if want not in ids:
                bad.append(f"élément « {want} » absent")
        for want in step.get("contient", []):
            if want not in text:
                bad.append(f"« {want} » absent")
        for unwanted in step.get("absent", []):
            if unwanted in text:
                bad.append(f"« {unwanted} » présent")
        return bad

    def wait_screen(self, step: dict[str, Any]) -> None:
        deadline = now() + float(step.get("delai", 5.0))
        while True:
            st = self.state()
            bad = self._screen_ok(st, step)
            if not bad or now() >= deadline:
                break
            time.sleep(0.15)
        what = step.get("ecran") or ("menu caché" if step.get("menu_cache") else
                                     f"monde ouvert {step['monde']}" if "monde" in step else "menu visible")
        detail = ", ".join(f"{k}={step[k]!r}" for k in ("titre", "groupe", "focus", "contient", "elements") if k in step)
        self.check(not bad, f"écran {what}" + (f" ({detail})" if detail else ""),
                   "; ".join(bad) if bad else f"« {st.get('title', '')} »")

    def wait_config(self, want: dict[str, Any], delay: float) -> None:
        deadline = now() + delay
        while True:
            try:
                data = tomllib.loads(self.config.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError) as exc:
                data = {"_erreur": str(exc)}
            bad = {k: config_get(data, k) for k, v in want.items()
                   if (config_get(data, k) is None if v == "*" else config_get(data, k) != v)}
            if not bad or now() >= deadline:
                break
            time.sleep(0.2)
        self.check(not bad, "config.toml : " + ", ".join(f"{k} = {v!r}" for k, v in want.items()),
                   "lu : " + ", ".join(f"{k} = {v!r}" for k, v in bad.items()) if bad else "OK")

    def wait_exit(self, code: int, delay: float) -> None:
        assert self.engine is not None
        deadline = now() + delay
        rc = None
        while now() < deadline and rc is None:
            rc = self.engine.p.poll()
            time.sleep(0.2)
        self.report.check(rc == code, f"l'engine sort avec le code {code}", f"code {rc}")

    # --- lancement -------------------------------------------------------------------------

    def prepare(self) -> None:
        doc = self.doc
        self.out.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="openride-menus-"))
        self.home = self.tmp / "home"
        self.routes = self.home / ".local" / "share" / "openride" / "routes"
        self.routes.mkdir(parents=True)
        shutil.copytree(ENGINE_DIR / "demo" / "demo.world", self.routes / "demo.world")
        if doc.get("entrainement"):
            wdir = self.home / "OpenRide" / "Workouts"
            wdir.mkdir(parents=True)
            (wdir / "erg_court.zwo").write_text(ERG_SHORT_ZWO, encoding="utf-8")
        if doc.get("plans"):
            from openride_core.plans import install_builtin
            install_builtin(self.home / "OpenRide" / "Plans", self.home / "OpenRide" / "Workouts")
        if doc.get("telechargements"):
            dl = self.home / "Téléchargements"
            dl.mkdir(parents=True)
            for fname, wname in doc["telechargements"].items():
                (dl / fname).write_text(ERG_SHORT_ZWO.replace("ERG court (banc simulé)", wname), encoding="utf-8")
        for rel, content in doc.get("fichiers", {}).items():
            path = self.home / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False),
                            encoding="utf-8")
        self.state_port, self.cmd_port = free_udp_ports(2)
        self.config = self.tmp / "config.toml"
        self.config.write_text(f"[ipc]\nport_state = {self.state_port}\nport_commands = {self.cmd_port}\n"
                               + config_text({**BASE_CONFIG, **doc.get("config", {})}), encoding="utf-8")
        self.control = self.tmp / "click.jsonl"
        scen = {**APPAREILS[doc.get("appareils", "prets")], "control_file": str(self.control)}
        (self.tmp / "scenario.json").write_text(json.dumps(scen), encoding="utf-8")

    def start(self, n: int = 0) -> bool:
        a = self.args
        env = {**os.environ, "HOME": str(self.home), "PYTHONUNBUFFERED": "1",
               "PYTHONPATH": os.pathsep.join([str(REPO / "core" / "src"), str(REPO / "compiler" / "src")])}
        for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
            env.pop(k, None)
        suffix = f"_{n}" if n else ""
        argv = [sys.executable, "-m", "openride_core", "run", "--config", str(self.config), "--trainer", "sim",
                "--input", "sim", "--hr", "sim", "--sim-scenario", str(self.tmp / "scenario.json")]
        self.core = BenchProc("core", argv, env, self.out / f"core{suffix}.log")
        if not self.report.check(self.core.wait_for(r"Core démarré", 20.0) is not None, "démarrage du core",
                                 "« Core démarré »"):
            return False
        cmd = [str(a.godot), "--path", str(ENGINE_DIR), "--resolution", "1280x720", "--audio-driver", "Dummy"]
        if not a.native:
            cmd = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"] + cmd + [
                "--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
        # Arguments de l'engine tirés de config.toml par le vrai lanceur (qualité, caméra, mode d'affichage…).
        sup = build_supervisor(["--config", str(self.config)], env={"GODOT": str(a.godot),
                                                                     "OPENRIDE_ENGINE": str(ENGINE_DIR)})
        cmd += sup.engine_cmd[sup.engine_cmd.index("--"):] + [f"--routes-dir={self.routes}", "--test-mode"]
        self.engine = BenchProc("engine", cmd, env, self.out / f"engine{suffix}.log")
        ok = self.engine.wait_for(r"hello_ack reçu", 40.0) is not None
        self.report.check(ok, "engine relié au core", "hello_ack")
        return ok and self.wait_engine_ready()

    def wait_engine_ready(self) -> bool:
        """Attend la première réponse de l'engine à une demande d'état (ENGINE_READY_S au plus)."""
        t0 = now()
        while not self.state(ENGINE_READY_ASK_S) and now() - t0 < ENGINE_READY_S and self.engine.p.poll() is None:
            pass
        ok = bool(self.last)
        return self.report.check(ok, "engine prêt (première réponse à menu_state)",
                                 f"{now() - t0:.1f} s" if ok else f"sans réponse en {ENGINE_READY_S:.0f} s")

    def stop(self) -> None:
        if self.engine is not None and self.engine.p.poll() is None:
            # xvfb-run ne transmet pas SIGTERM à Godot : le moteur et son Xvfb sont arrêtés d'abord.
            for pid in descendants(self.engine.p.pid):
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGTERM)
            self.engine.stop(signal.SIGTERM, timeout=5.0)
        if self.core is not None:
            rc = self.core.stop(signal.SIGINT, timeout=15.0)
            self.report.check(rc == 0, "arrêt du core", f"code de sortie {rc}")
            self.core = None

    def cleanup(self) -> None:
        if not self.args.keep:
            shutil.rmtree(self.tmp, ignore_errors=True)

    # --- déroulé ---------------------------------------------------------------------------

    def step(self, step: dict[str, Any]) -> bool:
        """Joue une étape ; faux si le passage ne peut pas continuer (engine arrêté)."""
        assert self.engine is not None and self.core is not None
        delay = float(step.get("delai", 5.0))
        if "appui" in step:
            for ev in [step["appui"]] if isinstance(step["appui"], str) else step["appui"]:
                if not self.gesture(ev):
                    break
        elif "choisir" in step:
            self.check(self.choose(step["choisir"]), f"choisir « {step['choisir']} »",
                       f"écran « {self.last.get('screen')} », focus « {self.last.get('focus_id')} »")
        elif "aller" in step:
            self.check(self.move_focus(step["aller"]), f"focus sur « {step['aller']} »",
                       f"écran « {self.last.get('screen')} », focus « {self.last.get('focus_id')} »")
        elif "touche" in step:
            t = now()
            self._send({"type": "_test", "action": "key", "key": step["touche"], "shift": bool(step.get("maj")),
                        "hold_ms": int(step.get("duree_ms", 150))})
            self.engine.wait_for(r"\[test\] key ", int(step.get("duree_ms", 150)) / 1000.0 + 10.0, after=t)
            time.sleep(0.2)
        elif "souris" in step:
            item = step.get("element", "")
            if item and not any(r["id"] == item for r in self.state().get("rows", [])):
                # Rangée hors de la partie affichée de la liste : la molette l'amène, comme le ferait le cycliste.
                if not self.move_focus(item):
                    self.check(False, f"souris : molette jusqu'à « {item} »", "élément introuvable")
                    return True
            t = now()
            self._send({"type": "_test", "action": "mouse", "kind": step["souris"], "item": step.get("element", ""),
                        "at": step.get("point", [])})
            got = self.engine.wait_for(r"\[test\] mouse (done|hidden)", 10.0, after=t)
            self.check(got is not None and got[1].group(1) == "done", f"souris {step['souris']} "
                       f"{step.get('element', step.get('point', ''))}", got[1].group(0) if got else "sans réponse")
            time.sleep(0.2)
        elif "click" in step:
            with self.control.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"action": "press", "button": step["click"],
                                    "duration_s": float(step.get("duree_s", COURT_S))}) + "\n")
            time.sleep(float(step.get("duree_s", COURT_S)) + 0.5)
        elif "ecran" in step or "menu_cache" in step or "monde" in step:
            self.wait_screen(step)
        elif "config" in step:
            self.wait_config(step["config"], delay if "delai" in step else 3.0)
        elif "journal" in step:
            proc = self.core if step["journal"] == "core" else self.engine
            got = proc.wait_for(step["motif"], delay)
            self.check(got is not None, f"journal du {step['journal']} : « {step['motif']} »",
                       got[1].group(0) if got else f"absent après {delay:.0f} s")
        elif "fichier" in step:
            want = bool(step.get("existe", True))
            found = lambda: sorted(str(p.relative_to(self.home)) for p in self.home.glob(step["fichier"]))
            deadline = now() + delay
            while bool(found()) != want and now() < deadline:
                time.sleep(0.2)
            self.check(bool(found()) == want, f"fichier ~/{step['fichier']} {'présent' if want else 'absent'}",
                       ", ".join(found()) or "absent")
        elif "sortie" in step:
            self.wait_exit(int(step["sortie"]), delay if "delai" in step else 10.0)
            return False
        elif "commande" in step:
            self._send({"type": "_test", "action": "command", "name": step["commande"], "args": step.get("args", {})})
            time.sleep(1.0)
        elif "attendre" in step:
            time.sleep(float(step["attendre"]))
        elif "capture" in step:
            self.capture(step["capture"])
        elif "relancer" in step:
            self.stop()
            self.restarts = getattr(self, "restarts", 0) + 1
            return self.start(self.restarts)
        if self.args.captures == "ecrans" and "ecran" in step:
            self.capture(str(self.last.get("screen", "ecran")))
        return self.engine.p.poll() is None

    def play(self) -> None:
        t0 = now()
        print(f"== {self.name} ({self.voie}) ==", flush=True)
        self.prepare()
        try:
            if self.start():
                for i, step in enumerate(self.doc.get("etapes", [])):
                    if self.voie not in step.get("voies", VOIES):
                        continue
                    if not self.step(step):
                        break
                    if self.report.failed >= MAX_FAILURES:
                        self.report.check(False, f"passage interrompu après {MAX_FAILURES} échecs",
                                          f"étape {i + 1} sur {len(self.doc['etapes'])}")
                        break
                if self.replis:
                    self.report.check(None, "souris : gestes joués au clavier (pas de geste de souris)", str(self.replis))
        finally:
            self.stop()
            self.cleanup()
            self.duration_s = now() - t0


# --- rapport -------------------------------------------------------------------------------------

def write_reports(out: Path, runs: list[Run]) -> Path:
    names = list(dict.fromkeys(r.name for r in runs))
    voies = [v for v in VOIES if any(r.voie == v for r in runs)]
    by = {(r.name, r.voie): r for r in runs}

    def cell(r: Run | None) -> str:
        if r is None:
            return "<td>—</td>"
        total = sum(ok is not None for ok, _, _ in r.report.rows)
        cls = "ok" if r.report.failed == 0 else "ko"
        return (f"<td class='{cls}'><a href='#{html.escape(r.name)}-{r.voie}'>{total - r.report.failed}/{total}</a>"
                f"<br><small>{r.duration_s:.0f} s</small></td>")

    parts = ["<!doctype html><meta charset='utf-8'><title>Banc des menus</title>",
             "<style>body{font-family:sans-serif;margin:16px;max-width:1400px}table{border-collapse:collapse}"
             "td,th{border:1px solid #999;padding:4px 10px;text-align:center}td.ok{background:#dfd}td.ko{background:#fdd}"
             "img{width:420px;border:1px solid #888}figure{display:inline-block;margin:6px;vertical-align:top;"
             "max-width:430px}li.ko{color:#b00}li.ok{color:#070}li.info{color:#555}figcaption{font-size:12px}</style>",
             "<h1>Banc des menus</h1>", "<table><tr><th>Scénario</th>"
             + "".join(f"<th>{v}</th>" for v in voies) + "</tr>"]
    for n in names:
        parts.append(f"<tr><th style='text-align:left'>{html.escape(n)}</th>"
                     + "".join(cell(by.get((n, v))) for v in voies) + "</tr>")
    parts.append("</table>")
    for r in runs:
        parts.append(f"<h2 id='{html.escape(r.name)}-{r.voie}'>{html.escape(r.name)} — {r.voie}</h2>"
                     f"<p>{html.escape(r.doc.get('description', ''))}</p><ul>")
        for ok, label, measure in r.report.rows:
            cls, word = ("info", "INFO") if ok is None else ("ok", "OK") if ok else ("ko", "ÉCHEC")
            parts.append(f"<li class='{cls}'>{word} {html.escape(label)} : {html.escape(measure)}</li>")
        parts.append("</ul>")
        for s in r.shots:
            img = f"<img src='{html.escape(r.name)}/{r.voie}/{html.escape(s['file'])}'>" if s["file"] else ""
            parts.append(f"<figure>{img}<figcaption><b>{html.escape(s['tag'])}</b> : écran {html.escape(s['screen'])}, "
                         f"« {html.escape(s['title'])} »<br>{html.escape(s['why'])}<br>"
                         f"{html.escape(' | '.join(s['rows']))}</figcaption></figure>")
    path = out / "rapport.html"
    path.write_text("\n".join(parts), encoding="utf-8")
    results = [{"scenario": r.name, "voie": r.voie, "echecs": r.report.failed, "duree_s": round(r.duration_s, 1),
                "verifications": [{"ok": ok, "quoi": label, "mesure": measure} for ok, label, measure in r.report.rows]}
               for r in runs]
    (out / "resultats.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"{r.name:24s} {r.voie:8s} {'OK' if r.report.failed == 0 else f'{r.report.failed} ÉCHEC(S)':12s} "
             f"{r.duration_s:5.0f} s" for r in runs]
    (out / "resume.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--godot", type=Path, default=Path(os.environ.get(
        "GODOT", Path.home() / "Applications/godot/Godot_v4.7.2-stable_linux.x86_64")))
    ap.add_argument("--scenario", action="append", help="nom (menu_scenarios/) ou fichier JSON ; défaut : tous")
    ap.add_argument("--voies", default=",".join(VOIES), help="voies d'entrée, séparées par des virgules")
    ap.add_argument("--rotation", action="store_true",
                    help="une seule voie par scénario, à tour de rôle (intégration continue : trois fois plus court)")
    ap.add_argument("--native", action="store_true", help="fenêtre sur l'écran réel au lieu de Xvfb")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--captures", choices=["echecs", "ecrans"], default="echecs",
                    help="captures aux échecs seulement (défaut) ou aussi à chaque écran vérifié")
    ap.add_argument("--keep", action="store_true", help="garde le HOME temporaire")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    known = scenarios()
    if args.list:
        for name, path in known.items():
            doc = load_scenario(path)
            print(f"{name:24s} {','.join(doc.get('voies', VOIES)):22s} {doc.get('description', '')}")
        return 0
    voies = [v for v in args.voies.split(",") if v]
    if any(v not in VOIES for v in voies):
        print(f"voies inconnues : {args.voies} (permises : {', '.join(VOIES)})")
        return 2
    if not os.access(args.godot, os.X_OK):
        print(f"Godot introuvable : {args.godot}")
        return 2
    if not args.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable : sudo apt install xvfb xauth, ou --native (fenêtre sur l'écran)")
        return 2
    chosen: list[tuple[str, Path]] = []
    for name in args.scenario or list(known):
        path = known.get(name) or Path(name)
        if not path.is_file():
            print(f"scénario inconnu : {name} (--list pour la liste)")
            return 2
        chosen.append((path.stem, path))
    out = args.out or Path(tempfile.mkdtemp(prefix="openride-banc-menus-"))
    runs: list[Run] = []
    for i, (name, path) in enumerate(chosen):
        doc = load_scenario(path)
        mine = [v for v in voies if v in doc.get("voies", VOIES)]
        if args.rotation and mine:
            mine = [mine[i % len(mine)]]
        for voie in mine:
            run = Run(args, name, doc, voie, out / name / voie)
            run.play()
            runs.append(run)
    report = write_reports(out, runs)
    failed = [r for r in runs if r.report.failed]
    print((out / "resume.txt").read_text(encoding="utf-8"), end="")
    print(f"Rapport : {report}\n{'OK' if not failed else f'{len(failed)} passage(s) en échec sur {len(runs)}'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.path.insert(0, str(REPO / "scripts"))
    from isolation_tests import verrou_suite   # une seule suite de tests ou banc à la fois

    with verrou_suite("menu_bench"):
        code = main()
    sys.exit(code)
