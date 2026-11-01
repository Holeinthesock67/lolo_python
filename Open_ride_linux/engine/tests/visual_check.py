#!/usr/bin/env python3
"""Tests graphiques automatiques de l'engine : vraie scène principale rendue, captures analysées.

Usage : visual_check.py --godot CHEMIN [--configs 1280x720:low,…] [--out DOSSIER] [--native]
                        [--golden DOSSIER [--update-golden]] [--keep]

Pour chaque configuration (résolution et préréglage de qualité), le script lance l'engine avec sa
vraie scène (`main.tscn`) sous Xvfb (OpenGL logiciel de Mesa, moteur Compatibility), face au faux
core de `fake_core.py`, et lui fait parcourir des scènes de séance : attente du core, vue fixe,
mouvement, ERG, fin d'un entraînement, pause, core muet, reprise, erreur. À chaque étape, l'engine (en `--test-mode`)
enregistre l'image affichée et l'état de son HUD (textes, visibilité, rectangles à l'écran) ; le
script vérifie alors :

- les textes du HUD, calculés à partir des valeurs envoyées ;
- la mise en page : éléments visibles dans l'écran, sans chevauchement (HUD, bandeau) ;
- l'image : ni noire ni uniforme, ciel en haut, sol en bas, texte du HUD lisible, bandeau rouge ;
- l'animation : la caméra avance en mouvement, se fige quand le core se tait ;
- le journal de Godot : aucune erreur ni avertissement de script ;
- avec `--golden` : l'écart moyen aux images de référence (`--update-golden` les enregistre).

Sortie : une ligne [OK] / [ÉCHEC] par vérification, un rapport `rapport.html` (captures, mesures,
écarts aux références) et les PNG dans le dossier de sortie. Code de sortie 0 si tout passe, 1 si
une vérification échoue, 2 si Godot ou xvfb-run manque.

`--native` lance l'engine sur l'écran réel avec son moteur de rendu habituel (Forward+ sur la
GTX 1060) au lieu de Xvfb : la fenêtre s'ouvre pendant une minute, sans rien à faire.

Bibliothèque standard seulement (PNG lu et écrit avec zlib).
"""

from __future__ import annotations

import argparse
import base64
import copy
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fake_core import CONTRACT_VERSION, EngineLog, FakeCore, now  # noqa: E402
import hud_lisibilite  # noqa: E402
import image_diff  # noqa: E402
from image_diff import Image, luminance, mean_abs_diff, read_png, write_png  # noqa: E402
import quality_guard  # noqa: E402

ENGINE_DIR = Path(__file__).resolve().parents[1]
CORE_SRC = ENGINE_DIR.parent / "core" / "src"
COMPILER_SRC = ENGINE_DIR.parent / "compiler" / "src"
DEFAULT_CONFIGS = "1280x720:low,1920x1080:high,1024x600:medium"
TAU = 2.0 * math.pi
AVATAR_CADENCE_RPM = 37.0   # cadence des scènes de l'avatar (un tour en 1,62 s)
# Mêmes tolérances que run_engine_tests.sh, plus la synchronisation verticale sous Xvfb.
GODOT_ISSUE = re.compile(r"SCRIPT ERROR|ERROR:|WARNING:")
GODOT_TOLERATED = re.compile(
    r"ObjectDB instances (were )?leaked|resources still in use at exit|[Mm]esh.*(null|nul)|V-Sync|set_use_vsync|"
    r"XOpenIM failed|XCreateIC couldn't create")   # méthode de saisie X du bureau, hors OpenRide
CONTROLS_HINT_PREFIX = "Click : Y = pause"   # hud_view_model.controls_text()
HUD_LABELS = ("power", "target", "speed", "cadence", "hr", "grade", "distance", "time", "erg", "status",
              "erg_title", "erg_target", "erg_remaining", "erg_next", "erg_hist",
              "wind_speed", "wind_level", "wind_verdict", "draft", "bots_line1", "bots_line2",
              "bots_gap1", "bots_jerseys")   # bots_ahead, bots_behind : lignes de bots (lot X22)
BANNER_RGB = (153, 26, 13)        # fond du bandeau (main.tscn : Color(0.6, 0.1, 0.05))
GOLDEN_SSIM = 0.97                # SSIM minimale face aux images de référence (lot X20, image_diff.py)
FREEZE_SSIM = 0.995               # deux captures de suite d'une scène figée (--fige)
FREEZE_T = 30.0                   # instant imposé au décor vivant par --fige (s)
# Éléments du HUD ignorés dans la comparaison aux références : valeurs qui dépendent de l'instant de la capture.
GOLDEN_MASKS = ("status", "distance", "time", "erg_remaining", "chart_sim", "chart_erg", "bots_line1", "bots_line2")
FREEZE_SETTLE_S = 8.0             # --fige : attente du chargement complet des tuiles et du décor avant la vue fixe
ROUTE_TIMEOUT_S = 20.0
SETTLE_S = 2.5                    # tuiles de terrain et lissage de la caméra après un saut de s
PENDING_RETRIES = 15              # scènes de référence : captures reprises (1 s d'écart) tant que des tuiles manquent
SPEED_MPS = 8.0
# Scènes reproductibles (s fixé, rien ne bouge) : les seules comparées aux images de référence.
# Records de la scène « records » : la montée a deux temps sans bonus et un avec bonus, le sprint aucun.
DEMO_RECORDS = {"version": 1, "routes": {"demo": {"climb1": {
    "no_bonus": [{"time_s": 248.07, "date": "2026-10-27 18:05", "avg_power_w": 251.0, "avg_wkg": 3.38},
                 {"time_s": 251.5, "date": "2026-10-26 18:00", "avg_power_w": 240.0, "avg_wkg": 3.2}],
    "bonus": [{"time_s": 239.9, "date": "2026-10-27 18:05", "avg_power_w": 251.0, "avg_wkg": None}]}}}}
GOLDEN_SCENES = ("attente", "vue_fixe", "pause", "erreur", "menu_accueil", "bilan", "pente_0pct", "pente_4pct")
FIXED_S = 1500.0
DEMO_SUMMIT_S = 1500.0             # sommet de `climb1`, seule montée de la couche segments de la démo (T3, T8)
# Listes servies par le faux core aux menus (lot N6) : un parcours « à compiler » non choisissable.
MENU_CATALOG = {
    "routes": [
        # Fiche calculée (lot O15) : chiffres de la carte de détail (présentation des menus, étape 2).
        {"id": "demo", "name": "Démo", "length_m": 4000.0, "is_loop": True, "status": "ready",
         "stats": {"distance_m": 4000.0, "gain_m": 62.0, "max_grade_pct": 4.5, "duration_s": 540.0, "difficulty": 1,
                   "main_climb": {"length_m": 1500.0, "gain_m": 55.0, "avg_grade_pct": 3.7, "category": None}},
         "library": {"description": "Boucle de démonstration.", "region": "", "tags": ["boucle"]}},
        {"id": "vallee", "name": "Vallée de test", "length_m": 32500.0, "is_loop": False, "status": "ready"},
        {"id": "nouveau", "name": "Nouveau GPX", "length_m": 12000.0, "is_loop": False, "status": "to_compile"},
    ],
    # Profil de la scène « erg » : tous les blocs dessinés à leur durée et leur couleur de zone.
    "workouts": [{"id": "sweet_spot", "name": "Sweet spot 3x10", "duration_s": 3600, "selectable": True,
                  "profile": [[600, 0.5, 0.75], [600, 0.92, 0.92], [300, 0.6, 0.6], [600, 0.92, 0.92],
                              [300, 0.6, 0.6], [600, 0.92, 0.92], [600, 0.6, 0.4]],
                  "profile_truncated": False}],
}
MENU_DEVICES = {
    "trainer": {"status": "CONNECTED", "name": "HomeTrainer 0001"},
    "click": [{"status": "CONNECTED", "role": "plus"}, {"status": "LOST", "role": "minus"}],
    "hr": {"status": "CONNECTED", "name": "Ceinture"},
}


# --- mesures sur l'image -------------------------------------------------------------------------

def is_sky(p: tuple[int, int, int]) -> bool:
    """Bleu du ciel procédural (zénith à l'horizon), brume de l'horizon ou nuage (lot P16)."""
    r, g, b = p
    return (b >= 190 and b >= r + 25 and b >= g + 5) or is_cloud(p)


def is_open_sky(p: tuple[int, int, int]) -> bool:
    """Bleu franc du ciel (zénith et haut de l'horizon), sans la route ni la brume grises bleutées : un trou dans
    le terrain sous l'horizon le laisse voir (lot X20)."""
    r, _, b = p
    return b >= 200 and b - r >= 50


def is_cloud(p: tuple[int, int, int]) -> bool:
    """Nuage du ciel de P6 : blanc ou gris très clair, légèrement bleuté."""
    r, g, b = p
    return min(r, g, b) >= 205 and b >= r - 4 and max(r, g, b) - min(r, g, b) <= 40


def stats(img: Image, box=None) -> dict[str, float]:
    n = 0
    s = [0.0, 0.0, 0.0]
    s2 = 0.0
    for p in img.pixels(box, step=4):
        n += 1
        for k in range(3):
            s[k] += p[k]
        lum = luminance(p)
        s2 += lum * lum
    if n == 0:
        return {"n": 0, "mean": (0.0, 0.0, 0.0), "lum": 0.0, "std": 0.0}
    mean = tuple(v / n for v in s)
    lum = luminance(mean)  # type: ignore[arg-type]
    return {"n": n, "mean": mean, "lum": lum, "std": max(0.0, s2 / n - lum * lum) ** 0.5}


def fraction(img: Image, box, pred, step: int = 2) -> float:
    n = hit = 0
    for p in img.pixels(box, step):
        n += 1
        hit += 1 if pred(p) else 0
    return hit / n if n else 0.0


def wrapped_angle(x: float) -> float:
    """Angle ramené dans [−π, π[ (écart entre deux positions du pédalier)."""
    return (x + math.pi) % TAU - math.pi


def rect_box(rect: list[float]) -> tuple[int, int, int, int]:
    x, y, w, h = rect
    return int(x), int(y), int(x + w), int(y + h)


def overlap(a: list[float], b: list[float]) -> float:
    """Aire commune de deux rectangles [x, y, w, h], en pixels."""
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


# Profil de démonstration du hello_ack (lot V6) : avatar réglé, seuils de danseuse par défaut.
# Catalogue de démonstration du message `garage` (lot V7) : un identifiant par `look`, un par emplacement.
# Lot V8 : états, niveaux, prix et noms pour le Garage ; frame_round, wheels_spoked et kit_plain sont choisis.
GARAGE_NAMES = {"frame_round": "Polyvalent", "frame_light": "Léger", "frame_aero": "Profilé", "frame_tt": "Contre-la-montre",
                "wheels_spoked": "Standard", "wheels_spoked_light": "Légères", "wheels_deep": "Profilées", "wheels_disc": "Lenticulaire",
                "kit_plain": "Unie", "kit_stripes": "Rayée", "kit_polka": "À pois", "kit_neon": "Néon",
                "helmet_road": "Route", "socks_white": "Blanches", "glasses_clear": "Claires"}
GARAGE_STATES = {"frame_round": "equipped", "wheels_spoked": "equipped", "kit_plain": "equipped", "helmet_road": "equipped",
                 "socks_white": "equipped", "glasses_clear": "equipped", "frame_light": "owned", "wheels_spoked_light": "owned",
                 "kit_stripes": "owned", "frame_aero": "buyable", "wheels_deep": "buyable", "kit_polka": "buyable",
                 "frame_tt": "locked", "wheels_disc": "locked", "kit_neon": "locked"}
GARAGE_PRICES = {"frame_aero": 150, "wheels_deep": 90, "kit_polka": 400, "frame_tt": 600, "wheels_disc": 500, "kit_neon": 300}
GARAGE_LEVELS = {"frame_light": 2, "wheels_spoked_light": 3, "kit_stripes": 2, "frame_aero": 5, "wheels_deep": 4, "kit_polka": 6,
                 "frame_tt": 20, "wheels_disc": 15, "kit_neon": 12}
AVATAR_GARAGE = [{"id": look, "slot": slot, "name": GARAGE_NAMES[look], "state": GARAGE_STATES[look],
                  "level_required": GARAGE_LEVELS.get(look, 1), "price": GARAGE_PRICES.get(look, 0), "challenge": None,
                  "mass_delta_kg": -1.5 if look == "frame_light" else 0.0, "cda_delta_pct": -4.0 if look == "frame_aero" else 0.0,
                  "terrain": "flat" if look in ("frame_aero", "wheels_deep") else "all", "look": look}
                 for slot, looks in {
                     "frame": ["frame_round", "frame_light", "frame_aero", "frame_tt"],
                     "wheels": ["wheels_spoked", "wheels_spoked_light", "wheels_deep", "wheels_disc"],
                     "helmet": ["helmet_road"], "socks": ["socks_white"], "glasses": ["glasses_clear"],
                     "kit": ["kit_plain", "kit_stripes", "kit_polka", "kit_neon"]}.items() for look in looks]

AVATAR_PROGRESSION = {
    "level": 8, "xp": 4310, "xp_level_start": 3800, "xp_next_level": 5000, "coins": 210,
    "equipped": {"frame": "frame_round", "wheels": "wheels_spoked", "helmet": "helmet_road",
                 "kit": "kit_plain", "socks": "socks_white", "glasses": "glasses_clear"},
    "avatar": {"height": "M", "build": "medium", "skin": 3, "hair": 2, "hair_color": 1, "kit_primary": 4,
               "kit_secondary": 11, "number": 27, "standing_grade_pct": 8, "standing_power_pct": 150},
    "lives": 0,
}


# --- faux core piloté pas à pas -------------------------------------------------------------------

@dataclass
class VisualCore(FakeCore):
    """Faux core dont les trames `state` reprennent les valeurs fixées par chaque scène."""

    fields: dict[str, Any] = field(default_factory=dict)
    speed: float = 0.0            # m/s ; s avance de speed × temps écoulé depuis la dernière scène
    s_origin: float = 0.0
    t_origin: float = field(default_factory=now)

    def set_scene(self, speed: float | None = None, s: float | None = None, **values: Any) -> None:
        with self.lock:
            s_now = self.current_s()
            self.s_origin = s_now if s is None else s
            self.t_origin = now()
            if speed is not None:
                self.speed = speed
            self.fields.update(values)
            self.fields["v"] = self.speed

    def current_s(self) -> float:
        return self.s_origin + self.speed * (now() - self.t_origin)

    def state_msg(self, seq: int | None = None, s: float | None = None) -> dict[str, Any]:
        msg = super().state_msg(seq, s)
        msg.update(self.fields)
        msg["s"] = self.current_s() if s is None else s
        msg["session_state"] = self.fields.get("session_state", "RUNNING")
        return msg

    def send_raw(self, msg: dict[str, Any]) -> None:
        """Envoi même quand le core joue le core muet (messages de test)."""
        self.tx.sendto(json.dumps(msg).encode("utf-8"), ("127.0.0.1", self.state_port))


# --- rapport -------------------------------------------------------------------------------------

