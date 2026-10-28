#!/usr/bin/env python3
"""Robot des menus : scénarios déclaratifs joués au Click simulé, au clavier simulé et à la souris simulée.

Usage :
    menu_robot.py [--scenario NOM]... [--canal click|clavier|souris]... [--godot CHEMIN] [--native]
                  [--out DOSSIER] [--keep] [--list] [--check]

Chaque scénario (`engine/tests/menu_scenarios/<nom>.json`) lance un vrai core (Bluetooth simulé : trainer,
paire de Click, ceinture) et un vrai engine (`--test-mode`, sous Xvfb ou sur l'écran avec `--native`), dans un
HOME temporaire, puis joue ses étapes une fois par canal d'entrée :
- `click` : appuis sur le Click simulé par le port de pilotage du Bluetooth simulé (`control_port`) : trame
  0x23 du boîtier, décodeur et pilote du core, relais `input` à l'engine, comme le vrai Click ;
- `clavier` : appui puis relâchement d'une touche injectés dans Godot (`Input.parse_input_event`) avec la
  vraie durée d'appui : `_unhandled_input`, `key_map.gd`, comme une vraie touche ;
- `souris` : survol, clic gauche, clic droit et molette injectés sur la ligne du menu (`menu_view.gd`) ; un
  bouton sans geste de souris (A court, Z, appuis longs) est joué au clavier, et le rapport le dit.

Un seul tableau (BOUTONS, spécification générale §7.1, seule référence) dit pour chaque bouton le geste de
chaque canal et l'effet attendu dans un menu ; l'étape « tableau » le vérifie sur l'écran affiché. Les étapes
et vérifications désignent écrans et éléments par leurs identifiants stables (`menu_model.gd`,
`menu_flow.gd`), pas par leurs libellés. Format des scénarios : `engine/tests/menu_scenarios/README.md`.

Résultat dans `--out` (défaut : dossier temporaire) : `rapport.html` (réussi ou échec par scénario et par
canal, chaque vérification, captures d'écran, capture et état du menu à chaque échec), `rapport.json` et les
journaux du core et de l'engine. Code de sortie : 0 si tout passe, 1 sinon, 2 si Godot ou xvfb-run manque
ou si un scénario est invalide. `--check` valide les scénarios sans rien lancer.
"""

from __future__ import annotations

import argparse
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent
REPO = ENGINE_DIR.parent
SCENARIOS_DIR = TESTS_DIR / "menu_scenarios"
sys.path.insert(0, str(TESTS_DIR))

from e2e_check import free_udp_ports, now  # noqa: E402
from sim_bench import ERG_SHORT_ZWO, BenchProc  # noqa: E402

CANAUX = ("click", "clavier", "souris")

# --- un seul tableau bouton -> action (spécification générale §7.1) --------------------------------

SHORT_S = 0.15     # appui court (< 0,5 s)
LONG_S = 1.1       # appui long (>= 0,9 s)
UNCLEAR_S = 0.7    # zone floue (entre 0,5 et 0,9 s)


@dataclass(frozen=True)
class Bouton:
    """Un bouton du Click et sa durée d'appui : geste de chaque canal et effet dans un menu."""
    click: str            # bouton du Click simulé (ble_sim.CLICK_BUTTONS, « + », « - »)
    touche: str           # touche du clavier (test_input.gd KEYS), même durée d'appui
    duree: float
    souris: str | None    # geste de la souris (test_input.gd MOUSE_BUTTONS) ; None : joué au clavier
    effet: str            # suivant, precedent, +5, -5, valider, retour, rien


BOUTONS: dict[str, Bouton] = {
    "+ court": Bouton("+", "+", SHORT_S, "wheel_down", "suivant"),
    "+ long": Bouton("+", "+", LONG_S, None, "+5"),
    "+ flou": Bouton("+", "+", UNCLEAR_S, None, "rien"),
    "- court": Bouton("-", "-", SHORT_S, "wheel_up", "precedent"),
    "- long": Bouton("-", "-", LONG_S, None, "-5"),
    "- flou": Bouton("-", "-", UNCLEAR_S, None, "rien"),
    "B court": Bouton("B", "-", SHORT_S, "wheel_up", "precedent"),
    "B long": Bouton("B", "-", LONG_S, None, "-5"),
    "A court": Bouton("A", "A", SHORT_S, None, "suivant"),
    "A long": Bouton("A", "A", LONG_S, "left", "valider"),
    "Y court": Bouton("Y", "Y", SHORT_S, "right", "retour"),
    "Z court": Bouton("Z", "Z", SHORT_S, None, "rien"),
    "Z long": Bouton("Z", "Z", LONG_S, None, "rien"),
    "gauche": Bouton("LEFT", "Gauche", SHORT_S, None, "precedent"),
    "droite": Bouton("RIGHT", "Droite", SHORT_S, None, "suivant"),
    "haut": Bouton("UP", "Haut", SHORT_S, None, "rien"),
    "bas": Bouton("DOWN", "Bas", SHORT_S, None, "rien"),
}
# Synonymes du clavier (tableau du clavier, §7.1) : touche (« Maj+ » : Maj tenue) -> bouton doublé.
SYNONYMES: dict[str, str] = {
    "=": "+ court", "Pavé+": "+ court", "Pavé-": "- court", "PageHaut": "+ long", "PageBas": "- long",
    "Maj+A": "A long", "Entrée": "A long", "PavéEntrée": "A long", "Maj+Z": "Z long", "Échap": "Y court",
}
# Boutons du tableau joués par défaut (« tableau » sans liste) ; Y en dernier (il quitte l'écran).
TABLEAU_DEFAUT = ["+ court", "- court", "B court", "A court", "droite", "gauche", "+ long", "- long", "B long",
                  "Z court", "Z long", "haut", "bas", "+ flou"]
