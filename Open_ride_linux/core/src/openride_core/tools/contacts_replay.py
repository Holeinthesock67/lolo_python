"""Rejeu des contacts sur la route, sans écran (lot AS11) : vrai core à 50 Hz sur les parcours d'un dossier.

Pour chaque parcours, chaque vitesse visée et chaque jeu de bots : une séance du core (`CoreSession._step`, comme
`draft_bench`) roule le cycliste à la vitesse visée (régulateur de puissance) ; à chaque pas, tous les usagers que
le core fait rouler (cycliste, bots, voiture d'équipe, véhicules de `traffic`, cyclistes du décor de
`road_cyclists`) sont comptés comme `living_decor._count_contacts` de l'engine : deux usagers de groupes différents
se touchent si leurs gabarits se chevauchent en long et en travers. Sortie : contacts par paire de types d'usagers
(images à 50 Hz et épisodes, un épisode étant une paire qui entre en contact), et la signature du premier.

    python -m openride_core.tools.contacts_replay --routes DOSSIER [--kmh 15,30,45,60] [--duree 900] [--bots 0,4]
        [--parcours demo,demo-volcan] [--demi-tour 600] [--json FICHIER]

Code de sortie : 0 sans contact, 1 sinon.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .. import draft as draft_mod
from .. import traffic as traffic_mod
from ..bots import ConstantPowerBot
from ..config import Config
from ..input_providers import NullProvider
from ..mock_driver import MockDriver
from ..session import CoreSession

DT = 0.02
BIKE_HALF_M = 0.85      # living_decor.CONTACT_BIKE_HALF_M : demi-longueur d'un vélo (draft.BIKE_LENGTH_M / 2)
BIKE_HALF_WIDTH_M = 0.3  # traffic_model.RIDER_HALF_WIDTH_M
CONTACT_M = 300.0        # living_decor.CONTACT_M : autour du cycliste
KP_W_PER_MPS = 120.0
BOT_POWERS_W = (180.0, 210.0, 240.0, 270.0, 300.0, 330.0, 200.0, 260.0, 220.0, 280.0)


def usage_kind(name: str) -> str:
    """Type d'usager pour le tableau : véhicule, cycliste du décor, bot, cycliste, voiture d'équipe."""
    if name in traffic_mod.KINDS:
        return "vehicule"
    if name.startswith("escort"):
        return "voiture_equipe"
    if name in ("cycliste",):
        return "cycliste"
    if name.startswith("bot"):
        return "bot"
    return "decor"


def road_items(s: CoreSession) -> list[dict[str, Any]]:
    """Usagers que le core fait rouler, dans le repère de la circulation (celui du sens de marche, lot N23)."""
    tr = s.traffic
    d = s.physics.direction
    model = tr.model_s if tr is not None else (lambda x: x)
    rider_u = model(s.physics.s)
    items: list[dict[str, Any]] = [{"name": "cycliste", "s": rider_u, "lat": s._lane.m, "hl": BIKE_HALF_M,
                                    "hw": BIKE_HALF_WIDTH_M, "group": "me"}]
    length = s.route.length_m if s.route is not None and not s.route.is_loop else None
    for b in s.bots:
        if length is not None and b.s >= length:
            continue   # arrivé : arrêté sur la ligne, hors du jeu (lot PL1), comme pour le placement
        lane = draft_mod.lane_of(b)
        items.append({"name": f"bot:{b.id}", "s": model(b.s),
                      "lat": d * (draft_mod.BOT_LANE_M if lane is None else lane),
                      "hl": BIKE_HALF_M, "hw": BIKE_HALF_WIDTH_M, "group": f"bot:{b.id}"})
    if tr is not None:
        for v in tr.vehicles:
            k = traffic_mod.KINDS[v.kind]
            items.append({"name": v.kind, "s": v.s, "lat": v.lateral, "hl": k["length"] * 0.5,
                          "hw": k["half_width"], "group": f"v:{v.id}"})
    if s.road_cyclists is not None:
        for r in s.road_cyclists.riders():
            items.append({"name": r.case, "s": r.s, "lat": r.lane_m, "hl": BIKE_HALF_M, "hw": BIKE_HALF_WIDTH_M,
                          "group": f"g:{r.group}", "id": r.id})
    for e in getattr(s, "_escorts", []) or []:
        k = traffic_mod.KINDS[e.kind]
        items.append({"name": f"escort:{e.kind}", "s": model(e.s), "lat": d * e.lateral,
                      "hl": k["length"] * 0.5, "hw": k["half_width"], "group": f"e:{e.id}"})
    return [it for it in items if abs(it["s"] - rider_u) <= CONTACT_M]


def contacts_in(items: list[dict[str, Any]]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for i in range(len(items)):
        a = items[i]
        for j in range(i + 1, len(items)):
            b = items[j]
            if a["group"] == b["group"]:
                continue
            if abs(a["s"] - b["s"]) < a["hl"] + b["hl"] and abs(a["lat"] - b["lat"]) < a["hw"] + b["hw"]:
                yield a, b


def pair_key(a: dict[str, Any], b: dict[str, Any]) -> str:
    return " / ".join(sorted((usage_kind(a["name"]), usage_kind(b["name"]))))


def item_id(it: dict[str, Any]) -> str:
    return str(it.get("id", it["group"]))


def state_frame(s: CoreSession, t: float) -> list[Any]:
    """Trame `state` réduite à ce que lit `living_decor.gd` : [t, s, v, dir, lane_m, bots, vehicles, riders,
    road_part], listes construites par les vraies fonctions de la séance (`_fill_vehicles_frame`)."""
    s._frame_count += 1
    s._fill_vehicles_frame()
    s._fill_riders_frame()   # sans effet depuis le lot AS11 (parties de `_fill_vehicles_frame`), utile sur main
    bots = [[round(b.s, 2), round(b.v, 3), round(draft_mod.lane_of(b) if draft_mod.lane_of(b) is not None
                                                else draft_mod.BOT_LANE_M, 2)] for b in s.bots]
    lane = s.physics.direction * s._lane.m   # `lane_m` de la trame : repère de la route (à rebours, à gauche de son axe)
    return [round(t, 4), round(s.physics.s, 3), round(s.physics.v, 3), s.physics.direction, round(lane, 3), bots,
            s.state.vehicles, s.state.riders, getattr(s.state, "road_part", None)]


class Replay:
    def __init__(self, routes: Path, tmp: Path, mode: str = "ride") -> None:
        self.routes, self.tmp, self.n, self.mode = routes, tmp, 0, mode

    def session(self, route_id: str, n_bots: int) -> CoreSession:
        """Séance libre avec `n_bots` bots à puissance constante ; Grand Prix ou Dernier survivant (`mode`) avec
        `n_bots` adversaires à profil (bornes de la configuration)."""
        self.n += 1
        run = self.tmp / f"run{self.n}"
        cfg = Config()
        cfg.depart.mode = "immediat"
        cfg.powerups.mode = "off"
        bots = [] if self.mode != "ride" else \
            [ConstantPowerBot(BOT_POWERS_W[i % len(BOT_POWERS_W)], bot_id=f"b{i + 1}", s=5.0 + 4.0 * i, v=8.0)
             for i in range(n_bots)]
        if self.mode == "grandprix":
            cfg.grandprix.opponents = n_bots
        elif self.mode == "survivor":
            cfg.survivor.opponents = n_bots
        s = CoreSession(cfg, driver=MockDriver(base_power_w=200.0, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=run / "journal", routes_root=self.routes,
                        workouts_dir=run / "workouts", bots=bots, records_path=run / "records.json",
                        powerups_path=run / "powerups.toml", profile_path=run / "profile.json",
                        wtf_path=run / "wtf.toml", grandprix_path=run / "grandprix.toml")
        s.server.send_raw = lambda m, max_size=None: None
        s.server.send_input_event = lambda ev: None
        s._on_command("select_route", {"route_id": route_id}, 1)
        s._on_command("start", {"mode": self.mode} if self.mode != "ride" else {}, 2)
        return s

    def run(self, route_id: str, kmh: float, seconds: float, n_bots: int, u_turn_s: float = 0.0,
            trace: Path | None = None) -> dict[str, Any]:
        """Une passe ; `trace` : trames `state` du core (30 Hz, champs lus par `living_decor.gd`) écrites pour le
        rejeu de l'affichage dans l'engine (`engine/tests/rejeu_contacts.gd`)."""
        s = self.session(route_id, n_bots)
        frames_out: list[list[Any]] = []
        next_frame = 0.0
        target = kmh / 3.6
        frames: Counter[str] = Counter()
        episodes: Counter[str] = Counter()
        first: dict[str, str] = {}
        touching: set[tuple[str, str]] = set()
        t, turned, steps = 0.0, False, 0
        t0 = time.perf_counter()
        length = s.route.length_m if s.route is not None else 0.0
        while t < seconds - 1e-9:
            if s.route is not None and not s.route.is_loop and (s.physics.s > length - 50.0 if s.physics.direction > 0
                                                                 else s.physics.s < 50.0):
                break
            if u_turn_s > 0.0 and not turned and t >= u_turn_s:
                turned = True
                s._u_turn_riding()   # Y maintenu en roulant (révision 1.11), comme au banc demi_tour
            s.driver.base_power_w = min(1000.0, max(0.0, s.driver.base_power_w
                                                    + KP_W_PER_MPS * (target - s.physics.v) * DT))
            s._step(DT, time.monotonic())
            t += DT
            steps += 1
            if trace is not None and t >= next_frame:
                next_frame += 1.0 / 30.0
                frames_out.append(state_frame(s, t))
            now: set[tuple[str, str]] = set()
            for a, b in contacts_in(road_items(s)):
                key = pair_key(a, b)
                frames[key] += 1
                ids = tuple(sorted((item_id(a), item_id(b))))
                now.add(ids)   # type: ignore[arg-type]
                if ids not in touching:
                    episodes[key] += 1
                    rel = a["s"] - road_items(s)[0]["s"]
                    first.setdefault(key, f"{a['name']} / {b['name']} à {rel:.0f} m (écarts {a['lat']:.1f} et "
                                          f"{b['lat']:.1f} m, t = {t:.0f} s, {s.physics.v * 3.6:.0f} km/h)")
            touching = now
        s._finish(save=False)
        if trace is not None:
            trace.write_text(json.dumps({"route": route_id, "frames": frames_out}, separators=(",", ":")),
                             encoding="utf-8")
        return {"route": route_id, "kmh": kmh, "bots": n_bots, "u_turn_s": u_turn_s, "seconds": round(t, 1),
                "distance_m": round(s.physics.s, 0), "frames": dict(frames), "episodes": dict(episodes),
                "first": first, "corrections": dict(getattr(s, "road_space_counts", {})), "step_ms": round((time.perf_counter() - t0) / max(1, steps) * 1000.0, 3)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--routes", type=Path, required=True, help="dossier des parcours (.world)")
    ap.add_argument("--parcours", default="", help="identifiants séparés par des virgules (défaut : tous)")
    ap.add_argument("--kmh", default="15,30,45,60")
    ap.add_argument("--bots", default="0,4")
    ap.add_argument("--duree", type=float, default=900.0, help="secondes simulées par passe")
    ap.add_argument("--demi-tour", type=float, default=0.0, help="demi-tour à N s (0 : jamais)")
    ap.add_argument("--mode", default="ride", choices=("ride", "grandprix", "survivor"),
                    help="séance libre (bots à puissance constante) ou mode de course (adversaires à profil, --bots)")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--traces", type=Path, help="dossier où écrire les trames de chaque passe (rejeu de l'engine)")
    a = ap.parse_args(argv)
    ids = [x for x in a.parcours.split(",") if x] or sorted(p.name[:-6] for p in a.routes.glob("*.world"))
    rows = []
    with tempfile.TemporaryDirectory(prefix="contacts_replay_") as tmp:
        rp = Replay(a.routes, Path(tmp), a.mode)
        for rid in ids:
            for kmh in (float(x) for x in a.kmh.split(",")):
                for nb in (int(x) for x in a.bots.split(",")):
                    tr = None
                    if a.traces:
                        a.traces.mkdir(parents=True, exist_ok=True)
                        tr = a.traces / f"{rid}_{kmh:.0f}_{nb}_{a.mode}{'_dt' if a.demi_tour else ''}.json"
                    r = rp.run(rid, kmh, a.duree, nb, a.demi_tour, tr)
                    rows.append(r)
                    total = sum(r["episodes"].values())
                    print(f"{rid:24s} {kmh:4.0f} km/h bots {nb:2d} {r['distance_m']:7.0f} m : {total:4d} épisodes "
                          f"{sum(r['frames'].values()):6d} images  {r['episodes']}  corrections {r['corrections']}  "
                          f"({r['step_ms']} ms/pas)",
                          flush=True)
                    for k, sig in r["first"].items():
                        print(f"      {k} : {sig}", flush=True)
    if a.json:
        a.json.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if any(r["episodes"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