@dataclass
class Check:
    config: str
    scene: str
    name: str
    ok: bool
    detail: str


@dataclass
class Capture:
    config: str
    scene: str
    png: Path
    info: dict[str, Any]
    golden_diff: float | None = None      # écart moyen à la référence (information)
    golden_ssim: float | None = None
    diff_png: Path | None = None


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    captures: list[Capture] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def check(self, config: str, scene: str, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append(Check(config, scene, name, ok, detail))
        print(f"[{'OK' if ok else 'ÉCHEC'}] {config} · {scene} · {name}{' : ' + detail if detail else ''}", flush=True)
        return ok

    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]


def _img_tag(path: Path, width: int = 480) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<a href="{html.escape(path.name)}"><img src="data:image/png;base64,{data}" width="{width}"></a>'


def write_html(report: Report, out_dir: Path, elapsed: float) -> Path:
    fails = report.failures()
    verdict = "tous les tests graphiques passent" if not fails else f"{len(fails)} échec(s)"
    parts = [
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Tests graphiques OpenRide</title>",
        "<style>body{font-family:sans-serif;margin:16px;background:#fafafa;color:#222}"
        "table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #ccc;padding:3px 6px;font-size:13px;"
        "vertical-align:top}.ok{color:#176b2c}.ko{color:#b00020;font-weight:bold}"
        ".cap{display:inline-block;margin:6px;padding:6px;background:#fff;border:1px solid #ddd;vertical-align:top}"
        ".cap.ko{border:2px solid #b00020}pre{white-space:pre-wrap;font-size:12px;max-width:480px}</style></head><body>",
        f"<h1>Tests graphiques OpenRide</h1><p><b>Résultat : {html.escape(verdict)}</b> "
        f"({len(report.checks)} vérifications, {elapsed:.0f} s, {time.strftime('%Y-%m-%d %H:%M')})</p>",
    ]
    for note in report.notes:
        parts.append(f"<p>{html.escape(note)}</p>")
    if fails:
        parts.append("<h2>Échecs</h2><table><tr><th>Configuration</th><th>Scène</th><th>Vérification</th><th>Détail</th></tr>")
        for c in fails:
            parts.append(f"<tr><td>{html.escape(c.config)}</td><td>{html.escape(c.scene)}</td>"
                         f"<td>{html.escape(c.name)}</td><td>{html.escape(c.detail)}</td></tr>")
        parts.append("</table>")
    for config in dict.fromkeys(c.config for c in report.checks):
        parts.append(f"<h2>{html.escape(config)}</h2>")
        for cap in [c for c in report.captures if c.config == config]:
            bad = [c for c in report.checks if c.config == config and c.scene == cap.scene and not c.ok]
            info = cap.info
            meta = (f"fps {info.get('fps')} · {info.get('meshes')} maillages · {info.get('draw_calls')} appels de dessin"
                    + (f" · SSIM {cap.golden_ssim:.4f}, écart moyen {cap.golden_diff:.2f} à la référence"
                       if cap.golden_ssim is not None else ""))
            parts.append(f"<div class='cap{' ko' if bad else ''}'><b>{html.escape(cap.scene)}</b><br>"
                         + _img_tag(cap.png) + f"<br><small>{html.escape(meta)}</small>")
            if cap.diff_png is not None:
                parts.append("<br><small>écarts à la référence (blocs en rouge, masques en bleu)</small><br>"
                             + _img_tag(cap.diff_png))
            texts = "\n".join(f"{k}: {w['text']}" for k, w in info.get("widgets", {}).items()
                              if w.get("visible") and w.get("text"))
            parts.append(f"<pre>{html.escape(texts)}</pre></div>")
        parts.append("<table><tr><th>Scène</th><th>Vérification</th><th>Résultat</th><th>Détail</th></tr>")
        for c in [c for c in report.checks if c.config == config]:
            parts.append(f"<tr><td>{html.escape(c.scene)}</td><td>{html.escape(c.name)}</td>"
                         f"<td class='{'ok' if c.ok else 'ko'}'>{'OK' if c.ok else 'ÉCHEC'}</td>"
                         f"<td>{html.escape(c.detail)}</td></tr>")
        parts.append("</table>")
    parts.append("</body></html>")
    path = out_dir / "rapport.html"
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


# --- une configuration ---------------------------------------------------------------------------

def free_udp_ports(n: int) -> list[int]:
    import socket
    socks = []
    for _ in range(n):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        socks.append(s)
    ports = [s.getsockname()[1] for s in socks]
    for s in socks:
        s.close()
    return ports


@dataclass
class Session:
    name: str
    width: int
    height: int
    core: VisualCore
    out_dir: Path
    report: Report
    golden_dir: Path | None       # <références>/<moteur>/<préréglage>
    update_golden: set[str] | None   # scènes dont la référence est réécrite ; {"*"} : toutes
    freeze_t: float | None = None    # --fige : instant imposé au décor
    lisibilite: bool = False      # --lisibilite : hauteur et contraste des textes du HUD (lot X22)

    def check(self, scene: str, name: str, ok: bool, detail: str = "") -> bool:
        return self.report.check(self.name, scene, name, ok, detail)

    def capture(self, scene: str) -> tuple[Image, dict[str, Any]] | None:
        png = self.out_dir / f"{self.name}_{scene}.png"
        # Scène de référence : capture reprise tant que des tuiles voulues manquent (`streaming_pending`, comme le
        # tour visuel X21). Une attente fixe ne suffisait pas : `vue_fixe` en low sur le PC (31 octobre) sortait
        # sans terrain ni arbres, sol brun et personnage en l'air, et la SSIM variait d'un passage à l'autre.
        # Même reprise tant que le rappel des commandes du départ (10 s) est affiché : présent sur une capture et pas
        # sur l'autre, il faisait tomber `vue_fixe` à SSIM 0,96 face à sa référence (PC, 1er novembre).
        tries = PENDING_RETRIES if scene in GOLDEN_SCENES else 1
        for attempt in range(tries):
            mark = self.core.log.mark()
            self.core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "screenshot",
                                "path": str(png), "tag": scene})
            hit = self.core.log.wait_for(r"^screenshot (\{.*\})$", 10.0, mark)
            if hit is None or not capture_unsettled(json.loads(hit[1].group(1))):
                break
            if attempt < tries - 1:
                time.sleep(1.0)
        if not self.check(scene, "capture enregistrée", hit is not None and png.exists(),
                          "" if hit else "aucune ligne « screenshot » dans le journal de l'engine"):
            return None
        info = json.loads(hit[1].group(1))
        if scene in GOLDEN_SCENES:
            pending = int(info.get("streaming_pending", 0))
            self.check(scene, "tuiles du terrain toutes affichées", pending == 0,
                       f"{pending} tuile(s) encore en attente après {tries} capture(s)")
        img = read_png(png)
        cap = Capture(self.name, scene, png, info)
        self.report.captures.append(cap)
        self.check(scene, "taille de l'image", (img.width, img.height) == (self.width, self.height),
                   f"{img.width}x{img.height}, attendu {self.width}x{self.height}")
        self._golden(cap, img)
        if self.lisibilite:
            for name, ok, detail in hud_lisibilite.readability_checks(img, info):
                self.check(scene, name, ok, detail)
        return img, info

    def _golden(self, cap: Capture, img: Image) -> None:
        """Comparaison à l'image de référence de la scène (vignette de 640 pixels de large, lot X20) : SSIM par
        blocs sur la luminance, éléments du HUD de GOLDEN_MASKS ignorés."""
        if self.golden_dir is None or cap.scene not in GOLDEN_SCENES:
            return
        ref_path = self.golden_dir / f"{cap.scene}.png"
        if self.update_golden and ("*" in self.update_golden or cap.scene in self.update_golden):
            self.golden_dir.mkdir(parents=True, exist_ok=True)
            write_png(ref_path, image_diff.vignette(img))
            return
        if not ref_path.exists():
            self.check(cap.scene, "image de référence", False, f"{ref_path} absente (lancer avec --update-golden)")
            return
        ref = read_png(ref_path)
        if not image_diff.same_format(ref, img):
            self.check(cap.scene, "écart à l'image de référence", False,
                       f"référence {ref.width}x{ref.height}, capture {img.width}x{img.height} : autre format")
            return
        masks = self.golden_masks(cap.info, img.width, ref.width)
        res = image_diff.compare(ref, img, masks)
        small = image_diff.resize(img, ref.width, ref.height)
        cap.golden_ssim, cap.golden_diff = res.score, mean_abs_diff(ref, small)
        ok = res.score >= GOLDEN_SSIM
        if not ok:
            cap.diff_png = self.out_dir / f"{self.name}_{cap.scene}_ecart.png"
            write_png(cap.diff_png, image_diff.ssim_map(ref, res, masks))
        self.check(cap.scene, "écart à l'image de référence", ok,
                   f"SSIM {res.score:.4f} (seuil {GOLDEN_SSIM}), pire bloc {res.worst:.2f}, écart moyen "
                   f"{cap.golden_diff:.2f} niveaux, {res.masked} blocs masqués")

    @staticmethod
    def golden_masks(info: dict[str, Any], width: int, ref_width: int) -> list[tuple[int, int, int, int]]:
        """Rectangles des éléments de GOLDEN_MASKS affichés, à l'échelle d'une image de `ref_width` pixels de large."""
        k = ref_width / width
        widgets = info.get("widgets", {})
        return [image_diff.scale_box(rect_box(widgets[key]["rect"]), k, k) for key in GOLDEN_MASKS
                if widgets.get(key, {}).get("visible")]

    # --- vérifications communes ---

    def check_texts(self, scene: str, info: dict[str, Any], expected: dict[str, str], contains: bool = False) -> None:
        w = info["widgets"]
        for key, text in expected.items():
            got = w[key]["text"]
            ok = (text in got) if contains else (got == text)
            self.check(scene, f"texte {key}", ok and w[key]["visible"], f"« {got} »" + ("" if ok else f", attendu « {text} »"))

    def check_layout(self, scene: str, info: dict[str, Any]) -> None:
        w = info["widgets"]
        vis = {k: v for k, v in w.items() if v["visible"]}
        outside = [k for k, v in vis.items() if v["rect"][0] < -0.5 or v["rect"][1] < -0.5
                   or v["rect"][0] + v["rect"][2] > self.width + 0.5 or v["rect"][1] + v["rect"][3] > self.height + 0.5]
        self.check(scene, "éléments dans l'écran", not outside, "hors écran : " + ", ".join(outside) if outside else
                   f"{len(vis)} éléments visibles")
        labels = [k for k in HUD_LABELS if k in vis]
        pairs = [f"{a}/{b}" for i, a in enumerate(labels) for b in labels[i + 1:]
                 if overlap(vis[a]["rect"], vis[b]["rect"]) > 1.0]
        self.check(scene, "lignes du HUD sans chevauchement", not pairs, ", ".join(pairs))
        # Panneaux (colonnes, vent, abri, blocs segment et bonus, encart des bots, profil) : lot X22.
        for name, ok, detail in (hud_lisibilite.panel_checks(info, self.width, self.height)
                                 + hud_lisibilite.column_checks(info)):
            self.check(scene, name, ok, detail)
        if "banner" in vis:
            hit = [k for k in labels + ["panel"] if k in vis and overlap(vis[k]["rect"], vis["banner"]["rect"]) > 1.0]
            self.check(scene, "bandeau sans chevauchement du HUD", not hit, "recouvre : " + ", ".join(hit) if hit else "")

    def check_hud_pixels(self, scene: str, img: Image, info: dict[str, Any]) -> None:
        w = info["widgets"]
        for key in ("power", "status"):
            if not w[key]["visible"]:
                continue
            frac = fraction(img, rect_box(w[key]["rect"]), lambda p: luminance(p) > 0.75, step=1)
            self.check(scene, f"texte {key} dessiné (pixels clairs)", 0.01 <= frac <= 0.6, f"{frac:.1%} de pixels clairs")

    def check_world(self, scene: str, img: Image, info: dict[str, Any]) -> None:
        """Image non noire, non uniforme ; ciel en haut à droite (hors HUD), sol en bas."""
        whole = stats(img)
        self.check(scene, "image ni noire ni uniforme", whole["lum"] > 0.05 and whole["std"] > 0.02,
                   f"luminance {whole['lum']:.2f}, écart type {whole['std']:.3f}")
        # Ciel au centre, sous le panneau central du HUD (et sous le bandeau s'il est affiché) : les
        # panneaux latéraux du HUD (lot E3) couvrent les coins hauts.
        below = info["widgets"]["panel"]["rect"]
        y0 = below[1] + below[3] + 4
        banner = info["widgets"]["banner"]
        if banner["visible"]:
            y0 = max(y0, banner["rect"][1] + banner["rect"][3] + 4)
        top = (self.width * 0.35, y0, self.width * 0.65, y0 + self.height * 0.06)
        sky = fraction(img, top, is_sky)
        self.check(scene, "ciel en haut de l'image", sky >= 0.8, f"{sky:.0%} de pixels de ciel")
        bottom = (0, self.height * 0.75, self.width, self.height)
        ground = 1.0 - fraction(img, bottom, is_sky)
        self.check(scene, "sol en bas de l'image", ground >= 0.8, f"{ground:.0%} de pixels hors ciel")
        self.check(scene, "maillages affichés", info["meshes"] > 0, f"{info['meshes']} maillages visibles")

    def check_banner(self, scene: str, img: Image, info: dict[str, Any], text: str | None) -> None:
        b = info["widgets"]["banner"]
        if text is None:
            # Le rappel des commandes du départ de séance (main.gd, 10 s) n'est pas une alerte.
            alert = b["visible"] and not b["text"].startswith(CONTROLS_HINT_PREFIX)
            self.check(scene, "bandeau caché (hors rappel des commandes)", not alert,
                       f"« {b['text']} »" if b["visible"] else "")
            return
        self.check(scene, "bandeau affiché", b["visible"] and text in b["text"], f"« {b['text']} »")
        if b["visible"]:
            def red(p):
                return abs(p[0] - BANNER_RGB[0]) < 50 and p[1] < 80 and p[2] < 70
            frac = fraction(img, rect_box(b["rect"]), red, step=1)
            self.check(scene, "bandeau rouge dessiné", frac >= 0.4, f"{frac:.0%} de pixels rouges")


## Écart moyen (niveaux sur 255) du sol entre deux captures au-delà duquel le sol défile. En dessous, l'image
## est figée : seuls bougent le décor vivant (touffes et vagues de vent sur l'herbe) et le bruit de rendu d'une
## image à l'autre sur le grain fin de la route et du terrain (Y11), environ 0,1 niveau ; un défilement à
## 8 m/s donne environ 3 niveaux.
GROUND_SCROLL_LEVEL = 0.2


def capture_unsettled(info: dict[str, Any]) -> bool:
    """Capture d'une scène de référence à reprendre : tuiles du terrain en attente, ou rappel des commandes du
    départ de séance encore affiché (il s'efface seul au bout de 10 s)."""
    if int(info.get("streaming_pending", 0)) > 0:
        return True
    b = info.get("widgets", {}).get("banner", {})
    return bool(b.get("visible")) and str(b.get("text", "")).startswith(CONTROLS_HINT_PREFIX)


