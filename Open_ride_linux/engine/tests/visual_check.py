#!/usr/bin/env python3
"""Tests graphiques automatiques de l'engine : vraie scène principale rendue, captures analysées.

Usage : visual_check.py --godot CHEMIN [--configs 1280x720:low,…] [--out DOSSIER] [--native]
                        [--golden DOSSIER [--update-golden]] [--keep]

Pour chaque configuration (résolution et préréglage de qualité), le script lance l'engine avec sa
vraie scène (`main.tscn`) sous Xvfb (OpenGL logiciel de Mesa, moteur Compatibility), face au faux
core de `fake_core.py`, et lui fait parcourir des scènes de séance : attente du core, vue fixe,
mouvement, ERG, pause, core muet, reprise, erreur. À chaque étape, l'engine (en `--test-mode`)
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
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fake_core import CONTRACT_VERSION, EngineLog, FakeCore, now  # noqa: E402

ENGINE_DIR = Path(__file__).resolve().parents[1]
CORE_SRC = ENGINE_DIR.parent / "core" / "src"
DEFAULT_CONFIGS = "1280x720:low,1920x1080:high,1024x600:medium"
# Mêmes tolérances que run_engine_tests.sh, plus la synchronisation verticale sous Xvfb.
GODOT_ISSUE = re.compile(r"SCRIPT ERROR|ERROR:|WARNING:")
GODOT_TOLERATED = re.compile(
    r"ObjectDB instances leaked|resources still in use at exit|[Mm]esh.*(null|nul)|V-Sync|set_use_vsync")
CONTROLS_HINT_PREFIX = "Click : Y = pause"   # hud_view_model.controls_text()
HUD_LABELS = ("power", "target", "speed", "cadence", "hr", "grade", "distance", "erg", "status",
              "erg_title", "erg_target", "erg_remaining", "erg_next", "erg_hist",
              "wind_speed", "wind_level", "wind_verdict", "draft", "bots_line1", "bots_line2")
BANNER_RGB = (153, 26, 13)        # fond du bandeau (main.tscn : Color(0.6, 0.1, 0.05))
GOLDEN_TOLERANCE = 6.0            # écart moyen admis aux références, en niveaux sur 255
GOLDEN_CHANGED_MAX = 0.01         # part admise de pixels changés de plus de CHANGED_LEVEL (défaut local)
CHANGED_LEVEL = 40
ROUTE_TIMEOUT_S = 20.0
SETTLE_S = 2.5                    # tuiles de terrain et lissage de la caméra après un saut de s
SPEED_MPS = 8.0
# Scènes reproductibles (s fixé, rien ne bouge) : les seules comparées aux images de référence.
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


# --- PNG (bibliothèque standard) ------------------------------------------------------------------

@dataclass
class Image:
    width: int
    height: int
    rgb: bytes                    # 3 octets par pixel, ligne par ligne

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        i = (y * self.width + x) * 3
        return self.rgb[i], self.rgb[i + 1], self.rgb[i + 2]

    def pixels(self, box: tuple[int, int, int, int] | None = None, step: int = 2):
        """Pixels d'un rectangle (x0, y0, x1, y1), un sur `step` dans chaque direction."""
        x0, y0, x1, y1 = box if box else (0, 0, self.width, self.height)
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(self.width, int(x1)), min(self.height, int(y1))
        for y in range(y0, y1, step):
            row = y * self.width * 3
            for x in range(x0, x1, step):
                i = row + x * 3
                yield self.rgb[i], self.rgb[i + 1], self.rgb[i + 2]


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path: Path) -> Image:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} : pas un PNG")
    pos, idat, width = 8, bytearray(), 0
    height = depth = ctype = 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype not in (2, 6) or interlace:
                raise ValueError(f"{path} : PNG non pris en charge (profondeur {depth}, type {ctype})")
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    bpp = 3 if ctype == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = width * bpp
    out = bytearray(width * height * 3)
    prev = bytearray(stride)
    for y in range(height):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up_left = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, prev[i], up_left)) & 0xFF
        if bpp == 3:
            out[y * width * 3:(y + 1) * width * 3] = line
        else:
            o = y * width * 3
            for x in range(width):
                out[o + x * 3:o + x * 3 + 3] = line[x * 4:x * 4 + 3]
        prev = line
    return Image(width, height, bytes(out))


def write_png(path: Path, img: Image) -> None:
    stride = img.width * 3
    raw = b"".join(b"\x00" + img.rgb[y * stride:(y + 1) * stride] for y in range(img.height))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", img.width, img.height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# --- mesures sur l'image -------------------------------------------------------------------------

def luminance(p: tuple[int, int, int]) -> float:
    return (0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]) / 255.0


