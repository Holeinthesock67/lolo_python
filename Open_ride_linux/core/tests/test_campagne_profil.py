"""Série MJ, lot MJ3 : campagne simulée accélérée sur le profil d'essai et garde-fou d'empreinte."""

import json

import pytest

from openride_core import coins, profiles
from openride_core.tools import campagne_profil as cp


def checks(rep):
    return {label: ok for ok, label, _ in rep.checks}


def test_short_campaign_passes_every_check():
    rep = cp.run(seances=8, seed=7)
    assert rep.ok, cp.format_text(rep)
    labels = checks(rep)
    for wanted in ("achat refusé faute de pièces", "achat accepté", "équipement porté (equip)",
                   "relance du core : profil, solde et expérience gardés",
                   "expérience du dernier xp_result = recalcul du journal", "solde = gagnées − dépensées",
                   "équipement appliqué à la physique",
                   "journaux des séances suivantes avec l'équipement acheté (loadout)",
                   "empreinte du vrai profil identique (SHA-256)", "rien d'écrit hors du profil d'essai"):
        assert labels.get(wanted) is True, wanted
    kinds = [r["kind"] for r in rep.rides]
    assert {"court", "erg_fini", "erg_abandon", "rogue"} <= set(kinds) and len(kinds) == 8
    assert rep.wall_s < 60
    assert profiles._active is None   # contexte rendu après la campagne


def test_journal_written_for_another_profile_fails(monkeypatch):
    """Défaut injecté : les journaux d'essai se disent du vrai profil."""
    monkeypatch.setattr(profiles.ProfileContext, "journal_header",
                        lambda self: {"profile_id": "principal", "profile_type": "joueur"})
    rep = cp.run(seances=4, seed=1)
    assert not rep.ok and checks(rep)["journaux marqués profile_id = _essai"] is False


def test_purchase_not_debited_fails(monkeypatch):
    """Défaut injecté : l'achat n'est pas écrit dans le profil (pièce non débitée)."""
    monkeypatch.setattr(coins, "buy", lambda item_id, progress, profile, catalogue, ct: None)
    rep = cp.run(seances=4, seed=1)
    assert not rep.ok and checks(rep)["achat accepté"] is False


def test_write_into_true_profile_breaks_fingerprint(monkeypatch):
    """Défaut injecté : la séance écrit aussi dans le vrai profil."""
    real = cp.Campaign.ride

    def leaky(self, ride):
        principal = profiles.ProfileContext.for_id("principal")
        (principal.root / "records.json").write_text("{}", encoding="utf-8")
        return real(self, ride)
    monkeypatch.setattr(cp.Campaign, "ride", leaky)
    rep = cp.run(seances=4, seed=1)
    labels = checks(rep)
    assert labels["empreinte du vrai profil identique (SHA-256)"] is False
    assert labels["rien d'écrit hors du profil d'essai"] is False


def test_cli_json_and_bad_call(capsys):
    assert cp.main(["--seances", "4", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["seances"] == 4 and out["checks"]
    assert cp.main(["--seances", "2"]) == 2


def test_program_always_has_the_key_sessions():
    for seed in range(5):
        kinds = [r.kind for r in cp.program(6, seed)]
        assert kinds[0] == "libre" and {"court", "erg_fini", "erg_abandon"} <= set(kinds)
    with pytest.raises(cp.CampaignError):
        cp.program(3, 0)