def ground_box(s: Session, info: dict[str, Any]) -> tuple[int, int, int, int]:
    """Bas de l'image hors HUD : là où la route et le terrain défilent."""
    return 0, int(s.height * 0.6), s.width, s.height


def run_config(config: str, args, routes_dir: Path, out_dir: Path, report: Report, scenes=None) -> None:
    """Lance l'engine à une configuration et joue `scenes(session)` (les scènes de ce fichier par défaut ;
    hud_galerie.py passe les siennes)."""
    size, _, quality = config.partition(":")
    quality = quality or "low"
    width, height = (int(v) for v in size.lower().split("x"))
    v_grade = getattr(args, "visual_grade", 1.0)
    name = f"{width}x{height}_{quality}" if v_grade == 1.0 else f"{width}x{height}_{quality}_k{v_grade}"
    state_port, cmd_port = free_udp_ports(2)
    engine_log = out_dir / f"{name}_engine.log"
    engine_log.write_text("")
    core = VisualCore(state_port, cmd_port, EngineLog(engine_log))
    core.progression = copy.deepcopy(AVATAR_PROGRESSION)   # le faux core les modifie (achats, choix)
    core.garage = copy.deepcopy(AVATAR_GARAGE)
    core.start()
    cmd = [args.godot, "--path", str(ENGINE_DIR), "--resolution", f"{width}x{height}", "--audio-driver", "Dummy"]
    if not args.native:
        cmd = ["xvfb-run", "-a", "-s", f"-screen 0 {width}x{height}x24"] + cmd + [
            "--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
    v_grade = getattr(args, "visual_grade", 1.0)
    cmd += ["--", f"--ipc-state-port={state_port}", f"--ipc-cmd-port={cmd_port}", f"--routes-dir={routes_dir}",
            "--test-mode", f"--quality={quality}", f"--visual-grade={v_grade}", f"--living={args.decor_vivant}",
            "--camera=subjective"]   # les scènes d'avant le lot V12 supposent la caméra subjective
    preset_dir = quality + ("" if args.decor_vivant == "on" else "_sans_vivant") + ("" if v_grade == 1.0 else f"_k{v_grade}")
    gold = Path(args.golden) / ("natif" if args.native else "xvfb") / preset_dir if args.golden else None
    update = {v.strip() for v in args.update_golden.split(",") if v.strip()} if args.update_golden else None
    s = Session(name, width, height, core, out_dir, report, gold, update, args.fige, args.lisibilite)
    print(f"== {name} ==", flush=True)
    records_file = out_dir / f"{name}_records.json"   # records de démonstration, pas ceux du propriétaire
    records_file.write_text(json.dumps(DEMO_RECORDS), encoding="utf-8")
    with engine_log.open("w") as log_fh:
        proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, start_new_session=True,
                                env={**os.environ, "OPENRIDE_RECORDS_FILE": str(records_file)})
    try:
        (scenes or _scenes)(s)
    finally:
        core.stop()
        try:
            os.killpg(proc.pid, 15)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, 9)
            except ProcessLookupError:
                pass
    issues = [ln for ln in engine_log.read_text(errors="replace").splitlines()
              if GODOT_ISSUE.search(ln) and not GODOT_TOLERATED.search(ln)]
    s.check("journal", "aucune erreur ni avertissement Godot", not issues, " | ".join(issues[:5]))
    # Qualité réellement appliquée (lot X32) : le faux core ne doit pas la ramener à une autre valeur.
    q_ok, q_msg = quality_guard.check(engine_log.read_text(errors="replace"), quality)
    s.check("journal", "qualité réellement appliquée", bool(q_ok), q_msg)


