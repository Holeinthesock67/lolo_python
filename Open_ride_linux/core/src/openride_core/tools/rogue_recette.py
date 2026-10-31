"""Partie automatique de la recette du Cyber-Rogue (lot X51, fiche R14), sans vélo ni engine.

    python -m openride_core.tools.rogue_recette [--essai calendrier|abandon|click|plantage|tous]
        [--seed 5] [--profil moyen] [--json]

Chaque essai joue une run dans la vraie séance du core (`CoreSession`), en temps accéléré, avec le cycliste
simulé du banc de bout en bout (lot X40) sur le trainer simulé :

- **calendrier** (essais 2, 3 et 10 de R14) : endurance 30 min, seuil 45 min et VO2max 45 min. IF de la run
  dans la plage de l'objectif (R7 §4.3) ; boss atteint et résultats affichés à ± 1 min du calendrier prévu ;
  FIT décodé par le SDK de Garmin, sans erreur, avec un tour par salle et par phase du boss.
- **abandon** (essai 8) : Y dans la première salle, puis « Terminer » depuis la pause. Bilan `abandoned`,
  FIT écrit et lisible, run comptée comme abandonnée au journal.
- **click** (essai 6) : le Click se coupe 30 s pendant le combat d'une salle. Le Firewall s'arrête net, la
  séance signale le Click perdu, puis tout reprend au retour du Click et la run va jusqu'aux résultats.
- **plantage** (essai 7) : le core est « tué » au milieu de la deuxième salle (seul ce qui est déjà écrit
  sur le disque reste), puis relancé sur ce journal. La séance reprend en pause au début de la même salle,
  repart à la commande `resume` et finit la run dans le même journal.

Ce que la recette garde pour le vélo : le ressenti (surchauffe, bosses, difficulté), les vrais appuis sur
le Click et le délai du frein (R0). Journal, FIT et profil restent dans un dossier temporaire.

Code de sortie : 0 si toutes les vérifications passent, 1 sinon, 2 pour un appel invalide.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest import mock

from .. import fit_export
from ..fit_export import lap_starts
from ..input_providers import ZwiftClickProvider
from ..journal import read_journal
from ..zwift_click import InputEvent
from .fit_check import FitCheckError, check as fit_lines, decode
from .rogue_bout_en_bout import Report, RunError, bot_step, format_text, new_session, to_json
from .rogue_sim import DT, IF_RANGE, PROFILES, Bot, normalized_power

ESSAIS = ("calendrier", "abandon", "click", "plantage")
CALENDAR_RUNS = (("endurance", 30), ("threshold", 45), ("vo2max", 45))   # fiche R14, essais 2 à 4
CALENDAR_TOL_S = 60.0          # calendrier tenu à ± 1 min
CLICK_OFF_S = 30.0
CLICK_AFTER_S = 20.0           # coupure du Click 20 s après le début du combat
CRASH_AFTER_S = 60.0           # plantage 1 min après le début de la deuxième salle
END_WAIT_S = 30.0


def _limit(duration_min: int) -> float:
    return 3 * duration_min * 60.0


def _start(s: Any, objective: str, duration_min: int, seed: int) -> Any:
    s._on_command("start_run", {"objective": objective, "duration_min": duration_min, "seed": seed}, 1)
    s._on_command("start", {}, 2)
    return s.rogue


def _finish_run(s: Any, bot: Bot, driver: Any, pressed: dict, limit: float, on_step=None) -> tuple[list[float], dict]:
    """Fait rouler le cycliste jusqu'à la fin de la séance ; puissances jouées et instants de phase (temps de run)."""
    rg = s.rogue
    powers: list[float] = []
    marks: dict[str, float] = {}
    results_at = None
    while s._t_session < limit and s.state.session_state == "RUNNING":
        e = rg.engine
        marks.setdefault(e.phase, e.t_total)
        powers.append(bot_step(s, bot, driver, pressed))
        if on_step is not None:
            on_step(s)
        if rg.finished and results_at is None:
            results_at = s._t_session
            marks.setdefault("RESULTS", e.t_total)
        if results_at is not None and s._t_session - results_at > END_WAIT_S:
            break
    return powers, marks


