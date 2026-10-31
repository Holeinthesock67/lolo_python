"""Lot X53 : garde-fou des options hors menu (audit des options du 31 octobre).

Toute clé de `config.toml` est réglée par le menu Réglages, par un autre écran, ou rangée avec sa raison
dans une liste de `config.py` (EXPERT, DEV, ou à relier par un lot nommé) ; tout argument lu par l'engine
est passé par le lanceur depuis la configuration, ou rangé dans `launcher.ENGINE_ARGS_NOT_FROM_CONFIG` ;
toute commande citée par le guide d'utilisation a une raison ou le lot qui la remplacera par un menu.
Une option ajoutée sans menu ni raison fait échouer ce test (cas du gravel et de la ceinture cardio).
"""

from __future__ import annotations

import inspect
import re
from dataclasses import fields, is_dataclass
from pathlib import Path

from openride_core import config as config_mod
from openride_core import launcher, pairing, session, settings

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ARGS = REPO_ROOT / "engine" / "scripts" / "engine_args.gd"
GUIDE = REPO_ROOT / "docs" / "GUIDE_UTILISATION.md"
LOT_RE = re.compile(r"^[A-Z]{1,3}\d+$")

# Commandes que le guide d'utilisation peut citer : raison, ou lot qui les remplace par un menu (le lot
# retire alors la commande du guide et la ligne d'ici).
GUIDE_COMMANDS: dict[str, str] = {
    "openride-core profil essai --vider": "O33",
    "openride-core recover": "O34",
    "openride --profil": "raccourci facultatif : l'écran « Qui roule ? » fait la même chose",
    "openride-core profil list": "facultatif : les profils sont listés à l'écran « Qui roule ? »",
    "openride-core release-trainer": "secours en terminal : l'icône « Libérer le trainer » fait la même chose",
}
# Éditions de fichier que le guide demande encore, avec le lot qui les remplace.
GUIDE_FILE_EDITS: dict[str, str] = {}

CATEGORIES = {"OTHER_SCREEN_KEYS": config_mod.OTHER_SCREEN_KEYS, "EXPERT_KEYS": config_mod.EXPERT_KEYS,
              "DEV_KEYS": config_mod.DEV_KEYS, "PENDING_KEYS": config_mod.PENDING_KEYS}


def all_keys() -> set[tuple[str, str]]:
    cfg = config_mod.Config()
    return {(sec.name, f.name) for sec in fields(cfg) if is_dataclass(getattr(cfg, sec.name))
            for f in fields(getattr(cfg, sec.name))}


def classify(keys: set[tuple[str, str]], menu: set[tuple[str, str]],
             categories: dict[str, dict[tuple[str, str], str]]) -> list[str]:
    """Défauts : clé sans place, clé rangée deux fois, clé rangée qui n'existe pas, raison vide."""
    errors: list[str] = []
    for key in sorted(keys):
        places = (["menu Réglages"] if key in menu else []) + [n for n, d in categories.items() if key in d]
        if not places:
            errors.append(f"[{key[0]}] {key[1]} : ni au menu ni rangée dans config.py (lot X53)")
        elif len(places) > 1:
            errors.append(f"[{key[0]}] {key[1]} : rangée deux fois ({', '.join(places)})")
    for name, d in categories.items():
        for key, why in d.items():
            if key not in keys:
                errors.append(f"{name} : [{key[0]}] {key[1]} n'existe pas dans Config")
            if not why.strip():
                errors.append(f"{name} : [{key[0]}] {key[1]} sans raison")
    return errors


def test_every_config_key_has_a_place_and_negative() -> None:
    menu = {(s.section, s.name) for s in settings.SETTINGS}
    assert classify(all_keys(), menu, CATEGORIES) == []
    # Test négatif : une nouvelle clé sans menu (cas du gravel), une clé rangée deux fois, une ligne périmée.
    errs = classify({("gravel", "mode"), ("rider", "ftp_w"), ("x", "y")}, {("rider", "ftp_w")},
                    {"DEV_KEYS": {("rider", "ftp_w"): "essai", ("z", "w"): "vieux"}})
    assert errs == ["[gravel] mode : ni au menu ni rangée dans config.py (lot X53)",
                    "[rider] ftp_w : rangée deux fois (menu Réglages, DEV_KEYS)",
                    "[x] y : ni au menu ni rangée dans config.py (lot X53)",
                    "DEV_KEYS : [z] w n'existe pas dans Config"]


