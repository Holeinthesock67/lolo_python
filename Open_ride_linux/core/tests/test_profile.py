"""Lot V4 : profil local (choix, achats, vies, avatar), lecture et écriture sûres, migration."""

from __future__ import annotations

import json
import os

import pytest

from openride_core import profile as prof_mod
from openride_core.profile import (
    DEFAULT_AVATAR, DEFAULT_EQUIPPED, Profile, ProfileError, ProfileTooNew, equip, load_profile,
    record_life_purchase, record_purchase, save_profile, set_avatar, use_life,
)


def test_absent_profile_gives_defaults_without_writing(tmp_path):
    path = tmp_path / "profile.json"
    p = load_profile(path)
    assert p.equipped == DEFAULT_EQUIPPED and p.avatar == DEFAULT_AVATAR
    assert p.purchases == [] and p.lives_left == 0
    assert not path.exists()


def test_round_trip(tmp_path):
    path = tmp_path / "profile.json"
    p = Profile()
    record_purchase(p, "frame_climber", 150, ts=1_761_500_000)
    equip(p, "frame", "frame_climber", owned={"frame_climber"})
    set_avatar(p, {"height": "L", "skin": 5, "number": 42})
    record_life_purchase(p, 30)
    save_profile(p, path)
    q = load_profile(path)
    assert q.to_dict() == p.to_dict()
    assert q.equipped["frame"] == "frame_climber" and q.avatar["height"] == "L"
    assert q.spent == 180 and q.lives_left == 1
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1


def test_truncated_file_uses_backup(tmp_path):
    path = tmp_path / "profile.json"
    p = Profile()
    record_purchase(p, "wheels_light", 100)
    save_profile(p, path)
    record_purchase(p, "frame_climber", 150)
    save_profile(p, path)            # l'ancienne version devient profile.json.bak
    path.write_text(path.read_text(encoding="utf-8")[:20], encoding="utf-8")
    q = load_profile(path)
    assert q.purchased == {"wheels_light"}
    kept = list(tmp_path.glob("profile.json.corrompu-*"))
    assert len(kept) == 1 and not path.exists()


def test_broken_file_without_backup_gives_defaults(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("{pas du json", encoding="utf-8")
    q = load_profile(path)
    assert q.equipped == DEFAULT_EQUIPPED
    assert len(list(tmp_path.glob("profile.json.corrompu-*"))) == 1


def test_wrong_shape_is_treated_as_broken(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"version": 1, "purchases": "beaucoup"}), encoding="utf-8")
    assert load_profile(path).purchases == []


def test_interrupted_write_keeps_old_file(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    p = Profile()
    record_purchase(p, "wheels_light", 100)
    save_profile(p, path)
    before = path.read_text(encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("disque plein (simulé)")
    monkeypatch.setattr(prof_mod.os, "replace", boom)
    record_purchase(p, "frame_climber", 150)
    with pytest.raises(OSError):
        save_profile(p, path)
    monkeypatch.undo()
    assert path.read_text(encoding="utf-8") == before
    assert [f.name for f in tmp_path.iterdir() if f.suffix == ".tmp"] == []


def test_migration_from_unversioned(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"equipped": {"frame": "frame_aero"}}), encoding="utf-8")
    p = load_profile(path)
    assert p.version == 0 and p.equipped["frame"] == "frame_aero"
    assert p.equipped["wheels"] == DEFAULT_EQUIPPED["wheels"] and p.avatar == DEFAULT_AVATAR
    save_profile(p, path)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_newer_profile_is_read_only(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"version": 2, "equipped": {"frame": "frame_aero"},
                                "nouveau_champ": True}), encoding="utf-8")
    p = load_profile(path)
    assert p.read_only and p.equipped["frame"] == "frame_aero"
    before = path.read_text(encoding="utf-8")
    with pytest.raises(ProfileTooNew):
        save_profile(p, path)
    assert path.read_text(encoding="utf-8") == before


def test_unknown_item_reverts_to_default(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"version": 1, "equipped": {"frame": "frame_retire"}}), encoding="utf-8")
    p = load_profile(path, known_items={"frame_allround", "frame_aero"})
    assert p.equipped["frame"] == "frame_allround"


def test_equip_refusals_change_nothing():
    p = Profile()
    with pytest.raises(ProfileError, match="possédée"):
        equip(p, "frame", "frame_aero", owned={"frame_allround"})
    with pytest.raises(ProfileError, match="emplacement"):
        equip(p, "selle", "x", owned={"x"})
    assert p.equipped == DEFAULT_EQUIPPED


@pytest.mark.parametrize("avatar, field", [
    ({"height": "XXL"}, "height"),
    ({"skin": 8}, "skin"),
    ({"number": -1}, "number"),
    ({"number": True}, "number"),
    ({"kit_primary": 2.5}, "kit_primary"),
    ({"taille_cm": 180}, "taille_cm"),
])
def test_set_avatar_refusals(avatar, field):
    p = Profile()
    with pytest.raises(ProfileError, match=field):
        set_avatar(p, {"build": "slim", **avatar})
    assert p.avatar == DEFAULT_AVATAR


def test_invalid_avatar_in_file_falls_back(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"version": 1, "avatar": {"skin": 99},
                                "purchases": [{"item_id": "wheels_light", "price": 100}]}),
                    encoding="utf-8")
    p = load_profile(path)
    assert p.avatar == DEFAULT_AVATAR and p.purchased == {"wheels_light"}


def test_purchases_and_lives():
    p = Profile()
    record_purchase(p, "frame_aero", 250)
    with pytest.raises(ProfileError, match="déjà"):
        record_purchase(p, "frame_aero", 250)
    with pytest.raises(ProfileError, match="aucune vie"):
        use_life(p)
    record_life_purchase(p, 30)
    use_life(p)
    assert p.lives == {"bought": 1, "used": 1, "spent": 30}
    assert p.spent == 280 and p.lives_left == 0


def test_profile_holds_no_personal_fields():
    keys = set(Profile().to_dict()) | set(DEFAULT_AVATAR)
    assert not keys & {"name", "nom", "weight", "mass_kg", "masse", "height_cm", "ftp", "ftp_w"}


def test_save_creates_parent_dir(tmp_path):
    path = tmp_path / "sous" / "profile.json"
    save_profile(Profile(), path)
    assert path.exists() and not os.path.exists(str(path) + ".bak")