def _check_fit(rep: Report, s: Any, journal_dir: Path, label: str = "FIT lisible par le SDK de Garmin") -> None:
    path = (s.state.summary or {}).get("fit_path")
    if not path:
        rep.add(False, label, "aucun FIT écrit")
        return
    try:
        messages, errors, integrity = decode(Path(path))
    except FitCheckError as exc:
        rep.add(None, label, str(exc))
        return
    journal = list(read_journal(sorted(journal_dir.glob("*.jsonl"))[-1]))
    lines = fit_lines(messages, errors, integrity, journal)
    failed = [f"{ln['controle']} : {ln['detail']}" for ln in lines if ln["niveau"] == "ÉCHEC"]
    rep.add(not failed, label, "; ".join(failed[:3]) or f"{len(lines)} contrôles de fit-check passés")
    laps, starts = len(messages.get("lap", [])), len(lap_starts(journal))
    rep.add(laps == starts + 1 and starts >= 1, "FIT : un tour par salle et par phase du boss",
            f"{laps} tours pour {starts} débuts de salle (plus l'échauffement)")


def essai_calendrier(seed: int, profile: str) -> list[Report]:
    out = []
    prof = PROFILES[profile]
    for objective, duration in CALENDAR_RUNS:
        rep = Report(objective, duration, seed, profile)
        rep.add(None, "essai", "calendrier, IF et FIT")
        t_wall = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="openride-rogue-recette-") as tmp_s, \
                mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"):
            tmp = Path(tmp_s)
            s, driver, _ = new_session(tmp, prof)
            rg = _start(s, objective, duration, seed)
            bot = Bot(rg.engine, prof, seed, body=s.physics)
            powers, marks = _finish_run(s, bot, driver, {}, _limit(duration))
            rep.run_s = rg.engine.t_total
            plan = _planned(rg.engine.sc)
            low, high = IF_RANGE[objective]
            if_run = round(normalized_power(powers) / prof.ftp_w, 2)   # au centième, comme la fiche R14
            rep.add(low <= if_run <= high, f"IF de la run entre {low:.2f} et {high:.2f}", f"IF {if_run:.2f}")
            boss = marks.get("BOSS")
            rep.add(boss is not None and abs(boss - plan["BOSS"]) <= CALENDAR_TOL_S,
                    "boss atteint à ± 1 min du calendrier",
                    f"boss à {_mmss(boss)} pour {_mmss(plan['BOSS'])} prévues")
            end = marks.get("RESULTS")
            rep.add(end is not None and abs(end - duration * 60.0) <= CALENDAR_TOL_S,
                    "résultats à ± 1 min de la durée choisie", f"résultats à {_mmss(end)} pour {duration} min")
            rep.add(s.state.session_state == "FINISHED", "séance terminée d'elle-même", f"séance {s.state.session_state}")
            rep.summary = (s.state.summary or {}).get("rogue")
            _check_fit(rep, s, tmp / "journal")
        rep.wall_s = time.perf_counter() - t_wall
        out.append(rep)
    return out


def _planned(sc: Any) -> dict[str, float]:
    """Début prévu du boss : somme des durées nominales des étapes qui le précèdent (salle jouée après une porte comprise)."""
    t = 0.0
    for st in sc.steps:
        if st.kind == "boss":
            break
        t += st.nominal_s + (st.doors[0].nominal_s if st.kind == "corridor" and st.doors else 0.0)
    return {"BOSS": t}


def _mmss(t: float | None) -> str:
    return "—" if t is None else f"{int(t // 60)} min {int(t % 60):02d} s"


def essai_abandon(seed: int, profile: str) -> Report:
    prof = PROFILES[profile]
    rep = Report("threshold", 30, seed, profile)
    rep.add(None, "essai", "abandon depuis la pause")
    t_wall = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="openride-rogue-recette-") as tmp_s, \
            mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"):
        tmp = Path(tmp_s)
        s, driver, _ = new_session(tmp, prof)
        rg = _start(s, "threshold", 30, seed)
        bot = Bot(rg.engine, prof, seed, body=s.physics)
        while not (rg.engine.phase == "ROOM" and rg.engine.t_phase >= 60.0) and s._t_session < _limit(30):
            bot_step(s, bot, driver, {})
        s._handle_input(InputEvent.Y_SHORT)
        paused = s.state.session_state
        s._on_command("end_session", {"save": True}, 3)          # « Terminer » de l'écran de pause
        rep.run_s = rg.engine.t_total
        summ = (s.state.summary or {}).get("rogue") or {}
        rep.summary = summ
        rep.add(paused == "PAUSED" and s.state.session_state == "FINISHED", "pause par Y puis fin de séance",
                f"séance {paused} puis {s.state.session_state}")
        rep.add(summ.get("result") == "abandoned", "bilan « abandoned »",
                f"résultat {summ.get('result')}, salles gagnées {summ.get('rooms_won')}/{summ.get('rooms_total')}, "
                f"or {summ.get('gold')}")
        _check_fit(rep, s, tmp / "journal")
        files = sorted((tmp / "journal").glob("*.jsonl"))
        run_line = next((ln for ln in read_journal(files[-1]) if ln.get("kind") == "rogue_run"), None) if files else None
        rep.add(run_line is not None and run_line.get("result") == "abandoned", "run comptée abandonnée au journal",
                f"rogue_run {run_line.get('result') if run_line else 'absente'}")
    rep.wall_s = time.perf_counter() - t_wall
    return rep