def test_pending_keys_name_their_lot() -> None:
    bad = {k: v for k, v in config_mod.PENDING_KEYS.items() if not LOT_RE.match(v)}
    assert bad == {}, "PENDING_KEYS : la raison est le numéro du lot qui reliera la clé au menu"


def test_other_screen_keys_are_really_written_by_their_screen() -> None:
    """Écran Appareils : `pairing` écrit chaque clé ; profil : la session écrit `[profils] dernier`."""
    every = pairing.PairedDevices(trainer_name="T", trainer_address="AA:00:00:00:00:01",
                                  click_plus_address="AA:00:00:00:00:02", click_minus_address="AA:00:00:00:00:03",
                                  hr_name="H", hr_address="AA:00:00:00:00:04")
    written = {(sec, key) for sec, key, _ in pairing._values(every)}
    written |= {(sec, key) for values in pairing.FORGET_VALUES.values() for sec, key, _ in values}
    if '("profils", "dernier"' in inspect.getsource(session):
        written.add(("profils", "dernier"))
    assert set(config_mod.OTHER_SCREEN_KEYS) - written == set()


def engine_args(text: str) -> set[str]:
    return set(re.findall(r'arg\.begins_with\("(--[a-z-]+)="\)', text)) | set(re.findall(r'arg == "(--[a-z-]+)"', text))


def test_every_engine_argument_comes_from_config_or_is_listed() -> None:
    read = engine_args(ENGINE_ARGS.read_text(encoding="utf-8"))
    passed = set(re.findall(r'f"(--[a-z-]+)=', inspect.getsource(launcher.build_supervisor)))
    listed = set(launcher.ENGINE_ARGS_NOT_FROM_CONFIG)
    assert read - passed - listed == set(), "argument de l'engine sans réglage ni raison (lot X53)"
    assert passed & listed == set(), "argument passé depuis la configuration et rangé dans la liste"
    assert listed - read == set(), "ENGINE_ARGS_NOT_FROM_CONFIG cite un argument que l'engine ne lit plus"
    assert {"--quality", "--display", "--living"} <= passed and "--gravel" in read


def guide_commands(text: str) -> list[str]:
    return re.findall(r"`((?:openride-core|openride-compiler|openride|python -m) [^`]*)`", text)


def check_guide(text: str, commands: dict[str, str], edits: dict[str, str]) -> list[str]:
    errors: list[str] = []
    cited = guide_commands(text)
    for cmd in cited:
        if not any(cmd.startswith(k) for k in commands):
            errors.append(f"guide : commande « {cmd} » sans menu ni raison (lot X53)")
    for k in commands:
        if not any(cmd.startswith(k) for cmd in cited):
            errors.append(f"guide : « {k} » n'est plus cité, retirer la ligne de GUIDE_COMMANDS")
    for phrase in re.findall(r"(?:écrivez|ajoutez|modifiez) dans `~/OpenRide/[^`]*`", text):
        if phrase not in edits:
            errors.append(f"guide : « {phrase} » : édition de fichier sans menu ni raison (lot X53)")
    for phrase in edits:
        if phrase not in text:
            errors.append(f"guide : « {phrase} » n'est plus cité, retirer la ligne de GUIDE_FILE_EDITS")
    return errors


def test_guide_commands_have_a_reason_and_negative() -> None:
    assert check_guide(GUIDE.read_text(encoding="utf-8"), GUIDE_COMMANDS, GUIDE_FILE_EDITS) == []
    errs = check_guide("Lancez `openride-core gravel on`, puis écrivez dans `~/OpenRide/config.toml` :",
                       {"openride-core recover": "O34"}, {"ajoutez dans `~/OpenRide/powerups.toml`": "O99"})
    assert errs == ["guide : commande « openride-core gravel on » sans menu ni raison (lot X53)",
                    "guide : « openride-core recover » n'est plus cité, retirer la ligne de GUIDE_COMMANDS",
                    "guide : « écrivez dans `~/OpenRide/config.toml` » : édition de fichier sans menu ni raison (lot X53)",
                    "guide : « ajoutez dans `~/OpenRide/powerups.toml` » n'est plus cité, retirer la ligne de GUIDE_FILE_EDITS"]
