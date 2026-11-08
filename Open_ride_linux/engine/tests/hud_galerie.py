#!/usr/bin/env python3
"""Galerie des cas du HUD : chaque situation de séance capturée et contrôlée, à chaque résolution.

    engine/tests/hud_galerie.py [--configs 1024x600:medium,1920x1080:high] [--out DOSSIER] [--cas erg_cible,…]
                                [--native] [--godot GODOT]

L'engine réel tourne avec le faux core de visual_check.py (Xvfb, ou l'écran avec --native) sur le parcours
de démonstration et passe par les cas de CAS : SIM simple, vent et abri, bots avec segment et bonus, ERG
avec une cible courte ou longue, palier de 50 W (FreeRide, lot O19), palier d'un test de FTP avec la FTP provisoire, courbes réduites et complètes, teintes des
zones de puissance et de FC, valeurs extrêmes, Grand Prix des objets (lot GP8 : HUD complet, attaque,
orage et roulette, 12 coureurs, bilan). Sur chaque
capture : panneaux dans l'écran et sans chevauchement, textes dans leur colonne, hauteur et contraste des
chiffres (hud_lisibilite.py), texte attendu des valeurs. Sortie : une capture par cas et par
configuration, une planche par configuration (`planche_<config>.png`, cas dans l'ordre de CAS, trois par
ligne) et le rapport HTML de visual_check (`rapport.html`). Code de sortie : 0 si tout passe, 1 si une
vérification échoue, 2 si Godot ou xvfb-run manque. Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import visual_check as vc  # noqa: E402

DEFAULT_CONFIGS = "1024x600:medium,1920x1080:high"
THUMBS_PER_ROW = 3
THUMB_W = 640

SIM = {"session_state": "RUNNING", "mode": "SIM", "erg": None, "power": 250.0, "power_3s": 248.0, "cadence": 90.0,
       "hr": 142, "grade": 4.5, "grade_sent": 4.5, "gear": 12, "gears_total": 24, "pause_reason": None,
       "trainer_status": "CONNECTED", "input_status": "CONNECTED", "wind": None, "draft": 0.0, "draft_w": None, "bots": None,
       "bot_ahead": None, "bot_behind": None, "jerseys": None, "segment": None, "powerup": None}


# Teintes du texte par zone (UiTheme.ZONE_TEXT_1 à 7) : puissance selon la FTP (250 W du faux core), fréquence
# cardiaque selon la FC max (185 bpm du faux core).
ZONE_TEXT = {1: (0.93, 0.94, 0.96), 2: (0.70, 0.84, 1.00), 3: (0.62, 0.95, 0.66), 4: (1.00, 0.89, 0.48),
             5: (1.00, 0.77, 0.54), 6: (1.00, 0.72, 0.86), 7: (0.86, 0.76, 1.00)}


def zone_color_ok(html: str, zone: int) -> bool:
    """Couleur `to_html(false)` de Godot égale (à un pas de 8 bits près) à la teinte de la zone."""
    rgb = [int(html[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return all(abs(a - b) <= 1.5 / 255.0 for a, b in zip(rgb, ZONE_TEXT[zone]))


def _erg(target_w: float, bias_pct: int, block_type: str = "interval_on") -> dict[str, Any]:
    return {"workout_name": "Sweet spot 3x10", "block_index": 2, "block_count": 7, "block_type": block_type,
            "block_remaining_s": 95.0, "block_total_s": 600.0, "target_w": target_w, "next_target_w": 150.0,
            "bias_pct": bias_pct, "paused": False}


def _bots(s_now: float) -> list[dict[str, Any]]:
    return [{k: v for k, v in b.items() if k != "ds"} | {"s": s_now + b["ds"], "v": 0.0, "kind": "constant"}
            for b in vc.PROFILE_BOTS]


# Grand Prix des objets (lot GP8, maquettes GP6 scènes 3, 4, 6 et 7) : bots de la scène 6 (écart au cycliste en s,
# objet tenu, effets en cours) placés à `ds` mètres du cycliste ; objets de `gp.obj` donnés en mètres devant lui.
GP_BOTS = [("Grimpeur", 60.0, 6.4, "bell", []), ("Rouleur", 40.0, 4.3, None, []), ("Sprinteur", -6.0, -0.6, "bottle", []),
           ("Diesel", -60.0, -6.4, None, ["musette"])]
GP_BASE = {"place": 3, "of": 5, "gap_s": 2.1, "held": "musette_x3", "n": 3, "roll_s": 0.0, "lane": 1, "auto": False,
           "fx": [], "warn": None, "obj": [], "boxes": [], "pick": True, "lap": [2, 3]}


def _gp_bots(s_now: float, count: int = 0) -> list[dict[str, Any]]:
    """Bots du Grand Prix : ceux de la scène 6, ou `count` bots en file (cas des 12 coureurs)."""
    if count:
        items = ["gel", "bottle", None, "musette", "bell", None, "homing", "star", None, "storm", "team_car"]
        return [{"id": f"g{i}", "name": f"Coureur {i + 1}", "s": s_now + 120.0 - 30.0 * i, "v": 0.0, "kind": "constant",
                 "gap_s": (120.0 - 30.0 * i) / 10.0, "item": items[i % len(items)], "fx": ["bottle"] if i == 9 else []}
                for i in range(count)]
    return [{"id": f"g{i}", "name": n, "s": s_now + ds, "v": 0.0, "kind": "constant", "gap_s": gap, "item": item, "fx": fx}
            for i, (n, ds, gap, item, fx) in enumerate(GP_BOTS)]


def _gp(s_now: float, spec: dict[str, Any]) -> dict[str, Any]:
    gp = GP_BASE | {k: v for k, v in spec.items() if k != "obj_ahead"}
    gp["obj"] = [[i + 1, kind, round(s_now + ds, 1), lane] for i, (kind, ds, lane) in enumerate(spec.get("obj_ahead", []))]
    return gp


GP_SUMMARY = {"duration_s": 1455.0, "distance_m": 15200.0, "avg_power_w": 246.0, "fit_path": "/tmp/openride/seance.fit",
              "gp": {"place": 2, "of": 5, "launched": {"gel": 2, "musette_x3": 1, "bottle": 1},
                     "received": {"homing": 1, "bottle": 1}, "dodged": 4,
                     "gained_s": {"gel": 7.6, "musette_x3": 5.2, "bottle": 2.1}, "lost_s": {"homing": 3.9, "bottle": 3.7},
                     "distance_km": 15.2}}


# Cas : nom, valeurs de la trame `state` (par-dessus SIM), textes attendus des widgets, zones attendues des
# teintes (zones, de 1 à 7), widgets visibles ou cachés, taille des courbes (chart, None : courbes cachées)
# et attente avant la capture.
CAS: list[dict[str, Any]] = [
    {"name": "sim", "state": {}, "texts": {"power": "248", "grade": "+4.5 %"}, "zones": {"power": 4, "hr": 3},
     "shown": ["gear", "profile"], "hidden": ["target", "erg_hist"]},
    {"name": "zones_recuperation", "state": {"power": 100.0, "power_3s": 100.0, "hr": 100},
     "zones": {"power": 1, "hr": 1}},
    {"name": "zones_sprint", "state": {"power": 450.0, "power_3s": 450.0, "hr": 176},
     "zones": {"power": 7, "hr": 5}},
    {"name": "zones_seuil_vo2", "state": {"power": 330.0, "power_3s": 330.0, "hr": 120},
     "zones": {"power": 6, "hr": 2}},
    {"name": "sim_vent_abri", "state": {"wind": {"speed_mps": 26.0 / 3.6, "from_deg": 100.0, "gust": 0.0,
                                                 "head_mps": 26.0 / 3.6, "grade_pct": 1.2}, "draft": 0.165,
                                       "draft_w": 48},
     "texts": {"draft": "Abri 30 %", "draft_w": "−48 W"}, "shown": ["wind", "draft", "draft_w"]},
    {"name": "sim_bots_segment_bonus", "bots": True,
     "state": {"bot_ahead": "b2", "bot_behind": "b3", "jerseys": {"sprint": "b3", "kom": "b1"},
               "segment": {"id": "climb1", "kind": "climb", "category": "4", "d_to_start_m": 0.0,
                           "elapsed_s": 42.0, "gap_to_pr_s": -1.6},
               "powerup": {"held": "aero", "active": None, "remaining_s": 0.0}},
     "shown": ["bots_panel", "segment_panel", "bonus_panel"]},
    {"name": "erg_cible", "state": {"mode": "ERG", "erg": _erg(230.0, 100)}, "texts": {"target": "230 W"},
     "shown": ["target", "erg_hist"], "hidden": ["gear", "profile"]},
    {"name": "erg_cible_longue", "state": {"mode": "ERG", "erg": _erg(152.0, 98)}, "texts": {"target": "152 W (98 %)"},
     "hidden": ["gear", "profile"]},
    {"name": "erg_palier_50w", "state": {"mode": "ERG", "erg": _erg(50.0, 98, "steady")}, "texts": {"target": "50 W (98 %)"},
     "hidden": ["gear", "profile"]},
    {"name": "erg_test_ftp", "state": {"mode": "ERG", "erg": _erg(300.0, 100, "steady") | {
        "workout_name": "Test de FTP : rampe", "block_index": 12, "block_count": 33, "block_remaining_s": 40.0,
        "block_total_s": 60.0, "next_target_w": 320.0, "bias_locked": True, "ftp_test": "ramp",
        "ftp_provisional_w": 214}},
     "texts": {"erg_next": "Ensuite : 320 W · FTP provisoire : 214 W"}, "hidden": ["gear", "profile"]},
    {"name": "erg_courbes_reduites", "state": {"mode": "ERG", "erg": _erg(230.0, 100)}, "chart": "reduced", "wait": 7.0,
     "shown": ["chart_erg"], "hidden": ["profile"]},
    {"name": "erg_courbes_completes", "state": {"mode": "ERG", "erg": _erg(230.0, 100)}, "chart": "full", "wait": 7.0,
     "shown": ["chart_erg"], "hidden": ["profile"]},
    {"name": "sim_courbes", "state": {}, "chart": "full", "wait": 7.0, "shown": ["chart_sim", "profile"]},
    {"name": "valeurs_extremes", "state": {"power": 1999.0, "power_3s": 1999.0, "cadence": 199.0, "hr": 199,
                                           "grade": -19.9, "grade_sent": -19.9, "mode": "ERG",
                                           "erg": _erg(1999.0, 150)},
     "texts": {"power": "1999"}},
    # Grand Prix des objets (lot GP8) : HUD complet (maquette 6), attaque (maquette 3), orage, roulette et
    # super-forme (maquette 4), 12 coureurs (lot GP10), bilan (maquette 7, en dernier : écran de fin de séance)
    {"name": "gp_hud", "gp": {"obj_ahead": [("bottle", 60.0, 1)]},
     "expect": {"item": "musette_x3", "key": "Z : Trois musettes", "place": "3e / 5", "warn": "",
                "hint": "Bidon glissant en vue : A ou ← →"}, "hidden": ["bots_panel"]},
    {"name": "gp_attaque", "gp": {"n": 2, "warn": ["homing", 42.0], "obj_ahead": [("homing", -42.0, 1), ("bottle", 25.0, 0)]},
     "expect": {"warn": "Musette guidée derrière !", "outline": True}},
    {"name": "gp_orage_roulette", "gp": {"roll_s": 1.2, "held": None, "n": 0, "fx": [["star", 5.2]], "auto": True,
                                         "lane": 2, "pick": False, "obj_ahead": [("storm", 140.0, -1)]},
     "expect": {"warn": "Orage vers le premier", "outline": False, "hint": "← → : voie"}},
    {"name": "gp_12_coureurs", "gp": {"place": 9, "of": 12, "gap_s": 3.0, "held": "homing", "n": 1, "lap": None},
     "gp_count": 11, "expect": {"place": "9e / 12", "key": "Z : Musette guidée"}},
    {"name": "gp_bilan", "state": {"session_state": "FINISHED", "summary": GP_SUMMARY},
     "texts_contains": {"menu": "Grand Prix des objets : 2e sur 5"}},
]


def _cases(s: vc.Session, names: list[str] | None) -> None:
    core = s.core
    t0 = vc.now()
    while vc.now() - t0 < 20.0 and "IpcClient attaché" not in core.log.path.read_text(errors="replace"):
        time.sleep(0.1)
    time.sleep(1.5)
    core.set_scene(speed=0.0, s=vc.FIXED_S, **SIM)
    core.auto_hello_ack = True
    core.catalog_data = vc.MENU_CATALOG
    core.streaming = True
    loaded = core.log.wait_for(r"^route_loaded id=demo", vc.ROUTE_TIMEOUT_S)
    s.check("galerie", "parcours demo chargé", loaded is not None, loaded[1].string if loaded else "aucun route_loaded")
    time.sleep(vc.SETTLE_S)
    for cas in CAS:
        if names and cas["name"] not in names:
            continue
        chart = cas.get("chart")
        if chart != core.chart:
            core.chart = chart
            core.send_hello_ack()
        state = dict(SIM) | cas.get("state", {})
        if cas.get("bots"):
            state["bots"] = _bots(core.current_s())
        if "gp" in cas:
            gp = _gp(core.current_s(), cas["gp"])
            if gp.get("lap") is None:
                gp.pop("lap")
            state |= {"gp": gp, "bots": _gp_bots(core.current_s(), cas.get("gp_count", 0)), "summary": None}
        else:
            state["gp"] = None
        core.set_scene(speed=7.0 if chart else 0.0, **state)
        time.sleep(cas.get("wait", vc.SETTLE_S))
        shot = s.capture(cas["name"])
        if not shot:
            continue
        img, info = shot
        w = info["widgets"]
        if cas.get("texts"):
            s.check_texts(cas["name"], info, cas["texts"])
        if cas.get("texts_contains"):
            s.check_texts(cas["name"], info, cas["texts_contains"], contains=True)
        gp_info = info.get("grandprix", {})
        for key, want in cas.get("expect", {}).items():
            s.check(cas["name"], f"Grand Prix : {key} = {want!r}", gp_info.get(key) == want, f"affiché {gp_info.get(key)!r}")
        for key, zone in cas.get("zones", {}).items():
            s.check(cas["name"], f"{key} teinté en zone {zone}", zone_color_ok(w[key]["color"], zone),
                    f"teinte #{w[key]['color']}")
        for key in cas.get("shown", []):
            s.check(cas["name"], f"{key} affiché", w[key]["visible"])
        for key in cas.get("hidden", []):
            s.check(cas["name"], f"{key} caché", not w[key]["visible"])
        s.check_layout(cas["name"], info)
        s.check_hud_pixels(cas["name"], img, info)
    core.chart = None
    core.send_hello_ack()


def _thumb(img: vc.Image, width: int) -> vc.Image:
    """Réduction au plus proche voisin (bibliothèque standard)."""
    k = img.width / width
    height = max(1, int(img.height / k))
    out = bytearray(width * height * 3)
    for y in range(height):
        sy = min(img.height - 1, int(y * k))
        for x in range(width):
            i = (sy * img.width + min(img.width - 1, int(x * k))) * 3
            o = (y * width + x) * 3
            out[o:o + 3] = img.rgb[i:i + 3]
    return vc.Image(width, height, bytes(out))


def write_sheet(paths: list[Path], dest: Path) -> None:
    """Planche des captures, THUMBS_PER_ROW par ligne, 8 px entre les vignettes."""
    thumbs = [_thumb(vc.read_png(p), THUMB_W) for p in paths]
    if not thumbs:
        return
    gap = 8
    th = max(t.height for t in thumbs)
    cols = min(THUMBS_PER_ROW, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    width = cols * THUMB_W + (cols + 1) * gap
    height = rows * th + (rows + 1) * gap
    out = bytearray(width * height * 3)
    for n, t in enumerate(thumbs):
        x0 = gap + (n % cols) * (THUMB_W + gap)
        y0 = gap + (n // cols) * (th + gap)
        for y in range(t.height):
            o = ((y0 + y) * width + x0) * 3
            out[o:o + t.width * 3] = t.rgb[y * t.width * 3:(y + 1) * t.width * 3]
    vc.write_png(dest, vc.Image(width, height, bytes(out)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--godot", default=os.environ.get(
        "GODOT", str(Path.home() / "Applications/godot/Godot_v4.7.2-stable_linux.x86_64")))
    ap.add_argument("--configs", default=DEFAULT_CONFIGS, help=f"résolution:qualité, séparées par des virgules (défaut {DEFAULT_CONFIGS})")
    ap.add_argument("--out", type=Path, default=None, help="dossier des captures, des planches et du rapport")
    ap.add_argument("--cas", default="", help="cas à jouer, séparés par des virgules (défaut : tous) : "
                    + ", ".join(c["name"] for c in CAS))
    ap.add_argument("--native", action="store_true", help="écran réel et rendu habituel, sans Xvfb")
    args = ap.parse_args()
    args.visual_grade, args.golden, args.update_golden, args.lisibilite = 1.0, None, False, True
    args.fige, args.decor_vivant = None, "on"   # options de visual_check : scène animée, décor vivant
    names = [n.strip() for n in args.cas.split(",") if n.strip()] or None
    unknown = [n for n in names or [] if n not in {c["name"] for c in CAS}]
    if unknown:
        ap.error("cas inconnus : " + ", ".join(unknown))
    if not (Path(args.godot).is_file() and os.access(args.godot, os.X_OK)):
        print(f"Godot introuvable : {args.godot} (définir GODOT=/chemin/vers/godot)")
        return 2
    if not args.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable : installer xvfb, xauth et mesa-vulkan-drivers (ou lancer avec --native)")
        return 2

    out_dir = args.out or Path(tempfile.mkdtemp(prefix="openride-hud-galerie-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    routes_dir = Path(tempfile.mkdtemp(prefix="openride-hud-galerie-routes-"))
    report = vc.Report()
    t0 = vc.now()
    try:
        gen = subprocess.run([sys.executable, "-m", "openride_core.tools.fake_world", "--demo", "--terrain",
                              "--out", str(routes_dir)], env={**os.environ, "PYTHONPATH": str(vc.CORE_SRC)},
                             capture_output=True, text=True)
        if gen.returncode != 0:
            print("Génération du parcours demo avec terrain impossible :\n" + gen.stderr)
            return 1
        for config in [c.strip() for c in args.configs.split(",") if c.strip()]:
            vc.run_config(config, args, routes_dir, out_dir, report, scenes=lambda s: _cases(s, names))
            size, _, quality = config.partition(":")
            name = f"{size}_{quality or 'low'}"
            shots = [out_dir / f"{name}_{c['name']}.png" for c in CAS if not names or c["name"] in names]
            write_sheet([p for p in shots if p.exists()], out_dir / f"planche_{name}.png")
    finally:
        shutil.rmtree(routes_dir, ignore_errors=True)
    page = vc.write_html(report, out_dir, vc.now() - t0)
    fails = report.failures()
    print(f"Galerie du HUD : {len(report.checks) - len(fails)}/{len(report.checks)} vérifications réussies")
    print(f"Rapport : {page}")
    print(f"Planches : {', '.join(str(p) for p in sorted(out_dir.glob('planche_*.png')))}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