def is_sky(p: tuple[int, int, int]) -> bool:
    """Bleu du ciel procédural (zénith à l'horizon), brume de l'horizon ou nuage (lot P16)."""
    r, g, b = p
    return (b >= 190 and b >= r + 25 and b >= g + 5) or is_cloud(p)


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


def mean_abs_diff(a: Image, b: Image, box=None, step: int = 2) -> float:
    """Écart moyen par composante, en niveaux sur 255 (images de même taille)."""
    if (a.width, a.height) != (b.width, b.height):
        return 255.0
    n = 0
    total = 0
    for pa, pb in zip(a.pixels(box, step), b.pixels(box, step)):
        n += 1
        total += abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
    return total / (3 * n) if n else 0.0


def changed_fraction(a: Image, b: Image, level: int = CHANGED_LEVEL, step: int = 2) -> float:
    """Part des pixels dont une composante change de plus de `level` niveaux (défaut localisé)."""
    if (a.width, a.height) != (b.width, b.height):
        return 1.0
    n = hit = 0
    for pa, pb in zip(a.pixels(None, step), b.pixels(None, step)):
        n += 1
        if max(abs(pa[0] - pb[0]), abs(pa[1] - pb[1]), abs(pa[2] - pb[2])) > level:
            hit += 1
    return hit / n if n else 0.0


def diff_image(a: Image, b: Image) -> Image:
    """Écarts amplifiés ×4, en rouge sur l'image de référence assombrie."""
    out = bytearray(len(a.rgb))
    for i in range(0, len(a.rgb), 3):
        d = (abs(a.rgb[i] - b.rgb[i]) + abs(a.rgb[i + 1] - b.rgb[i + 1]) + abs(a.rgb[i + 2] - b.rgb[i + 2])) // 3
        base = (a.rgb[i] + a.rgb[i + 1] + a.rgb[i + 2]) // 12
        out[i] = min(255, base + 4 * d)
        out[i + 1] = base
        out[i + 2] = base
    return Image(a.width, a.height, bytes(out))


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
AVATAR_GARAGE = [{"id": look, "slot": slot, "name": look, "state": "owned", "level_required": 1, "price": 0,
                  "challenge": None, "mass_delta_kg": 0.0, "cda_delta_pct": 0.0, "terrain": "any", "look": look}
                 for slot, looks in {
                     "frame": ["frame_round", "frame_light", "frame_aero", "frame_tt"],
                     "wheels": ["wheels_spoked", "wheels_spoked_light", "wheels_deep", "wheels_disc"],
                     "kit": ["kit_plain", "kit_stripes", "kit_polka", "kit_neon"]}.items() for look in looks]

AVATAR_PROGRESSION = {
    "level": 8, "xp": 4310, "xp_level_start": 3800, "xp_next_level": 5000, "coins": 210,
    "equipped": {"frame": "frame-alu", "wheels": "wheels-carbon-40", "helmet": "helmet-basic",
                 "kit": "kit-blue", "socks": "socks-white", "glasses": "glasses-none"},
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
    golden_diff: float | None = None
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
                    + (f" · écart à la référence {cap.golden_diff:.2f}" if cap.golden_diff is not None else ""))
            parts.append(f"<div class='cap{' ko' if bad else ''}'><b>{html.escape(cap.scene)}</b><br>"
                         + _img_tag(cap.png) + f"<br><small>{html.escape(meta)}</small>")
            if cap.diff_png is not None:
                parts.append("<br><small>écarts à la référence (rouge)</small><br>" + _img_tag(cap.diff_png))
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
    golden_dir: Path | None
    update_golden: bool

    def check(self, scene: str, name: str, ok: bool, detail: str = "") -> bool:
        return self.report.check(self.name, scene, name, ok, detail)

    def capture(self, scene: str) -> tuple[Image, dict[str, Any]] | None:
        png = self.out_dir / f"{self.name}_{scene}.png"
        mark = self.core.log.mark()
        self.core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "screenshot",
                            "path": str(png), "tag": scene})
        hit = self.core.log.wait_for(r"^screenshot (\{.*\})$", 10.0, mark)
        if not self.check(scene, "capture enregistrée", hit is not None and png.exists(),
                          "" if hit else "aucune ligne « screenshot » dans le journal de l'engine"):
            return None
        info = json.loads(hit[1].group(1))
        img = read_png(png)
        cap = Capture(self.name, scene, png, info)
        self.report.captures.append(cap)
        self.check(scene, "taille de l'image", (img.width, img.height) == (self.width, self.height),
                   f"{img.width}x{img.height}, attendu {self.width}x{self.height}")
        self._golden(cap, img)
        return img, info

    def _golden(self, cap: Capture, img: Image) -> None:
        if self.golden_dir is None or cap.scene not in GOLDEN_SCENES:
            return
        ref_path = self.golden_dir / cap.png.name
        if self.update_golden:
            self.golden_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cap.png, ref_path)
            return
        if not ref_path.exists():
            self.check(cap.scene, "image de référence", False, f"{ref_path} absente (lancer avec --update-golden)")
            return
        ref = read_png(ref_path)
        d = mean_abs_diff(ref, img)
        cap.golden_diff = d
        if d > 0.5 and (ref.width, ref.height) == (img.width, img.height):
            cap.diff_png = self.out_dir / f"{self.name}_{cap.scene}_ecart.png"
            write_png(cap.diff_png, diff_image(ref, img))
        changed = changed_fraction(ref, img)
        self.check(cap.scene, "écart à l'image de référence", d <= GOLDEN_TOLERANCE and changed <= GOLDEN_CHANGED_MAX,
                   f"écart moyen {d:.2f} niveaux sur 255 (seuil {GOLDEN_TOLERANCE}), {changed:.2%} de pixels "
                   f"très différents (seuil {GOLDEN_CHANGED_MAX:.0%})")

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