def _scenes(s: Session) -> None:
    core = s.core
    t0 = now()
    while now() - t0 < 20.0 and "IpcClient attaché" not in core.log.path.read_text(errors="replace"):
        time.sleep(0.1)
    if s.freeze_t is not None:   # avant toute trame : le vent du thème et le décor sont posés à l'instant imposé
        core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "freeze", "t": s.freeze_t})
    time.sleep(1.5)

    # 1. Attente du core : aucun hello_ack, aucune trame.
    shot = s.capture("attente")
    if shot:
        img, info = shot
        s.check_texts("attente", info, {"status": "ÉTAT: en attente du core…", "power": "—"})
        s.check_layout("attente", info)
        st = stats(img)
        s.check("attente", "image affichée (ni noire ni uniforme)", st["lum"] > 0.05, f"luminance {st['lum']:.2f}")

    # 2. Vue fixe : séance à l'arrêt sur le parcours, valeurs connues (image comparable aux références).
    core.set_scene(speed=0.0, s=FIXED_S, session_state="RUNNING", power=250.0, power_3s=248.0, cadence=90.0, hr=142,
                   grade=4.5, grade_sent=4.5, gear=12, gears_total=24, mode="SIM", erg=None, pause_reason=None,
                   trainer_status="CONNECTED", input_status="CONNECTED")
    core.auto_hello_ack = True
    core.catalog_data = MENU_CATALOG
    core.streaming = True
    loaded = core.log.wait_for(r"^route_loaded id=demo", ROUTE_TIMEOUT_S)
    s.check("vue_fixe", "parcours demo chargé", loaded is not None, loaded[1].string if loaded else "aucun route_loaded")
    time.sleep(SETTLE_S if s.freeze_t is None else FREEZE_SETTLE_S)
    shot = s.capture("vue_fixe")
    if shot:
        img, info = shot
        s.check_texts("vue_fixe", info, {
            "power": "248", "speed": "0.0", "cadence": "90", "hr": "142", "grade": "+4.5 %", "distance": "1.50 km",
            "status": "ÉTAT: RUNNING | TRAINER: CONNECTED | ENTRÉE: CONNECTED"})
        s.check("vue_fixe", "ligne ERG cachée en SIM", not info["widgets"]["erg"]["visible"])
        s.check("vue_fixe", "cible ERG cachée en SIM", not info["widgets"]["target"]["visible"])
        s.check("vue_fixe", "bandeau ERG caché en SIM", not info["widgets"]["erg_hist"]["visible"])
        s.check("vue_fixe", "menu caché pendant la séance", not info["widgets"]["menu"]["visible"])
        s.check_banner("vue_fixe", img, info, None)
        s.check_layout("vue_fixe", info)
        s.check_hud_pixels("vue_fixe", img, info)
        s.check_world("vue_fixe", img, info)
        if s.freeze_t is not None:
            # Scène figée (lot X20) : la même vue, 2 s plus tard, donne la même image (hors chronomètre et bandeau
            # de l'aide des commandes, qui s'efface au bout de quelques secondes).
            time.sleep(2.0)
            again = s.capture("vue_fixe_figee")
            if again:
                a, b = image_diff.vignette(img), image_diff.vignette(again[0])
                k = a.width / img.width
                masks = s.golden_masks(again[1], img.width, a.width) + [
                    image_diff.scale_box(rect_box(i["widgets"]["banner"]["rect"]), k, k)
                    for i in (info, again[1]) if i["widgets"]["banner"]["visible"]]
                res = image_diff.ssim(a, b, masks)
                s.check("vue_fixe_figee", "scène figée : image identique 2 s plus tard", res.score >= FREEZE_SSIM,
                        f"SSIM {res.score:.4f} (seuil {FREEZE_SSIM}), pire bloc {res.worst:.2f}")

    # 2 bis. Nuages (lot P16) : ciel de P6 du thème par défaut (couverture 0,3), pixels clairs au-dessus
    # de l'horizon, entre les panneaux du HUD.
    shot = s.capture("nuages")
    if shot:
        img, info = shot
        below = info["widgets"]["panel"]["rect"]
        y0 = below[1] + below[3] + 4
        sky_box = (s.width * 0.30, y0, s.width * 0.70, s.height * 0.42)
        frac = fraction(img, sky_box, is_cloud, step=2)
        s.check("nuages", "nuages dessinés au-dessus de l'horizon", frac >= 0.005, f"{frac:.1%} de pixels de nuage")

    # 3. Mouvement : à 8 m/s, la route défile et la distance avance.
    core.set_scene(speed=SPEED_MPS)
    time.sleep(1.0)
    a = s.capture("mouvement_1")
    time.sleep(1.0)
    b = s.capture("mouvement_2")
    if a and b:
        (img_a, info_a), (img_b, info_b) = a, b
        s.check_texts("mouvement_2", info_b, {"speed": "28.8"})
        s.check("mouvement_2", "distance affichée qui avance",
                info_a["widgets"]["distance"]["text"] != info_b["widgets"]["distance"]["text"],
                f"{info_a['widgets']['distance']['text']} → {info_b['widgets']['distance']['text']}")
        moved = sum((p - q) ** 2 for p, q in zip(info_a["camera"], info_b["camera"])) ** 0.5
        dt = (info_b["ticks_ms"] - info_a["ticks_ms"]) / 1000.0
        speed = moved / dt if dt > 0 else 0.0
        s.check("mouvement_2", "caméra à la vitesse du core (8 m/s ± 25 %)", abs(speed - SPEED_MPS) <= 0.25 * SPEED_MPS,
                f"{moved:.1f} m en {dt:.2f} s, soit {speed:.1f} m/s")
        d = mean_abs_diff(img_a, img_b, ground_box(s, info_b))
        s.check("mouvement_2", "le sol défile à l'image", d >= GROUND_SCROLL_LEVEL, f"écart moyen {d:.2f} niveaux")
        s.check_world("mouvement_2", img_b, info_b)

    # 3 bis. Vent (lot P16) : vent de face de 25 km/h dans la trame, indicateur sous le panneau de gauche.
    # La route va vers l'est-sud-est (cap de 100° vers 1,5 km de la démo) : vent venant de 100°, de face.
    core.set_scene(wind={"speed_mps": 26.0 / 3.6, "from_deg": 100.0, "gust": 0.0, "head_mps": 26.0 / 3.6, "grade_pct": 1.2})
    time.sleep(2.0)
    shot = s.capture("vent")
    if shot:
        img, info = shot
        w = info["widgets"]
        s.check("vent", "indicateur du vent affiché", w["wind"]["visible"] and w["wind_speed"]["visible"])
        s.check_texts("vent", info, {"wind_verdict": "Vent défavorable", "wind_level": "fort"})
        s.check_texts("vent", info, {"wind_speed": "km/h"}, contains=True)
        s.check_layout("vent", info)
        def red(p):
            return p[0] > 150 and p[1] < 90 and p[2] < 80
        frac = fraction(img, rect_box(w["wind_verdict"]["rect"]), red, step=1)
        s.check("vent", "pastille « Vent défavorable » en rouge", frac >= 0.3, f"{frac:.0%} de pixels rouges")
        left = w["power"]["rect"]
        s.check("vent", "indicateur sous la colonne de gauche", w["wind"]["rect"][0] < s.width * 0.35
                and w["wind"]["rect"][1] > left[1] + left[3], f"rectangle {w['wind']['rect']}")
    # 3 ter. Abri (lot P17) : aspiration de 13,5 % derrière un bot, « Abri 30 % » sous l'indicateur du vent.
    core.set_scene(draft=0.135)
    time.sleep(1.0)
    shot = s.capture("abri")
    if shot:
        img, info = shot
        w = info["widgets"]
        s.check("abri", "pastille de l'abri affichée", w["draft"]["visible"])
        s.check_texts("abri", info, {"draft": "Abri 30 %"})
        s.check_layout("abri", info)
        s.check("abri", "abri sous l'indicateur du vent", w["draft"]["rect"][1] >= w["wind"]["rect"][1] + w["wind"]["rect"][3],
                f"rectangle {w['draft']['rect']}")
    core.set_scene(wind=None, draft=None)
    time.sleep(2.5)

    # 3 ter bis. Bots (lot O7) : un bot à 20 m devant, un fantôme à 60 m derrière ; silhouettes sur la route,
    # encart du HUD sous le panneau de droite (au plus 5 lignes), sans chevauchement ; lot T15 : voisins
    # immédiats (`bot_ahead`, `bot_behind`) et porteurs des maillots (`jerseys`).
    # La caméra ne recule jamais pendant une séance (camera_follow.gd) : les bots se placent autour de la
    # position actuelle du cycliste, sans revenir à FIXED_S.
    s_now = core.current_s()
    core.set_scene(speed=0.0, bots=[
        {"id": "bot1", "name": "Bot 250 W", "s": s_now + 20.0, "v": 0.0, "kind": "constant"},
        {"id": "ghost", "name": "Fantôme du 26/10", "s": s_now - 60.0, "v": 0.0, "kind": "ghost"}],
        bot_ahead="bot1", bot_behind="ghost", jerseys={"sprint": "me", "kom": "bot1"})
    time.sleep(SETTLE_S)
    shot = s.capture("bots")
    if shot:
        img, info = shot
        w = info["widgets"]
        s.check("bots", "encart des bots affiché", w["bots_panel"]["visible"] and w["bots_line1"]["visible"]
                and w["bots_line2"]["visible"])
        s.check_texts("bots", info, {"bots_line1": "Bot 250 W", "bots_line2": "Fantôme du 26/10"}, contains=True)
        s.check_texts("bots", info, {"bots_ahead": "Bot 250 W", "bots_behind": "Fantôme du 26/10",
                                     "bots_jerseys": "Vert : toi · Pois : Bot 250 W"}, contains=True)
        s.check("bots", "encart sous le panneau de droite", w["bots_panel"]["rect"][1] >= w["panel"]["rect"][1],
                f"rectangle {w['bots_panel']['rect']}")
        b = info.get("bots", {})
        s.check("bots", "bot devant visible dans le champ de la caméra", b.get("shown") == 2 and b.get("in_view", 0) >= 1,
                f"{b}")
        s.check_layout("bots", info)
    _draft_gauge_scene(s)
    core.set_scene(speed=SPEED_MPS, bots=None, bot_ahead=None, bot_behind=None, jerseys=None, draft=None, draft_bot=None)
    time.sleep(SETTLE_S)
    shot = s.capture("sans_bot")
    if shot:
        img, info = shot
        s.check("sans_bot", "sans bot : encart caché, aucune silhouette",
                not info["widgets"]["bots_panel"]["visible"] and info.get("bots", {}).get("shown") == 0,
                f"{info.get('bots')}")
    time.sleep(1.0)
    _bots_segment_bonus_scene(s)

    # 3 ter ter. Avatar (lot V6), vu par la caméra de contrôle derrière lui (la caméra du jeu reste
    # subjective, où l'avatar est caché) : visible, jambes à des angles différents sur deux captures
    # espacées (cadence de 37 tr/min, angle attendu tiré du temps entre les captures), assis à plat, en danseuse sur une pente de 10 %.
    shot = s.capture("avatar_subjectif")
    if shot:
        s.check("avatar_subjectif", "avatar caché en vue subjective", not shot[1].get("avatar", {}).get("visible", True),
                f"{shot[1].get('avatar')}")
    core.set_scene(speed=0.0, grade=0.0, grade_sent=0.0, power=200.0, power_3s=200.0, cadence=AVATAR_CADENCE_RPM)
    core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "avatar_camera", "view": "follow"})
    time.sleep(1.0)
    a = s.capture("avatar_assis")
    # Entre deux captures, le pédalier avance de ω·Δt : Δt dépend du temps d'écriture des PNG (plus long sur
    # le PC en fenêtre réelle) et peut tomber près d'un tour entier, d'où deux images au même angle. Δt est lu
    # dans les captures (`ticks_ms`) : tant que l'avance attendue est à moins de 0,8 rad d'un tour entier,
    # nouvelle capture après un demi-tour d'attente (phase décalée de π ; trois essais au plus).
    omega = AVATAR_CADENCE_RPM / 60.0 * TAU
    b, expected = None, 0.0
    for attempt in range(3):
        time.sleep(0.37 if attempt == 0 else math.pi / omega)
        b = s.capture("avatar_assis_2")
        if not (a and b):
            break
        expected = wrapped_angle(omega * (b[1].get("ticks_ms", 0) - a[1].get("ticks_ms", 0)) / 1000.0)
        if abs(expected) >= 0.8:
            break
    if a and b:
        (img_a, info_a), (img_b, info_b) = a, b
        av_a, av_b = info_a.get("avatar", {}), info_b.get("avatar", {})
        s.check("avatar_assis", "avatar visible dans le champ de la caméra de contrôle",
                av_a.get("visible") and av_a.get("on_screen"), f"{av_a}")
        s.check("avatar_assis", "avatar assis à plat", av_a.get("standing") is False)
        s.check("avatar_assis", "avatar entier (niveau de détail 0)", av_a.get("lod") == 0 and av_a.get("triangles", 0) > 1000,
                f"{av_a.get('triangles')} triangles")
        turn = abs(wrapped_angle(av_b.get("crank", 0.0) - av_a.get("crank", 0.0)))
        s.check("avatar_assis_2", "pédalier à un autre angle d'une capture à l'autre", turn > 0.15,
                f"{turn:.2f} rad d'écart, {abs(expected):.2f} rad attendus d'après le temps entre les captures")
        box = (s.width * 0.30, s.height * 0.25, s.width * 0.70, s.height * 0.95)
        d = mean_abs_diff(img_a, img_b, box)
        s.check("avatar_assis_2", "les jambes changent l'image", d >= 0.2, f"écart moyen {d:.2f} niveaux")
        s.check_world("avatar_assis", img_a, info_a)
    core.set_scene(grade=10.0, grade_sent=10.0)
    time.sleep(1.5)
    shot = s.capture("avatar_danseuse")
    if shot:
        av = shot[1].get("avatar", {})
        s.check("avatar_danseuse", "en danseuse sur 10 % de pente", av.get("standing") is True and av.get("on_screen"), f"{av}")
    # Équipement (lot V7) : quatre cadres et quatre roues se distinguent à l'image (caméra de côté) ;
    # traînées d'air à 50 km/h, absentes à 40 km/h.
    core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "avatar_camera", "view": "side"})
    core.set_scene(grade=0.0, grade_sent=0.0, power=200.0, power_3s=200.0, cadence=37.0)

    def equip(**ids: str) -> None:
        core.send({"type": "progression", "v": CONTRACT_VERSION, "request_cmd_id": 0, "level": 9, "xp": 0, "xp_next_level": 1,
                   "coins": 0, "equipped": ids, "avatar": AVATAR_PROGRESSION["avatar"], "lives": 3})
        time.sleep(0.8)

    shots: dict[str, Any] = {}
    box = (s.width * 0.20, s.height * 0.20, s.width * 0.80, s.height * 0.95)
    for group, slot, looks in (("cadre", "frame", ["frame_round", "frame_light", "frame_aero", "frame_tt"]),
                               ("roues", "wheels", ["wheels_spoked", "wheels_spoked_light", "wheels_deep", "wheels_disc"])):
        for look in looks:
            equip(**{slot: look})
            shot = s.capture(f"avatar_{look}")
            if shot:
                shots[look] = shot
                s.check(f"avatar_{look}", f"{look} : équipement appliqué", shot[1].get("avatar", {}).get("looks", {}).get(slot) == look,
                        f"{shot[1].get('avatar', {}).get('looks')}")
        names = [n for n in looks if n in shots]
        for i, a_name in enumerate(names):
            for b_name in names[i + 1:]:
                d = mean_abs_diff(shots[a_name][0], shots[b_name][0], box)
                s.check(f"avatar_{b_name}", f"{group} : {a_name} et {b_name} se distinguent", d >= 0.15, f"écart moyen {d:.2f} niveaux")
    equip(kit="kit_stripes")
    core.set_scene(speed=40.0 / 3.6)
    time.sleep(0.8)
    shot = s.capture("avatar_40kmh")
    if shot:
        s.check("avatar_40kmh", "pas de traînées d'air à 40 km/h", shot[1].get("avatar", {}).get("streaks") is False, f"{shot[1].get('avatar')}")
    core.set_scene(speed=50.0 / 3.6)
    time.sleep(0.8)
    shot = s.capture("avatar_50kmh")
    if shot:
        s.check("avatar_50kmh", "traînées d'air visibles à 50 km/h", shot[1].get("avatar", {}).get("streaks") is True, f"{shot[1].get('avatar')}")
    equip()
    core.set_scene(speed=0.0)
    core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "avatar_camera", "view": ""})
    core.set_scene(grade=0.0, grade_sent=0.0, power=250.0, power_3s=248.0, cadence=90.0)
    time.sleep(1.0)

    _camera_scenes(s)

    # 3 quater. Pluie (lot P17) : météo imposée, particules autour de la caméra et chaussée mouillée.
    core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "weather",
                   "weather": {"kind": "rain", "intensity": 0.8, "morning_mist": False}})
    time.sleep(1.5)
    shot = s.capture("pluie")
    if shot:
        img, info = shot
        dec = info.get("decor", {})
        s.check("pluie", "particules de pluie actives", dec.get("particles", 0) > 0, f"{dec.get('particles', 0)} particules")
        s.check("pluie", "chaussée mouillée", dec.get("wetness", 0.0) > 0.5, f"wetness {dec.get('wetness', 0.0):.2f}")
        s.check_layout("pluie", info)
        s.check_world("pluie", img, info)
    core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "weather", "weather": {"kind": "clear"}})

    # 3 quinquies. Col (lot P17) : arrêt à 25 m du panneau du sommet de la démo : panneau lisible
    # (lettres prévues pour 30 m). Depuis T8, le décor suit la couche `segments` du parcours : la seule
    # montée de la démo est `climb1` (0 à 1 500 m, détectée par le core), trop courte pour les
    # spectateurs de P15 (moins de 3 km) : aucun spectateur attendu.
    # Sommet derrière la position courante : passage par READY (en RUNNING, la caméra ne recule jamais).
    s_back = core.current_s()
    core.set_scene(speed=0.0, s=DEMO_SUMMIT_S - 25.0, session_state="READY")
    time.sleep(SETTLE_S)
    core.set_scene(speed=0.0, s=DEMO_SUMMIT_S - 25.0, session_state="RUNNING")
    time.sleep(1.0)
    shot = s.capture("col")
    if shot:
        img, info = shot
        dec = info.get("decor", {})
        sign = dec.get("sign", {})
        s.check("col", "panneau du sommet devant la caméra", "Sommet" in str(sign.get("text", "")),
                f"« {str(sign.get('text', '')).replace(chr(10), ' / ')} » à {float(sign.get('dist_m', 0.0)):.0f} m")
        s.check("col", "lettres du panneau lisibles", float(sign.get("letter_px_720", 0.0)) >= 6.0,
                f"{float(sign.get('letter_px_720', 0.0)):.1f} px pour 720 lignes")
        s.check("col", "aucun spectateur sur une montée de moins de 3 km", dec.get("spectators", 0) == 0,
                f"{dec.get('spectators', 0)} spectateurs")
        s.check_layout("col", info)
        s.check_world("col", img, info)
    core.set_scene(speed=SPEED_MPS, s=s_back)
    time.sleep(2.0)

    # 4. ERG : cible dans la ligne de puissance, bandeau et histogramme des blocs (lot N7).
    core.set_scene(speed=7.0, mode="ERG", erg={
        "workout_name": "Sweet spot 3x10", "block_index": 2, "block_count": 7, "block_type": "interval_on",
        "block_remaining_s": 95.0, "block_total_s": 600.0, "target_w": 230.0, "next_target_w": 150.0,
        "bias_pct": 100, "paused": False})
    time.sleep(1.0)
    shot = s.capture("erg")
    if shot:
        img, info = shot
        s.check_texts("erg", info, {"target": "230 W", "erg_title": "Sweet spot 3x10 — Bloc 2 / 7 · Effort",
                                    "erg_target": "230 W", "erg_next": "Ensuite : 150 W"}, contains=True)
        narrow = [k for k in ("erg_title", "erg_target", "erg_remaining", "erg_next") if info["widgets"][k]["rect"][2] < 20]
        s.check("erg", "textes du bandeau ERG de largeur lisible", not narrow, "trop étroits : " + ", ".join(narrow))
        s.check("erg", "ligne ERG du panneau central laissée au bandeau", not info["widgets"]["erg"]["visible"])
        s.check("erg", "profil d'altitude caché en ERG", not info["widgets"]["profile"]["visible"])
        s.check_layout("erg", info)
        s.check_hud_pixels("erg", img, info)
        hist = info["widgets"]["erg_hist"]
        s.check("erg", "histogramme des blocs affiché", hist["visible"] and hist["rect"][2] >= 0.8 * s.width
                and hist["rect"][3] >= 40 * info["ui_scale"] and hist["rect"][1] + hist["rect"][3] <= s.height - 10 * info["ui_scale"],
                f"rectangle {hist['rect']}")
        if hist["visible"]:
            # Case du bloc en cours (2 sur 7) colorée en zone 4 (230 W pour une FTP de 250 W) : jaune.
            def yellow(p):
                return p[0] > 150 and p[1] > 120 and p[2] < 110
            frac = fraction(img, rect_box(hist["rect"]), yellow, step=2)
            s.check("erg", "bloc en cours dessiné en couleur de zone", frac >= 0.02, f"{frac:.1%} de pixels jaunes")
            # Blocs à venir (4 et 6, zone 4) visibles dès maintenant : du jaune hors du bloc en cours.
            x0, y0, x1, y1 = rect_box(hist["rect"])
            later = (x0 + (x1 - x0) * 0.55, y0, x1, y1)
            frac = fraction(img, later, yellow, step=2)
            s.check("erg", "blocs à venir visibles en couleur de zone", frac >= 0.02, f"{frac:.1%} de pixels jaunes")

    # 4 ter. Cible ERG longue (« 152 W (98 %) », biais −2 %) : la valeur tient dans la colonne gauche, police
    # réduite au besoin, et le braquet, sans effet en ERG, est caché (suite X22) ; même au palier de 50 W d'un
    # FreeRide (lot O19 : jamais de roue libre en ERG).
    core.set_scene(speed=7.0, mode="ERG", erg={
        "workout_name": "Recette 8 min", "block_index": 1, "block_count": 4, "block_type": "warmup",
        "block_remaining_s": 22.0, "block_total_s": 120.0, "target_w": 152.0, "next_target_w": 184.0,
        "bias_pct": 98, "paused": False})
    time.sleep(1.0)
    shot = s.capture("erg_cible_longue")
    if shot:
        img, info = shot
        s.check_texts("erg_cible_longue", info, {"target": "152 W (98 %)"})
        s.check("erg_cible_longue", "braquet caché en ERG", not info["widgets"]["gear"]["visible"])
        s.check_layout("erg_cible_longue", info)
    core.set_scene(speed=7.0, mode="ERG", erg={
        "workout_name": "Recette 8 min", "block_index": 2, "block_count": 4, "block_type": "steady",
        "block_remaining_s": 60.0, "block_total_s": 120.0, "target_w": 50.0, "next_target_w": 184.0,
        "bias_pct": 98, "paused": False})
    time.sleep(1.0)
    shot = s.capture("erg_palier_50w")
    if shot:
        img, info = shot
        s.check_texts("erg_palier_50w", info, {"target": "50 W (98 %)"})
        s.check("erg_palier_50w", "braquet caché au palier de 50 W", not info["widgets"]["gear"]["visible"])
        s.check_layout("erg_palier_50w", info)

    # 4 bis. Courbes de la séance (lot O14), taille complète : en ERG à la place de l'histogramme (profil
    # cible, puissance blanche, FC rouge, légende) ; en SIM dans un panneau centré, sans toucher aux
    # panneaux latéraux. Le core annonce la taille dans hello_ack.config.chart.
    core.chart = "full"
    core.send_hello_ack()
    core.set_scene(speed=7.0, mode="ERG", hr=140, erg={
        "workout_name": "Sweet spot 3x10", "block_index": 2, "block_count": 7, "block_type": "interval_on",
        "block_remaining_s": 95.0, "block_total_s": 600.0, "target_w": 230.0, "next_target_w": 150.0,
        "bias_pct": 100, "paused": False})
    time.sleep(7.0)
    shot = s.capture("erg_courbes")
    if shot:
        img, info = shot
        w = info["widgets"]
        chart = w["chart_erg"]
        s.check("erg_courbes", "courbes affichées à la place de l'histogramme",
                chart["visible"] and not w["erg_hist"]["visible"] and chart["rect"][2] >= 0.8 * s.width
                and chart["rect"][1] + chart["rect"][3] <= s.height - 10 * info["ui_scale"], f"rectangle {chart['rect']}")
        s.check_layout("erg_courbes", info)
        box = rect_box(chart["rect"])
        # Seuil bas : à 1024x600 (échelle 0,8) le panneau ne fait que 55 px de haut et le trait blanc
        # couvre ~0,17 % de sa surface (mesuré sur le PC).
        s.check("erg_courbes", "courbe de puissance blanche tracée",
                fraction(img, box, lambda p: p[0] > 235 and p[1] > 235 and p[2] > 235, step=2) >= 0.001)
        s.check("erg_courbes", "courbe de fréquence cardiaque rouge tracée",
                fraction(img, box, lambda p: p[0] > 200 and p[1] < 90 and p[2] < 90, step=2) >= 0.001)
        s.check("erg_courbes", "profil cible coloré en zone",
                fraction(img, box, lambda p: p[0] > 110 and p[1] > 90 and p[2] < 70, step=2) >= 0.02)
    core.set_scene(speed=SPEED_MPS, mode="SIM", erg=None, hr=140)
    time.sleep(7.0)
    shot = s.capture("sim_courbes")
    if shot:
        img, info = shot
        w = info["widgets"]
        chart = w["chart_sim"]
        screen = [0, 0, s.width, s.height]
        s.check("sim_courbes", "panneau des courbes affiché dans l'écran",
                chart["visible"] and overlap(chart["rect"], screen) >= 0.999 * chart["rect"][2] * chart["rect"][3],
                f"rectangle {chart['rect']}")
        clash = [k for k in ("panel", "bots_panel") if k in w and w[k]["visible"]
                 and overlap(chart["rect"], w[k]["rect"]) > 0]
        s.check("sim_courbes", "pas de chevauchement avec les panneaux du HUD", not clash, ", ".join(clash))
        s.check("sim_courbes", "courbe de puissance blanche tracée",
                fraction(img, rect_box(chart["rect"]), lambda p: p[0] > 235 and p[1] > 235 and p[2] > 235, step=2) >= 0.002)
    core.chart = None
    core.send_hello_ack()
    time.sleep(0.5)

    # 4 ter. Fin d'un entraînement (constat du vélo du 1er novembre) : invite au bandeau, sans alerte rouge,
    # puis pause ouverte sur « Terminer et enregistrer », que la ligne sous le titre rappelle.
    core.set_scene(speed=SPEED_MPS, mode="SIM", erg=None, workout_done={"workout_name": "Sweet spot"})
    time.sleep(SETTLE_S)
    shot = s.capture("fin_entrainement")
    if shot:
        img, info = shot
        b = info["widgets"]["banner"]
        s.check("fin_entrainement", "invite de fin d'entraînement au bandeau",
                b["visible"] and "« Sweet spot » terminé : Y puis A maintenu pour terminer et enregistrer" in b["text"],
                f"« {b['text']} »")
        s.check_layout("fin_entrainement", info)
    core.set_scene(speed=0.0, session_state="PAUSED", pause_reason="user", power=0.0, power_3s=0.0, cadence=0.0)
    time.sleep(SETTLE_S)
    shot = s.capture("fin_entrainement_pause")
    if shot:
        img, info = shot
        s.check_texts("fin_entrainement_pause", info, {"menu": "Reprendre | [Terminer et enregistrer]"}, contains=True)
        s.check_texts("fin_entrainement_pause", info,
                      {"menu": "Entraînement terminé : A maintenu pour terminer et enregistrer"}, contains=True)
        s.check_layout("fin_entrainement_pause", info)
    core.set_scene(speed=SPEED_MPS, session_state="RUNNING", pause_reason=None, workout_done=None,
                   power=250.0, power_3s=248.0, cadence=90.0)
    time.sleep(1.0)

    # 5. Pause : trainer perdu, raison visible sous le titre du menu de pause.
    core.set_scene(speed=0.0, s=FIXED_S, mode="SIM", erg=None, session_state="PAUSED", pause_reason="trainer_lost",
                   trainer_status="RECONNECTING", power=0.0, power_3s=0.0, cadence=0.0)
    time.sleep(SETTLE_S)
    shot = s.capture("pause")
    if shot:
        img, info = shot
        # HUD caché pendant un menu (présentation des menus) : la raison de la pause est sous le titre du menu.
        s.check_texts("pause", info, {"menu_title": "Pause", "menu": "[Reprendre] | Terminer et enregistrer"}, contains=True)
        s.check_texts("pause", info, {"menu": "Trainer perdu : reconnexion en cours…"}, contains=True)
        s.check("pause", "HUD de séance caché derrière le menu", not info["widgets"]["power"]["visible"])
        s.check_texts("pause", info, {"menu": "Séance en cours"}, contains=True)
        s.check_texts("pause", info, {"menu": "Puissance moy."}, contains=True)
        s.check_layout("pause", info)
    _confirmation_scene(s)

    # 6. Core muet : bandeau, caméra extrapolée puis figée.
    core.set_scene(speed=SPEED_MPS, session_state="RUNNING", pause_reason=None, trainer_status="CONNECTED",
                   power=250.0, power_3s=248.0, cadence=90.0)
    time.sleep(1.0)
    core.silent = True
    lost = core.log.wait_for(r"^core_lost", 3.0, core.log.mark())
    s.check("core_muet", "core_lost signalé", lost is not None)
    time.sleep(0.6)
    a = s.capture("core_muet_1")
    time.sleep(0.6)
    b = s.capture("core_muet_2")
    if a and b:
        (img_a, info_a), (img_b, info_b) = a, b
        s.check_banner("core_muet_2", img_b, info_b, "Core non joignable")
        s.check_layout("core_muet_2", info_b)
        moved = sum((p - q) ** 2 for p, q in zip(info_a["camera"], info_b["camera"])) ** 0.5
        dt = (info_b["ticks_ms"] - info_a["ticks_ms"]) / 1000.0
        s.check("core_muet_2", "caméra figée", moved < 0.05, f"{moved:.3f} m en {dt:.2f} s")
        d = mean_abs_diff(img_a, img_b, ground_box(s, info_b))
        s.check("core_muet_2", "image figée", d < GROUND_SCROLL_LEVEL, f"écart moyen {d:.2f} niveaux")

    # 7. Reprise : le bandeau disparaît.
    core.silent = False
    core.log.wait_for(r"^core_returned", 3.0)
    time.sleep(1.5)
    shot = s.capture("reprise")
    if shot:
        img, info = shot
        s.check_banner("reprise", img, info, None)
        s.check_world("reprise", img, info)

    # 8. Erreur du core : code dans le bandeau, sans recouvrir le HUD.
    # READY : en RUNNING, la caméra ne recule jamais et ne reviendrait pas à FIXED_S.
    core.set_scene(speed=0.0, s=FIXED_S, session_state="READY")
    time.sleep(SETTLE_S)
    core.send({"type": "error", "v": CONTRACT_VERSION, "code": "route_invalid", "message": "parcours de test illisible"})
    time.sleep(0.6)
    shot = s.capture("erreur")
    if shot:
        img, info = shot
        s.check_banner("erreur", img, info, "route_invalid")
        s.check_layout("erreur", info)
    _menu_scenes(s)
    _pentes_scenes(s)
    _decor_vivant_scene(s)
    _voies_scene(s)
    _peloton_face_scene(s)
    fps = [c.info.get("fps", 0) for c in s.report.captures if c.config == s.name]
    s.check("journal", "rendu actif (images par seconde)", bool(fps) and max(fps) >= 1, f"fps relevés : {fps}")