# Écrans dont la navigation suit menu_model.gd (focus, boucle, grand pas borné) : le tableau s'y applique.
SETTLE_S = {"click": 0.45, "clavier": 0.2, "souris": 0.25}


def cle_bouton(nom: str) -> str:
    """Nom du tableau d'un bouton écrit « − long », « -long », « A » (appui court par défaut)…"""
    n = " ".join(nom.replace("−", "-").split())
    if n in BOUTONS:
        return n
    if n + " court" in BOUTONS:
        return n + " court"
    raise ValueError(f"bouton inconnu : {nom!r} (connus : {', '.join(BOUTONS)})")


def focus_attendu(items: list[dict[str, Any]], focus: int, effet: str) -> int:
    """Focus après un effet de navigation, d'après les règles de menu_model.gd (oracle indépendant)."""
    n = len(items)
    if focus < 0 or n == 0:
        return focus

    def premier_actif(start: int, d: int) -> int:
        for k in range(n):
            i = (start + d * k) % n
            if items[i]["enabled"]:
                return i
        return -1

    if effet == "suivant":
        return premier_actif(focus + 1, 1)
    if effet == "precedent":
        return premier_actif(focus - 1, -1)
    if effet in ("+5", "-5"):
        d = 1 if effet == "+5" else -1
        left, i, out = 5, focus + d, focus
        while left > 0 and 0 <= i < n:
            if items[i]["enabled"]:
                out, left = i, left - 1
            i += d
        return out
    return focus


# --- scénarios ---------------------------------------------------------------------------------------

class ScenarioError(Exception):
    """Scénario invalide ; le message dit où."""


ACTIONS = {"bouton", "touche", "click", "souris", "aller", "ouvrir", "commande", "attendre", "attendre_etat",
           "attendre_ecran", "tableau", "capture", "ecrire"}
CHECKS = {"ecran", "titre", "titre_debut", "focus", "elements", "absents", "texte", "pas_texte", "actifs",
          "inactifs", "menu_visible", "config", "config_absent", "fichier", "journal_core", "journal_engine",
          "sortie_engine", "bandeau", "statut", "aide", "action_menu", "edition", "monde_ouvert", "signaler",
          "config_present"}
OPTIONS = {"note", "connu", "delai", "duree", "maj", "element", "n", "args", "retour_vers", "sauf", "canaux", "contenu"}
PREPARATION = {"entrainements", "plans", "imports", "records", "config", "click", "parcours", "profil"}
TOP = {"description", "canaux", "preparation", "etapes", "lent"}


def valider_scenario(name: str, doc: Any) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise ScenarioError(f"{name} : objet JSON attendu")
    unknown = sorted(set(doc) - TOP)
    if unknown:
        raise ScenarioError(f"{name} : clé(s) inconnue(s) {', '.join(unknown)}")
    for c in doc.get("canaux", CANAUX):
        if c not in CANAUX:
            raise ScenarioError(f"{name} : canal inconnu {c!r}")
    prep = doc.get("preparation", {}) or {}
    bad = sorted(set(prep) - PREPARATION)
    if bad:
        raise ScenarioError(f"{name}.preparation : clé(s) inconnue(s) {', '.join(bad)}")
    steps = doc.get("etapes")
    if not isinstance(steps, list) or not steps:
        raise ScenarioError(f"{name} : « etapes » doit être une liste non vide")
    for i, st in enumerate(steps):
        where = f"{name}.etapes[{i}]"
        if not isinstance(st, dict):
            raise ScenarioError(f"{where} : objet attendu")
        keys = set(st) - OPTIONS
        main = keys & (ACTIONS | CHECKS)
        if keys - ACTIONS - CHECKS:
            raise ScenarioError(f"{where} : clé(s) inconnue(s) {', '.join(sorted(keys - ACTIONS - CHECKS))}")
        if not main:
            raise ScenarioError(f"{where} : aucune action ni vérification")
        if len(main & ACTIONS) > 1:
            raise ScenarioError(f"{where} : une seule action par étape ({', '.join(sorted(main & ACTIONS))})")
        try:
            if "bouton" in st:
                cle_bouton(st["bouton"])
            for b in st.get("tableau") or []:
                cle_bouton(b)
            for b in st.get("sauf", []):
                cle_bouton(b)
        except ValueError as exc:
            raise ScenarioError(f"{where} : {exc}") from None
        if "touche" in st:
            t = str(st["touche"])
            if t not in SYNONYMES and t.removeprefix("Maj+") not in {b.touche for b in BOUTONS.values()} | {"P", "Espace"}:
                raise ScenarioError(f"{where} : touche inconnue {t!r}")
        for c in st.get("canaux", CANAUX):
            if c not in CANAUX:
                raise ScenarioError(f"{where} : canal inconnu {c!r}")
    return doc


