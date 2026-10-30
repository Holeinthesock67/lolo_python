"""Campagne simulée accélérée sur le profil d'essai (série MJ, lot MJ3).

    python -m openride_core.tools.campagne_profil [--seances 8] [--graine 7] [--json] [--reel]

La vraie séance du core (`CoreSession`) tourne sans engine ni trainer réel, au pas d'une seconde,
sur le profil d'essai `_essai` : sessions libres à différentes intensités, une séance ERG terminée
et une abandonnée, une séance trop courte, une run Cyber-Rogue (à partir de 8 séances). Entre les
séances, les commandes du Garage passent par le même chemin que celles de l'engine : `list_garage`,
`buy` refusé faute de pièces puis accepté, `equip`, `set_avatar`. Au milieu de la campagne, le core
est « relancé » (nouvelle `CoreSession`) : le profil et le solde doivent survivre.

Vérifications : expérience de chaque `xp_result` = expérience recalculée depuis le journal (comme
`openride-core xp`) ; niveau conforme aux seuils ; défis débloqués une seule fois ; solde = gagnées
− dépensées ; achat présent dans `profile.json` et appliqué à la physique (`loadout` de l'en-tête du
journal suivant) ; séance trop courte sans gain ; journaux marqués `profile_id = "_essai"` ; rien
d'écrit hors du dossier du profil d'essai ; **empreinte SHA-256 du vrai profil identique avant et
après** (contexte historique de `~/OpenRide`, `Profils/*` hors `_essai`, `config.toml`).

Par défaut, tout se passe dans un dossier temporaire : un faux profil `principal` y sert de vrai
profil, et le profil d'essai reçoit une surcharge `progression.toml` qui accélère l'expérience et
les pièces (gains ×10). `--reel` roule sur le vrai `~/OpenRide/Profils/_essai/` (PC), sans toucher
sa surcharge. L'horloge est simulée : les séances sont datées d'un jour à l'autre.

Code de sortie : 0 si toutes les vérifications passent, 1 sinon, 2 pour un appel invalide.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import tempfile
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from unittest import mock

from .. import coins as coins_mod
from .. import config as config_mod
from .. import profiles
from ..config import Config
from ..garage import workout_duration_finder
from ..input_providers import NullProvider
from ..journal import read_journal
from ..mock_driver import MockDriver
from ..physics import PhysicsParams
from ..progression import level_for, load_table, recompute
from ..session import CoreSession

DT = 1.0                                  # pas de la séance simulée (s)
DAY_S = 86400.0
START_TS = 1_790_000_000.0                # horloge simulée : première séance (sept. 2026)
FTP_W = 250.0
WORKOUT_ID = "campagne_court"
WORKOUT_ZWO = """<workout_file>
  <name>Campagne courte</name>
  <workout>
    <SteadyState Duration="180" Power="0.60"/>
    <SteadyState Duration="300" Power="0.85"/>
    <SteadyState Duration="120" Power="0.55"/>
  </workout>
