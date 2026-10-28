"""Recette de la fréquence cardiaque (lot X9) : contrôles, analyse d'un journal ou d'un FIT, essai simulé."""

import asyncio
import dataclasses
import json

import pytest

from openride_core.fit_export import write_fit
from openride_core.journal import JournalWriter, Record
from openride_core.tools import fc_recette as fc
from openride_core.tools.fc_recette import Limits, evaluate

PHASE = 60


def fabricate(gone_after=5, back_after=8, frozen_bpm=None):
    """240 relevés à 1 Hz : FC qui varie, retirée à 60 s (disparue `gone_after` s plus tard, figée à
    `frozen_bpm` jusque-là), remise à 120 s (revenue `back_after` s plus tard)."""
    out = []
    for t in range(4 * PHASE):
        phase = fc.phase_at(t, PHASE, 2 * PHASE, PHASE)
        power = 180 + (t % 7) * 3
        if phase == "retiree":
            hr = (frozen_bpm or 128) if t - PHASE < gone_after else None
        elif phase == "remise" and t - 2 * PHASE < back_after:
            hr = None
        else:
            hr = 125 + t % 5
        out.append({"t": float(t), "phase": phase, "source": "trainer" if hr else "", "fc": hr,
                    "contact": None, "puissance": power})
    return out


def verdicts(report):
    return {c["nom"]: c["ok"] for c in report["controles"]}


def test_good_trial_passes():
    rep = evaluate(fabricate(), Limits(), "ceinture")
    assert rep["ok"] and rep["source_texte"] == "ceinture Bluetooth"


def test_frozen_value_fails_while_power_varies():
    rep = evaluate(fabricate(gone_after=PHASE + 1, frozen_bpm=105), Limits(), "trainer")
    assert verdicts(rep) == {"absence": False, "valeur figée": False, "retour": True}
    assert "105 bpm pendant 59 s" in rep["controles"][1]["detail"]
    steady = [dict(s, puissance=180) for s in fabricate(gone_after=30, frozen_bpm=105)]
    assert verdicts(evaluate(steady, Limits(), "ceinture"))["valeur figée"]   # puissance constante : admis


def test_late_absence_admitted_only_for_the_relay_freeze():
    late = fabricate(gone_after=14)
    assert not verdicts(evaluate(late, Limits(), "ceinture"))["absence"]
    rep = evaluate(late, Limits(), "trainer")       # gel du lot Q5 à 15 s : délai admis 17 s
    assert verdicts(rep)["absence"] and rep["controles"][0]["delai_admis_s"] == 17.0
    assert "régler hr_relay_freeze_s à 8 s" in rep["controles"][0]["detail"]
    assert verdicts(evaluate(late, Limits(freeze_cfg_s=8.0), "trainer"))["absence"] is False


def test_late_return_fails():
    rep = evaluate(fabricate(back_after=25), Limits(), "ceinture")
    assert verdicts(rep) == {"absence": True, "valeur figée": True, "retour": False}


def records(samples, t0=1730000000.0):
    return [Record(ts=t0 + s["t"], t=s["t"], power=float(s["puissance"]), cadence=85.0, speed=8.0,
                   distance=s["t"] * 8.0, hr=s["fc"]) for s in samples]


def test_analyse_journal_and_fit(tmp_path, capsys):
    recs = records(fabricate(gone_after=PHASE + 1, frozen_bpm=105))
    journal, fit = tmp_path / "seance.jsonl", tmp_path / "seance.fit"
    with JournalWriter(journal) as j:
        j.event("start", recs[0].ts)
        for r in recs:
            j.record(r)
        j.event("stop", recs[-1].ts + 1)
    write_fit([dataclasses.asdict(r) for r in recs], [], fit)
    absent_cfg = ["--config", str(tmp_path / "absent.toml")]
    for path, source in ((journal, "relais du trainer"), (fit, "inconnue")):
        assert fc.main(["--analyse", str(path)] + absent_cfg) == 1
        out = capsys.readouterr().out
        assert f"source : {source}" in out and "[ÉCHEC] valeur figée : plus longue valeur identique : 105 bpm" in out
    good = records(fabricate())
    with JournalWriter(tmp_path / "bon.jsonl") as j:
        for r in good:
            j.record(r)
    assert fc.main(["--analyse", str(tmp_path / "bon.jsonl"), "--source", "ceinture", "--out",
                    str(tmp_path / "bon")] + absent_cfg) == 0
    assert fc.main(["--analyse", str(tmp_path / "bon"), "--source", "ceinture"] + absent_cfg) == 0   # fc.csv
    assert fc.main(["--analyse", str(tmp_path / "rien.jsonl")] + absent_cfg) == 2


def test_sim_trial_relay_strap_and_frozen(tmp_path):
    """Les trois essais simulés en même temps (phases de 8 s) : relais avec gel à 5 s, ceinture, et relais
    sans gel effectif (120 s) dont la valeur figée doit échouer."""
    common = ["--sim", "--phase-s", "8", "--absence", "6", "--fige", "6", "--retour", "6",
              "--config", str(tmp_path / "absent.toml")]
    runs = {"relais": ["--source", "trainer", "--gel", "5"], "ceinture": ["--source", "ceinture"],
            "fige": ["--source", "trainer", "--gel", "120"]}

    async def go():
        return await asyncio.gather(*(fc.main_async(fc.parse_args(common + extra + ["--out", str(tmp_path / k)]))
                                      for k, extra in runs.items()))
    codes = dict(zip(runs, asyncio.run(go())))
    assert codes == {"relais": 0, "ceinture": 0, "fige": 1}, codes
    rep = json.loads((tmp_path / "fige" / "rapport.json").read_text(encoding="utf-8"))
    assert {c["nom"]: c["ok"] for c in rep["controles"]} == {"absence": False, "valeur figée": False, "retour": True}
    head = (tmp_path / "ceinture" / "fc.csv").read_text(encoding="utf-8").splitlines()[0]
    assert head == "t,phase,source,fc,contact,puissance"


def test_trial_in_guide_materials():
    from openride_core.tools.guide import TRIALS, materials_text
    assert "fc_recette" in TRIALS and "fc_recette" in materials_text(["fc_recette"])


@pytest.mark.parametrize("t, phase", [(0, "portee"), (59.9, "portee"), (60, "retiree"), (120, "remise"),
                                      (180, "portee_fin")])
def test_phase_at(t, phase):
    assert fc.phase_at(t, 60, 120, 60) == phase
