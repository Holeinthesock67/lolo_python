"""Chaque script GDScript de l'engine a son fichier `.uid` versionné (audit du 22 novembre, G6) : sans lui,
Godot le recrée au premier lancement et salit le dépôt sur le PC."""

import re
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / "engine"
UID = re.compile(r"uid://[a-z0-9]{1,13}")


def test_chaque_script_a_son_uid() -> None:
    manquants = [p.relative_to(ENGINE).as_posix() for p in sorted(ENGINE.rglob("*.gd"))
                 if ".godot" not in p.parts and not p.with_name(p.name + ".uid").is_file()]
    assert not manquants, "fichiers .uid manquants (lancer Godot une fois, ou les écrire) : " + ", ".join(manquants)


def test_uid_bien_formes_et_uniques() -> None:
    vus: dict[str, str] = {}
    for p in sorted(ENGINE.rglob("*.gd.uid")):
        texte = p.read_text(encoding="utf-8").strip()
        assert UID.fullmatch(texte), f"{p.name} : {texte!r}"
        assert texte not in vus, f"{p.name} et {vus.get(texte)} ont le même uid"
        vus[texte] = p.name
