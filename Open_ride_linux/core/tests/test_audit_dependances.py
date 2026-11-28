"""Audit des dépendances (lot X24) : workflows lus, versions comparées, sortie de pip-audit fabriquée, sans réseau."""

import importlib.util
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_dependances.py"
spec = importlib.util.spec_from_file_location("audit_dependances", SCRIPT)
ad = importlib.util.module_from_spec(spec)
sys.modules["audit_dependances"] = ad
spec.loader.exec_module(ad)

PIP_AUDIT = {"dependencies": [
    {"name": "numpy", "version": "2.4.6", "vulns": []},
    {"name": "jsonschema", "version": "4.0.0", "vulns": [{"id": "GHSA-xxxx-yyyy", "fix_versions": ["4.1.0", "4.2.0"]}]},
], "fixes": []}


def test_real_files_are_read():
    pins = ad.read_constraints()
    assert pins["numpy"] and pins["pip-audit"]
    used = ad.read_workflows()
    assert "actions/checkout" in used and "openride.yml" in used["actions/checkout"]["fichiers"]


def test_workflows_and_late_action(tmp_path):
    (tmp_path / "a.yml").write_text("steps:\n  - uses: actions/checkout@v5\n  - name: x\n    uses: actions/cache@v4\n",
                                    encoding="utf-8")
    (tmp_path / "b.yaml").write_text("      - uses: actions/checkout@v4\n        with: {}\n", encoding="utf-8")
    used = ad.read_workflows(tmp_path)
    assert used["actions/checkout"] == {"majeures": {4, 5}, "fichiers": ["a.yml", "b.yaml"], "shas": {}}
    ls = "abc\trefs/tags/v4.2.1\nabd\trefs/tags/v5\nabe\trefs/tags/v6.0.0\nabf\trefs/tags/v6.0.0^{}\nx\trefs/tags/latest\n"
    assert ad.latest_major(ls) == 6 and ad.latest_major("") is None
    rows = {r["action"]: r for r in ad.compare_actions(used, {"actions/checkout": 6, "actions/cache": None})}
    assert rows["actions/checkout"]["en_retard"] and rows["actions/checkout"]["utilise"] == "v4"
    assert not rows["actions/cache"]["en_retard"] and rows["actions/cache"]["derniere"] == "?"


def test_sha_pins_are_read_and_stale_pins_reported(tmp_path):
    """Lot SHA1 : `@<sha> # vN.x.y` lu comme la majeure N ; étiquette avancée signalée à rafraîchir."""
    old, new = "a" * 40, "b" * 40
    (tmp_path / "a.yml").write_text(f"steps:\n  - uses: actions/checkout@{old} # v7.0.1\n"
                                    f"  - uses: actions/cache@{new}  #  v6.1.0\n  - uses: actions/cache@v5\n",
                                    encoding="utf-8")
    used = ad.read_workflows(tmp_path)
    assert used["actions/checkout"] == {"majeures": {7}, "fichiers": ["a.yml"], "shas": {old: 7}}
    assert used["actions/cache"]["majeures"] == {5, 6} and used["actions/cache"]["shas"] == {new: 6}
    tags = {"actions/checkout": f"{new}\trefs/tags/v7\n{old}\trefs/tags/v7.0.1\n",
            "actions/cache": f"c\trefs/tags/v6\n{new}\trefs/tags/v6^{{}}\n"}
    assert ad.tag_sha(tags["actions/cache"], 6) == new and ad.tag_sha("", 6) is None
    stale = ad.stale_pins(used, tags)
    assert [(r["action"], r["majeure"], r["etiquette"]) for r in stale] == [("actions/checkout", "v7", new)]
    rep = ad.Rapport(actions=ad.compare_actions(used, {"actions/checkout": 7, "actions/cache": 6}), a_rafraichir=stale)
    text = ad.format_report(rep, datetime(2026, 11, 27, tzinfo=timezone.utc))
    assert "Épinglages à rafraîchir (étiquette avancée) : 1" in text and "aaaaaaaaaaaa" in text


