"""Test guidé des boutons du Click : plan des boutons conforme à la spécification §7.1, encadré, bips, déroulé simulé."""

import asyncio
import io
import json
import re
from pathlib import Path

import pytest

from openride_core import sim_scenarios
from openride_core.config import Config
from openride_core.tools import boutons_click as bc
from openride_core.tools import guide as gd
from openride_core.tools.click_recette import Recorder
from openride_core.zwift_click import InputEvent

SPEC = Path(__file__).resolve().parents[2] / "docs" / "SPECIFICATION_GENERALE.md"


def spec_plan() -> dict[str, list[str]]:
    """Lignes du tableau des boutons (§7.1) : première colonne → [famille, menus, SIM, ERG, Rogue, monde]."""
    text = SPEC.read_text(encoding="utf-8")
    section = text.split("### 7.1", 1)[1].split("### 7.2", 1)[0]
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 7 and cells[0] not in ("Bouton", "---"):
            rows[cells[0]] = cells[1:]
    return rows


def test_every_event_has_an_action():
    assert set(bc.PLAN) == set(InputEvent)
    assert all(len(a.modes) == len(bc.MODES) for a in bc.PLAN.values())


def test_plan_matches_specification_table():
    rows = spec_plan()
    used = {a.row for a in bc.PLAN.values() if a.row}
    assert used == set(rows), "chaque ligne du tableau §7.1 a ses événements, et rien d'autre"
    for ev, act in bc.PLAN.items():
        if not act.row:
            continue
        family, *cells = rows[act.row]
        assert act.family == family, ev
        two_ways = act.row.startswith("+ / B") or act.row.startswith("Flèches")
        for mine, cell in zip(act.modes, cells):
            if not two_ways:
                assert mine == cell, (ev, mine, cell)     # mot pour mot
            elif "±" in cell:
                sign = "+" if ev.value.startswith("PLUS") else "−"
                assert mine == cell.replace("±", sign), (ev, mine, cell)


def test_steps_cover_every_event_left_unit_first():
    assert {s.event for s in bc.STEPS} == set(InputEvent)
    assert len({s.key for s in bc.STEPS}) == len(bc.STEPS) == 17
    lefts = [s.left for s in bc.STEPS]
    assert lefts == sorted(lefts, reverse=True), "boîtier gauche d'abord (il se tait après une minute)"
    assert {s.button for s in bc.STEPS if s.event == InputEvent.MINUS_SHORT} == {"MINUS", "B"}
    assert "17 appuis" in " ".join(gd.TRIALS["boutons_click"].notes)