def essai_click(seed: int, profile: str) -> Report:
    prof = PROFILES[profile]
    rep = Report("threshold", 30, seed, profile)
    rep.add(None, "essai", f"Click coupé {CLICK_OFF_S:.0f} s pendant une salle")
    t_wall = time.perf_counter()
    click = ZwiftClickProvider()
    click._link_up = True
    with tempfile.TemporaryDirectory(prefix="openride-rogue-recette-") as tmp_s, \
            mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"):
        tmp = Path(tmp_s)
        s, driver, _ = new_session(tmp, prof, inputs=[click])
        rg = _start(s, "threshold", 30, seed)
        bot = Bot(rg.engine, prof, seed, body=s.physics)
        cut: dict[str, Any] = {}

        def on_step(sess: Any) -> None:
            e = sess.rogue.engine
            fighting = e.phase == "ROOM" and e.combat is not None and e.combat.phase == "FIGHT"
            if not cut and fighting and e.t_phase >= CLICK_AFTER_S:
                click._link_up = False
                sess._drain_inputs()                # le pas suivant voit déjà le Click perdu
                cut.update(t0=sess._t_session, wall0=e.firewall.state.s, status=None, room=e.room_id, moved=0.0)
            elif cut and "t1" not in cut:
                cut["status"] = cut["status"] or sess.state.input_status
                if e.firewall is not None and e.room_id == cut["room"]:
                    cut["moved"] = max(cut["moved"], abs(e.firewall.state.s - cut["wall0"]))
                if sess._t_session - cut["t0"] >= CLICK_OFF_S:
                    click._link_up = True
                    sess._drain_inputs()
                    cut.update(t1=sess._t_session, wall1=e.firewall.state.s if e.firewall else None)
            elif "t1" in cut and "after" not in cut and sess._t_session - cut["t1"] >= 10.0:
                f = e.firewall
                cut["after"] = abs(f.state.s - cut["wall1"]) if f is not None and e.room_id == cut["room"] else None

        def step_all(sess: Any) -> None:
            sess._drain_inputs()                    # statut d'entrée relu comme dans la boucle du core
            if sess.rogue is not None:              # la run est rendue à la fin de la séance
                on_step(sess)

        _, _ = _finish_run(s, bot, driver, {}, _limit(30), on_step=step_all)
        rep.run_s = rg.engine.t_total
        rep.add(bool(cut) and cut.get("status") == "LOST", "Click perdu signalé à l'engine",
                f"input_status {cut.get('status')}" if cut else "aucun combat de plus de 20 s")
        rep.add(bool(cut) and cut["moved"] < 0.05, "Firewall arrêté pendant la coupure",
                f"mur déplacé de {cut.get('moved', 0.0):.2f} m en {CLICK_OFF_S:.0f} s")
        after = cut.get("after")
        rep.add(after is not None and after > 1.0, "Firewall reparti au retour du Click",
                "salle finie avant 10 s" if after is None else f"mur avancé de {after:.0f} m en 10 s")
        summ = (s.state.summary or {}).get("rogue") or {}
        rep.summary = summ
        rep.add(summ.get("result") in ("victory", "defeat") and s.state.session_state == "FINISHED",
                "run menue jusqu'aux résultats après la coupure", f"résultat {summ.get('result')}, séance {s.state.session_state}")
    rep.wall_s = time.perf_counter() - t_wall
    return rep