def test_real_workflows_are_all_pinned():
    """Lot SHA1 : toute action des workflows est épinglée par SHA complet, version en commentaire."""
    for wf in sorted(ad.WORKFLOWS.glob("*.y*ml")):
        for line in wf.read_text(encoding="utf-8").splitlines():
            if re.match(r"^\s*(?:-\s*)?uses:", line) and "./" not in line:
                assert re.search(r"@[0-9a-f]{40} # v\d+\.\d+\.\d+$", line), f"{wf.name} : {line.strip()}"


def test_pip_audit_and_old_packages():
    vulns = ad.parse_pip_audit(json.dumps(PIP_AUDIT))
    assert vulns == [{"paquet": "jsonschema", "version": "4.0.0", "id": "GHSA-xxxx-yyyy", "corrige": "4.1.0, 4.2.0"}]
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    rows = ad.old_packages({"a": ("1.0", now - timedelta(days=400)), "b": ("2.0", now - timedelta(days=30))}, now)
    assert rows == [{"paquet": "a", "version": "1.0", "publie": "2025-09-23", "jours": 400}]


def test_vulnerability_gives_code_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ad, "network_ok", lambda: True)
    monkeypatch.setattr(ad, "run_pip_audit", lambda c: (1, json.dumps(PIP_AUDIT), ""))
    assert ad.main(["--out", str(tmp_path), "--hors-ligne"]) == 1
    text = (tmp_path / "resume.txt").read_text(encoding="utf-8")
    assert "jsonschema 4.0.0 : GHSA-xxxx-yyyy, corrigé en 4.1.0, 4.2.0" in text and "Sautés : actions, anciens" in text
    data = json.loads((tmp_path / "resume.json").read_text(encoding="utf-8"))
    assert data["ok"] is False and len(data["vulnerabilites"]) == 1


def test_clean_run_and_missing_tools(tmp_path, monkeypatch, capsys):
    clean = {"dependencies": [{"name": "numpy", "version": "2.4.6", "vulns": []}]}
    monkeypatch.setattr(ad, "network_ok", lambda: True)
    monkeypatch.setattr(ad, "run_pip_audit", lambda c: (0, json.dumps(clean), ""))
    monkeypatch.setattr(ad, "fetch_tags", lambda name: "abc\trefs/tags/v99\n")
    monkeypatch.setattr(ad, "fetch_published", lambda n, v: datetime.now(timezone.utc))
    assert ad.main(["--out", str(tmp_path / "a")]) == 0
    text = (tmp_path / "a" / "resume.txt").read_text(encoding="utf-8")
    assert "en retard" in text and "v99 publiée" in text and text.rstrip().endswith("aucune vulnérabilité connue")
    monkeypatch.setattr(ad, "run_pip_audit", lambda c: (1, "", "/usr/bin/python3: No module named pip_audit"))
    assert ad.main(["--out", str(tmp_path / "b")]) == 2 and not (tmp_path / "b").exists()
    monkeypatch.setattr(ad, "network_ok", lambda: False)
    assert ad.main(["--out", str(tmp_path / "c")]) == ad.EXIT_NO_NETWORK


def test_unverified_items_are_reported(tmp_path, monkeypatch):
    """Revue de code vague 5, O1-10 : action, âge ou paquet non vérifié n'est plus compté comme sain."""
    audited = {"dependencies": [{"name": "numpy", "version": "2.4.6", "vulns": []},
                                {"name": "maison", "version": "0.1", "skip_reason": "absent de PyPI"}]}
    monkeypatch.setattr(ad, "network_ok", lambda: True)
    monkeypatch.setattr(ad, "run_pip_audit", lambda c: (0, json.dumps(audited), ""))
    monkeypatch.setattr(ad, "fetch_tags", lambda name: None)
    monkeypatch.setattr(ad, "fetch_published", lambda n, v: None)
    assert ad.main(["--out", str(tmp_path)]) == 0
    text = (tmp_path / "resume.txt").read_text(encoding="utf-8")
    assert "non vérifiée" in text and "Non vérifiés :" in text
    assert "maison (pip-audit : absent de PyPI)" in text
    assert "âge de numpy" in text
    assert "certains n'ont pas pu l'être" in text
    data = json.loads((tmp_path / "resume.json").read_text(encoding="utf-8"))
    assert any(n.startswith("action actions/checkout") for n in data["non_verifies"])
