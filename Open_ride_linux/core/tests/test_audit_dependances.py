"""Audit des dépendances (lot X24) : workflows lus, versions comparées, sortie de pip-audit fabriquée, sans réseau."""

import importlib.util
import json
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
    assert used["actions/checkout"] == {"majeures": {4, 5}, "fichiers": ["a.yml", "b.yaml"]}
    ls = "abc\trefs/tags/v4.2.1\nabd\trefs/tags/v5\nabe\trefs/tags/v6.0.0\nabf\trefs/tags/v6.0.0^{}\nx\trefs/tags/latest\n"
    assert ad.latest_major(ls) == 6 and ad.latest_major("") is None
    rows = {r["action"]: r for r in ad.compare_actions(used, {"actions/checkout": 6, "actions/cache": None})}
    assert rows["actions/checkout"]["en_retard"] and rows["actions/checkout"]["utilise"] == "v4"
    assert not rows["actions/cache"]["en_retard"] and rows["actions/cache"]["derniere"] == "?"


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
    monkeypatch.setattr(ad, "fetch_latest", lambda name: 99)
    monkeypatch.setattr(ad, "fetch_published", lambda n, v: datetime.now(timezone.utc))
    assert ad.main(["--out", str(tmp_path / "a")]) == 0
    text = (tmp_path / "a" / "resume.txt").read_text(encoding="utf-8")
    assert "en retard" in text and "v99 publiée" in text and text.rstrip().endswith("aucune vulnérabilité connue")
    monkeypatch.setattr(ad, "run_pip_audit", lambda c: (1, "", "/usr/bin/python3: No module named pip_audit"))
    assert ad.main(["--out", str(tmp_path / "b")]) == 2 and not (tmp_path / "b").exists()
    monkeypatch.setattr(ad, "network_ok", lambda: False)
    assert ad.main(["--out", str(tmp_path / "c")]) == ad.EXIT_NO_NETWORK