def ground_box(s: Session, info: dict[str, Any]) -> tuple[int, int, int, int]:
    """Bas de l'image hors HUD : là où la route et le terrain défilent."""
    return 0, int(s.height * 0.6), s.width, s.height


def run_config(config: str, args, routes_dir: Path, out_dir: Path, report: Report) -> None:
    size, _, quality = config.partition(":")
    quality = quality or "low"
    width, height = (int(v) for v in size.lower().split("x"))
    v_grade = getattr(args, "visual_grade", 1.0)
    name = f"{width}x{height}_{quality}" if v_grade == 1.0 else f"{width}x{height}_{quality}_k{v_grade}"
    state_port, cmd_port = free_udp_ports(2)
    engine_log = out_dir / f"{name}_engine.log"
    engine_log.write_text("")
    core = VisualCore(state_port, cmd_port, EngineLog(engine_log))
    core.progression = AVATAR_PROGRESSION
    core.garage = AVATAR_GARAGE
    core.start()
    cmd = [args.godot, "--path", str(ENGINE_DIR), "--resolution", f"{width}x{height}", "--audio-driver", "Dummy"]
    if not args.native:
        cmd = ["xvfb-run", "-a", "-s", f"-screen 0 {width}x{height}x24"] + cmd + [
            "--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
    v_grade = getattr(args, "visual_grade", 1.0)
    cmd += ["--", f"--ipc-state-port={state_port}", f"--ipc-cmd-port={cmd_port}", f"--routes-dir={routes_dir}",
            "--test-mode", f"--quality={quality}", f"--visual-grade={v_grade}"]
    gold = Path(args.golden) / name if args.golden else None
    s = Session(name, width, height, core, out_dir, report, gold, args.update_golden)
    print(f"== {name} ==", flush=True)
    with engine_log.open("w") as log_fh:
        proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        _scenes(s)
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


def _scenes(s: Session) -> None:
    core = s.core
    t0 = now()
    while now() - t0 < 20.0 and "IpcClient attaché" not in core.log.path.read_text(errors="replace"):
        time.sleep(0.1)
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
    time.sleep(SETTLE_S)
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
        s.check("mouvement_2", "le sol défile à l'image", d >= 0.2, f"écart moyen {d:.2f} niveaux")
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
    # encart du HUD sous le panneau de droite (au plus 5 lignes), sans chevauchement.
    # La caméra ne recule jamais pendant une séance (camera_follow.gd) : les bots se placent autour de la
    # position actuelle du cycliste, sans revenir à FIXED_S.
    s_now = core.current_s()
    core.set_scene(speed=0.0, bots=[
        {"id": "bot1", "name": "Bot 250 W", "s": s_now + 20.0, "v": 0.0, "kind": "constant"},
        {"id": "ghost", "name": "Fantôme du 26/10", "s": s_now - 60.0, "v": 0.0, "kind": "ghost"}])
    time.sleep(SETTLE_S)
    shot = s.capture("bots")
    if shot:
        img, info = shot
        w = info["widgets"]
        s.check("bots", "encart des bots affiché", w["bots_panel"]["visible"] and w["bots_line1"]["visible"]
                and w["bots_line2"]["visible"])
        s.check_texts("bots", info, {"bots_line1": "Bot 250 W", "bots_line2": "Fantôme du 26/10"}, contains=True)
        s.check("bots", "encart sous le panneau de droite", w["bots_panel"]["rect"][1] >= w["panel"]["rect"][1],
                f"rectangle {w['bots_panel']['rect']}")
        b = info.get("bots", {})
        s.check("bots", "bot devant visible dans le champ de la caméra", b.get("shown") == 2 and b.get("in_view", 0) >= 1,
                f"{b}")
        s.check_layout("bots", info)
    core.set_scene(speed=SPEED_MPS, bots=None)
    time.sleep(SETTLE_S)
    shot = s.capture("sans_bot")
    if shot:
        img, info = shot
        s.check("sans_bot", "sans bot : encart caché, aucune silhouette",
                not info["widgets"]["bots_panel"]["visible"] and info.get("bots", {}).get("shown") == 0,
                f"{info.get('bots')}")
    time.sleep(1.0)

    # 3 ter ter. Avatar (lot V6), vu par la caméra de contrôle derrière lui (la caméra du jeu reste
    # subjective, où l'avatar est caché) : visible, jambes à des angles différents sur deux captures
    # espacées (cadence de 37 tr/min : moins d'un tour entre les deux), assis à plat, en danseuse sur une pente de 10 %.
    shot = s.capture("avatar_subjectif")
    if shot:
        s.check("avatar_subjectif", "avatar caché en vue subjective", not shot[1].get("avatar", {}).get("visible", True),
                f"{shot[1].get('avatar')}")
    core.set_scene(speed=0.0, grade=0.0, grade_sent=0.0, power=200.0, power_3s=200.0, cadence=37.0)
    core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "avatar_camera", "view": "follow"})
    time.sleep(1.0)
    a = s.capture("avatar_assis")
    time.sleep(0.37)
    b = s.capture("avatar_assis_2")
    if a and b:
        (img_a, info_a), (img_b, info_b) = a, b
        av_a, av_b = info_a.get("avatar", {}), info_b.get("avatar", {})
        s.check("avatar_assis", "avatar visible dans le champ de la caméra de contrôle",
                av_a.get("visible") and av_a.get("on_screen"), f"{av_a}")
        s.check("avatar_assis", "avatar assis à plat", av_a.get("standing") is False)
        s.check("avatar_assis", "avatar entier (niveau de détail 0)", av_a.get("lod") == 0 and av_a.get("triangles", 0) > 1000,
                f"{av_a.get('triangles')} triangles")
        turn = abs((av_b.get("crank", 0.0) - av_a.get("crank", 0.0) + 3.14159) % 6.28318 - 3.14159)
        s.check("avatar_assis_2", "pédalier à un autre angle d'une capture à l'autre", turn > 0.5, f"{turn:.2f} rad d'écart")
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
        s.check_layout("erg", info)
        s.check_hud_pixels("erg", img, info)
        hist = info["widgets"]["erg_hist"]
        s.check("erg", "histogramme des blocs affiché", hist["visible"] and hist["rect"][2] >= 0.8 * s.width
                and hist["rect"][3] >= 40 * info["ui_scale"] and hist["rect"][1] + hist["rect"][3] <= s.height - 120 * info["ui_scale"],
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
                and chart["rect"][1] + chart["rect"][3] <= s.height - 120 * info["ui_scale"], f"rectangle {chart['rect']}")
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
        s.check_layout("pause", info)

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
        s.check("core_muet_2", "image figée", d < 0.1, f"écart moyen {d:.2f} niveaux")

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
    fps = [c.info.get("fps", 0) for c in s.report.captures if c.config == s.name]
    s.check("journal", "rendu actif (images par seconde)", bool(fps) and max(fps) >= 1, f"fps relevés : {fps}")


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--godot", default=os.environ.get(
        "GODOT", str(Path.home() / "Applications/godot/Godot_v4.3-stable_linux.x86_64")))
    ap.add_argument("--visual-grade", type=float, default=1.0, help="facteur d'exagération visuelle du relief (lot Q2, défaut : 1.0)")
    ap.add_argument("--configs", default=DEFAULT_CONFIGS,
                    help=f"résolution:qualité, séparées par des virgules (défaut {DEFAULT_CONFIGS})")
    ap.add_argument("--out", type=Path, default=None, help="dossier des captures et du rapport (défaut : dossier temporaire)")
    ap.add_argument("--native", action="store_true", help="écran réel et rendu habituel, sans Xvfb")
    ap.add_argument("--golden", default=None, help="dossier des images de référence (un sous-dossier par configuration)")
    ap.add_argument("--update-golden", action="store_true", help="enregistre les captures comme nouvelles références")
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
        for config in [c.strip() for c in args.configs.split(",") if c.strip()]:
            run_config(config, args, routes_dir, out_dir, report)
    finally:
        shutil.rmtree(routes_dir, ignore_errors=True)
    if args.update_golden:
        report.notes.append(f"Références enregistrées dans {args.golden}.")
    page = write_html(report, out_dir, now() - t0)
    fails = report.failures()
    print(f"Tests graphiques : {len(report.checks) - len(fails)}/{len(report.checks)} vérifications réussies")
    print(f"Rapport : {page}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