def charger_scenarios() -> dict[str, dict[str, Any]]:
    out = {}
    for p in sorted(SCENARIOS_DIR.glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ScenarioError(f"{p.name} : JSON illisible : {exc}") from None
        out[p.stem] = valider_scenario(p.stem, doc)
    return out


# --- données préparées dans le HOME temporaire ----------------------------------------------------------

PLAN_TOML = """[plan]
name = "Plan du banc"
description = "Deux semaines, trois séances (banc des menus)."
days_per_week = 2

[[week]]
focus = "Endurance"
days = [
  { day = "jour1", workout = "erg_court" },
  { day = "jour3", workout = "erg_court" },
]

[[week]]
days = [
  { day = "jour1", workout = "erg_court" },
]
"""

# Sim BLE : tout se connecte en une seconde.
READY = {"trainer": {"appear_at": 0.3, "connect_delay_s": 0.3},
         "click": {"appear_at": 0.5, "connect_delay_s": 0.3},
         "hr": {"appear_at": 0.5, "connect_delay_s": 0.2}, "events": []}


# --- résultat --------------------------------------------------------------------------------------------

@dataclass
class Ligne:
    ok: bool | None      # None : information (jamais un échec)
    etape: int
    label: str
    mesure: str
    capture: str = ""
    etat: dict[str, Any] | None = None


@dataclass
class Resultat:
    scenario: str
    canal: str
    description: str = ""
    lignes: list[Ligne] = field(default_factory=list)
    captures: list[tuple[str, str]] = field(default_factory=list)
    duree_s: float = 0.0
    replis_clavier: int = 0

    @property
    def echecs(self) -> int:
        return sum(ln.ok is False for ln in self.lignes)

    @property
    def verifs(self) -> int:
        return sum(ln.ok is not None for ln in self.lignes)


# --- une partie : core + engine, un canal ---------------------------------------------------------------

class Partie:
    """Un scénario joué sur un canal : lancement, entrées, lecture de l'état, vérifications."""

    def __init__(self, args: argparse.Namespace, name: str, doc: dict[str, Any], canal: str, out: Path) -> None:
        self.args = args
        self.name = name
        self.doc = doc
        self.canal = canal
        self.out = out
        self.res = Resultat(name, canal, str(doc.get("description", "")))
        self.engine: BenchProc | None = None
        self.core: BenchProc | None = None
        self.state_port = self.cmd_port = self.control_port = 0
        self.tmp = Path()
        self.home = Path()
        self.config = Path()
        self.etape = 0
        self.connu = ""
        self._n = 0

    # --- journal du résultat -------------------------------------------------------------------------

    def check(self, ok: bool | None, label: str, mesure: str, etat: dict[str, Any] | None = None) -> bool:
        if ok is False and self.connu:   # défaut connu (« connu » de l'étape) : signalé, pas compté
            ok, label = None, f"défaut connu ({self.connu}) : {label}"
        elif ok is True and self.connu:
            ok, label = None, f"défaut connu corrigé ? retirer « connu » : {label}"
        tag = "INFO" if ok is None else ("OK" if ok else "ÉCHEC")
        print(f"  [{tag}] {label} : {mesure}", flush=True)
        ligne = Ligne(ok, self.etape, label, mesure)
        if ok is False and self.engine is not None and self.engine.p.poll() is None:
            ligne.capture = self.capture(f"echec_{self.etape:02d}")
            ligne.etat = etat if etat is not None else self.etat()
        self.res.lignes.append(ligne)
        return ok is not False

    # --- engine --------------------------------------------------------------------------------------

    def _send(self, msg: dict[str, Any], port: int | None = None) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(json.dumps(msg).encode(), ("127.0.0.1", port or self.state_port))

    def _test(self, action: str, **kw: Any) -> None:
        self._send({"type": "_test", "action": action, **kw})

    def etat(self, timeout: float = 5.0) -> dict[str, Any]:
        """État des menus lu dans l'engine (`menu_state`) ; {} si l'engine ne répond pas."""
        if self.engine is None or self.engine.p.poll() is not None:
            return {}
        self._n += 1
        tag = f"s{self._n}"
        t = now()
        self._test("menu_state", tag=tag)
        got = self.engine.wait_for(r"\[test\] menu_state (\{.*\"tag\":\"" + tag + r"\".*\})$", timeout, after=t)
        if got is None:
            return {}
        try:
            return json.loads(got[1].group(1))
        except ValueError:
            return {}

    def capture(self, tag: str) -> str:
        if self.engine is None or self.engine.p.poll() is not None:
            return ""
        self._n += 1
        path = (self.out / f"{self._n:03d}_{tag}.png").resolve()
        t = now()
        self._test("screenshot", path=str(path), tag=tag)
        got = self.engine.wait_for(r"\[test\] screenshot \{.*\"tag\":\"" + re.escape(tag) + r"\"", 8.0, after=t)
        if got is None:
            return ""
        self.res.captures.append((tag, path.name))
        return path.name

    # --- entrées -------------------------------------------------------------------------------------

    def _touche(self, touche: str, duree: float) -> None:
        """Appui tenu `duree` secondes : l'engine appuie, attend et relâche (durée exacte, quel que soit le
        nombre d'images par seconde) ; le robot attend l'accusé `key_done`."""
        maj = touche.startswith("Maj+")
        nom = touche.removeprefix("Maj+")
        t = now()
        self._test("key", key=nom, shift=maj, hold_s=duree)
        # Marge large : sous Xvfb, une image peut durer plusieurs secondes (changement de qualité graphique).
        if self.engine is not None and self.engine.wait_for(r"\[test\] key_done " + re.escape(nom) + "$", duree + 20.0, after=t) is None:
            self.check(False, f"touche « {touche} » jouée", "pas d'accusé key_done de l'engine")

    def _click(self, bouton: str, duree: float) -> None:
        self._send({"action": "press", "button": bouton, "duration_s": duree}, self.control_port)
        time.sleep(duree)

    def _souris(self, geste: str, element: str = "") -> None:
        self._test("mouse", kind=geste, item=element)

    def jouer(self, nom: str, canal: str | None = None) -> str:
        """Joue un bouton du tableau sur le canal ; renvoie le canal réellement utilisé."""
        b = BOUTONS[cle_bouton(nom)]
        canal = canal or self.canal
        if canal == "souris" and b.souris is not None:
            element = ""
            if b.souris == "left":   # clic sur l'élément du focus : focus puis validation (A long)
                element = str(self.etat().get("focus_id", ""))
            self._souris(b.souris, element)
        elif canal == "click":
            self._click(b.click, b.duree)
        else:
            if canal == "souris":
                self.res.replis_clavier += 1
                canal = "clavier"
            self._touche(b.touche, b.duree)
        time.sleep(SETTLE_S[canal])
        return canal

    def attendre(self, pred: Callable[[dict[str, Any]], bool], timeout: float) -> dict[str, Any]:
        """Relit l'état jusqu'à ce que `pred` soit vrai (ou le délai écoulé) ; renvoie le dernier état."""
        deadline = now() + timeout
        st = self.etat()
        while not pred(st) and now() < deadline:
            time.sleep(0.15)
            st = self.etat()
        return st

    def unilateral(self) -> bool:
        """Click simulé sans boîtier « − » (préparation `click: unilateral`), sur le canal du Click."""
        return self.canal == "click" and (self.doc.get("preparation", {}) or {}).get("click") == "unilateral"

    def aller(self, cible: str, limite: int = 30) -> bool:
        """Focus sur l'élément `cible` par petits pas du canal (+ court ou − court, le plus court chemin)."""
        for _ in range(limite):
            st = self.etat()
            ids = [it["id"] for it in st.get("items", [])]
            if st.get("focus_id") == cible:
                return True
            if cible not in ids or st.get("focus", -1) < 0:
                return False
            d = ids.index(cible) - int(st["focus"])
            avant = d if d > 0 else d + len(ids)
            # Click d'un seul boîtier : pas de « − », B (boîtier « + ») recule aussi (§7.1).
            arriere = "B court" if self.unilateral() else "- court"
            self.jouer("+ court" if avant <= len(ids) - avant else arriere)
        return self.etat().get("focus_id") == cible

    # --- lancement -----------------------------------------------------------------------------------

    def demarrer(self) -> bool:
        a = self.args
        prep = self.doc.get("preparation", {}) or {}
        self.out.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="openride-robot-"))
        self.home = self.tmp / "home"
        routes = self.home / ".local" / "share" / "openride" / "routes"
        routes.mkdir(parents=True)
        shutil.copytree(ENGINE_DIR / "demo" / "demo.world", routes / "demo.world")
        for extra in prep.get("parcours", []):   # copies du parcours de démonstration, autres noms
            shutil.copytree(ENGINE_DIR / "demo" / "demo.world", routes / f"{extra}.world")
        openride = self.home / "OpenRide"
        if prep.get("entrainements") or prep.get("plans"):
            (openride / "Workouts").mkdir(parents=True, exist_ok=True)
            (openride / "Workouts" / "erg_court.zwo").write_text(ERG_SHORT_ZWO, encoding="utf-8")
        if prep.get("plans"):
            (openride / "Plans").mkdir(parents=True, exist_ok=True)
            (openride / "Plans" / "plan_banc.toml").write_text(PLAN_TOML, encoding="utf-8")
        if prep.get("imports"):
            dl = self.home / "Téléchargements"
            dl.mkdir(parents=True, exist_ok=True)
            (dl / "seuil_import.zwo").write_text(ERG_SHORT_ZWO.replace("ERG court", "Seuil importé"), encoding="utf-8")
        if prep.get("profil"):
            openride.mkdir(parents=True, exist_ok=True)
            (openride / "profile.json").write_text(json.dumps(prep["profil"]), encoding="utf-8")
        self.state_port, self.cmd_port, self.control_port = free_udp_ports(3)
        self.config = self.tmp / "config.toml"
        self.config.write_text(f"[ipc]\nport_state = {self.state_port}\nport_commands = {self.cmd_port}\n"
                               + str(prep.get("config", "")), encoding="utf-8")
        spec = json.loads(json.dumps(READY))
        if prep.get("click") == "unilateral":   # boîtier « − » jamais annoncé
            spec["click"]["minus"] = {"appear_at": 100000}
        spec["control_port"] = self.control_port
        scen = self.tmp / "scenario.json"
        scen.write_text(json.dumps(spec), encoding="utf-8")
        env = {**os.environ, "HOME": str(self.home), "PYTHONUNBUFFERED": "1",
               "PYTHONPATH": str(REPO / "core" / "src")}
        for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
            env.pop(k, None)
        argv = [sys.executable, "-m", "openride_core", "run", "--config", str(self.config), "--trainer", "sim",
                "--input", "sim", "--hr", "sim", "--sim-scenario", str(scen)]
        self.core = BenchProc("core", argv, env, self.out / "core.log")
        if not self.check(self.core.wait_for(r"Core démarré", 20.0) is not None, "démarrage du core", "« Core démarré »"):
            return False
        cmd = [str(a.godot), "--path", str(ENGINE_DIR), "--resolution", "1280x720", "--audio-driver", "Dummy"]
        if not a.native:
            cmd = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"] + cmd + [
                "--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
        cmd += ["--", f"--ipc-state-port={self.state_port}", f"--ipc-cmd-port={self.cmd_port}",
                f"--routes-dir={routes}", "--test-mode", "--quality=low"]
        self.engine = BenchProc("engine", cmd, env, self.out / "engine.log")
        ok = self.engine.wait_for(r"hello_ack reçu", 30.0) is not None
        self.check(ok, "engine relié au core", "hello_ack")
        if not ok:
            return False
        self.check(self.engine.wait_for(r"route_loaded id=demo", 30.0) is not None, "décor de fond chargé", "demo")
        # Click : les deux boîtiers reliés (handshake RideOn) avant le premier appui.
        if self.canal == "click":
            got = self.core.wait_for(r"Click.*(connecté|CONNECTED|RideOn)", 15.0)
            self.check(None, "Click simulé relié", "oui" if got else "pas de ligne au journal (on continue)")
        return True

    def arreter(self) -> None:
        if self.engine is not None and self.engine.p.poll() is None:
            self.engine.stop(signal.SIGTERM, timeout=5.0)
        if self.core is not None:
            self.core.stop(signal.SIGINT, timeout=15.0)
        if not self.args.keep:
            shutil.rmtree(self.tmp, ignore_errors=True)

    # --- étapes --------------------------------------------------------------------------------------

    def jouer_scenario(self) -> None:
        t0 = now()
        try:
            if not self.demarrer():
                return
            for i, st in enumerate(self.doc["etapes"]):
                self.etape = i
                if self.canal not in st.get("canaux", CANAUX):
                    continue
                if "note" in st:
                    print(f"  # {st['note']}", flush=True)
                self.connu = str(st.get("connu", ""))
                self.faire(st)
                self.connu = ""
                if self.engine is not None and self.engine.p.poll() is not None and "sortie_engine" not in st:
                    nxt = self.doc["etapes"][i + 1:] if i + 1 < len(self.doc["etapes"]) else []
                    if any("sortie_engine" in s for s in nxt):
                        continue
                    self.check(False, "engine toujours lancé", f"sorti avec le code {self.engine.p.poll()}")
                    return
        finally:
            self.arreter()
            self.res.duree_s = now() - t0

    def faire(self, st: dict[str, Any]) -> None:
        delai = float(st.get("delai", 8.0))
        if "bouton" in st:
            for _ in range(int(st.get("n", 1))):
                used = self.jouer(st["bouton"])
            if used != self.canal:
                self.check(None, f"{st['bouton']} sans geste {self.canal}", f"joué au {used}")
        elif "touche" in st:
            t = str(st["touche"])
            b = BOUTONS[SYNONYMES[t]] if t in SYNONYMES else None
            duree = float(st.get("duree", b.duree if b is not None and t not in ("PageHaut", "PageBas", "Entrée",
                                                                               "PavéEntrée", "Maj+A", "Maj+Z") else SHORT_S))
            for _ in range(int(st.get("n", 1))):
                self._touche(t, duree)
                time.sleep(SETTLE_S["clavier"])
        elif "click" in st:
            self._click(str(st["click"]), float(st.get("duree", SHORT_S)))
            time.sleep(SETTLE_S["click"])
        elif "souris" in st:
            for _ in range(int(st.get("n", 1))):
                self._souris(str(st["souris"]), str(st.get("element", "")))
                time.sleep(SETTLE_S["souris"])
        elif "aller" in st:
            cible = str(st["aller"])
            self.check(self.aller(cible), f"focus sur « {cible} »", str(self.etat().get("focus_id", "")))
        elif "ouvrir" in st:
            self.ouvrir(str(st["ouvrir"]))
        elif "commande" in st:
            self._test("command", name=str(st["commande"]), args=st.get("args", {}))
            time.sleep(0.5)
        elif "attendre" in st:
            time.sleep(float(st["attendre"]))
        elif "attendre_etat" in st:
            voulu = str(st["attendre_etat"])
            got = self.attendre(lambda s: s.get("session_state") == voulu, delai)
            self.check(got.get("session_state") == voulu, f"séance en {voulu}", str(got.get("session_state")), got)
        elif "attendre_ecran" in st:
            voulu = str(st["attendre_ecran"])
            got = self.attendre(lambda s: s.get("screen") == voulu and s.get("visible"), delai)
            self.check(got.get("screen") == voulu and bool(got.get("visible")), f"écran « {voulu} »",
                       f"{got.get('screen')} (visible={got.get('visible')})", got)
        elif "tableau" in st:
            self.tableau(st)
        elif "capture" in st:
            name = self.capture(str(st["capture"]))
            self.check(None, f"capture « {st['capture']} »", name or "impossible")
        elif "ecrire" in st:
            path = self.home / str(st["ecrire"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(st.get("contenu", "")), encoding="utf-8")
        self.verifier(st, delai)

    def ouvrir(self, cible: str) -> None:
        """Focus puis validation : appui long sur A, ou clic sur la ligne à la souris (elle doit être affichée)."""
        if self.canal == "souris":
            st = self.etat()
            rows = [r["id"] for r in st.get("rows", [])]
            if cible not in rows:   # ligne cachée : la molette amène le focus dessus
                self.aller(cible)
            t = now()
            self._souris("left", cible)
            ok = self.engine is not None and self.engine.wait_for(
                r"mouse_done .*\"item\":\"" + re.escape(cible) + r"\"", 3.0, after=t) is not None
            self.check(ok, f"clic sur « {cible} »", "ligne trouvée" if ok else "ligne absente de l'écran")
            time.sleep(SETTLE_S["souris"])
            return
        ok = self.aller(cible)
        self.check(ok, f"focus sur « {cible} »", str(self.etat().get("focus_id", "")))
        if ok:
            self.jouer("A long")

    def tableau(self, st: dict[str, Any]) -> None:
        """Chaque bouton du tableau sur l'écran affiché : effet attendu (§7.1), puis retour au focus de départ."""
        boutons = [cle_bouton(b) for b in (st["tableau"] or TABLEAU_DEFAUT)]
        sauf = {cle_bouton(b) for b in st.get("sauf", [])}
        depart = self.etat()
        ecran = depart.get("screen", "")
        for nom in boutons:
            if nom in sauf:
                continue
            b = BOUTONS[nom]
            if self.canal == "souris" and b.souris is None:
                continue   # sans geste de souris : couvert par les canaux clavier et Click
            avant = self.etat()
            if b.effet in ("valider", "retour"):
                continue   # vérifiés par les étapes (ouvrir, retour_vers)
            self.jouer(nom)
            attendu = focus_attendu(avant.get("items", []), int(avant.get("focus", -1)), b.effet)
            apres = self.attendre(lambda s: s.get("screen") == ecran and int(s.get("focus", -1)) == attendu,
                                  1.5 if b.effet != "rien" else 0.0)
            ids = [it["id"] for it in avant.get("items", [])]
            nom_att = ids[attendu] if 0 <= attendu < len(ids) else "?"
            ok = apres.get("screen") == ecran and int(apres.get("focus", -1)) == attendu
            self.check(ok, f"{ecran} : {nom} → {b.effet}", f"focus {apres.get('focus_id')} (attendu {nom_att}), "
                       f"écran {apres.get('screen')}", apres)
            if nom.endswith("flou"):
                self.check(bool(apres.get("banner")), f"{ecran} : {nom} → explication à l'écran",
                           repr(apres.get("banner", ""))[:80], apres)
        if "retour_vers" in st and "Y court" not in sauf:
            self.jouer("Y court")
            voulu = str(st["retour_vers"])
            got = self.attendre(lambda s: s.get("screen") == voulu, 3.0)
            self.check(got.get("screen") == voulu, f"{ecran} : Y court → retour à « {voulu} »",
                       str(got.get("screen")), got)

    # --- vérifications -------------------------------------------------------------------------------

    def verifier(self, st: dict[str, Any], delai: float) -> None:
        checks = set(st) & CHECKS
        if not checks:
            return
        menu_checks = checks & {"ecran", "titre", "titre_debut", "focus", "elements", "absents", "texte", "pas_texte",
                                "actifs", "inactifs", "menu_visible", "bandeau", "statut", "aide", "edition",
                                "monde_ouvert"}
        if menu_checks:
            def tout(s: dict[str, Any]) -> bool:
                return all(ok for ok, _, _ in self._menu_checks(st, s))
            s = self.attendre(tout, delai if "ecran" in st or "menu_visible" in st else 2.0)
            for ok, label, mesure in self._menu_checks(st, s):
                self.check(ok, label, mesure, s)
        if "config" in st:
            for cle, voulu in st["config"].items():
                got = self._attendre_config(cle, voulu, delai)
                self.check(got == voulu, f"config.toml : {cle} = {voulu!r}", repr(got))
        if "config_present" in st:
            for cle in st["config_present"]:
                deadline = now() + min(delai, 5.0)
                got = self._config_value(cle)
                while got is None and now() < deadline:
                    time.sleep(0.2)
                    got = self._config_value(cle)
                self.check(got is not None, f"config.toml : {cle} écrit", repr(got))
        if "signaler" in st:   # information seule : élément présent ou non (menu encore à couvrir)
            s = self.etat()
            ids = [it["id"] for it in s.get("items", [])]
            self.check(None, f"élément « {st['signaler']} » sur « {s.get('screen')} »",
                       "présent" if st["signaler"] in ids else f"absent — {st.get('note', '')}")
        if "config_absent" in st:
            for cle in st["config_absent"]:
                got = self._config_value(cle)
                self.check(got is None, f"config.toml : {cle} non écrit", repr(got))
        if "fichier" in st:
            path = self.home / str(st["fichier"])
            deadline = now() + delai
            while not path.exists() and now() < deadline:
                time.sleep(0.2)
            self.check(path.exists(), f"fichier ~/{st['fichier']}", "présent" if path.exists() else "absent")
        for key, proc in (("journal_core", self.core), ("journal_engine", self.engine)):
            if key in st and proc is not None:
                got = proc.wait_for(str(st[key]), delai)
                self.check(got is not None, f"{key.replace('_', ' du ')} : /{st[key]}/",
                           got[1].group(0)[:120] if got else "absent")
        if "action_menu" in st and self.engine is not None:
            got = self.engine.wait_for(r"menu_action (\{.*\"action\":\"" + re.escape(str(st["action_menu"])) + r"\".*\})",
                                       delai)
            self.check(got is not None, f"action du menu « {st['action_menu']} »", got[1].group(1)[:120] if got else "absente")
        if "sortie_engine" in st and self.engine is not None:
            deadline = now() + delai
            rc = self.engine.p.poll()
            while rc is None and now() < deadline:
                time.sleep(0.2)
                rc = self.engine.p.poll()
            self.check(rc == int(st["sortie_engine"]), f"engine sorti avec le code {st['sortie_engine']}", f"code {rc}")

    def _menu_checks(self, st: dict[str, Any], s: dict[str, Any]) -> list[tuple[bool, str, str]]:
        out: list[tuple[bool, str, str]] = []
        items = s.get("items", [])
        ids = [it["id"] for it in items]
        textes = [it["label"] + (" — " + it["detail"] if it.get("detail") else "") for it in items]
        if "ecran" in st:
            out.append((s.get("screen") == st["ecran"] and bool(s.get("visible")), f"écran « {st['ecran']} »",
                        f"{s.get('screen')} « {s.get('title')} » (visible={s.get('visible')})"))
        if "menu_visible" in st:
            out.append((bool(s.get("visible")) == bool(st["menu_visible"]), f"menu {'affiché' if st['menu_visible'] else 'caché'}",
                        f"visible={s.get('visible')}"))
        if "titre" in st:
            out.append((s.get("title") == st["titre"], f"titre « {st['titre']} »", f"« {s.get('title')} »"))
        if "titre_debut" in st:
            out.append((str(s.get("title", "")).startswith(st["titre_debut"]), f"titre « {st['titre_debut']}… »",
                        f"« {s.get('title')} »"))
        if "focus" in st:
            out.append((s.get("focus_id") == st["focus"], f"focus sur « {st['focus']} »", str(s.get("focus_id"))))
        for e in st.get("elements", []):
            out.append((any(i == e or (e.endswith("*") and i.startswith(e[:-1])) for i in ids), f"élément « {e} »",
                        ", ".join(ids)[:160]))
        for e in st.get("absents", []):
            out.append((e not in ids, f"pas d'élément « {e} »", ", ".join(ids)[:160]))
        for e in st.get("actifs", []):
            it = next((x for x in items if x["id"] == e), None)
            out.append((it is not None and it["enabled"], f"« {e} » actif", "absent" if it is None else str(it["enabled"])))
        for e in st.get("inactifs", []):
            it = next((x for x in items if x["id"] == e), None)
            out.append((it is not None and not it["enabled"], f"« {e} » désactivé",
                        "absent" if it is None else str(it["enabled"])))
        for t in ([st["texte"]] if isinstance(st.get("texte"), str) else st.get("texte", [])):
            out.append((any(t in x for x in textes) or t in str(s.get("title", "")), f"texte « {t} »", " | ".join(textes)[:160]))
        for t in ([st["pas_texte"]] if isinstance(st.get("pas_texte"), str) else st.get("pas_texte", [])):
            out.append((not any(t in x for x in textes), f"pas de texte « {t} »", " | ".join(textes)[:160]))
        if "edition" in st:
            out.append((bool(s.get("editing")) == bool(st["edition"]), f"réglage {'en' if st['edition'] else 'hors'} modification",
                        f"editing={s.get('editing')}"))
        if "monde_ouvert" in st:
            out.append((bool(s.get("world_menu")) == bool(st["monde_ouvert"]),
                        f"menu du monde ouvert {'affiché' if st['monde_ouvert'] else 'fermé'}", f"world_menu={s.get('world_menu')}"))
        if "bandeau" in st:
            out.append((st["bandeau"] in str(s.get("banner", "")), f"bandeau « {st['bandeau']} »", repr(s.get("banner", ""))[:120]))
        if "statut" in st:
            out.append((st["statut"] in str(s.get("status", "")), f"ligne d'état « {st['statut']} »", repr(s.get("status", ""))[:120]))
        if "aide" in st:
            out.append((st["aide"] in str(s.get("hint", "")), f"aide des boutons « {st['aide']} »", repr(s.get("hint", ""))[:120]))
        return out

    def _config_value(self, cle: str) -> Any:
        try:
            data: Any = tomllib.loads(self.config.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return None
        for part in cle.split("."):
            if not isinstance(data, dict) or part not in data:
                return None
            data = data[part]
        return data

    def _attendre_config(self, cle: str, voulu: Any, delai: float) -> Any:
        deadline = now() + min(delai, 5.0)
        got = self._config_value(cle)
        while got != voulu and now() < deadline:
            time.sleep(0.2)
            got = self._config_value(cle)
        return got


# --- rapport ---------------------------------------------------------------------------------------------

CSS = """body{font-family:system-ui,sans-serif;margin:16px;max-width:1200px}
table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:4px 8px;text-align:left;vertical-align:top}
.ok{color:#0a6b0a}.ko{color:#b00020;font-weight:bold}.info{color:#555}
img{width:420px;border:1px solid #888}figure{display:inline-block;margin:6px}
details{margin:4px 0}pre{white-space:pre-wrap;font-size:12px;background:#f4f4f4;padding:6px}"""


def ecrire_rapport(out: Path, resultats: list[Resultat]) -> Path:
    total_ko = sum(r.echecs for r in resultats)
    p = ["<!doctype html><meta charset='utf-8'><title>Robot des menus</title>", f"<style>{CSS}</style>",
         "<h1>Robot des menus</h1>",
         f"<p class='{'ok' if total_ko == 0 else 'ko'}'>{'Tout passe' if total_ko == 0 else f'{total_ko} vérification(s) en échec'}"
         f" — {len(resultats)} partie(s), {sum(r.verifs for r in resultats)} vérifications.</p>",
         "<table><tr><th>Scénario</th><th>Canal</th><th>Résultat</th><th>Vérifications</th><th>Durée</th>"
         "<th>Joués au clavier (souris)</th></tr>"]
    for r in resultats:
        ok = r.echecs == 0
        p.append(f"<tr><td><a href='#{html.escape(r.scenario)}-{r.canal}'>{html.escape(r.scenario)}</a></td>"
                 f"<td>{r.canal}</td><td class='{'ok' if ok else 'ko'}'>{'RÉUSSI' if ok else 'ÉCHEC'}</td>"
                 f"<td>{r.verifs - r.echecs}/{r.verifs}</td><td>{r.duree_s:.0f} s</td><td>{r.replis_clavier or ''}</td></tr>")
    p.append("</table>")
    for r in resultats:
        p.append(f"<h2 id='{html.escape(r.scenario)}-{r.canal}'>{html.escape(r.scenario)} ({r.canal}) : "
                 f"<span class='{'ok' if r.echecs == 0 else 'ko'}'>{'réussi' if r.echecs == 0 else f'{r.echecs} échec(s)'}</span></h2>")
        if r.description:
            p.append(f"<p>{html.escape(r.description)}</p>")
        p.append(f"<p><a href='{html.escape(r.scenario)}/{r.canal}/core.log'>journal du core</a> · "
                 f"<a href='{html.escape(r.scenario)}/{r.canal}/engine.log'>journal de l'engine</a></p><ul>")
        for ln in r.lignes:
            cls = "info" if ln.ok is None else ("ok" if ln.ok else "ko")
            tag = "INFO" if ln.ok is None else ("OK" if ln.ok else "ÉCHEC")
            p.append(f"<li class='{cls}'>[{ln.etape}] {tag} {html.escape(ln.label)} : {html.escape(ln.mesure)}")
            if ln.ok is False:
                if ln.capture:
                    p.append(f"<br><img src='{html.escape(r.scenario)}/{r.canal}/{html.escape(ln.capture)}'>")
                if ln.etat:
                    resume = {k: ln.etat.get(k) for k in ("screen", "title", "focus_id", "visible", "status", "session_state", "banner")}
                    resume["items"] = [f"{it['id']}{'' if it['enabled'] else ' (désactivé)'} : {it['label']}"
                                       for it in ln.etat.get("items", [])]
                    p.append(f"<details><summary>état du menu</summary><pre>{html.escape(json.dumps(resume, ensure_ascii=False, indent=1))}</pre></details>")
            p.append("</li>")
        p.append("</ul>")
        shots = [(t, f) for t, f in r.captures if not t.startswith("echec_")]
        for tag, f in shots:
            p.append(f"<figure><img src='{html.escape(r.scenario)}/{r.canal}/{html.escape(f)}'><figcaption>{html.escape(tag)}</figcaption></figure>")
    path = out / "rapport.html"
    path.write_text("\n".join(p), encoding="utf-8")
    (out / "rapport.json").write_text(json.dumps([{
        "scenario": r.scenario, "canal": r.canal, "reussi": r.echecs == 0, "echecs": r.echecs, "verifications": r.verifs,
        "duree_s": round(r.duree_s, 1), "replis_clavier": r.replis_clavier,
        "lignes": [{"ok": ln.ok, "etape": ln.etape, "label": ln.label, "mesure": ln.mesure, "capture": ln.capture}
                   for ln in r.lignes]} for r in resultats], ensure_ascii=False, indent=1), encoding="utf-8")
    return path


# --- programme -------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--godot", type=Path, default=Path(os.environ.get(
        "GODOT", Path.home() / "Applications/godot/Godot_v4.3-stable_linux.x86_64")))
    ap.add_argument("--scenario", action="append", help="nom d'un scénario (défaut : tous)")
    ap.add_argument("--canal", action="append", choices=CANAUX, help="canal d'entrée (défaut : ceux du scénario)")
    ap.add_argument("--rapide", action="store_true", help="un seul canal par scénario (le premier de sa liste)")
    ap.add_argument("--native", action="store_true", help="fenêtre sur l'écran réel au lieu de Xvfb")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--keep", action="store_true", help="garde le HOME temporaire")
    ap.add_argument("--list", action="store_true", help="liste les scénarios")
    ap.add_argument("--check", action="store_true", help="valide les scénarios sans rien lancer")
    args = ap.parse_args(argv)
    try:
        scenarios = charger_scenarios()
    except ScenarioError as exc:
        print(f"Scénario invalide : {exc}")
        return 2
    if args.list or args.check:
        for name, doc in scenarios.items():
            print(f"{name:22s} [{', '.join(doc.get('canaux', CANAUX))}] {doc.get('description', '')}")
        if args.check:
            print(f"{len(scenarios)} scénario(s) valides")
        return 0
    for name in args.scenario or []:
        if name not in scenarios:
            print(f"Scénario inconnu : {name} (--list)")
            return 2
    if not os.access(args.godot, os.X_OK):
        print(f"Godot introuvable : {args.godot}")
        return 2
    if not args.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable")
        return 2
    out = (args.out or Path(tempfile.mkdtemp(prefix="openride-robot-menus-"))).resolve()
    out.mkdir(parents=True, exist_ok=True)
    resultats: list[Resultat] = []
    for name in args.scenario or list(scenarios):
        doc = scenarios[name]
        canaux = [c for c in doc.get("canaux", CANAUX) if not args.canal or c in args.canal]
        if args.rapide:
            canaux = canaux[:1]
        for canal in canaux:
            print(f"== {name} ({canal}) ==", flush=True)
            partie = Partie(args, name, doc, canal, out / name / canal)
            partie.jouer_scenario()
            resultats.append(partie.res)
            r = partie.res
            print(f"   {'RÉUSSI' if r.echecs == 0 else 'ÉCHEC'} : {r.verifs - r.echecs}/{r.verifs} en {r.duree_s:.0f} s", flush=True)
    report = ecrire_rapport(out, resultats)
    ko = [f"{r.scenario} ({r.canal})" for r in resultats if r.echecs]
    print(f"Rapport : {report}")
    print("OK : toutes les parties passent" if not ko else f"ÉCHEC : {', '.join(ko)}")
    return 0 if not ko else 1


if __name__ == "__main__":
    if "--list" in sys.argv or "--check" in sys.argv:
        sys.exit(main())
    sys.path.insert(0, str(REPO / "scripts"))
    from isolation_tests import verrou_suite   # une seule suite de tests ou banc à la fois

    with verrou_suite("menu_robot"):
        code = main()
    sys.exit(code)