# Colonne de droite la plus chargée (lot X22) : 4 bots à profil (maillots, jauges W′), deux voisins, un
# segment en cours et un bonus en réserve, empilés sous le panneau de droite jusqu'au-dessus du profil.
PROFILE_BOTS = [
    {"id": "b1", "name": "Grimpeur", "profile": "climber", "cp_w": 262.0, "mass_kg": 62.0, "wbal_pct": 74.0, "jersey": "kom", "ds": 35.0},
    {"id": "b2", "name": "Rouleur", "profile": "rouleur", "cp_w": 281.0, "mass_kg": 75.0, "wbal_pct": 92.0, "jersey": None, "ds": 12.0},
    {"id": "b3", "name": "Sprinteur", "profile": "sprinter", "cp_w": 255.0, "mass_kg": 72.0, "wbal_pct": 38.0, "jersey": "sprint", "ds": -15.0},
    {"id": "b4", "name": "Diesel", "profile": "diesel", "cp_w": 248.0, "mass_kg": 70.0, "wbal_pct": 100.0, "jersey": None, "ds": -40.0},
]


def _bots_segment_bonus_scene(s: Session) -> None:
    core = s.core
    s_now = core.current_s()
    bots = [{k: v for k, v in b.items() if k != "ds"} | {"s": s_now + b["ds"], "v": 0.0, "kind": "constant"}
            for b in PROFILE_BOTS]
    core.set_scene(speed=0.0, bots=bots, bot_ahead="b2", bot_behind="b3", jerseys={"sprint": "b3", "kom": "b1"},
                   segment={"id": "climb1", "kind": "climb", "category": "4", "d_to_start_m": 0.0,
                            "elapsed_s": 42.0, "gap_to_pr_s": -1.6},
                   powerup={"held": "aero", "active": None, "remaining_s": 0.0})
    time.sleep(SETTLE_S)
    shot = s.capture("bots_segment_bonus")
    if shot:
        img, info = shot
        w = info["widgets"]
        # Lot X22 : blocs segment et bonus à la hauteur de leur contenu ; l'encart garde au moins les deux
        # lignes autour du cycliste (ses voisins, avec FTP, maillot et W′) et la ligne des maillots.
        need = ("segment_panel", "bonus_panel", "bots_panel", "bots_ahead", "bots_behind", "bots_line1", "bots_line2",
                "bots_jerseys")
        missing = [k for k in need if not w[k]["visible"]]
        s.check("bots_segment_bonus", "blocs segment et bonus, voisins avec leur ligne complète et maillots affichés",
                not missing, "manquent : " + ", ".join(missing) if missing else "")
        s.check_texts("bots_segment_bonus", info, {"bots_ahead": "Rouleur  281 W", "bots_behind": "Sprinteur  255 W",
                                                   "bots_jerseys": "Vert : Sprinteur · Pois : Grimpeur"}, contains=True)
        seg, bonus, panel = w["segment_panel"]["rect"], w["bonus_panel"]["rect"], w["bots_panel"]["rect"]
        s.check("bots_segment_bonus", "segment, bonus puis bots empilés", seg[1] < bonus[1] < panel[1],
                f"hauts {seg[1]:.0f}, {bonus[1]:.0f}, {panel[1]:.0f} px")
        prof, right = w["profile"]["rect"], w["panel_right"]["rect"]
        s.check("bots_segment_bonus", "profil d'altitude sous le panneau de droite, au-dessus du segment",
                right[1] + right[3] <= prof[1] + 0.5 and prof[1] + prof[3] <= seg[1] + 0.5
                and abs(prof[0] - right[0]) <= 1.0 and abs(prof[2] - right[2]) <= 1.0,
                f"profil {prof[1]:.0f}–{prof[1] + prof[3]:.0f} px, panneau jusqu'à {right[1] + right[3]:.0f} px, "
                f"segment à {seg[1]:.0f} px")
        s.check_layout("bots_segment_bonus", info)
    core.set_scene(speed=SPEED_MPS, bots=None, bot_ahead=None, bot_behind=None, jerseys=None, segment=None, powerup=None)
    time.sleep(SETTLE_S)


def _pentes_scenes(s: Session) -> None:
    """Lot Q2 : captures sur le parcours demo à des points de ~0 % (0,6 %) et ~4 % (4,5 %)."""
    core = s.core
    # 1. Pente 0 % (s = 4000 m : replat)
    core.set_scene(speed=0.0, s=4000.0, session_state="RUNNING", grade=0.0, grade_sent=0.0,
                   power=150.0, cadence=85.0, hr=130)
    time.sleep(SETTLE_S)
    shot0 = s.capture("pente_0pct")
    if shot0:
        img, info = shot0
        s.check_texts("pente_0pct", info, {"grade": "0.0 %"})
        s.check_layout("pente_0pct", info)
        s.check_world("pente_0pct", img, info)

    # 2. Pente ~4 % (s = 1400 m : montée douce à 4.5 %)
    core.set_scene(speed=0.0, s=1400.0, session_state="RUNNING", grade=4.5, grade_sent=4.5,
                   power=220.0, cadence=80.0, hr=145)
    time.sleep(SETTLE_S)
    shot4 = s.capture("pente_4pct")
    if shot4:
        img, info = shot4
        s.check_texts("pente_4pct", info, {"grade": "+4.5 %"})
        s.check_layout("pente_4pct", info)
        s.check_world("pente_4pct", img, info)
    # Le parcours demo ne dépasse pas 4,5 % : l'aspect d'une pente de 8 % se juge sur la scène
    # pente_4pct lancée avec --visual-grade=1.8 (captures suffixées _k1.8).


## Lot P27 : monde de test OSM (make_osm_world.py) : troupeau à 2 180 m, route secondaire à 100 m et
## autoroute à 250 m du parcours, canal à 120 m ; la scène roule de DECOR_S pendant DECOR_WAIT_S au plus.
## Avec la graine 0 de traffic_model.gd, la case de 1 500 à 1 750 m porte un utilitaire qui double.
OSM_ROUTE_ID = "osm-test"
DECOR_S = 1480.0
ROAD_HALF_WIDTH_M = 3.0   # RoadBuilder.ROAD_WIDTH_M / 2, SHOULDER_WIDTH_M et TrafficModel.VERGE_M (peloton_face)
SHOULDER_M = 0.5
VERGE_M = 0.25
DECOR_WAIT_S = 30.0
DECOR_PAUSE_S = 2.0
DECOR_KINDS = {"animals": "troupeau", "birds": "oiseaux", "vehicles": "véhicule croisé",
               "distant_vehicles": "véhicule lointain", "aircraft": "objet du ciel"}


def _decor_vivant_scene(s: Session) -> None:
    """Lot P27 : décor vivant de la deuxième vague sur le monde de test OSM, vérifié par la présence des
    objets (le décor bouge : pas d'image de référence). Captures toutes les 2 s jusqu'à ce que chaque sorte
    ait été vue, DECOR_WAIT_S au plus ; la dernière est gardée dans le rapport. Lot P30 : pause, ce qui se
    fige (véhicules, cyclistes, ciel, bateaux) n'a pas bougé entre deux captures à DECOR_PAUSE_S d'écart
    (`frozen_sig` du décor). Les sons du décor, plus rares, se vérifient au banc simulé (decor_vivant_2)."""
    core = s.core
    mark = core.log.mark()
    core.route_id = OSM_ROUTE_ID
    core.set_scene(speed=SPEED_MPS, s=DECOR_S, session_state="RUNNING", grade=5.0, grade_sent=5.0, power=280.0,
                   cadence=88.0, hr=150, summary=None)
    loaded = core.log.wait_for(rf"^route_loaded id={OSM_ROUTE_ID}", ROUTE_TIMEOUT_S, mark)
    s.check("decor_vivant", "monde de test OSM chargé", loaded is not None, loaded[1].string if loaded else "aucun route_loaded")
    time.sleep(SETTLE_S)
    seen = dict.fromkeys(DECOR_KINDS, 0)
    t0 = now()
    shot = None
    while now() - t0 < DECOR_WAIT_S:
        shot = s.capture("decor_vivant") or shot
        dec = shot[1].get("decor", {}) if shot else {}
        for k in seen:
            seen[k] = max(seen[k], int(dec.get(k, 0)))
        if all(seen.values()):
            break
        time.sleep(2.0)
    caps = [c for c in s.report.captures if c.config == s.name and c.scene == "decor_vivant"]
    for c in caps[:-1]:
        s.report.captures.remove(c)
    if shot:
        img, info = shot
        s.check("decor_vivant", "décor vivant préparé", bool(info.get("decor", {}).get("prepared")))
        for k, label in DECOR_KINDS.items():
            s.check("decor_vivant", f"{label} en vue", seen[k] > 0, f"{seen[k]} au plus")
        s.check_layout("decor_vivant", info)
        s.check_world("decor_vivant", img, info)
        _check_contacts(s, "decor_vivant", info)
    # Pause : véhicules, cyclistes, ciel et bateaux figés
    core.set_scene(speed=0.0, session_state="PAUSED", pause_reason="user")
    time.sleep(1.0)
    a = s.capture("decor_pause_1")
    time.sleep(DECOR_PAUSE_S)
    b = s.capture("decor_pause_2")
    if a and b:
        sig_a = a[1].get("decor", {}).get("frozen_sig")
        sig_b = b[1].get("decor", {}).get("frozen_sig")
        s.check("decor_pause", "décor figé en pause (véhicules, cyclistes, ciel, bateaux)",
                sig_a is not None and sig_a != 0 and sig_a == sig_b, f"signature {sig_a} puis {sig_b}")
    core.set_scene(speed=SPEED_MPS, session_state="RUNNING", pause_reason=None)


