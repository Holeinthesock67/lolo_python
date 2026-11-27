"""Scanner de confidentialité (lot X23) : règles sur du texte fictif et sur un petit dépôt git."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "privacy" / "privacy_scan.py"
spec = importlib.util.spec_from_file_location("privacy_scan", SCRIPT)
ps = importlib.util.module_from_spec(spec)
sys.modules["privacy_scan"] = ps
spec.loader.exec_module(ps)

DL = ps.parse_denylist("jean-exemple\nDupont  # commentaire\nregex: ftp_w\\s*=\\s*999\nzone: 45.0, 5.0, 5\n")


def rules(text: str) -> list[str]:
    return [f.rule for f in ps.scan_text("f", text, DL)]


def test_words_ignore_case_and_accents_and_need_whole_words():
    assert rules("Auteur : DÛPONT") == ["mot interdit"]
    assert rules("dupontel et redupont") == []
    assert rules("par jean-exemple") == ["mot interdit"]


def test_findings_are_masked():
    (f,) = ps.scan_text("f", "dupont", DL)
    assert "dupont" not in str(f) and "d*" not in str(f) and f.detail == "mot n° 2 de la liste"


def test_regex_entries():
    assert rules("ftp_w = 999") == ["motif interdit"]
    assert rules("ftp_w = 250") == []


def test_gps_zone_flags_precise_points_only():
    assert rules("48.85, 2.35") == []                        # hors zone
    assert rules("lat = 45.0123 ; lon = 5.0456") == ["coordonnée dans une zone privée"]
    assert rules('<trkpt lat="45.01" lon="5.02">') == ["coordonnée dans une zone privée"]
    assert rules("45.0, 5.0") == []                          # arrondi à une décimale : admis


def test_gps_zone_other_layouts():
    # RC18, O2-08 : deux lignes, ordre GeoJSON, virgule décimale.
    z = ["coordonnée dans une zone privée"]
    assert rules("lat = 45.0123\nlon = 5.0456") == z                    # TOML
    assert rules('{\n  "lat": 45.0123,\n  "ele": 300,\n  "lon": 5.0456\n}') == z   # JSON indenté
    assert rules('<trkpt lat="45.01"\n       lon="5.02">') == z         # GPX sur deux lignes
    assert rules('"coordinates": [5.0456, 45.0123]') == z                # GeoJSON
    assert rules('"coordinates": [\n  5.0456,\n  45.0123\n]') == z     # GeoJSON indenté
    assert rules("45,0123 ; 5,0456") == z                                # virgule décimale
    assert rules("lat = 45,0123\nlon = 5,0456") == z
    (f,) = ps.scan_text("f", "x\nlat = 45.0123\nlon = 5.0456", DL)
    assert f.where == "f:2"
    assert rules("lat = 45.0123\n\n\n\n\nlon = 5.0456") == []             # trop loin l'une de l'autre
    assert rules("lat = 48.85\nlon = 2.35") == []                         # hors zone
    assert rules("45,0, 5,0") == []                                      # une décimale : admis


def test_bluetooth_addresses():
    assert rules("C1:1C:00:00:00:01 AA:BB:CC:DD:EE:FF 00:00:00:00:00:00") == []
    assert rules("adresse E4:5F:01:" + "23:9A:7B") == ["adresse Bluetooth réelle ?"]


def test_bluetooth_other_spellings_and_narrow_allowlist():
    # RC18, O2-11 : forme BlueZ, forme à tirets, et préfixes « AA: » / « BB: » qui ne suffisent plus.
    real = "E4:5F:01:" + "23:9A:7B"
    for text in ("/org/bluez/hci0/dev_" + real.replace(":", "_"), "mac " + real.replace(":", "-"),
                 "AA:5F:01:" + "23:9A:7B", "bb:12:34:" + "56:78:9a"):
        assert rules(text) == ["adresse Bluetooth réelle ?"], text
    (f,) = ps.scan_text("f", real, DL)
    assert "E4" not in str(f)                                   # rien de l'adresse dans le journal
    assert rules("dev_C1_1C_00_00_00_01 aa-00-00-00-00-02 AA:BB:CC:00:11:22") == []
    assert rules("2026-11-24-03-21-44") == []                   # date : groupes de 4 chiffres
    assert rules("id 11:22:33:44:55:66:77") == []               # sept octets : pas une adresse


def test_secrets():
    assert rules("token = ghp_" + "a" * 36) == ["jeton GitHub"]
    assert rules("-----BEGIN OPENSSH " + "PRIVATE KEY-----") == ["clé privée"]
    assert rules("AKIA" + "A" * 16) == ["clé AWS"]


def test_forbidden_file_names():
    assert ps.scan_path_name("x/sortie.FIT")
    assert ps.scan_path_name("trace.gpx")
    assert ps.scan_path_name("seance.jsonl")
    assert ps.scan_path_name(".env")
    assert not ps.scan_path_name(".env.example")
    assert not ps.scan_path_name("scripts/config.example.toml")


def test_load_denylist_merges_env_and_file(tmp_path, monkeypatch):
    f = tmp_path / "liste.txt"
    f.write_text("dupont\n", encoding="utf-8")
    monkeypatch.setenv("PRIVACY_DENYLIST", "jean-exemple\nzone: 1, 2, 3")
    dl = ps.load_denylist(f)
    assert dl.words == ["jean-exemple", "dupont"] and dl.zones == [(1.0, 2.0, 3.0)]


def _git(repo, *args, env=None):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACY_DENYLIST", "dupont\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "1+ex@users.noreply.github.com")
    _git(tmp_path, "config", "user.name", "Exemple")
    (tmp_path / "a.txt").write_text("rien\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "départ")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_staged_mode_blocks_a_commit(repo, capsys):
    (repo / "b.txt").write_text("écrit par Dupont\n", encoding="utf-8")
    _git(repo, "add", "b.txt")
    assert ps.main(["--staged"]) == 1
    assert "b.txt:1: mot interdit" in capsys.readouterr().out


def test_commits_mode_checks_author_and_removed_lines(repo, capsys):
    _git(repo, "config", "user.name", "Dupont")
    _git(repo, "config", "user.email", "dupont@example.org")
    (repo / "a.txt").write_text("clé ghp_" + "b" * 36 + "\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "ajout")
    (repo / "a.txt").write_text("rien\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "retrait")
    assert ps.main(["--all"]) == 0          # l'arbre final est propre…
    capsys.readouterr()
    assert ps.main(["--commits", "HEAD~2..HEAD"]) == 1   # …mais l'historique ne l'est pas
    out = capsys.readouterr().out
    assert "adresse e-mail de l'auteur" in out and "mot interdit" in out and "jeton GitHub" in out


def test_commits_mode_checks_merge_commits(repo, capsys):
    # RC18, O2-07 : une fusion --no-ff faite avec une autre configuration git est contrôlée.
    _git(repo, "checkout", "-q", "-b", "pr")
    (repo / "b.txt").write_text("propre\n", encoding="utf-8")
    _git(repo, "add", "b.txt")
    _git(repo, "commit", "-qm", "branche")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "config", "user.name", "Dupont")
    _git(repo, "config", "user.email", "dupont@example.org")
    _git(repo, "merge", "-q", "--no-ff", "-m", "fusion par Dupont", "pr")
    capsys.readouterr()
    assert ps.main(["--commits", "HEAD~1..HEAD"]) == 1
    out = capsys.readouterr().out
    assert "adresse e-mail de l'auteur" in out and "(message)" in out and "(auteur et committer)" in out


def test_commits_mode_unknown_or_null_base(repo, capsys):
    # Envoi d'une branche nouvelle (before nul) ou après réécriture : on contrôle au moins la tête.
    _git(repo, "config", "user.email", "dupont@example.org")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "vide")
    capsys.readouterr()
    assert ps.main(["--commits", "0" * 40 + "..HEAD"]) == 1
    assert ps.main(["--commits", "deadbeef" * 5 + "..HEAD"]) == 1
    assert "adresse e-mail" in capsys.readouterr().out


def test_malformed_denylist_does_not_print_its_value(repo, monkeypatch, capsys):
    # RC18, O2-12 : le journal public de la CI ne montre pas le morceau de coordonnée.
    monkeypatch.setenv("PRIVACY_DENYLIST", "zone: 45.01234 6.98765, 2\n")
    assert ps.main(["--all"]) == 2
    err = capsys.readouterr().err
    assert "ligne 1" in err and "45.01" not in err and "6.98" not in err
    monkeypatch.setenv("PRIVACY_DENYLIST", "regex: secret(\n")
    assert ps.main(["--all"]) == 2
    assert "secret" not in capsys.readouterr().err


def test_require_denylist(repo, monkeypatch):
    monkeypatch.delenv("PRIVACY_DENYLIST")
    assert ps.main(["--all", "--require-denylist"]) == 2
    assert ps.main(["--all"]) == 0
