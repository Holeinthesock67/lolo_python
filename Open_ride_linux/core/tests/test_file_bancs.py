"""File des bancs en étapes courtes avec reprise (plan du 19 novembre) et garde-fou du cache de menu_bench."""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fb = _load("file_bancs", ROOT / "scripts" / "file_bancs.py")
mb = _load("menu_bench", ROOT / "engine" / "tests" / "menu_bench.py")

PY = sys.executable


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def depot(tmp_path):
    """Dépôt avec une origine : main et une branche, chacune avec un dossier Open_ride_linux."""
    origine = tmp_path / "origine"
    origine.mkdir()
    _git(origine, "init", "-q", "-b", "main")
    _git(origine, "config", "user.email", "t@t")
    _git(origine, "config", "user.name", "t")
    (origine / "Open_ride_linux").mkdir()
    (origine / "Open_ride_linux" / "x.txt").write_text("main", encoding="utf-8")
    _git(origine, "add", ".")
    _git(origine, "commit", "-q", "-m", "main")
    _git(origine, "checkout", "-q", "-b", "br")
    (origine / "Open_ride_linux" / "x.txt").write_text("branche", encoding="utf-8")
    _git(origine, "commit", "-q", "-am", "br")
    _git(origine, "checkout", "-q", "main")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(origine), str(clone)], check=True)
    return origine, clone


def _cmd(code, texte=""):
    """Commande d'étape : écrit un texte, compte ses passages dans {sortie}.n, rend un code."""
    script = (f"import pathlib,sys; p=pathlib.Path(sys.argv[1]+\".n\"); p.write_text(str(int(p.read_text() or 0)+1) "
              f"if p.exists() else '1'); print({texte!r}); sys.exit({code})")
    return f"{PY} -c {json.dumps(script)} {{sortie}}"


def _file(tmp_path, clone, prs: str) -> Path:
    f = tmp_path / "file.toml"
    f.write_text(f'[file]\ndepot = "{clone}"\nsortie = "{tmp_path / "sortie"}"\n{prs}', encoding="utf-8")
    return f


def _etat(tmp_path):
    return json.loads((tmp_path / "sortie" / "etat.json").read_text(encoding="utf-8"))


def _passages(tmp_path, pr, etape):
    p = tmp_path / "sortie" / pr / etape / "rapport.n"
    return int(p.read_text()) if p.exists() else 0


def test_classer_separe_contacts_environnement_et_echec():
    assert fb.classer(0, "")[0] == fb.OK
    fin = "\nRapport : /x/index.html\n"                # ligne de fin d'un banc allé au bout
    assert fb.classer(1, "[ÉCHEC] décor : aucun contact sur la route : 3" + fin)[0] == fb.CONTACTS
    v, d = fb.classer(1, "[ÉCHEC] décor : aucun contact sur la route : 3\n[ÉCHEC] pire image : 140 ms" + fin)
    assert v == fb.ACOUPS and "1 à-coup(s) connu(s), 1 contact(s)" in d
    assert fb.classer(1, "[ÉCHEC] images lentes : 8 par minute" + fin)[0] == fb.ACOUPS
    assert fb.ACOUPS in fb.ACQUIS
    v, d = fb.classer(1, "[ÉCHEC] pire image : 140 ms\n[ÉCHEC] pont : tablier absent")
    assert v == fb.ECHEC and "2 échec(s)" in d
    assert fb.classer(1, "CompileError: x.sqlite : schéma 2 au lieu de 1, refaire `region-add`")[0] == fb.ENV
    assert fb.classer(2, "Godot introuvable : /x")[0] == fb.ENV
    assert fb.classer(1, "Traceback")[0] == fb.ECHEC