PASS_WINDOW_M = 10.0   # voiture qui double vue à moins de 10 m devant ou derrière le cycliste (lot P32)
PASS_WAIT_S = 60.0   # la voiture d'en face croisée, puis l'utilitaire qui double (décor ralenti sous Xvfb)


def _place(s: Session, **spec: Any) -> None:
    s.core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "decor_place", **spec})


def _check_lanes(s: Session, scene: str, info: dict[str, Any]) -> None:
    """Lot P32 : chacun roule à droite dans son sens. Cycliste à droite de l'axe ; usagers en face à gauche de
    l'axe (leur droite) ; cyclistes du décor qui roulent devant, dans le même sens, à droite."""
    dec = info.get("decor", {})
    rider = float(dec.get("rider_lateral", 0.0))
    s.check(scene, "cycliste dans la voie de droite", 0.5 <= rider <= 2.0, f"{rider:+.2f} m de l'axe")
    users = dec.get("road_users", [])
    facing = [u for u in users if u["dir"] < 0]
    s.check(scene, "usagers en face sur leur droite (à gauche de l'axe)", bool(facing) and all(u["lateral"] < 0.0 for u in facing),
            ", ".join(f"{u['what']} {u['lateral']:+.2f} m" for u in facing) or "aucun en face")
    ahead = [u for u in users if u["dir"] > 0 and u["what"] == "cyclist" and u["kind"] == "ahead"]
    if ahead:
        s.check(scene, "cyclistes devant, même sens, à droite du cycliste", all(u["lateral"] > rider for u in ahead),
                ", ".join(f"{u['lateral']:+.2f} m" for u in ahead))


def _check_contacts(s: Session, scene: str, info: dict[str, Any]) -> None:
    """Lot P32 : compteur de contacts du décor (living_decor.gd), cumulé depuis le début : véhicules entre eux,
    véhicule et cycliste, cyclistes de groupes différents, bots et cycliste compris."""
    dec = info.get("decor", {})
    n = int(dec.get("contacts", -1))
    s.check(scene, "aucun contact sur la route", n == 0, f"{n} ({dec.get('last_contact', '')})" if n else "0")


def _voies_scene(s: Session) -> None:
    """Lot P32 (demande du 29 octobre : « les véhicules et les cyclistes roulent à droite de la route et pas au
    milieu ») : une voiture et un cycliste en face, deux cyclistes devant dans le même sens, puis un utilitaire
    posé en train de doubler (caméra derrière l'avatar), posés par le test (`decor_place`) ; positions lues dans
    `road_users`. Le décor avance au pas de l'image : sous Xvfb (quelques images/s), il paraît ralenti."""
    core = s.core
    core.set_scene(speed=SPEED_MPS, s=DECOR_S + 400.0, session_state="RUNNING", grade=0.0, grade_sent=0.0)
    time.sleep(SETTLE_S)
    _place(s, vehicle={"kind": "car_a", "dir": -1, "rel_m": 70.0, "kmh": 40.0},
           cyclists={"case": "ahead", "rel_m": 14.0, "size": 2, "abreast": False})
    _place(s, cyclists={"case": "oncoming", "rel_m": 45.0, "size": 1})
    time.sleep(1.5)
    shot = s.capture("voies_face")
    if shot:
        _check_lanes(s, "voies_face", shot[1])
        s.check_world("voies_face", *shot)
    core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "avatar_camera", "view": "follow"})
    time.sleep(1.0)
    # Demande du 29 octobre : « un véhicule doit attendre avant de dépasser si obstacle en face ». Une voiture
    # arrive en face, l'utilitaire posé en train de doubler reste derrière ; il double une fois la voie libre.
    _place(s, vehicle={"kind": "car_b", "dir": -1, "rel_m": 70.0, "kmh": 50.0})
    _place(s, vehicle={"kind": "van", "dir": 1, "rel_m": 4.0, "kmh": 60.0})
    time.sleep(0.7)   # affiché à l'image suivante : deux images au moins sous Xvfb
    wait = s.capture("voies_attente")
    if wait:
        users = wait[1].get("decor", {}).get("road_users", [])
        vans = [u for u in users if u["what"] == "vehicle" and u["dir"] > 0]
        facing = [u for u in users if u["what"] == "vehicle" and u["dir"] < 0 and u["rel_m"] > 0.0]
        s.check("voies_attente", "voiture en face : l'utilitaire attend derrière au lieu de doubler",
                bool(facing) and bool(vans) and all(u["rel_m"] < -PASS_WINDOW_M for u in vans),
                ", ".join(f"{u['kind']} à {u['rel_m']:+.0f} m" for u in vans + facing))
    # Une fois la voiture d'en face croisée, un utilitaire posé en train de doubler double vraiment. Le décor
    # avance au pas de l'image et le cycliste en temps réel : sous Xvfb, celui qui attend derrière ne rattrape
    # jamais le cycliste, d'où un second utilitaire posé à côté de lui.
    shot = None
    t0 = now()
    while now() - t0 < PASS_WAIT_S:
        time.sleep(0.5)
        shot = s.capture("voies_depassement")
        users = shot[1].get("decor", {}).get("road_users", []) if shot else []
        if any(u["what"] == "vehicle" and u["dir"] > 0 and -PASS_WINDOW_M < u["rel_m"] < PASS_WINDOW_M for u in users):
            break
        if not any(u["what"] == "vehicle" and u["dir"] < 0 and u["rel_m"] > 0.0 for u in users):
            _place(s, vehicle={"kind": "van", "dir": 1, "rel_m": 4.0, "kmh": 60.0})
            time.sleep(0.7)
    caps = [c for c in s.report.captures if c.config == s.name and c.scene == "voies_depassement"]
    for c in caps[:-1]:
        s.report.captures.remove(c)
    if shot:
        dec = shot[1].get("decor", {})
        rider = float(dec.get("rider_lateral", 0.0))
        passing = [u for u in dec.get("road_users", []) if u["what"] == "vehicle" and u["dir"] > 0
                   and -PASS_WINDOW_M < u["rel_m"] < PASS_WINDOW_M]
        gap = [abs(rider - u["lateral"]) - u["half_width"] - 0.3 for u in passing]
        s.check("voies_depassement", "voiture qui double à 1,5 m au moins, sur la gauche", bool(passing)
                and all(u["lateral"] < rider for u in passing) and min(gap) >= 1.5 - 1e-3,
                ", ".join(f"{u['lateral']:+.2f} m, écart {g:.2f} m" for u, g in zip(passing, gap)) or "aucune à côté")
        _check_contacts(s, "voies_depassement", shot[1])
    core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "avatar_camera", "view": ""})



def _peloton_face_scene(s: Session) -> None:
    """Demande du 31 octobre (« et si véhicule en face ? ») : cinq bots de front devant le cycliste arrêté
    (peloton au départ), puis une voiture posée en face (`decor_place`). Les bots serrent à droite, deux de front
    au plus, en file derrière au besoin (bots_view_model.gd) ; la voiture croise sur la chaussée, sans contact."""
    core = s.core
    s_now = core.current_s() + 400.0   # loin des véhicules des scènes précédentes
    core.set_scene(speed=0.0, s=s_now, bots=[
        {"id": f"p{i}", "name": f"Bot {i + 1}", "s": s_now + 12.0 + 0.3 * i, "v": 0.0, "kind": "constant"}
        for i in range(5)])
    shot = None
    t0 = now()
    while now() - t0 < PASS_WAIT_S:   # la caméra rejoint le saut de s à son rythme
        time.sleep(SETTLE_S)
        shot = s.capture("peloton_large")
        if shot and any(0.0 < b["rel_m"] < 30.0 for b in shot[1].get("decor", {}).get("bot_places", [])):
            break
    caps = [c for c in s.report.captures if c.config == s.name and c.scene == "peloton_large"]
    for c in caps[:-1]:
        s.report.captures.remove(c)
    if shot:
        lats = sorted(round(b["lateral"], 1) for b in shot[1].get("decor", {}).get("bot_places", []))
        near = [b for b in shot[1].get("decor", {}).get("bot_places", []) if 0.0 < b["rel_m"] < 30.0]
        s.check("peloton_large", "peloton au départ : cinq bots de front, devant le cycliste", len(set(lats)) == 5 and len(near) == 5,
                f"{lats}, {len(near)} à moins de 30 m")
    # Posée assez près pour croiser le peloton même quand le décor avance lentement (Xvfb, --fige) : les bots
    # serrent à droite dès qu'elle est là, elle attend devant eux s'ils ne lui laissent pas encore la place.
    _place(s, vehicle={"kind": "car_a", "dir": -1, "rel_m": 45.0, "kmh": 40.0})
    shot = None
    t0 = now()
    while now() - t0 < PASS_WAIT_S:
        time.sleep(0.5)
        shot = s.capture("peloton_face")
        dec = shot[1].get("decor", {}) if shot else {}
        near = [u for u in dec.get("road_users", []) if u["what"] == "vehicle" and u["dir"] < 0 and u["rel_m"] < 50.0]
        bots = dec.get("bot_places", [])
        if near and bots and all(b["lateral"] >= 0.0 for b in bots):
            break
    caps = [c for c in s.report.captures if c.config == s.name and c.scene == "peloton_face"]
    for c in caps[:-1]:
        s.report.captures.remove(c)
    if shot:
        dec = shot[1].get("decor", {})
        cars = [u for u in dec.get("road_users", []) if u["what"] == "vehicle" and u["dir"] < 0 and u["rel_m"] < 50.0]
        bots = dec.get("bot_places", [])
        edge = ROAD_HALF_WIDTH_M + SHOULDER_M + VERGE_M
        s.check("peloton_face", "voiture d'en face sur la chaussée", bool(cars) and all(abs(u["lateral"]) + u["half_width"] <= edge + 1e-3 for u in cars),
                ", ".join(f"{u['lateral']:+.2f} m" for u in cars) or "aucune près des bots")
        s.check("peloton_face", "bots serrés à droite, deux de front au plus", bool(bots) and all(b["lateral"] >= 0.0 for b in bots),
                ", ".join(f"{b['lateral']:+.2f} m à {b['rel_m']:+.1f} m" for b in bots))
        _check_contacts(s, "peloton_face", shot[1])
    core.set_scene(bots=None)
    time.sleep(1.0)


def _menu_scenes(s: Session) -> None:
    """Lot N6 : accueil avec l'état des appareils, liste des parcours au Click, bilan de fin ; menus en plein
    écran du lot « présentation des menus » : accueil entier, sélection en cyan, HUD caché ; étape 2 : carte
    de détail (fiche du parcours sous le focus, écran Prêt avec le profil d'altitude du parcours chargé)."""
    core = s.core
    core.set_scene(speed=0.0, s=FIXED_S, session_state="IDLE", devices=MENU_DEVICES, summary=None)
    time.sleep(SETTLE_S + 3.0)   # le bandeau d'erreur de la scène précédente reste 5 s au moins
    shot = s.capture("menu_accueil")
    if shot:
        img, info = shot
        s.check_texts("menu_accueil", info, {"menu_title": "OpenRide", "menu": "Session libre | Session ERG | Choisir un plan"}, contains=True)
        s.check_texts("menu_accueil", info, {"menu": "Trainer HomeTrainer 0001 : connecté"}, contains=True)
        s.check_layout("menu_accueil", info)
        s.check_banner("menu_accueil", img, info, None)
        m = info["widgets"]["menu"]
        s.check("menu_accueil", "menu en plein écran, HUD de séance caché", m["rect"][2] >= 0.99 * s.width
                and m["rect"][3] >= 0.99 * s.height and not info["widgets"]["power"]["visible"], f"rectangle {m['rect']}")
        s.check_texts("menu_accueil", info, {"menu": "Réglages | Quitter"}, contains=True)
        focus = fraction(img, rect_box(m["rect"]), lambda p: p[0] < 110 and p[1] > 170 and p[2] > 170, step=1)
        s.check("menu_accueil", "sélection très visible (cadre cyan)", focus >= 0.003, f"{focus:.2%} de pixels cyan")
    # Appui long sur A du Click relayé par le core : liste des parcours.
    core.send({"type": "input", "v": CONTRACT_VERSION, "event": "A_LONG"})
    time.sleep(0.8)
    shot = s.capture("menu_parcours")
    if shot:
        img, info = shot
        s.check_texts("menu_parcours", info, {"menu_title": "Parcours", "menu": "[Démo"}, contains=True)
        s.check_texts("menu_parcours", info, {"menu": "Nouveau GPX (12,0 km) — à compiler"}, contains=True)
        s.check_texts("menu_parcours", info, {"menu": "Parcours | Démo | Distance 4,0 km | Dénivelé ↑ 62 m"}, contains=True)
        s.check_layout("menu_parcours", info)
    # Démo choisie (retour à l'accueil), puis Session libre : écran Prêt.
    for event in ("A_LONG", "PLUS_SHORT", "A_LONG"):
        core.send({"type": "input", "v": CONTRACT_VERSION, "event": event})
        time.sleep(0.5)
    time.sleep(1.0)
    shot = s.capture("pret")
    if shot:
        img, info = shot
        s.check_texts("pret", info, {"menu_title": "Prêt", "menu": "Parcours | Démo | Distance 4,0 km"}, contains=True)
        s.check_texts("pret", info, {"menu": "Montée principale : 1,5 km à 3,7 %, ↑ 55 m"}, contains=True)
        s.check_layout("pret", info)
        card = info["widgets"]["menu_card"]
        line = fraction(img, rect_box(card["rect"]), lambda p: p[0] < 110 and p[1] > 170 and p[2] > 170, step=1)
        s.check("pret", "profil d'altitude tracé dans la carte (trait cyan)", card["visible"] and line >= 0.002,
                f"{line:.2%} de pixels cyan")
    _records_scene(s)
    _garage_scenes(s)
    core.set_scene(session_state="FINISHED", summary={
        "duration_s": 1805.0, "distance_m": 15230.0, "avg_power_w": 212.0, "np_w": 221.0, "tss": 41.0,
        "elevation_gain_m": 180.0, "fit_path": "/tmp/openride/seance.fit"})
    time.sleep(1.0)
    shot = s.capture("bilan")
    if shot:
        img, info = shot
        s.check_texts("bilan", info, {"menu_title": "Fin de séance", "menu": "Distance : 15,23 km"}, contains=True)
        s.check_texts("bilan", info, {"menu": "[Nouvelle séance]"}, contains=True)
        s.check_layout("bilan", info)
    _progress_scenes(s)


