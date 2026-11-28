"""Répétition d'un essai avec une copie d'un vrai profil (28 novembre) : `--profils-source` et `--parcours`."""

import argparse
import importlib.util
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mb = _load("menu_bench")


def _source(tmp_path):
    src = tmp_path / "Profils.sauvegarde"
    (src / "cycliste-a" / "Activities").mkdir(parents=True)
    (src / ".migration").write_text("fini\n", encoding="utf-8")
    (src / "cycliste-a" / "profil.toml").write_text("[profil]\nid = \"cycliste-a\"\n", encoding="utf-8")
    (src / "cycliste-a" / "Activities" / "s1.fit").write_bytes(b"fit")
    (src / "cycliste-a" / ".verrou").write_text("1234", encoding="utf-8")
    (src / "cycliste-a" / ".cache").mkdir()
    (src / "cycliste-a" / ".cache" / "courbe.json").write_text("{}", encoding="utf-8")
    return src


def test_copie_du_profil_sans_verrou_ni_cache_source_intacte(tmp_path):
    src = _source(tmp_path)
    routes_src = tmp_path / "routes"
    (routes_src / "circuit.world").mkdir(parents=True)
    (routes_src / "circuit.world" / "route.json").write_text("{}", encoding="utf-8")
    (routes_src / "circuit.fiche.toml").write_text("x = 1\n", encoding="utf-8")
    home, routes = tmp_path / "home", tmp_path / "home" / "routes"
    routes.mkdir(parents=True)
    (home / "OpenRide" / "Profils" / "du-scenario").mkdir(parents=True)   # profils du scénario remplacés
    args = argparse.Namespace(profils_source=src, parcours=["circuit"], parcours_source=routes_src)
    assert mb.check_real_sources(args) is None
    avant = sorted(p.relative_to(src) for p in src.rglob("*"))
    mb.copy_real_sources(args, home, routes)
    dest = home / "OpenRide" / "Profils"
    assert (dest / "cycliste-a" / "Activities" / "s1.fit").read_bytes() == b"fit"
    assert not (dest / "cycliste-a" / ".verrou").exists() and not (dest / "cycliste-a" / ".cache").exists()
    assert not (dest / "du-scenario").exists()
    assert (routes / "circuit.world" / "route.json").is_file() and (routes / "circuit.fiche.toml").is_file()
    assert sorted(p.relative_to(src) for p in src.rglob("*")) == avant   # la source n'est que lue


def test_sources_absentes_refusees(tmp_path):
    vide = tmp_path / "vide"
    vide.mkdir()
    args = argparse.Namespace(profils_source=vide, parcours=None, parcours_source=tmp_path)
    assert "n'est pas un dossier Profils" in mb.check_real_sources(args)
    args = argparse.Namespace(profils_source=None, parcours=["absent"], parcours_source=tmp_path)
    assert "absent" in mb.check_real_sources(args)
    assert mb.check_real_sources(argparse.Namespace(profils_source=None, parcours=None, parcours_source=tmp_path)) is None