def test_beep_kinds_exist_and_match_the_game():
    assert {bc.beep_kind(ev) for ev in InputEvent} == {"appui", "appui_long", "appui_flou"}
    assert all(kind in gd.BEEPS for kind in ("appui", "appui_long", "appui_flou"))
    main_gd = (SPEC.parents[1] / "engine" / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert '"PLUS_SHORT": [[880.0, 0.08]]' in main_gd and gd.BEEPS["appui"] == ((880, 0.08),)
    assert '"PLUS_LONG": [[660.0, 0.10], [990.0, 0.14]]' in main_gd
    assert gd.BEEPS["appui_long"] == ((660, 0.10), (990, 0.14))


def test_panel_lines_and_screen_box():
    step = next(s for s in bc.STEPS if s.key == "a_long")
    ok = bc.panel_lines(InputEvent.A_LONG, "A", "droit", step)
    assert ok[0].startswith("REÇU : A LONG") and "boîtier droit" in ok[0]
    assert any("Valider l'élément" in line for line in ok) and ok[-1] == "✔ C'est l'appui demandé"
    wrong = bc.panel_lines(InputEvent.A_SHORT, "A", "droit", step)
    assert wrong[-1] == "✘ Attendu : A long (touche A)"
    b = next(s for s in bc.STEPS if s.key == "b")
    assert bc.panel_lines(InputEvent.MINUS_SHORT, "MINUS", "gauche", b)[-1].startswith("✘")   # − au lieu de B
    g = gd.Guide("Test", sound=False, screen=True, out=io.StringIO())
    g.step("Appui long sur A", 20)
    g.show_panel(ok, ok=True)
    screen = "\n".join(re.sub(r"\033\[[0-9;]*m", "", line) for line in g.render())
    assert "┌" in screen and "│ REÇU : A LONG" in screen and "└" in screen
    g.step("suivante", 20)
    assert g.panel == []    # une nouvelle étape efface l'encadré


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_muted_unit_detected_from_notification_rate():
    clock = Clock()
    rec = Recorder(clock)
    for _ in range(100):                    # 10 s à 10 notifications par seconde
        rec.raw("AA", bytes([0x15]))
        rec.raw("BB", bytes([0x15]))
        clock.now += 0.1
    assert bc.muted_units(rec, ["AA", "BB"]) == []
    for _ in range(20):                     # puis 10 s : AA toutes les 2,5 s (muet), BB normal
        if round(clock.now * 10) % 25 == 0:
            rec.raw("AA", bytes([0x15]))
        rec.raw("BB", bytes([0x15]))
        clock.now += 0.5
    assert bc.muted_units(rec, ["AA", "BB"]) == ["AA"]
    assert bc.muted_units(rec, ["BB"]) == []      # un boîtier coupé n'est pas « muet »


def run_sim(spec: dict, timeout: float = 5.0) -> tuple[dict, gd.Guide]:
    async def go():
        world = sim_scenarios.build_world(spec, trainer=False, hr=False)
        prompts: asyncio.Queue = asyncio.Queue()
        rec = Recorder(asyncio.get_running_loop().time)
        guide = gd.Guide("Test", sound=False, screen=False, out=io.StringIO())
        providers = bc.make_providers(rec, Config(), world)
        extra = [asyncio.create_task(world.run()), asyncio.create_task(bc.sim_user(world, prompts))]
        try:
            report = await bc.run_steps(providers, rec, guide, prompts.put_nowait, step_timeout=timeout,
                                        connect_timeout=10.0, next_step_s=0.1)
        finally:
            world.stop()
            for t in extra:
                t.cancel()
            await asyncio.gather(*extra, return_exceptions=True)
        return report, guide
    return asyncio.run(go())


@pytest.mark.slow   # une trentaine de secondes
def test_all_buttons_on_simulated_click(tmp_path):
    report, guide = run_sim({"click": {"appear_at": 0.0}, "events": []})
    assert report["ok"] and report["steps_ok"] == report["steps_total"] == 17, report["steps"]
    sides = {s["key"]: s["side"] for s in report["steps"]}
    assert sides["moins"] == sides["haut"] == "gauche" and sides["b"] == sides["z_long"] == "droit"
    played = guide.sound.played
    assert played.count("debut") == 18 and played.count("appui_flou") == 2 and "alerte" not in played
    bc.write_outputs(report, tmp_path)
    assert "tout passe" in (tmp_path / "rapport.txt").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "rapport.json").read_text(encoding="utf-8"))["steps_ok"] == 17


@pytest.mark.slow
def test_silent_left_unit_is_reported():
    spec = {"click": {"appear_at": 0.0}, "events": [
        {"t": 0.5, "device": "click_minus", "action": "silence", "seconds": 600}]}
    report, guide = run_sim(spec, timeout=1.5)
    steps = {s["key"]: s for s in report["steps"]}
    left = [s for s in report["steps"] if next(x for x in bc.STEPS if x.key == s["key"]).left]
    assert all(not s["ok"] for s in left) and "muet" in steps["moins"]["detail"]
    assert steps["plus"]["ok"] and steps["b"]["ok"]
    assert not report["ok"] and "moins" in report["missed_left"]
    assert "click_reset_locked" in bc.report_text(report) and "echec" in guide.sound.played
    assert any("muet" in line for line in guide.out.getvalue().splitlines())   # alerte à l'écran