def _confirmation_scene(s: Session) -> None:
    """Étape 4d des menus : « Abandonner » depuis la pause ouvre une petite carte centrée sur le voile ; la question
    est en texte courant, « Non » est sélectionné d'office et « Oui » (qui perd la séance) est en rouge ; Y revient à la pause."""
    core = s.core
    for event in ("PLUS_SHORT", "PLUS_SHORT", "A_LONG"):
        core.send({"type": "input", "v": CONTRACT_VERSION, "event": event})
        time.sleep(0.3)
    time.sleep(0.6)
    shot = s.capture("confirmation")
    if shot:
        img, info = shot
        card = info["widgets"]["confirm_card"]
        s.check_texts("confirmation", info, {"confirm_question": "Abandonner la séance ?", "menu": "[Non] | Oui"}, contains=True)
        w, h = info["size"]
        cx = card["rect"][0] + card["rect"][2] / 2
        s.check("confirmation", "carte visible, étroite et centrée",
                card["visible"] and card["rect"][2] <= 0.6 * w and abs(cx - w / 2) <= 0.05 * w,
                f"rectangle {card['rect']}")
        s.check("confirmation", "détail de la liste caché", not info["widgets"]["menu_card"]["visible"])
        danger = fraction(img, rect_box(card["rect"]), lambda p: p[0] > 200 and p[1] < 110 and p[2] < 110, step=1)
        s.check("confirmation", "« Oui » en rouge (danger)", danger >= 0.0005, f"{danger:.2%} de pixels rouges")
        s.check_layout("confirmation", info)
    core.send({"type": "input", "v": CONTRACT_VERSION, "event": "Y_SHORT"})
    time.sleep(0.6)


def _records_scene(s: Session) -> None:
    """Étape 4c des menus : écran Records du parcours (depuis l'écran Prêt) avec la carte du record en or,
    puis la table des temps d'une montée ; retour à l'écran Prêt."""
    core = s.core
    for _ in range(5):   # Rouler, Entraînement, Changer de parcours, Bot, Fantôme, puis Records du parcours
        core.send({"type": "input", "v": CONTRACT_VERSION, "event": "PLUS_SHORT"})
        time.sleep(0.2)
    core.send({"type": "input", "v": CONTRACT_VERSION, "event": "A_LONG"})
    time.sleep(0.8)
    shot = s.capture("records")
    if shot:
        img, info = shot
        s.check_texts("records", info, {"menu_title": "Records", "menu": "Montée 1 · 4:08,1"}, contains=True)
        s.check_texts("records", info, {"menu": "Sprint 1"}, contains=True)
        s.check_texts("records", info, {"menu": "Record 4:08,1"}, contains=True)
        s.check_texts("records", info, {"menu": "Écart au 2e +3,4 s"}, contains=True)
        s.check_layout("records", info)
        card = info["widgets"]["menu_card"]
        gold = fraction(img, rect_box(card["rect"]), lambda p: p[0] > 220 and 180 < p[1] < 240 and p[2] < 100, step=1)
        s.check("records", "record en or dans la carte", card["visible"] and gold >= 0.0005, f"{gold:.2%} de pixels or")
    core.send({"type": "input", "v": CONTRACT_VERSION, "event": "A_LONG"})
    time.sleep(0.6)
    shot = s.capture("records_table")
    if shot:
        img, info = shot
        s.check_texts("records_table", info, {"menu_title": "Montée 1 : sans bonus", "menu": "1. 4:08,1 · 27/10/2026 18:05"}, contains=True)
        s.check_layout("records_table", info)
    for event in ("Y_SHORT", "Y_SHORT"):
        core.send({"type": "input", "v": CONTRACT_VERSION, "event": event})
        time.sleep(0.4)
    time.sleep(0.6)


def _menus_only(s: Session) -> None:
    """`--menus` : seulement les scènes des menus (accueil, parcours, Prêt, records, garage, bilan,
    progression), pour des captures de menus à chaque qualité en quelques minutes."""
    core = s.core
    t0 = now()
    while now() - t0 < 20.0 and "IpcClient attaché" not in core.log.path.read_text(errors="replace"):
        time.sleep(0.1)
    time.sleep(1.5)
    core.set_scene(speed=0.0, s=FIXED_S, session_state="IDLE", power=0.0, mode="SIM", erg=None, pause_reason=None,
                   trainer_status="CONNECTED", input_status="CONNECTED")
    core.auto_hello_ack = True
    core.catalog_data = MENU_CATALOG
    core.streaming = True
    loaded = core.log.wait_for(r"^route_loaded id=demo", ROUTE_TIMEOUT_S)
    s.check("menus", "parcours demo chargé", loaded is not None, loaded[1].string if loaded else "aucun route_loaded")
    time.sleep(SETTLE_S)
    _menu_scenes(s)


def _quality_guard_scenes(s: Session) -> None:
    """`--garde-qualite` (lot X32, garde-fou de régression) : la qualité demandée par `--quality` est appliquée au
    démarrage et à la première capture ; un réglage `render.quality` absent ou égal ne change rien ; une autre
    valeur est appliquée tout de suite (source `reglage`) ; une valeur inconnue est notée sans rien changer ;
    revenu à la qualité demandée, la dernière capture la porte. Le contrôle final de run_config vérifie le tout."""
    core = s.core
    wanted = s.name.split("_")[1]   # 1280x720_medium[_k2.5]
    other = "high" if wanted != "high" else "medium"
    started = core.log.wait_for(r"^quality applied=(\w+) requested=(\S+) source=(\w+)", 20.0)
    s.check("garde_qualite", "qualité du démarrage", started is not None and started[1].groups() == (wanted, wanted, "cli"),
            started[1].string if started else "aucune ligne « quality applied »")
    core.set_scene(speed=0.0, s=FIXED_S, session_state="RUNNING", power=200.0, mode="SIM", erg=None, pause_reason=None,
                   trainer_status="CONNECTED", input_status="CONNECTED")
    core.auto_hello_ack = True
    core.catalog_data = MENU_CATALOG
    core.streaming = True
    loaded = core.log.wait_for(r"^route_loaded id=demo", ROUTE_TIMEOUT_S)
    s.check("garde_qualite", "parcours demo chargé", loaded is not None, loaded[1].string if loaded else "aucun route_loaded")
    time.sleep(SETTLE_S)
    shot = s.capture("garde_qualite_depart")
    if shot:
        s.check("garde_qualite_depart", "qualité portée par la capture", shot[1].get("quality") == wanted,
                f"{shot[1].get('quality')!r}, attendu {wanted!r}")

    def send_quality(value: str | None) -> list[str]:
        """Réglages du core avec `render.quality` à `value` (absent si None) ; lignes « quality » qui suivent.
        `current` : qualité appliquée d'après le journal (aucune ligne attendue si `value` l'est déjà)."""
        items = [{"key": "render.fps", "label": "Afficher les images/s", "group": "graphics", "type": "choice",
                  "value": "off", "choices": ["off", "on", "detail"], "applies": "now"}]
        if value is not None:
            items.append({"key": "render.quality", "label": "Qualité graphique", "group": "graphics", "type": "choice",
                          "value": value, "choices": ["low", "medium", "high"], "applies": "now"})
        mark = core.log.mark()
        core.send({"type": "settings", "v": CONTRACT_VERSION, "request_cmd_id": 0, "items": items})
        # Un préréglage plus lourd se met en place en plusieurs secondes sous Xvfb (rendu logiciel).
        core.log.wait_for(r"^quality applied=", 1.5 if value in (None, current[0]) else 15.0, mark)
        time.sleep(0.3)
        lines = [line for _, line in core.log.since(mark) if line.startswith("quality applied=")]
        if lines:
            current[0] = lines[-1].split()[1].split("=")[1]
        return lines

    current = [wanted]

    lines = send_quality(None)
    s.check("garde_qualite", "réglage sans render.quality : qualité inchangée", not lines, " | ".join(lines) or "aucune ligne")
    lines = send_quality(wanted)
    s.check("garde_qualite", f"réglage {wanted} (déjà appliquée) : rien à refaire", not lines, " | ".join(lines) or "aucune ligne")
    lines = send_quality(other)
    s.check("garde_qualite", f"réglage {other} : appliquée tout de suite",
            lines == [f"quality applied={other} requested={other} source=reglage"], " | ".join(lines) or "aucune ligne")
    lines = send_quality("ultra")
    s.check("garde_qualite", "réglage inconnu : noté, qualité inchangée",
            lines == [f"quality applied={other} requested=ultra source=reglage"], " | ".join(lines) or "aucune ligne")
    lines = send_quality(wanted)
    s.check("garde_qualite", f"retour à {wanted}",
            lines == [f"quality applied={wanted} requested={wanted} source=reglage"], " | ".join(lines) or "aucune ligne")
    time.sleep(SETTLE_S)
    shot = s.capture("garde_qualite_fin")
    if shot:
        s.check("garde_qualite_fin", "qualité portée par la capture", shot[1].get("quality") == wanted,
                f"{shot[1].get('quality')!r}, attendu {wanted!r}")


def _draft_gauge_scene(s: Session) -> None:
    """Jauge d'abri (maquette C validée le 29 octobre) : un bot à 6 m devant donne 13,5 % d'abri (« Abri 30 % ») ;
    réglage `render.draft_gauge` coupé par défaut, rien au-dessus du bot ; à « on », arc au-dessus du bot, dans le
    champ de la caméra, avec « 30 % » en medium et high ; coupé à nouveau, plus rien."""
    core = s.core

    def gauge_setting(value: str) -> None:
        core.send({"type": "settings", "v": CONTRACT_VERSION, "request_cmd_id": 0, "items": [
            {"key": "render.draft_gauge", "label": "Jauge d'abri des bots", "group": "graphics", "type": "choice",
             "value": value, "choices": ["off", "on"], "applies": "now"}]})
        time.sleep(0.6)

    s_now = core.current_s()
    core.set_scene(speed=0.0, bots=[{"id": "bot1", "name": "Bot 250 W", "s": s_now + 6.0, "v": 0.0, "kind": "constant"}],
                   bot_ahead="bot1", bot_behind=None, jerseys=None, draft=0.135, draft_bot="bot1")
    time.sleep(SETTLE_S)
    shot = s.capture("jauge_abri_coupee")
    if shot:
        g = shot[1].get("draft_gauge", {})
        s.check("jauge_abri_coupee", "réglage coupé par défaut : pas de jauge", g.get("visible") is False, f"{g}")
    gauge_setting("on")
    shot = s.capture("jauge_abri")
    if shot:
        img, info = shot
        g = info.get("draft_gauge", {})
        s.check("jauge_abri", "jauge au-dessus du bot qui abrite, dans l'image",
                g.get("visible") and g.get("bot") == "bot1" and g.get("on_screen"), f"{g}")
        want = "" if info.get("quality") == "low" else "30 %"
        s.check("jauge_abri", f"texte sous l'arc : « {want} »", g.get("text") == want, f"{g.get('text')!r}")
        s.check("jauge_abri", "pastille du HUD au même pourcentage", info["widgets"]["draft"]["text"] == "Abri 30 %",
                f"{info['widgets']['draft']['text']!r}")
        s.check_layout("jauge_abri", info)
    gauge_setting("off")
    shot = s.capture("jauge_abri_retiree")
    if shot:
        g = shot[1].get("draft_gauge", {})
        s.check("jauge_abri_retiree", "réglage recoupé : jauge cachée", g.get("visible") is False, f"{g}")