</workout_file>
"""
# Surcharge du profil d'essai en dossier temporaire (donnée, pas de triche) : expérience ×10 pour
# franchir vite les niveaux, pièces à l'effort ×2 (la première séance ne suffit pas à un achat).
FAST_TABLE = """# Campagne simulée (lot MJ3) : gains accélérés, propres au profil d'essai.
[xp]
per_km = 200
per_climb_m = 20
erg_per_min = 100
[coins]
effort = [[0, 0.5], [55, 1.0], [75, 2.0], [90, 3.0], [105, 4.0]]
"""
AVATAR = {"height": "L", "build": "slim"}


class CampaignError(Exception):
    """Appel invalide."""


@dataclass(frozen=True)
class Ride:
    kind: str            # libre, erg_fini, erg_abandon, court, rogue
    minutes: float
    power_pct: float     # % de la FTP (sessions libres et cycliste de la run)


def program(n: int, seed: int) -> list[Ride]:
    """Séances de la campagne : toujours une trop courte, une ERG terminée et une abandonnée."""
    if n < 4:
        raise CampaignError("au moins 4 séances (libre, trop courte, ERG terminée, ERG abandonnée)")
    rng = random.Random(seed)
    fixed = [Ride("libre", 25, 70), Ride("court", 2, 70), Ride("erg_fini", 10, 0), Ride("erg_abandon", 6, 0)]
    if n >= 8:
        fixed.append(Ride("rogue", 30, 85))
    while len(fixed) < n:
        fixed.append(Ride("libre", rng.choice((20, 30, 40)), rng.choice((60, 75, 90))))
    first, rest = fixed[:1], fixed[1:]
    rng.shuffle(rest)
    return first + rest


@dataclass
class Report:
    seances: int
    seed: int
    home: str
    checks: list[tuple[bool | None, str, str]] = field(default_factory=list)
    rides: list[dict] = field(default_factory=list)
    wall_s: float = 0.0

    @property
    def ok(self) -> bool:
        return all(c[0] is not False for c in self.checks)

    def add(self, ok: bool | None, label: str, detail: str) -> None:
        self.checks.append((ok, label, detail))


# --- empreinte du vrai profil ----------------------------------------------------------------

def _files(path: Path) -> Iterator[Path]:
    if path.is_file():
        yield path
    elif path.is_dir():
        yield from sorted(p for p in path.rglob("*") if p.is_file())


def true_profile_paths(home: Path, legacy: profiles.ProfileContext) -> list[Path]:
    """Ce qui appartient au vrai joueur : contexte historique, profils joueurs, configuration."""
    paths = [legacy.profile_path, legacy.records_path, legacy.plan_state_path, legacy.activities_dir,
             home / "config.toml"]
    base = home / profiles.PROFILES_DIRNAME
    if base.is_dir():
        paths += sorted(p for p in base.iterdir() if p.name != profiles.TRIAL_ID)
    return paths


def fingerprint(paths: list[Path]) -> tuple[str, int]:
    """SHA-256 des chemins et contenus (fichiers absents compris) ; nombre de fichiers lus."""
    h = hashlib.sha256()
    count = 0
    for root in paths:
        h.update(f"<{root}>".encode())
        for f in _files(root):
            if f.name == profiles.LOCK_NAME:
                continue
            h.update(str(f.relative_to(root) if f != root else f.name).encode() + b"\0")
            h.update(f.read_bytes())
            count += 1
    return h.hexdigest(), count


def _tree(root: Path) -> set[Path]:
    return set(_files(root)) if root.is_dir() else set()


# --- horloge simulée --------------------------------------------------------------------------

class Clock:
    """`time.time()` et `time.strftime()` simulés : séances datées, noms de journaux distincts."""

    def __init__(self, start: float) -> None:
        self.now = start
        self._strftime = time.strftime
        self._localtime = time.localtime

    def time(self) -> float:
        return self.now

    def strftime(self, fmt: str, t: Any = None) -> str:
        return self._strftime(fmt, t if t is not None else self._localtime(self.now))

    def patches(self) -> list:
        return [mock.patch("time.time", self.time), mock.patch("time.strftime", self.strftime)]


# --- campagne --------------------------------------------------------------------------------

class Campaign:
    def __init__(self, rep: Report, ctx: profiles.ProfileContext, work: Path, clock: Clock,
                 reel: bool = False) -> None:
        self.rep, self.ctx, self.work, self.clock, self.reel = rep, ctx, work, clock, reel
        self.sent: list[dict] = []
        self.cmd_id = 0
        self.cfg = Config()
        self.cfg.rider.ftp_w = FTP_W
        self.driver = MockDriver(base_power_w=0.0, ramp_amplitude_w=0.0)
        self.session = self._new_session()
        self.xp_results: list[dict] = []
        self.challenges_seen: list[str] = []
        self.bought: str | None = None
        self.bought_slot: str | None = None
        self.refused = False
        self.listed = False

    def _new_session(self) -> CoreSession:
        s = CoreSession(self.cfg, driver=self.driver, inputs=[NullProvider()],
                        routes_root=self.work / "routes", workouts_dir=self.work / "workouts",
                        powerups_path=self.work / "powerups.toml", config_path=self.work / "config.toml")
        s.server.send_raw = lambda m, max_size=None: self.sent.append(m)
        s.server.send_input_event = lambda ev: None
        return s

    def command(self, name: str, args: dict | None = None) -> list[dict]:
        self.cmd_id += 1
        n0 = len(self.sent)
        self.session._on_command(name, args or {}, self.cmd_id)
        return self.sent[n0:]

    def _ride_steps(self, seconds: float, power_w: float) -> None:
        s = self.session
        self.driver.base_power_w, self.driver.base_cadence_rpm = power_w, 88.0
        end = s._t_session + seconds
        while s._t_session < end and s.state.session_state == "RUNNING":
            self.clock.now += DT
            s._step(DT, self.clock.now)

    def ride(self, ride: Ride) -> dict:
        s = self.session
        self.clock.now += DAY_S
        if ride.kind in ("erg_fini", "erg_abandon"):
            self.command("select_workout", {"workout_id": WORKOUT_ID})
        else:
            self.command("select_workout", {"workout_id": None})
        n0 = len(self.sent)
        if ride.kind == "rogue":
            self.command("start_run", {"objective": "threshold", "duration_min": int(ride.minutes), "seed": 3})
        else:
            self.command("select_route", {"route_id": "demo"})
        self.command("start")
        # En ERG, le trainer simulé suit la cible de l'entraînement ; la run s'arrête d'elle-même.
        self._ride_steps(ride.minutes * 60.0 if ride.kind != "rogue" else 3 * 3600.0,
                         ride.power_pct / 100.0 * FTP_W)
        if s.state.session_state == "RUNNING":
            self.command("end_session", {"save": True})
        results = [m for m in self.sent[n0:] if m.get("type") == "xp_result"]
        journal = sorted(self.ctx.journal_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)[-1]
        head = next(iter(read_journal(journal)), {})
        res = results[-1] if results else {}
        info = {"kind": ride.kind, "minutes": round(s._t_session / 60.0, 1), "journal": journal.name,
                "eligible": res.get("eligible"), "reason": res.get("reason"), "xp": res.get("total", 0),
                "coins": res.get("coins_gained", 0), "level": res.get("level_after"),
                "loadout": head.get("loadout"), "profile_id": head.get("profile_id")}
        self.rep.rides.append(info)
        if res:
            self.xp_results.append(res)
            self.challenges_seen += [c["id"] for c in res.get("challenges", [])]
        self.command("select_route", {"route_id": "demo"})   # retour à READY : le Garage répond
        return info

    # --- Garage ---------------------------------------------------------------------------

    def _target_item(self) -> Any:
        """Pièce à vendre la moins chère du niveau atteint, hors pièces possédées."""
        svc = self.session.progress_svc
        owned = coins_mod.owned_items(svc.progress, svc.profile, svc.catalogue)
        lvl = svc.progress.level.level
        items = [i for i in svc.catalogue.items.values()
                 if i.buyable and not i.default and i.id not in owned and i.level <= lvl and i.slot in ("frame", "wheels")]
        return min(items, key=lambda i: (i.price, i.id)) if items else None

    def garage_round(self) -> None:
        svc = self.session.progress_svc
        listing = self.command("list_garage")
        if not self.listed:
            self.listed = True
            self.rep.add(any(m.get("type") == "garage" for m in listing), "catalogue du Garage (list_garage)",
                         f"{sum(1 for m in listing if m.get('type') == 'garage')} partie(s)")
        item = self._target_item()
        if item is None or self.bought:
            return
        bal = svc.balance()
        out = self.command("buy", {"item_id": item.id})
        errors = [m.get("code") for m in out if m.get("type") == "error"]
        if bal < item.price:
            if not self.refused:
                self.refused = True
                self.rep.add(errors == ["not_enough_coins"], "achat refusé faute de pièces",
                             f"{item.id} à {item.price} pièces, solde {bal} : {errors or 'accepté'}")
            return
        ok = not errors and item.id in svc.profile.purchased
        on_disk = item.id in {p["item_id"] for p in json.loads(self.ctx.profile_path.read_text("utf-8"))["purchases"]}
        self.rep.add(ok and on_disk and svc.balance() == bal - item.price, "achat accepté",
                     f"{item.id} à {item.price} pièces, solde {bal} → {svc.balance()}, profile.json "
                     f"{'à jour' if on_disk else 'sans l’achat'}")
        out = self.command("equip", {"slot": item.slot, "item_id": item.id})
        self.rep.add(not [m for m in out if m.get("type") == "error"] and svc.profile.equipped[item.slot] == item.id,
                     "équipement porté (equip)", f"{item.slot} = {svc.profile.equipped.get(item.slot)}")
        head = svc.journal_header() or {}   # en-tête du journal de la prochaine séance
        lo = head.get("loadout") or {}
        plain = PhysicsParams.from_config(self.cfg)
        self.rep.add(lo.get(item.slot) == item.id and bool(lo.get("mass_delta_kg") or lo.get("cda_delta_pct"))
                     and self.session.physics.p != plain, "équipement appliqué à la physique",
                     f"loadout {lo}, masse {plain.mass_kg:.2f} → {self.session.physics.p.mass_kg:.2f} kg, "
                     f"CdA {plain.cda_m2:.4f} → {self.session.physics.p.cda_m2:.4f} m²")
        out = self.command("set_avatar", {"avatar": dict(svc.profile.avatar, **AVATAR)})
        self.rep.add(not [m for m in out if m.get("type") == "error"]
                     and all(svc.profile.avatar.get(k) == v for k, v in AVATAR.items()),
                     "avatar modifié (set_avatar)", ", ".join(f"{k} {svc.profile.avatar.get(k)}" for k in AVATAR))
        self.bought = item.id
        self.bought_slot = item.slot

    def restart(self) -> None:
        """Arrêt et relance du core : nouvelle séance du core, mêmes fichiers."""
        svc = self.session.progress_svc
        before = (svc.balance(), dict(svc.profile.equipped), svc.progress.total_xp)
        self.session = self._new_session()
        svc = self.session.progress_svc
        after = (svc.balance(), dict(svc.profile.equipped), svc.progress.total_xp)
        self.rep.add(before == after, "relance du core : profil, solde et expérience gardés",
                     f"solde {before[0]} → {after[0]}, XP {before[2]} → {after[2]}")


def _check_progression(rep: Report, camp: Campaign) -> None:
    ctx, svc = camp.ctx, camp.session.progress_svc
    table = load_table(ctx.table_path)
    progress = recompute(ctx.journal_dir, table, workout_duration_finder(camp.work / "workouts"),
                         counted=ctx.counted_sources, owns=ctx.owns)
    last = camp.xp_results[-1] if camp.xp_results else {}
    rep.add(last.get("xp_total") == progress.total_xp, "expérience du dernier xp_result = recalcul du journal",
            f"{last.get('xp_total')} contre {progress.total_xp} (openride-core xp)")
    per_session = sum(r["xp"] for r in rep.rides)
    rep.add(per_session == progress.total_xp, "somme des gains de séance = expérience totale",
            f"{per_session} contre {progress.total_xp}")
    rep.add(level_for(progress.total_xp, table).level == last.get("level_after"), "niveau conforme aux seuils",
            f"niveau {last.get('level_after')} pour {progress.total_xp} XP")
    rep.add(len(camp.challenges_seen) == len(set(camp.challenges_seen)), "défis débloqués une seule fois",
            ", ".join(camp.challenges_seen) or "aucun défi")
    earned = coins_mod.earned_coins(progress, svc.ct)
    spent = sum(p["price"] for p in svc.profile.purchases) + svc.profile.lives.get("spent", 0)
    rep.add(svc.balance() == max(earned - spent, 0) == last.get("coins_total", svc.balance()),
            "solde = gagnées − dépensées", f"{earned} − {spent} = {svc.balance()}")
    short = [r for r in rep.rides if r["kind"] == "court"]
    rep.add(bool(short) and all(not r["eligible"] and r["reason"] == "too_short" and r["xp"] == 0 for r in short),
            "séance trop courte : rien", f"{[(r['eligible'], r['reason']) for r in short]}")
    sims = [r for r in rep.rides if r["kind"] != "court"]
    rep.add(all(r["eligible"] for r in sims), "séances simulées comptées sur le profil d'essai",
            f"{sum(1 for r in sims if r['eligible'])}/{len(sims)} comptées")
    rep.add(all(r["profile_id"] == ctx.id for r in rep.rides), "journaux marqués profile_id = _essai",
            f"{sorted({str(r['profile_id']) for r in rep.rides})}")
    if camp.bought:
        after = [r for r in rep.rides if r.get("after_buy") and r["kind"] != "rogue"]   # run : sans équipement
        applied = [r for r in after if (r["loadout"] or {}).get(camp.bought_slot) == camp.bought]
        if after:
            rep.add(len(applied) == len(after), "journaux des séances suivantes avec l'équipement acheté (loadout)",
                    f"{len(applied)}/{len(after)} séance(s) après l'achat avec {camp.bought}")
    else:
        rep.add(False, "achat accepté", "aucune pièce achetée pendant la campagne")
    if not camp.refused:   # sur le vrai profil d'essai, le solde peut déjà suffire : simple information
        rep.add(None if camp.reel else False, "achat refusé faute de pièces", "jamais essayé : solde suffisant")


def run(seances: int = 8, seed: int = 7, reel: bool = False) -> Report:
    rides = program(seances, seed)
    t_wall = time.perf_counter()
    with ExitStack() as stack:
        if reel:
            home = config_mod.OPENRIDE_HOME
        else:
            home = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="openride-campagne-"))) / "OpenRide"
            stack.enter_context(mock.patch.object(config_mod, "OPENRIDE_HOME", home))
        rep = Report(seances, seed, str(home))
        work = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="openride-campagne-travail-")))
        (work / "workouts").mkdir()
        (work / "workouts" / f"{WORKOUT_ID}.zwo").write_text(WORKOUT_ZWO, encoding="utf-8")
        previous = profiles._active
        legacy = profiles.ProfileContext.legacy()
        if not reel:   # faux vrai profil : un joueur avec une séance et un équipement
            principal = profiles.ProfileContext.for_id("principal")
            principal.journal_dir.mkdir(parents=True)
            (principal.journal_dir / "2026-09-01_08-00-00.jsonl").write_text(
                '{"kind":"header","version":1,"route_id":"demo","workout_id":null,"source":"live"}\n', "utf-8")
            principal.profile_path.write_text('{"version": 1, "equipped": {}, "purchases": []}\n', "utf-8")
            (home / "config.toml").write_text("[rider]\nftp_w = 250\n", encoding="utf-8")
        ctx = profiles.ProfileContext.for_id(profiles.TRIAL_ID)
        if not reel:
            ctx.root.mkdir(parents=True)
            (ctx.root / "progression.toml").write_text(FAST_TABLE, encoding="utf-8")
        watched = true_profile_paths(home, legacy)
        print_before, n_files = fingerprint(watched)
        tree_before = _tree(home)
        stack.enter_context(profiles.ProfileLock(ctx))   # pas pendant une séance d'essai
        profiles.ensure_description(ctx)
        profiles.activate(ctx)
        stack.callback(profiles.activate, previous)
        clock = Clock(START_TS)
        for p in clock.patches():
            stack.enter_context(p)
        camp = Campaign(rep, ctx, work, clock, reel)
        rep.add(camp.session.progress_svc.enabled, "progression du profil d'essai chargée",
                f"{ctx.root} ; séances comptées : {', '.join(ctx.counted_sources)}")
        middle = len(rides) // 2
        for i, ride in enumerate(rides):
            if i == middle:
                camp.restart()
            info = camp.ride(ride)
            if camp.bought:
                info["after_buy"] = True
            camp.garage_round()
        _check_progression(rep, camp)
        print_after, _ = fingerprint(watched)
        rep.add(print_before == print_after, "empreinte du vrai profil identique (SHA-256)",
                f"{n_files} fichier(s) lus, {print_after[:16]}…")
        outside = sorted(str(p.relative_to(home)) for p in _tree(home) - tree_before
                         if not p.is_relative_to(ctx.root) and not p.is_relative_to(home / "Logs"))
        rep.add(not outside, "rien d'écrit hors du profil d'essai", ", ".join(outside[:5]) or "aucun fichier")
    rep.wall_s = time.perf_counter() - t_wall
    return rep


def format_text(rep: Report) -> str:
    out = [f"Campagne de {rep.seances} séances sur le profil d'essai (graine {rep.seed}, {rep.home}), "
           f"calculée en {rep.wall_s:.1f} s"]
    for r in rep.rides:
        tag = f"{r['xp']} XP, {r['coins']} pièces" if r["eligible"] else f"refusée ({r['reason']})"
        out.append(f"  {r['kind']:<12} {r['minutes']:>4.0f} min  niveau {r['level']}  {tag}")
    for ok, label, detail in rep.checks:
        out.append(f"  [{'INFO' if ok is None else ('OK' if ok else 'ÉCHEC')}] {label} : {detail}")
    out.append("Campagne : " + ("OK" if rep.ok else "ÉCHEC"))
    return "\n".join(out) + "\n"


def to_json(rep: Report) -> dict:
    return {"ok": rep.ok, "seances": rep.seances, "seed": rep.seed, "home": rep.home,
            "wall_s": round(rep.wall_s, 2), "rides": rep.rides,
            "checks": [{"ok": ok, "label": label, "detail": detail} for ok, label, detail in rep.checks]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seances", type=int, default=8, help="nombre de séances (au moins 4 ; défaut 8)")
    p.add_argument("--graine", type=int, default=7, help="graine du programme des séances (défaut 7)")
    p.add_argument("--reel", action="store_true", help="roule sur le vrai ~/OpenRide/Profils/_essai/ (PC)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    args = p.parse_args(argv)
    try:
        rep = run(args.seances, args.graine, args.reel)
    except (CampaignError, profiles.ProfileContextError) as exc:
        print(f"campagne_profil : erreur : {exc}", file=sys.stderr)
        return 2
    print(json.dumps(to_json(rep), ensure_ascii=False, indent=2) if args.json else format_text(rep), end="")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