def essai_plantage(seed: int, profile: str) -> Report:
    prof = PROFILES[profile]
    rep = Report("threshold", 30, seed, profile)
    rep.add(None, "essai", "core tué au milieu de la deuxième salle, puis relancé")
    t_wall = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="openride-rogue-recette-") as tmp_s, \
            mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"):
        tmp = Path(tmp_s)
        s, driver, _ = new_session(tmp / "avant", prof)
        rg = _start(s, "threshold", 30, seed)
        bot = Bot(rg.engine, prof, seed, body=s.physics)
        rooms_seen: list[int] = []
        while s._t_session < _limit(30):
            e = rg.engine
            if e.phase == "ROOM" and (not rooms_seen or rooms_seen[-1] != e.room_id):
                rooms_seen.append(e.room_id)
            if len(rooms_seen) >= 2 and e.phase == "ROOM" and e.t_phase >= CRASH_AFTER_S:
                break
            bot_step(s, bot, driver, {})
        crash_room, crash_t = rg.engine.room_id, rg.engine.t_total
        # Le processus meurt : seul ce qui est déjà sur le disque reste (aucune fermeture, aucun vidage).
        src = sorted((tmp / "avant" / "journal").glob("*.jsonl"))[-1]
        (tmp / "apres" / "journal").mkdir(parents=True)
        journal = tmp / "apres" / "journal" / src.name
        shutil.copyfile(src, journal)
        s2, driver2, _ = new_session(tmp / "apres", prof)
        try:
            s2.resume_session(journal)
        except Exception as exc:   # ResumeError ou défaut de reprise : l'essai échoue, la suite est sautée
            rep.add(False, "reprise sur le journal", f"{type(exc).__name__} : {exc}")
            rep.wall_s = time.perf_counter() - t_wall
            return rep
        e2 = s2.rogue.engine
        rep.add(s2.state.session_state == "PAUSED" and s2.state.pause_reason == "core_restarted",
                "séance reprise en pause (core_restarted)", f"séance {s2.state.session_state}, raison {s2.state.pause_reason}")
        rep.add(e2.phase == "ROOM" and e2.room_id == crash_room and e2.t_phase < 1.0,
                "reprise au début de la salle en cours",
                f"phase {e2.phase}, salle {e2.room_id} (plantage dans la salle {crash_room}), "
                f"{e2.t_phase:.0f} s de salle ; run à {_mmss(e2.t_total)} (plantage à {_mmss(crash_t)})")
        s2._on_command("resume", {}, 3)
        bot2 = Bot(e2, prof, seed, body=s2.physics)
        _finish_run(s2, bot2, driver2, {}, s2._t_session + _limit(30))
        rep.run_s = e2.t_total
        summ = (s2.state.summary or {}).get("rogue") or {}
        rep.summary = summ
        rep.add(summ.get("result") in ("victory", "defeat") and s2.state.session_state == "FINISHED",
                "run finie après la reprise", f"résultat {summ.get('result')}, séance {s2.state.session_state}")
        lines = list(read_journal(journal))
        rep.add(any(ln.get("event") == "resume_after_crash" for ln in lines)
                and any(ln.get("kind") == "rogue_run" for ln in lines),
                "même journal continué jusqu'au bilan", f"{len(lines)} lignes, resume_after_crash et rogue_run attendus")
        _check_fit(rep, s2, tmp / "apres" / "journal")
    rep.wall_s = time.perf_counter() - t_wall
    return rep


def run(essai: str, seed: int = 5, profile: str = "moyen") -> list[Report]:
    if essai not in (*ESSAIS, "tous"):
        raise RunError(f"essai inconnu : {essai} ({', '.join(ESSAIS)} ou tous)")
    if profile not in PROFILES:
        raise RunError(f"profil inconnu : {profile} ({', '.join(PROFILES)})")
    reps: list[Report] = []
    for name in ESSAIS if essai == "tous" else (essai,):
        if name == "calendrier":
            reps += essai_calendrier(seed, profile)
        else:
            reps.append({"abandon": essai_abandon, "click": essai_click, "plantage": essai_plantage}[name](seed, profile))
    return reps


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Partie automatique de la recette du Cyber-Rogue (lot X51).")
    ap.add_argument("--essai", default="tous", help=f"{', '.join(ESSAIS)} ou tous")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--profil", default="moyen", help=f"cycliste simulé : {', '.join(PROFILES)}")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        reps = run(args.essai, args.seed, args.profil)
    except RunError as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([to_json(r) for r in reps], ensure_ascii=False, indent=2))
    else:
        print(format_text(reps), end="")
    return 0 if all(r.ok for r in reps) else 1


if __name__ == "__main__":
    sys.exit(main())