def _camera_scenes(s: Session) -> None:
    """Lot V12 : quatre vues de caméra au Click sur le parcours de démonstration. A court et flèches : vue suivante,
    précédente ; A long : vue par défaut ; l'avatar n'apparaît pas en vue subjective ; la vue choisie est mémorisée
    (`set_setting render.camera`) au bout de quelques secondes."""
    core = s.core

    def press(event: str, wait: float = 1.2) -> None:
        core.send({"type": "input", "v": CONTRACT_VERSION, "event": event})
        time.sleep(wait)

    core.set_scene(speed=0.0, grade=0.0, grade_sent=0.0, power=200.0, power_3s=200.0, cadence=37.0)
    time.sleep(0.8)
    shots: dict[str, Any] = {}
    expected = [("subjective", None), ("follow_near", "A_SHORT"), ("follow_far", "A_SHORT"), ("side", "UP_SHORT"),
                ("subjective", "A_SHORT")]
    for view, event in expected:
        if event:
            press(event)
        shot = s.capture(f"camera_{view}" if view not in shots else f"camera_{view}_2")
        if not shot:
            continue
        img, info = shot
        label = f"camera_{view}" if view not in shots else f"camera_{view}_2"
        shots.setdefault(view, shot)
        s.check(label, f"vue {view} affichée", info.get("camera_view") == view and not info.get("camera_transition"),
                f"{info.get('camera_view')}")
        av = info.get("avatar", {})
        if view == "subjective":
            s.check(label, "avatar masqué en vue subjective", av.get("visible") is False, f"{av}")
        else:
            s.check(label, "avatar visible dans le champ de la caméra", av.get("visible") and av.get("on_screen"), f"{av}")
    names = [n for n in ("subjective", "follow_near", "follow_far", "side") if n in shots]
    for i, a_name in enumerate(names):
        for b_name in names[i + 1:]:
            d = mean_abs_diff(shots[a_name][0], shots[b_name][0], (0, 0, s.width, s.height))
            s.check(f"camera_{b_name}", f"{a_name} et {b_name} se distinguent", d >= 1.0, f"écart moyen {d:.2f} niveaux")
    far, near = shots.get("follow_far"), shots.get("follow_near")
    if far and near:
        cam_far, cam_near = far[1]["camera"], near[1]["camera"]
        s.check("camera_follow_far", "suivi éloigné plus haut que le suivi proche", cam_far[1] > cam_near[1] + 2.0,
                f"{cam_far[1]:.1f} m contre {cam_near[1]:.1f} m")
    # Transition douce : une image prise 0,1 s après l'appui est en cours de transition, sans saut de position, et
    # le terrain couvre déjà le bas de l'image (pas de ciel sous l'horizon pendant la bascule, lot X20).
    core.send({"type": "input", "v": CONTRACT_VERSION, "event": "A_SHORT"})   # subjective -> suivi proche
    time.sleep(0.1)
    shot = s.capture("camera_transition")
    if shot:
        s.check("camera_transition", "pose intermédiaire pendant la transition", shot[1].get("camera_transition") is True,
                f"{shot[1].get('camera_transition')}")
        low = fraction(shot[0], (0, s.height * 2 // 3, s.width, s.height), is_open_sky, step=4)
        s.check("camera_transition", "pas de ciel sous l'horizon pendant la bascule", low <= 0.02,
                f"{low:.1%} de pixels de ciel dans le tiers bas")
    time.sleep(1.0)
    press("A_SHORT")   # suivi éloigné
    press("A_LONG")    # vue par défaut
    shot = s.capture("camera_defaut")
    if shot:
        s.check("camera_defaut", "A long : retour au suivi proche", shot[1].get("camera_view") == "follow_near", f"{shot[1].get('camera_view')}")
    press("DOWN_SHORT")
    shot = s.capture("camera_precedente")
    if shot:
        s.check("camera_precedente", "flèche bas : vue précédente (subjective)", shot[1].get("camera_view") == "subjective",
                f"{shot[1].get('camera_view')}")
    time.sleep(2.5)
    with core.lock:
        saved = [r.msg.get("args", {}) for r in core.received if r.msg.get("name") == "set_setting"
                 and r.msg.get("args", {}).get("key") == "render.camera"]
    s.check("camera_memoire", "dernière vue écrite dans render.camera", bool(saved) and saved[-1].get("value") == "subjective",
            f"{saved}")
    core.set_scene(speed=0.0, grade=0.0, grade_sent=0.0, power=250.0, power_3s=248.0, cadence=90.0)
    time.sleep(1.0)


XP_RESULT = {"type": "xp_result", "v": CONTRACT_VERSION, "eligible": True, "reason": None,
             "gains": [{"source": "distance", "points": 302}, {"source": "climb", "points": 302}], "total": 604,
             "xp_total": 100, "xp_next_level": 1600, "level_before": 9, "level_after": 10, "coins_gained": 42,
             "coins_total": 232, "equipment_gain_s": -12.5, "unlocked": ["frame_aero"], "challenges": [], "more": False}


def _progress_scenes(s: Session) -> None:
    """Lot V9 : bilan de progression en fin de séance (xp_result répété par le core) : lignes, barre, niveau,
    déblocage, bandeau « Niveau N ! » et accès au Garage ; séance refusée."""
    core = s.core
    for _ in range(3):   # le core répète le message une fois par seconde
        core.send(dict(XP_RESULT))
        time.sleep(1.0)
    shot = s.capture("progression")
    if shot:
        img, info = shot
        s.check_texts("progression", info, {"menu": "Distance 15,2 km : +302 XP"}, contains=True)
        s.check_texts("progression", info, {"menu": "Pièces : +42 (solde 232)"}, contains=True)
        s.check_texts("progression", info, {"menu": "Niveau 10 : ■□□□□□□□□□ 100 / 1600 XP"}, contains=True)
        s.check_texts("progression", info, {"menu": "Niveau 10 !"}, contains=True)
        s.check_texts("progression", info, {"menu": "Aller au Garage"}, contains=True)
        s.check_layout("progression", info)
        banner = info["widgets"]["banner"]
        s.check("progression", "bandeau « Niveau 10 ! » affiché", banner["visible"] and "Niveau 10 !" in banner.get("text", ""),
                f"{banner.get('text')}")
    # Bilan complet (dix chiffres, fichier FIT, quatre blocs ERG du bilan détaillé) et progression : la carte
    # tient au-dessus du bandeau des boutons (suite X22, recette ERG du 28/10).
    core.set_scene(session_state="IDLE", summary=None)
    time.sleep(0.5)
    core.set_scene(session_state="FINISHED", summary={
        "duration_s": 516.0, "distance_m": 3210.0, "avg_power_w": 139.0, "np_w": 155.0, "intensity_factor": 0.62,
        "tss": 6.0, "elevation_gain_m": 33.0, "avg_cadence_rpm": 49.0, "avg_hr_bpm": 119.0, "max_power_w": 400.0,
        "fit_path": "/tmp/openride/2026-10-28_17-24_essai-69.fit",
        "blocks": [[1, 91.0, 141.0], [2, 149.0, 170.0], [3, 127.0, 126.0], [4, 182.0, 183.0]]})
    time.sleep(1.0)
    for _ in range(2):
        core.send(dict(XP_RESULT))
        time.sleep(1.0)
    for detailed in (False, True):
        if detailed:
            core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "menu_focus", "id": "details"})
            time.sleep(0.4)
            core.send({"type": "input", "v": CONTRACT_VERSION, "event": "A_LONG"})
            time.sleep(1.0)
        scene = "bilan_complet_detaille" if detailed else "bilan_complet"
        shot = s.capture(scene)
        if shot:
            img, info = shot
            w = info["widgets"]
            s.check_texts(scene, info, {"menu": "Puissance max : 400 W"}, contains=True)
            s.check_texts(scene, info, {"menu": "Pièces : +42 (solde 232)"}, contains=True)
            if detailed:
                s.check_texts(scene, info, {"menu": "Bloc 4 : 182 W pour 183 W"}, contains=True)
            card, bar = w["menu_card"], w["button_bar"]
            bottom = card["rect"][1] + card["rect"][3]
            s.check(scene, "carte du bilan au-dessus du bandeau des boutons",
                    card["visible"] and bottom <= bar["rect"][1] + 0.5,
                    f"bas de la carte {bottom:.0f} px, bandeau à {bar['rect'][1]:.0f} px")
            s.check_layout(scene, info)
    core.set_scene(session_state="IDLE", summary=None)
    time.sleep(0.5)
    core.set_scene(session_state="FINISHED", summary={"duration_s": 120.0, "distance_m": 800.0})
    time.sleep(1.0)
    for _ in range(2):
        core.send({"type": "xp_result", "v": CONTRACT_VERSION, "eligible": False, "reason": "too_short"})
        time.sleep(1.0)
    shot = s.capture("progression_refusee")
    if shot:
        img, info = shot
        s.check_texts("progression_refusee", info, {"menu": "Séance de moins de 5 minutes : pas d'expérience"}, contains=True)
        s.check_layout("progression_refusee", info)


def _garage_scenes(s: Session) -> None:
    """Lot V8 : Garage au Click avec le faux core : en-tête, fiche et aperçu 3D qui suit la pièce sous le focus,
    achat avec confirmation, choix de la pièce achetée, réglage de l'avatar et Enregistrer."""
    core = s.core

    def press(*events: str, wait: float = 0.5) -> None:
        for event in events:
            core.send({"type": "input", "v": CONTRACT_VERSION, "event": event})
            time.sleep(wait)

    def focus(item_id: str) -> None:
        core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "menu_focus", "id": item_id})
        time.sleep(0.4)

    press("Y_SHORT", wait=0.4)   # accueil
    focus("garage")
    press("A_LONG", wait=0.4)
    time.sleep(1.0)
    shot = s.capture("garage")
    if shot:
        img, info = shot
        s.check_texts("garage", info, {"menu_title": "Garage : niveau 8, 210 pièces", "menu": "[Vélo : cadre et roues"}, contains=True)
        s.check_texts("garage", info, {"menu": "Niveau 8"}, contains=True)
        s.check_layout("garage", info)
        prev = info["widgets"]["garage_preview"]
        s.check("garage", "aperçu 3D visible dans la carte", prev["visible"] and info["garage"]["preview"].get("triangles", 0) > 1000,
                f"{info['garage'].get('preview')}")
        time.sleep(0.6)
        shot2 = s.capture("garage_2")
        if shot2:
            d = mean_abs_diff(img, shot2[0], rect_box(prev["rect"]))
            s.check("garage_2", "l'aperçu tourne", d >= 0.3, f"écart moyen {d:.2f} niveaux")
    press("A_LONG", wait=0.4)   # Vélo
    shot = s.capture("garage_velo")
    if shot:
        img, info = shot
        s.check_texts("garage_velo", info, {"menu_title": "Garage : vélo", "menu": "Cadre : Polyvalent — choisie"}, contains=True)
        s.check_texts("garage_velo", info, {"menu": "Cadre : Profilé — 150 pièces"}, contains=True)
        s.check_layout("garage_velo", info)
    focus("item:frame_aero")   # Profilé (achetable)
    time.sleep(0.5)
    shot = s.capture("garage_fiche")
    if shot:
        img, info = shot
        s.check_texts("garage_fiche", info, {"menu": "Profilé"}, contains=True)
        s.check_texts("garage_fiche", info, {"menu": "−4,0"}, contains=True)
        s.check("garage_fiche", "l'aperçu montre le cadre sous le focus avant l'achat",
                info["garage"]["preview"].get("looks", {}).get("frame") == "frame_aero", f"{info['garage'].get('preview', {}).get('looks')}")
        s.check("garage_fiche", "l'équipement choisi ne change pas avant l'achat", info["garage"]["equipped"]["frame"] == "frame_round")
    press("A_LONG", wait=0.5)   # achat : confirmation
    shot = s.capture("garage_confirmation")
    if shot:
        s.check_texts("garage_confirmation", shot[1], {"confirm_question": "Acheter Profilé pour 150 pièces ? Solde après : 60"})
    press("PLUS_SHORT", "A_LONG", wait=0.5)   # Oui
    time.sleep(1.2)
    shot = s.capture("garage_achat")
    if shot:
        img, info = shot
        s.check("garage_achat", "pièce achetée : possédée, solde 60", info["garage"]["states"]["frame_aero"] == "owned"
                and info["garage"]["coins"] == 60, f"{info['garage']['coins']} pièces, {info['garage']['states'].get('frame_aero')}")
        s.check_texts("garage_achat", info, {"menu": "Cadre : Profilé — possédée"}, contains=True)
    press("A_LONG", wait=0.5)   # choisir le cadre
    time.sleep(1.0)
    shot = s.capture("garage_choix")
    if shot:
        img, info = shot
        s.check("garage_choix", "cadre choisi, états mis à jour", info["garage"]["equipped"]["frame"] == "frame_aero"
                and info["garage"]["states"]["frame_aero"] == "equipped" and info["garage"]["states"]["frame_round"] == "owned",
                f"{info['garage']['equipped']}")
        s.check("garage_choix", "l'avatar du jeu porte le nouveau cadre", info["avatar"].get("looks", {}).get("frame") == "frame_aero",
                f"{info['avatar'].get('looks')}")
    press("Y_SHORT", wait=0.4)   # Garage
    focus("avatar")
    press("A_LONG", wait=0.4)   # Avatar
    focus("field:height")
    press("A_LONG", wait=0.4)   # Taille
    shot = s.capture("garage_modif")
    if shot:
        img, info = shot
        s.check_texts("garage_modif", info, {"menu_title": "Taille", "menu": "moyenne"}, contains=True)
        s.check("garage_modif", "aperçu visible pendant la modification", info["widgets"]["garage_preview"]["visible"])
    press("PLUS_SHORT", "A_LONG", wait=0.4)   # grande, valider
    shot = s.capture("garage_avatar")
    if shot:
        img, info = shot
        s.check("garage_avatar", "brouillon modifié, rien d'enregistré", info["garage"]["draft"]["height"] == "L"
                and info["garage"]["avatar"]["height"] == "M" and info["garage"]["dirty"], f"{info['garage']['draft']}")
    focus("save")
    press("A_LONG", wait=0.4)   # Enregistrer
    time.sleep(1.0)
    shot = s.capture("garage_enregistre")
    if shot:
        img, info = shot
        s.check("garage_enregistre", "avatar enregistré par le core", info["garage"]["avatar"]["height"] == "L" and not info["garage"]["dirty"],
                f"{info['garage']['avatar']}")
        s.check_texts("garage_enregistre", info, {"menu": "Enregistré"}, contains=True)
    press("Y_SHORT", "Y_SHORT", wait=0.3)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--godot", default=os.environ.get(
        "GODOT", str(Path.home() / "Applications/godot/Godot_v4.7.2-stable_linux.x86_64")))
    ap.add_argument("--visual-grade", type=float, default=1.0, help="facteur d'exagération visuelle du relief (lot Q2, défaut : 1.0)")
    ap.add_argument("--configs", default=DEFAULT_CONFIGS,
                    help=f"résolution:qualité, séparées par des virgules (défaut {DEFAULT_CONFIGS})")
    ap.add_argument("--out", type=Path, default=None, help="dossier des captures et du rapport (défaut : dossier temporaire)")
    ap.add_argument("--menus", action="store_true", help="seulement les scènes des menus (captures rapides)")
    ap.add_argument("--native", action="store_true", help="écran réel et rendu habituel, sans Xvfb")
    ap.add_argument("--golden", default=None,
                    help="dossier des images de référence : <dossier>/<xvfb|natif>/<préréglage>/<scène>.png")
    ap.add_argument("--update-golden", nargs="?", const="*", default=None, metavar="SCÈNES",
                    help="réécrit les références (toutes, ou seulement les scènes listées, séparées par des virgules)")
    ap.add_argument("--fige", nargs="?", type=float, const=FREEZE_T, default=None, metavar="T",
                    help=f"scène figée : décor vivant, nuages, herbe et personnages arrêtés à l'instant T (défaut {FREEZE_T:g} s)")
    ap.add_argument("--decor-vivant", choices=("on", "off"), default="on",
                    help="off : décor vivant coupé, rendu de la 1.0 (références dans <préréglage>_sans_vivant)")
    ap.add_argument("--garde-qualite", action="store_true",
                    help="seulement le garde-fou de la qualité appliquée (démarrage, réglages du core, lot X32)")
    ap.add_argument("--lisibilite", action="store_true",
                    help="hauteur des chiffres et contraste des textes du HUD sur chaque capture (lot X22)")
    args = ap.parse_args()

    if not (Path(args.godot).is_file() and os.access(args.godot, os.X_OK)):
        print(f"Godot introuvable : {args.godot} (définir GODOT=/chemin/vers/godot)")
        return 2
    if not args.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable : installer xvfb, xauth et libgl1-mesa-dri (ou lancer avec --native)")
        return 2
    if args.update_golden and not args.golden:
        ap.error("--update-golden demande --golden DOSSIER")

    out_dir = args.out or Path(tempfile.mkdtemp(prefix="openride-visual-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    routes_dir = Path(tempfile.mkdtemp(prefix="openride-visual-routes-"))
    report = Report()
    t0 = now()
    try:
        gen = subprocess.run([sys.executable, "-m", "openride_core.tools.fake_world", "--demo", "--terrain",
                              "--out", str(routes_dir)], env={**os.environ, "PYTHONPATH": str(CORE_SRC)},
                             capture_output=True, text=True)
        if gen.returncode != 0:
            print("Génération du parcours demo avec terrain impossible :\n" + gen.stderr)
            return 1
        # Monde de test OSM de la scène decor_vivant (lot P27), avec le vrai compilateur
        osm_work = Path(tempfile.mkdtemp(prefix="openride-visual-osm-"))
        gen = subprocess.run([sys.executable, str(ENGINE_DIR / "tests" / "make_osm_world.py"), "--out", str(osm_work)],
                             env={**os.environ, "PYTHONPATH": os.pathsep.join([str(COMPILER_SRC), str(CORE_SRC)])},
                             capture_output=True, text=True)
        if gen.returncode != 0:
            print("Génération du monde de test OSM impossible (compilateur installé ?) :\n" + gen.stderr)
            return 1
        shutil.copytree(osm_work / f"{OSM_ROUTE_ID}.world", routes_dir / f"{OSM_ROUTE_ID}.world")
        shutil.rmtree(osm_work, ignore_errors=True)
        for config in [c.strip() for c in args.configs.split(",") if c.strip()]:
            scenes = _quality_guard_scenes if args.garde_qualite else _menus_only if args.menus else None
            run_config(config, args, routes_dir, out_dir, report, scenes)
    finally:
        shutil.rmtree(routes_dir, ignore_errors=True)
    if args.update_golden:
        report.notes.append(f"Références enregistrées dans {args.golden} ({args.update_golden}).")
    page = write_html(report, out_dir, now() - t0)
    fails = report.failures()
    print(f"Tests graphiques : {len(report.checks) - len(fails)}/{len(report.checks)} vérifications réussies")
    print(f"Rapport : {page}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