def test_fumees_dabord_puis_risque_et_pr_bloquee(tmp_path, depot):
    _, clone = depot
    f = _file(tmp_path, clone, f"""
[[pr]]
id = "sure"
branche = "br"
risque = 3
fumee = {json.dumps(_cmd(0))}
[[pr.etape]]
id = "low"
commande = {json.dumps(_cmd(0))}

[[pr]]
id = "risquee"
branche = "br"
risque = 1
fumee = {json.dumps(_cmd(1, "[ÉCHEC] départ du monde ouvert : refusé"))}
[[pr.etape]]
id = "low"
commande = {json.dumps(_cmd(0))}
""")
    journal = []
    r = fb.Runner(fb.lire_file(f), reseau=False, log=journal.append)
    assert r.lancer() == 1
    lancees = [l.split()[1] for l in journal if l.startswith("→")]
    assert lancees == ["risquee/fumee", "sure/fumee", "sure/low"]   # fumées d'abord, risque 1 en tête
    etat = _etat(tmp_path)["prs"]
    assert etat["risquee"]["low"]["verdict"] == fb.BLOQUE
    assert etat["sure"]["low"]["verdict"] == fb.OK
    assert "BLOQUÉ" in (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")


def test_reprise_ne_rejoue_pas_les_etapes_ok(tmp_path, depot):
    _, clone = depot
    marque = tmp_path / "high_ok"
    high = (f"{PY} -c \"import pathlib,sys; sys.exit(0 if pathlib.Path(r'{marque}').exists() else 1)\"")
    f = _file(tmp_path, clone, f"""
[[pr]]
id = "p"
branche = "br"
[[pr.etape]]
id = "low"
commande = {json.dumps(_cmd(0))}
[[pr.etape]]
id = "high"
commande = {json.dumps(high)}
""")
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    assert _etat(tmp_path)["prs"]["p"]["high"]["verdict"] == fb.ECHEC
    marque.touch()
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    assert _passages(tmp_path, "p", "low") == 1          # low n'a pas été rejoué
    assert _etat(tmp_path)["prs"]["p"]["high"]["verdict"] == fb.OK


def test_relancer_apres_correction_garde_les_ok_de_lancienne_tete(tmp_path, depot):
    origine, clone = depot
    f = _file(tmp_path, clone, f"""
[[pr]]
id = "p"
branche = "br"
fumee = {json.dumps(_cmd(0))}
[[pr.etape]]
id = "low"
commande = {json.dumps(_cmd(0))}
[[pr.etape]]
id = "high"
commande = "{PY} -c \\"import pathlib,sys; sys.exit(0 if pathlib.Path('x.txt').read_text()=='corrigé' else 1)\\""
""")
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    # Correction poussée sur la branche : nouvelle tête.
    _git(origine, "checkout", "-q", "br")
    (origine / "Open_ride_linux" / "x.txt").write_text("corrigé", encoding="utf-8")
    _git(origine, "commit", "-q", "-am", "corrige")
    _git(clone, "fetch", "-q", "origin")
    assert fb.main(["relancer", str(f), "--sans-reseau"]) == 0
    assert _passages(tmp_path, "p", "low") == 1          # OK de l'ancienne tête gardé
    assert _passages(tmp_path, "p", "fumee") == 2        # fumée rejouée avant le rebanc ciblé
    etat = _etat(tmp_path)["prs"]["p"]
    assert etat["high"]["verdict"] == fb.OK and etat["low"]["tete"] != etat["high"]["tete"]
    assert "sur tête" in (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")
    # `lancer` sur la nouvelle tête, lui, rejoue tout.
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    assert _passages(tmp_path, "p", "low") == 2


def test_reference_main_commune_a_toute_la_file(tmp_path, depot):
    _, clone = depot
    etape_main = f"""[[pr.etape]]
id = "main-low"
sur = "main"
commande = {json.dumps(_cmd(0))}
"""
    f = _file(tmp_path, clone, f'[[pr]]\nid = "a"\nbranche = "br"\n{etape_main}\n[[pr]]\nid = "b"\nbranche = "br"\n{etape_main}')
    journal = []
    assert fb.Runner(fb.lire_file(f), reseau=False, log=journal.append).lancer() == 0
    assert sum(l.startswith("→") for l in journal) == 1     # main joué une seule fois pour les deux PR


def test_pause_et_delai(tmp_path, depot):
    _, clone = depot
    f = _file(tmp_path, clone, f"""
[[pr]]
id = "p"
branche = "br"
[[pr.etape]]
id = "long"
commande = "{PY} -c 'import time; time.sleep(30)'"
delai_min = 0.02
""")
    (tmp_path / "sortie").mkdir()
    (tmp_path / "sortie" / "PAUSE").touch()
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 3
    (tmp_path / "sortie" / "PAUSE").unlink()
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    assert _etat(tmp_path)["prs"]["p"]["long"]["verdict"] == fb.DELAI


def test_file_invalide(tmp_path, depot):
    _, clone = depot
    g = _file(tmp_path, clone, '[[pr]]\nid = "p"\nbranche = "br"\ncache = "partage"\n')
    assert fb.main(["etat", str(g)]) == 2


def test_cache_separe_amorce_et_variable(tmp_path, depot, monkeypatch):
    _, clone = depot
    home = tmp_path / "home"
    (home / "OpenRide" / "Cache" / "monde" / "brut").mkdir(parents=True)
    (home / "OpenRide" / "Cache" / "monde" / "brut" / "a.txt").write_text("reel", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    cmd = f"{PY} -c \"import os; print(os.environ['OPENRIDE_BANC_CACHES'])\""
    f = _file(tmp_path, clone, f'[[pr]]\nid = "mer"\nbranche = "br"\ncache = "separe"\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(cmd)}\n')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    racine = tmp_path / "sortie" / "caches" / "mer"
    assert (racine / "monde" / "brut" / "a.txt").read_text(encoding="utf-8") == "reel"
    assert str(racine) in (tmp_path / "sortie" / "mer" / "low" / "journal.txt").read_text(encoding="utf-8")


def test_cache_separe_sans_les_balades_ni_les_carres_du_user(tmp_path, depot, monkeypatch):
    """Signalement du 21 novembre : le cache « séparé » contenait 107 balades du user et d'autres zones UTM."""
    _, clone = depot
    reel = tmp_path / "home" / "OpenRide" / "Cache" / "monde"
    for rel in ("brut/osm/fr.sqlite", "seances/ow-1/route.json", "genere/32T/1_2/meta.json", "mesures/m/x.json"):
        (reel / rel).parent.mkdir(parents=True, exist_ok=True)
        (reel / rel).write_text("x", encoding="utf-8")
    con = sqlite3.connect(reel / "index.sqlite")
    con.executescript("CREATE TABLE entries (key TEXT PRIMARY KEY, kind TEXT, path TEXT, bytes INTEGER, "
                      "last_used REAL, pinned INTEGER, prefetch INTEGER, region TEXT, versions TEXT);"
                      "CREATE TABLE regions (region TEXT PRIMARY KEY, pinned INTEGER, name TEXT, bbox TEXT);"
                      "INSERT INTO entries VALUES ('osm:fr','osm','brut/osm/fr.sqlite',1,0,1,0,'fr','{}');"
                      "INSERT INTO entries VALUES ('square:32T/1_2','square','genere/32T/1_2',1,0,0,0,NULL,'{}');"
                      "INSERT INTO regions VALUES ('fr',1,'France','[]');")
    con.commit()
    con.close()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    f = fb.lire_file(_file(tmp_path, clone, f'[[pr]]\nid = "ow"\nbranche = "br"\ncache = "separe"\n'
                                           f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n'))
    # Ancien amorçage (copie complète, 19 novembre) : refait.
    ancien = tmp_path / "sortie" / "caches" / "ow" / "monde" / "seances" / "ow-1"
    ancien.mkdir(parents=True)
    journal = []
    monde = fb.cache_separe(f, f.prs[0], journal.append) / "monde"
    assert "refait" in journal[0]
    assert (monde / "brut" / "osm" / "fr.sqlite").is_file()
    for absent in ("seances", "genere", "mesures"):
        assert not (monde / absent).exists()
    con = sqlite3.connect(monde / "index.sqlite")
    assert con.execute("SELECT key FROM entries").fetchall() == [("osm:fr",)]
    assert con.execute("SELECT name FROM regions").fetchall() == [("France",)]
    con.close()
    journal.clear()
    assert fb.cache_separe(f, f.prs[0], journal.append) / "monde" == monde and journal == []   # amorcé une fois
    assert (reel / "seances" / "ow-1" / "route.json").is_file()                              # cache réel intact


def _base(path: Path, schema: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE meta(key TEXT, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', ?)", (schema,))
    con.commit()
    con.close()


def test_menu_bench_refuse_un_cache_reel_dun_autre_schema(tmp_path, monkeypatch):
    cache = tmp_path / "monde"
    _base(cache / "brut" / "osm" / "tuiles.sqlite", "2")
    msg = mb.schema_guard(cache, "1")
    assert msg and "schéma 2" in msg and fb.classer(1, f"[ÉCHEC] cache : {msg}")[0] == fb.ENV
    assert mb.schema_guard(cache, "2") is None
    assert mb.branch_schema_version() == "1"
    monkeypatch.setenv(mb.VARIABLE_CACHES_BANC, str(tmp_path / "pr907"))
    assert mb.open_world_cache_dir() == (tmp_path / "pr907" / "monde", False)
    monkeypatch.delenv(mb.VARIABLE_CACHES_BANC)
    assert mb.open_world_cache_dir()[1] is True


def _branche(origine, nom, fichiers, depuis="main"):
    _git(origine, "checkout", "-q", "-b", nom, depuis)
    for rel, texte in fichiers.items():
        p = origine / "Open_ride_linux" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texte, encoding="utf-8")
    _git(origine, "add", ".")
    _git(origine, "commit", "-q", "-m", nom)
    _git(origine, "checkout", "-q", "main")


def test_portail_attend_puis_apres_etape_recoit_le_verdict(tmp_path, depot):
    _, clone = depot
    compteur, trace = tmp_path / "portail.n", tmp_path / "apres.txt"
    portail = (f"{PY} -c \"import pathlib,sys; p=pathlib.Path(r'{compteur}'); n=int(p.read_text()) if p.exists() else 0; "
               f"p.write_text(str(n+1)); print('Godot du user ouvert'); sys.exit(0 if n >= 2 else 1)\"")
    apres = f"{PY} -c \"import sys; open(r'{trace}','a').write(' '.join(sys.argv[1:])+chr(10))\" {{pr}} {{etape}} {{verdict}}"
    f = tmp_path / "file.toml"
    f.write_text(f'[file]\ndepot = "{clone}"\nsortie = "{tmp_path / "sortie"}"\nattente_s = 0\n'
                 f'avant_etape = {json.dumps(portail)}\napres_etape = {json.dumps(apres)}\n'
                 f'[[pr]]\nid = "p"\nbranche = "br"\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n',
                 encoding="utf-8")
    journal = []
    assert fb.Runner(fb.lire_file(f), reseau=False, log=journal.append).lancer() == 0
    assert int(compteur.read_text()) == 3                    # deux refus, puis feu vert
    assert any("en attente avant p/low : Godot du user ouvert" in l for l in journal)
    assert trace.read_text(encoding="utf-8").split() == ["p", "low", "OK"]
    assert _etat(tmp_path)["prs"]["p"]["low"]["apres_etape"] == "OK"


def test_essai_assemble_fusionne_les_branches(tmp_path, depot):
    origine, clone = depot
    _branche(origine, "b2", {"y.txt": "b2"})
    _git(clone, "fetch", "-q", "origin")
    cmd = f"{PY} -c \"import pathlib; print(pathlib.Path('x.txt').read_text(), pathlib.Path('y.txt').read_text())\""
    f = _file(tmp_path, clone, f'[[pr]]\nid = "essai-ow"\nbranche = "br"\nassemblage = ["b2"]\n'
                               f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(cmd)}\n')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    assert "branche b2" in (tmp_path / "sortie" / "essai-ow" / "low" / "journal.txt").read_text(encoding="utf-8")
    v = _etat(tmp_path)["prs"]["essai-ow"]["low"]
    assert v["verdict"] == fb.OK and "+" in v["tete"]
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0   # même assemblage : rien de rejoué
    assert "sur tête" not in (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")


def test_pr_qui_change_le_schema_jamais_sur_le_cache_reel(tmp_path, depot):
    origine, clone = depot
    src = "compiler/src/openride_compiler/worldgen/osmdb.py"
    _branche(origine, "base", {src: "SCHEMA_VERSION = 1\n"})
    _git(origine, "checkout", "-q", "main")
    _git(origine, "merge", "-q", "base")
    _branche(origine, "mer", {src: "SCHEMA_VERSION = 2\n"})
    _git(clone, "fetch", "-q", "origin")
    etape = f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n'
    f = _file(tmp_path, clone, f'[[pr]]\nid = "mer"\nbranche = "mer"\ncache = "reel"\n{etape}')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    v = _etat(tmp_path)["prs"]["mer"]["low"]
    assert v["verdict"] == fb.ENV and "1 → 2" in v["detail"]
    assert _passages(tmp_path, "mer", "low") == 0             # rien lancé
    g = _file(tmp_path, clone, f'[[pr]]\nid = "mer"\nbranche = "mer"\ncache = "separe"\n{etape}')
    assert fb.main(["lancer", str(g), "--sans-reseau"]) == 0


def test_tete_changee_en_cours_de_file_ne_bloque_que_sa_pr(tmp_path, depot):
    _, clone = depot
    f = _file(tmp_path, clone, f'[[pr]]\nid = "vieille"\nbranche = "br"\ntete = "deadbeef"\n'
                               f'fumee = {json.dumps(_cmd(0))}\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n'
                               f'[[pr]]\nid = "ok"\nbranche = "br"\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    etat = _etat(tmp_path)["prs"]
    assert etat["vieille"]["fumee"]["verdict"] == fb.ENV and "deadbeef" in etat["vieille"]["fumee"]["detail"]
    assert etat["vieille"]["low"]["verdict"] == fb.BLOQUE and etat["ok"]["low"]["verdict"] == fb.OK


def test_portail_pc_fenetre_du_user_et_godot(tmp_path):
    """portail_pc.sh : attend la fin de la fenêtre du user (ou son marqueur) et l'absence de Godot."""
    import time

    script = ROOT / "scripts" / "file_bancs" / "portail_pc.sh"
    binf = tmp_path / "bin"
    binf.mkdir()
    pgrep = binf / "pgrep"
    pgrep.write_text("#!/bin/sh\n[ -f \"$GODOT_OUVERT\" ] && { echo '42 Godot_v4.7'; exit 0; }\nexit 1\n", encoding="utf-8")
    pgrep.chmod(0o755)
    fen = tmp_path / "fenetre.txt"
    now = int(time.time())
    fen.write_text(f"{now + 600} {now + 3600} pc_rendu\n", encoding="utf-8")
    env = {"PATH": f"{binf}:/usr/bin:/bin", "HOME": str(tmp_path), "FENETRE": str(fen),
           "GODOT_OUVERT": str(tmp_path / "godot"), "FILE_DUREE_MIN": "30"}

    def code(**extra):
        return subprocess.run(["bash", str(script)], env={**env, **extra}, capture_output=True, text=True)

    p = code()
    assert p.returncode == 1 and "fenêtre du user" in p.stdout     # 30 min déborderaient sur la fenêtre
    assert code(FILE_DUREE_MIN="5").returncode == 0                  # 5 min finissent avant
    (tmp_path / "pc_rendu").touch()
    assert code().returncode == 0                                    # marqueur « PC rendu »
    (tmp_path / "godot").touch()
    p = code()
    assert p.returncode == 1 and "Godot" in p.stdout


def test_exemple_rfs3_se_lit():
    f = fb.lire_file(ROOT / "scripts" / "file_bancs" / "exemple_rFS3.toml")
    assert [e.id for e in f.prs[0].etapes] == ["fumee", "tests-engine", "low", "high", "medium"]
    assert f.avant_etape and f.apres_etape and "{dossier}" in f.apres_etape


def test_depot_qui_ne_suit_que_main(tmp_path, depot):
    """Dépôt du user : refspec de fetch réduite à main ; la file doit quand même trouver la tête de la branche."""
    _, clone = depot
    _git(clone, "config", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main")
    _git(clone, "update-ref", "-d", "refs/remotes/origin/br")
    f = _file(tmp_path, clone, f'[[pr]]\nid = "p"\nbranche = "br"\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n')
    assert fb.Runner(fb.lire_file(f), reseau=True, log=lambda *_: None).lancer() == 0
    assert _etat(tmp_path)["prs"]["p"]["low"]["verdict"] == fb.OK


def test_environnement_des_etapes_comme_job_sh(tmp_path, depot):
    """PYTHONPATH sur les sources du worktree et core/.venv du dépôt (étape tests-engine de rFS3 du 19 novembre)."""
    origine, clone = depot
    _branche(origine, "eng", {"core/a.txt": "x"})
    _git(clone, "fetch", "-q", "origin")
    venv = clone / "Open_ride_linux" / "core" / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("", encoding="utf-8")
    cmd = (f"{PY} -c \"import os; print(os.environ['PYTHONPATH']); print(os.environ['VIRTUAL_ENV']); "
           f"print(os.environ['PATH'].split(os.pathsep)[0]); print(os.environ['LC_NUMERIC'])\"")
    f = _file(tmp_path, clone, f'[[pr]]\nid = "p"\nbranche = "eng"\n[[pr.etape]]\nid = "tests-engine"\ncommande = {json.dumps(cmd)}\n')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    projet = tmp_path / "sortie" / "worktrees" / "p" / "Open_ride_linux"
    lignes = (tmp_path / "sortie" / "p" / "tests-engine" / "journal.txt").read_text(encoding="utf-8").splitlines()
    assert lignes[0].split(os.pathsep)[:2] == [str(projet / "core" / "src"), str(projet / "compiler" / "src")]
    assert lignes[1] == str(venv.parent) and lignes[2] == str(venv) and lignes[3] == "C"
    assert (projet / "core" / ".venv").resolve() == venv.parent.resolve()


def test_assemblage_en_conflit_resolu_par_strategie(tmp_path, depot):
    origine, clone = depot
    _branche(origine, "b2", {"x.txt": "b2"})                 # même fichier que br : conflit
    _git(clone, "fetch", "-q", "origin")
    cmd = f"{PY} -c \"import pathlib; print(pathlib.Path('x.txt').read_text())\""
    etape = f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(cmd)}\n'
    f = _file(tmp_path, clone, f'[[pr]]\nid = "ow"\nbranche = "br"\nassemblage = ["b2"]\n{etape}')
    fb.main(["lancer", str(f), "--sans-reseau"])
    assert _etat(tmp_path)["prs"]["ow"]["low"]["verdict"] != fb.OK
    f = _file(tmp_path, clone, f'[[pr]]\nid = "ow"\nbranche = "br"\nassemblage = ["b2"]\n'
                               f'assemblage_strategie = "ours"\n{etape}')
    assert fb.main(["relancer", str(f), "--sans-reseau"]) == 0
    assert _etat(tmp_path)["prs"]["ow"]["low"]["verdict"] == fb.OK
    assert "branche" in (tmp_path / "sortie" / "ow" / "low" / "journal.txt").read_text(encoding="utf-8")


def test_strategie_inconnue_refusee(tmp_path, depot):
    _, clone = depot
    f = _file(tmp_path, clone, '[[pr]]\nid = "p"\nbranche = "br"\nassemblage_strategie = "octopus"\n'
                               f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n')
    with pytest.raises(fb.FileInvalide):
        fb.lire_file(f)


# --- paquets, matrice rendu/logique, étapes cloud (plan du 20 novembre) -----------------------------------------

def _tete(clone, branche):
    return subprocess.run(["git", "-C", str(clone), "rev-parse", f"origin/{branche}"], check=True,
                          capture_output=True, text=True).stdout.strip()


def _paquet(clone, branches, corps="", pid="p1"):
    membres = "".join(f'[[paquet.membre]]\npr = {900 + i}\nbranche = "{b}"\ntete = "{_tete(clone, b)[:8]}"\n'
                      for i, b in enumerate(branches))
    return f'[[paquet]]\nid = "{pid}"\n{corps}\n{membres}'


def test_paquet_un_seul_banc_sur_les_branches_assemblees(tmp_path, depot):
    origine, clone = depot
    for b in ("pa", "pb", "pc"):
        _branche(origine, b, {f"{b}.txt": b})
    _git(clone, "fetch", "-q", "origin")
    lire = f"{PY} -c \"import pathlib; print(sorted(p.name for p in pathlib.Path('.').glob('p?.txt')))\" && "
    f = _file(tmp_path, clone, _paquet(clone, ["pa", "pb", "pc"],
              f'fumee = {json.dumps(_cmd(0))}\nmatrice = {json.dumps(lire + _cmd(0) + " {qualite}")}'))
    journal = []
    r = fb.Runner(fb.lire_file(f), reseau=False, log=journal.append)
    assert r.lancer() == 0
    lancees = [l.split()[1] for l in journal if l.startswith("→")]
    assert lancees == ["p1/fumee", "p1/low", "p1/high", "p1/medium"]   # rendu par défaut : 3 qualités, risque d'abord
    assert "['pa.txt', 'pb.txt', 'pc.txt']" in (tmp_path / "sortie" / "p1" / "low" / "journal.txt").read_text()
    assert "p1 (#900 + #901 + #902)" in (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")


def test_paquet_en_echec_separe_pr_par_pr_seulement_les_etapes_en_echec(tmp_path, depot):
    origine, clone = depot
    for b in ("pa", "pb", "pc"):
        _branche(origine, b, {f"{b}.txt": b})
    _git(clone, "fetch", "-q", "origin")
    # high échoue dès que pc.txt est là : la PR fautive est pc.
    high = (f"{PY} -c \"import pathlib,sys; print('[ÉCHEC] pont : tablier absent' if pathlib.Path('pc.txt').exists() "
            f"else 'ok'); sys.exit(1 if pathlib.Path('pc.txt').exists() else 0)\"")
    corps = (f'fumee = {json.dumps(_cmd(0))}\n[[paquet.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n'
             f'[[paquet.etape]]\nid = "high"\ncommande = {json.dumps(high)}\n')
    f = _file(tmp_path, clone, _paquet(clone, ["pa", "pb", "pc"], corps))
    journal = []
    r = fb.Runner(fb.lire_file(f), reseau=False, log=journal.append)
    assert r.lancer() == 1
    etat = _etat(tmp_path)["prs"]
    assert etat["p1"]["low"]["verdict"] == fb.OK
    assert etat["p1"]["high"]["verdict"] == fb.SCINDE and etat["p1"]["high"]["avant"] == fb.ECHEC
    assert etat["p1.r900"]["high"]["verdict"] == fb.OK and etat["p1.r901"]["high"]["verdict"] == fb.OK
    assert etat["p1.r902"]["high"]["verdict"] == fb.ECHEC
    assert "low" not in etat["p1.r902"]                     # seules les étapes en échec sont rejouées
    lancees = [l.split()[1] for l in journal if l.startswith("→")]
    assert lancees[-6:] == ["p1.r900/fumee", "p1.r901/fumee", "p1.r902/fumee",
                            "p1.r900/high", "p1.r901/high", "p1.r902/high"]
    # Reprise : rien de rejoué en paquet, la PR séparée en échec seule l'est.
    journal.clear()
    r = fb.Runner(fb.lire_file(f), reseau=False, log=journal.append)
    assert r.lancer() == 1
    assert [l.split()[1] for l in journal if l.startswith("→")] == ["p1.r902/high"]
    assert fb.main(["etat", str(f)]) == 0
    md = (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")
    assert "#902 p1.r902" in md and fb.SCINDE in md
    assert fb.main(["relancer", str(f), "--sans-reseau", "--pr", "p1.r902"]) == 1


def test_paquet_refuse_si_deux_pr_changent_la_meme_version(tmp_path, depot):
    origine, clone = depot
    ipc = "core/src/openride_core/ipc_server.py"
    osm = "compiler/src/openride_compiler/worldgen/osmdb.py"
    _branche(origine, "socle", {ipc: 'CONTRACT_REV = "1.21"\n', osm: "SCHEMA_VERSION = 1\n"})
    _git(origine, "checkout", "-q", "main")
    _git(origine, "merge", "-q", "--ff-only", "socle")
    _branche(origine, "ipc1", {ipc: 'CONTRACT_REV = "1.22"\n', "a.txt": "a"})
    _branche(origine, "ipc2", {ipc: 'CONTRACT_REV = "1.22"  # autre\n', "b.txt": "b"})
    _branche(origine, "schema", {osm: "SCHEMA_VERSION = 2\n"})
    _git(clone, "fetch", "-q", "origin")
    etape = f'fumee = {json.dumps(_cmd(0))}\n[[paquet.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n'
    f = _file(tmp_path, clone, _paquet(clone, ["ipc1", "ipc2"], etape))
    assert fb.main(["verifier", str(f), "--sans-reseau"]) == 1
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    v = _etat(tmp_path)["prs"]["p1"]
    assert v["fumee"]["verdict"] == fb.REFUSE and "révision IPC changé par 2 PR" in v["fumee"]["detail"]
    assert _passages(tmp_path, "p1", "fumee") == 0          # rien n'est lancé
    assert v["low"]["verdict"] == fb.BLOQUE
    # Une seule PR change la révision IPC, une autre le schéma : paquet accepté (cache séparé pour le schéma).
    (tmp_path / "b").mkdir()
    f = _file(tmp_path / "b", clone, _paquet(clone, ["ipc1", "schema"], 'cache = "separe"\n' + etape))
    shas = [_tete(clone, b) for b in ("ipc1", "schema")]
    pr = fb.lire_file(f).prs[0]
    refus, avis = fb.verifier_paquet(clone, pr, shas, _tete(clone, "main"))
    assert refus == [] and avis == []
    # Branche partie avant une montée de main : pas comptée comme un changement de version.
    assert fb.versions_changees(clone, _tete(clone, "br"), _tete(clone, "main")) == {}


def test_paquet_assemblage_en_conflit_refuse_a_blanc(tmp_path, depot):
    origine, clone = depot
    _branche(origine, "c1", {"x.txt": "c1"})
    _branche(origine, "c2", {"x.txt": "c2"})
    _git(clone, "fetch", "-q", "origin")
    f = _file(tmp_path, clone, _paquet(clone, ["c1", "c2"], f'fumee = {json.dumps(_cmd(0))}'))
    pr = fb.lire_file(f).prs[0]
    refus, avis = fb.verifier_paquet(clone, pr, [_tete(clone, "c1"), _tete(clone, "c2")], _tete(clone, "main"))
    assert refus and "conflit avec r901" in refus[0]
    assert avis and "x.txt" in avis[0]


def test_matrice_selon_la_categorie_et_composition_du_paquet(tmp_path, depot):
    _, clone = depot
    cmd = json.dumps(_cmd(0) + " {qualite}")
    f = _file(tmp_path, clone, f'[[pr]]\nid = "menu"\nbranche = "br"\ncategorie = "logique"\n'
                               f'fumee = {json.dumps(_cmd(0))}\nmatrice = {cmd}\n')
    pr = fb.lire_file(f).prs[0]
    assert [e.id for e in pr.etapes] == ["fumee", "medium"] and pr.etapes[1].commande.endswith(" medium")
    for corps in (f'categorie = "logique"\nmatrice = {cmd}\n',            # logique sans fumée
                  'categorie = "autre"\nfumee = "x"\n',
                  'fumee = "x"\nmatrice = "sans qualite"\n'):
        with pytest.raises(fb.FileInvalide):
            fb.lire_file(_file(tmp_path, clone, f'[[pr]]\nid = "p"\nbranche = "br"\n{corps}'))
    t = _tete(clone, "br")[:8]
    un = f'[[paquet.membre]]\npr = 1\nbranche = "br"\ntete = "{t}"\ncategorie = "logique"\n'
    deux = f'[[paquet.membre]]\npr = 2\nbranche = "main"\ntete = "{_tete(clone, "main")[:8]}"\n'
    base = f'[[paquet]]\nid = "q"\nfumee = "x"\nmatrice = {cmd}\n'
    with pytest.raises(fb.FileInvalide):
        fb.lire_file(_file(tmp_path, clone, base + un))                       # un seul membre
    with pytest.raises(fb.FileInvalide):
        fb.lire_file(_file(tmp_path, clone, base + un.replace(f'tete = "{t}"\n', "") + deux))   # tête non fixée
    q = fb.lire_file(_file(tmp_path, clone, base + un + deux)).prs[0]
    assert q.categorie == fb.RENDU and [e.id for e in q.etapes] == ["fumee", "low", "high", "medium"]
    q = fb.lire_file(_file(tmp_path, clone, base + un + deux + 'categorie = "logique"\n')).prs[0]
    assert q.categorie == fb.LOGIQUE and [e.id for e in q.etapes] == ["fumee", "medium"]


def test_categorie_lue_dans_la_section_recette_pc(tmp_path, capsys):
    assert fb.categorie_recette("## Résumé\nCatégorie : logique\n")[0] == fb.RENDU        # hors section
    assert fb.categorie_recette("## Recette PC\n\n- **Catégorie** : logique\n\n## Suite\n")[0] == fb.LOGIQUE
    assert fb.categorie_recette("## 5. Recette PC\nCatégorie : Rendu (biomes)\n")[0] == fb.RENDU
    assert fb.categorie_recette("## Recette PC\nrien\n## Autre\nCatégorie : logique")[0] == fb.RENDU
    corps = tmp_path / "corps.md"
    corps.write_text("## Recette PC\nCatégorie : logique\n", encoding="utf-8")
    assert fb.main(["categorie", str(corps)]) == 0
    assert capsys.readouterr().out.startswith("logique")


def test_etapes_cloud_hors_du_pc_puis_importees(tmp_path, depot):
    _, clone = depot
    corps = (f'[[pr]]\nid = "p"\nbranche = "br"\nfumee = {json.dumps(_cmd(0))}\n'
             f'[[pr.etape]]\nid = "sol"\nlieu = "cloud"\ncommande = {json.dumps(_cmd(0))}\n'
             f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n')
    portail = f'avant_etape = "{PY} -c \\"import sys; sys.exit(1)\\""\n'   # fenêtre du user : jamais ouverte
    cloud = tmp_path / "cloud"
    cloud.mkdir()
    fc = _file(cloud, clone, corps)
    fc.write_text(fc.read_text(encoding="utf-8").replace("[file]\n", "[file]\n" + portail), encoding="utf-8")
    assert fb.main(["lancer", str(fc), "--sans-reseau", "--lieu", "cloud"]) == 0   # sans portail, sans fumée du PC
    assert _passages(cloud, "p", "sol") == 1 and _passages(cloud, "p", "fumee") == 0
    f = _file(tmp_path, clone, corps)
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    assert _passages(tmp_path, "p", "sol") == 0 and _passages(tmp_path, "p", "low") == 1
    assert "À FAIRE (cloud)" in (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")
    assert fb.main(["importer", str(f), "--depuis", str(cloud / "sortie" / "etat.json")]) == 0
    assert _etat(tmp_path)["prs"]["p"]["sol"]["verdict"] == fb.OK
    assert fb.main(["importer", str(f)]) == 2


def test_godot_du_conteneur_cloud_pose_pour_les_etapes(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("GODOT", raising=False)
    env = tmp_path / ".cache" / "godot-4.7.2" / "env"
    env.parent.mkdir(parents=True)
    env.write_text("GODOT=/opt/godot\n", encoding="utf-8")
    assert fb.environnement_etape(tmp_path, tmp_path / "projet")["GODOT"] == "/opt/godot"
    monkeypatch.setenv("GODOT", "/pc/godot")                 # celui du PC reste prioritaire
    assert fb.environnement_etape(tmp_path, tmp_path / "projet")["GODOT"] == "/pc/godot"


def test_exemple_paquet_se_lit():
    f = fb.lire_file(ROOT / "scripts" / "file_bancs" / "exemple_paquet.toml")
    p1 = next(p for p in f.prs if p.id == "p1")
    assert p1.est_paquet and p1.categorie == fb.RENDU and len(p1.membres) == 3
    assert [e.id for e in p1.etapes if e.lieu == "cloud"] == ["contacts", "vitrine"]
    assert next(p for p in f.prs if p.id == "r933").categorie == fb.LOGIQUE


def test_delais_de_capture_du_cloud_ignores_seulement_en_cloud():
    lent = "[ÉCHEC] 9/10 images enregistrées après le chargement, 2 redemandée(s), réponse en 1.49 s : captures de l'engine"
    assert fb.classer(1, lent)[0] == fb.ECHEC                      # sur le PC : un vrai échec
    v, d = fb.classer(1, lent + "\n" + lent, "cloud")
    assert v == fb.OK and "2 délai(s)" in d
    v, d = fb.classer(1, lent + "\n[ÉCHEC] pont : tablier absent", "cloud")
    assert v == fb.ECHEC and "pont" in d and "1 échec(s)" in d


def test_etape_cloud_dun_paquet_jamais_separee(tmp_path, depot):
    origine, clone = depot
    for b in ("pa", "pb"):
        _branche(origine, b, {f"{b}.txt": b})
    _git(clone, "fetch", "-q", "origin")
    corps = (f'[[paquet.etape]]\nid = "cap"\nlieu = "cloud"\n'
             f'commande = {json.dumps(_cmd(1, "[ÉCHEC] décor : herbe absente"))}\n')
    f = _file(tmp_path, clone, _paquet(clone, ["pa", "pb"], corps))
    assert fb.main(["lancer", str(f), "--sans-reseau", "--lieu", "cloud"]) == 1
    etat = _etat(tmp_path)["prs"]
    assert etat["p1"]["cap"]["verdict"] == fb.ECHEC and not any(k.startswith("p1.") for k in etat)


# --- revue de code, vague 5, lot O2 (24 novembre) -------------------------------------------------------------

def test_o2_03_plantage_apres_des_contacts_reste_un_echec():
    contacts = "[ÉCHEC] décor : aucun contact sur la route : 3\n"
    assert fb.classer(1, contacts + "Traceback (most recent call last):\n  ...")[0] == fb.ECHEC
    assert fb.classer(137, contacts + "Killed\nRapport : /x")[0] == fb.ECHEC       # tué : jamais acquis
    v, d = fb.classer(-11, "[ÉCHEC] pire image : 140 ms\n")
    assert v == fb.ECHEC and "non terminé" in d
    assert fb.classer(1, contacts + "Rapport : /x/index.html\n")[0] == fb.CONTACTS   # banc allé au bout


def _echoue_si_assemble(etape_id=""):
    """Commande qui échoue seulement quand pa.txt et pb.txt sont là ensemble (défaut d'assemblage)."""
    return (f"{PY} -c \"import pathlib,sys; a=pathlib.Path('pa.txt').exists() and pathlib.Path('pb.txt').exists(); "
            f"print('[ÉCHEC] départ : refusé {etape_id}' if a else 'ok'); sys.exit(1 if a else 0)\"")


def test_o2_02_fumee_de_paquet_en_echec_rejoue_toute_la_matrice_pr_par_pr(tmp_path, depot):
    origine, clone = depot
    for b in ("pa", "pb"):
        _branche(origine, b, {f"{b}.txt": b})
    _git(clone, "fetch", "-q", "origin")
    f = _file(tmp_path, clone, _paquet(clone, ["pa", "pb"], f'fumee = {json.dumps(_echoue_si_assemble())}\n'
                                       f'matrice = {json.dumps(_cmd(0) + " {qualite}")}'))
    journal = []
    r = fb.Runner(fb.lire_file(f), reseau=False, log=journal.append)
    assert r.lancer() == 1                                    # défaut d'assemblage : jamais un code 0
    etat = _etat(tmp_path)["prs"]
    assert {etat["p1"][q]["verdict"] for q in ("fumee", "low", "high", "medium")} == {fb.SCINDE}
    for m in ("p1.r900", "p1.r901"):
        assert [etat[m][q]["verdict"] for q in ("fumee", "low", "high", "medium")] == [fb.OK] * 4
    md = (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")
    assert "p1/fumee : DÉFAUT D'ASSEMBLAGE" in md
    journal.clear()
    r = fb.Runner(fb.lire_file(f), reseau=False, log=journal.append)
    assert r.lancer() == 1 and not [l for l in journal if l.startswith("→")]   # rien à rejouer, toujours en échec


def test_o2_02_etape_en_echec_seulement_en_paquet_compte_en_echec(tmp_path, depot):
    origine, clone = depot
    for b in ("pa", "pb"):
        _branche(origine, b, {f"{b}.txt": b})
    _git(clone, "fetch", "-q", "origin")
    corps = (f'fumee = {json.dumps(_cmd(0))}\n[[paquet.etape]]\nid = "high"\n'
             f'commande = {json.dumps(_echoue_si_assemble("high"))}\n')
    f = _file(tmp_path, clone, _paquet(clone, ["pa", "pb"], corps))
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    etat = _etat(tmp_path)["prs"]
    assert etat["p1.r900"]["high"]["verdict"] == fb.OK and etat["p1.r901"]["high"]["verdict"] == fb.OK
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1


def test_o2_04_branche_disparue_nArrete_pas_la_file(tmp_path, depot):
    _, clone = depot
    etape = f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n'
    f = _file(tmp_path, clone, f'[[pr]]\nid = "partie"\nbranche = "fusionnee-et-supprimee"\nrisque = 1\n'
                               f'fumee = {json.dumps(_cmd(0))}\n{etape}\n'
                               f'[[pr]]\nid = "suite"\nbranche = "br"\nrisque = 2\n{etape}')
    assert fb.main(["lancer", str(f)]) == 1                  # avec git fetch : la branche n'existe pas
    etat = _etat(tmp_path)["prs"]
    assert etat["partie"]["fumee"]["verdict"] == fb.ENV and "git fetch" in etat["partie"]["fumee"]["detail"]
    assert etat["partie"]["low"]["verdict"] == fb.BLOQUE
    assert etat["suite"]["low"]["verdict"] == fb.OK          # la PR suivante est jouée
    assert "partie" in (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")


def test_o2_05_cache_separe_par_defaut_et_reel_refuse_si_la_generation_change(tmp_path, depot, monkeypatch):
    origine, clone = depot
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _branche(origine, "gen", {"compiler/src/openride_compiler/worldgen/squares.py": "def carre(): return 2\n"})
    _git(clone, "fetch", "-q", "origin")
    cmd = f"{PY} -c \"import os; print('cache', os.environ.get('OPENRIDE_BANC_CACHES'))\""
    etape = f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(cmd)}\n'
    f = _file(tmp_path, clone, f'[[pr]]\nid = "defaut"\nbranche = "br"\n{etape}')
    assert fb.lire_file(f).prs[0].cache == "separe"
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    journal = (tmp_path / "sortie" / "defaut" / "low" / "journal.txt").read_text(encoding="utf-8")
    assert str(tmp_path / "sortie" / "caches" / "defaut") in journal
    g = _file(tmp_path, clone, f'[[pr]]\nid = "gen"\nbranche = "gen"\ncache = "reel"\n{etape}')
    assert fb.main(["lancer", str(g), "--sans-reseau"]) == 1
    v = _etat(tmp_path)["prs"]["gen"]["low"]
    assert v["verdict"] == fb.ENV and "génération du monde ouvert" in v["detail"]
    assert not (tmp_path / "sortie" / "gen" / "low" / "journal.txt").exists()    # rien lancé
    h = _file(tmp_path, clone, f'[[pr]]\nid = "reel"\nbranche = "br"\ncache = "reel"\n{etape}')
    assert fb.main(["lancer", str(h), "--sans-reseau"]) == 0   # écrit en toutes lettres, génération inchangée
    assert "cache None" in (tmp_path / "sortie" / "reel" / "low" / "journal.txt").read_text(encoding="utf-8")


def test_o2_13_amorce_naffecte_pas_le_dossier_du_cache_reel(tmp_path, depot, monkeypatch):
    _, clone = depot
    reel = tmp_path / "home" / "OpenRide" / "Cache" / "monde"
    (reel / "brut" / "osm").mkdir(parents=True)
    (reel / "brut" / "osm" / "fr.sqlite").write_text("x", encoding="utf-8")
    con = sqlite3.connect(reel / "index.sqlite")
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("CREATE TABLE entries (key TEXT PRIMARY KEY, path TEXT);"
                      "INSERT INTO entries VALUES ('osm:fr','brut/osm/fr.sqlite');"
                      "INSERT INTO entries VALUES ('square:a','genere/a');")
    con.commit()
    con.close()
    avant = sorted(p.name for p in reel.iterdir())
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    f = fb.lire_file(_file(tmp_path, clone, '[[pr]]\nid = "ow"\nbranche = "br"\n'))
    monde = fb.cache_separe(f, f.prs[0], lambda *_: None) / "monde"
    assert sorted(p.name for p in reel.iterdir()) == avant          # ni -shm ni -wal dans le cache réel
    con = sqlite3.connect(monde / "index.sqlite")
    assert con.execute("SELECT key FROM entries").fetchall() == [("osm:fr",)]
    con.close()
