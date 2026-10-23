"""Tests de cohérence entre la documentation et le code (Lot I1).

Contrôles :
1. Exemple `config.toml` de la SRS §11 vs valeurs par défaut de `Config`.
2. Modules `*.py` cités dans la section « Architecture » de `CLAUDE.md` vs fichiers sur disque.
3. Commandes `openride-core`, `openride-compiler` et `python -m openride_core.tools.<x>`
   citées dans `README.md` et `CLAUDE.md` vs sous-commandes et options `argparse`.
4. Statut « Livré » dans `docs/lots/00_INDEX.md` vs section « Livraison » dans chaque cahier.
5. Validité JSON Schema Draft 2020-12 de tous les schémas `docs/contracts/**/*.schema.json`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import fields
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from openride_core.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
SRS_PATH = REPO_ROOT / "docs" / "SRS_v1.1.md"
CLAUDE_MD_PATH = REPO_ROOT / "CLAUDE.md"
README_PATH = REPO_ROOT / "README.md"
LOTS_DIR = REPO_ROOT / "docs" / "lots"
INDEX_PATH = LOTS_DIR / "00_INDEX.md"
CONTRACTS_DIR = REPO_ROOT / "docs" / "contracts"

CORE_SRC_DIR = REPO_ROOT / "core" / "src" / "openride_core"
CORE_TOOLS_DIR = CORE_SRC_DIR / "tools"
COMPILER_SRC_DIR = REPO_ROOT / "compiler" / "src" / "openride_compiler"

# Exceptions permises par la SRS §11 (« exemples de départ (FTP et masses à adapter) »).
ALLOWED_SRS_CONFIG_EXCEPTIONS: set[tuple[str, str]] = {
    ("rider", "ftp_w"),
    ("rider", "mass_kg"),
    ("bike", "mass_kg"),
}


# --- 1. Exemple config.toml de la SRS §11 --------------------------------------------

def check_srs_config_example(srs_text: str) -> list[str]:
    """Vérifie le bloc ```toml qui suit '## 11.' contre les valeurs par défaut de Config."""
    errors: list[str] = []
    m_sec = re.search(r"^## 11\..*$", srs_text, flags=re.MULTILINE)
    if not m_sec:
        return ["SRS_v1.1.md : section '## 11.' introuvable"]

    after_sec = srs_text[m_sec.end():]
    m_toml = re.search(r"```toml\r?\n(.*?)```", after_sec, flags=re.DOTALL)
    if not m_toml:
        return ["SRS_v1.1.md §11 : bloc ```toml introuvable"]

    try:
        parsed = tomllib.loads(m_toml.group(1))
    except tomllib.TOMLDecodeError as exc:
        return [f"SRS_v1.1.md §11 : TOML invalide : {exc}"]

    cfg = Config()
    expected_sections = {f.name: getattr(cfg, f.name) for f in fields(cfg)}

    for sec_name, sec_dict in parsed.items():
        if sec_name not in expected_sections:
            errors.append(f"SRS_v1.1.md §11 : section [{sec_name}] inconnue dans Config")
            continue
        dc = expected_sections[sec_name]
        dc_fields = {f.name: getattr(dc, f.name) for f in fields(dc)}
        if not isinstance(sec_dict, dict):
            errors.append(f"SRS_v1.1.md §11 : [{sec_name}] n'est pas une table")
            continue
        for key, val in sec_dict.items():
            if key not in dc_fields:
                errors.append(f"SRS_v1.1.md §11 : clé [{sec_name}].{key} inexistante dans Config")
                continue
            default_val = dc_fields[key]
            if (sec_name, key) in ALLOWED_SRS_CONFIG_EXCEPTIONS:
                if not isinstance(val, (int, float)):
                    errors.append(f"SRS_v1.1.md §11 : [{sec_name}].{key} doit être numérique")
                continue
            if val != default_val:
                errors.append(
                    f"SRS_v1.1.md §11 : [{sec_name}].{key} vaut {val!r} dans la SRS "
                    f"mais {default_val!r} par défaut dans config.py"
                )

    for sec_name, dc in expected_sections.items():
        if sec_name not in parsed:
            errors.append(f"SRS_v1.1.md §11 : section [{sec_name}] absente de l'exemple")
            continue
        sec_dict = parsed[sec_name]
        for f in fields(dc):
            if f.name not in sec_dict:
                errors.append(f"SRS_v1.1.md §11 : clé [{sec_name}].{f.name} absente de l'exemple")

    return errors


# --- 2. Modules cités dans CLAUDE.md -------------------------------------------------

def check_claude_architecture_modules(claude_text: str) -> list[str]:
    """Vérifie la correspondance entre la section Architecture de CLAUDE.md et les fichiers .py."""
    errors: list[str] = []
    m_arch = re.search(r"^## Architecture\s*$(.*?)(?=^## |\Z)", claude_text, flags=re.MULTILINE | re.DOTALL)
    if not m_arch:
        return ["CLAUDE.md : section '## Architecture' introuvable"]

    arch_block = m_arch.group(1)
    cited_py = set(re.findall(r"\b([a-zA-Z0-9_]+\.py)\b", arch_block))

    existing_core = {
        p.name
        for p in CORE_SRC_DIR.glob("*.py")
        if p.name not in ("__init__.py", "__main__.py")
    }
    existing_tools = {
        p.name
        for p in CORE_TOOLS_DIR.glob("*.py")
        if p.name not in ("__init__.py", "__main__.py")
    }
    existing_compiler = {
        p.name
        for p in COMPILER_SRC_DIR.glob("*.py")
        if p.name not in ("__init__.py", "__main__.py")
    }
    all_existing = existing_core | existing_tools | existing_compiler

    for mod in sorted(cited_py):
        if mod not in all_existing:
            errors.append(
                f"CLAUDE.md (Architecture) : module '{mod}' cité mais absent de core/, core/tools/ et compiler/"
            )

    for mod in sorted(existing_core):
        if mod not in cited_py:
            errors.append(
                f"CLAUDE.md (Architecture) : module core/src/openride_core/{mod} non cité dans CLAUDE.md"
            )

    return errors


# --- 3. Commandes dans README.md et CLAUDE.md ----------------------------------------

def _collect_parser_spec(parser: argparse.ArgumentParser) -> tuple[set[str], set[str], dict[str, set[str]]]:
    """Retourne (options_globales, sous_commandes, {sous_commande: options})."""
    global_opts: set[str] = set()
    subcommands: set[str] = set()
    sub_opts: dict[str, set[str]] = {}

    for action in parser._actions:
        for opt in action.option_strings:
            if opt.startswith("--"):
                global_opts.add(opt.split("=")[0])
        if isinstance(action, argparse._SubParsersAction):
            for sub_name, sub_parser in action.choices.items():
                subcommands.add(sub_name)
                opts: set[str] = set()
                for sub_act in sub_parser._actions:
                    for opt in sub_act.option_strings:
                        if opt.startswith("--"):
                            opts.add(opt.split("=")[0])
                sub_opts[sub_name] = opts
    return global_opts, subcommands, sub_opts


def _build_core_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="openride-core")
    p.add_argument("--version", action="version", version="0.1.0")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("recover")
    r.add_argument("journal", nargs="?")
    run = sub.add_parser("run")
    run.add_argument("--config")
    run.add_argument("--trainer", choices=["mock", "ftms"])
    run.add_argument("--input", choices=["click", "keyboard", "none"])
    run.add_argument("--gear", type=int)
    run.add_argument("--replay")
    run.add_argument("--autostart", action="store_true")
    summ = sub.add_parser("summary")
    summ.add_argument("file", nargs="?")
    summ.add_argument("--ftp", type=float)
    summ.add_argument("--json", action="store_true")
    summ.add_argument("--config")
    return p


_TOOL_HELP_CACHE: dict[str, str] = {}


def _get_tool_help_text(module_name: str) -> str:
    if module_name in _TOOL_HELP_CACHE:
        return _TOOL_HELP_CACHE[module_name]
    proc = subprocess.run(
        [sys.executable, "-m", f"openride_core.tools.{module_name}", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    # Récupère aussi l'aide des éventuelles sous-commandes {a,b,c}
    m_sub = re.search(r"\{([a-z0-9_,-]+)\}", out)
    if m_sub:
        for sub_cmd in m_sub.group(1).split(","):
            p2 = subprocess.run(
                [sys.executable, "-m", f"openride_core.tools.{module_name}", sub_cmd.strip(), "--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            out += "\n" + (p2.stdout or "") + "\n" + (p2.stderr or "")
    _TOOL_HELP_CACHE[module_name] = out
    return out


def check_cli_commands_in_markdown(md_text: str, doc_name: str = "README.md") -> list[str]:
    """Vérifie chaque commande des blocs de code de md_text contre les parseurs CLI."""
    errors: list[str] = []

    core_global, core_subs, core_sub_opts = _collect_parser_spec(_build_core_parser())

    compiler_spec: tuple[set[str], set[str], dict[str, set[str]]] | None = None
    try:
        from openride_compiler.cli import build_parser as build_compiler_parser
        compiler_spec = _collect_parser_spec(build_compiler_parser())
    except ImportError:
        compiler_spec = None

    tool_help_cache: dict[str, str] = {}

    in_code_block = False
    for line_no, raw_line in enumerate(md_text.splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if not in_code_block:
            continue

        # Coupe le commentaire de fin de ligne
        cmd_part = raw_line.split("#", 1)[0].strip()
        if not cmd_part:
            continue

        # Parcours les segments séparés par && ou ;
        for seg in re.split(r"&&|;", cmd_part):
            seg = seg.strip()
            if seg.startswith("openride-core "):
                rest = seg[len("openride-core "):].strip()
                tokens = re.sub(r"[\[\]]", " ", rest).split()
                if not tokens:
                    continue
                sub = tokens[0]
                if sub not in core_subs:
                    errors.append(
                        f"{doc_name}:{line_no} : sous-commande openride-core inconnue '{sub}'"
                    )
                    continue
                allowed_opts = core_global | core_sub_opts.get(sub, set())
                for tok in tokens[1:]:
                    if tok.startswith("--"):
                        opt_name = tok.split("=")[0]
                        if opt_name not in allowed_opts:
                            errors.append(
                                f"{doc_name}:{line_no} : option '{opt_name}' inconnue pour 'openride-core {sub}'"
                            )

            elif seg.startswith("openride-compiler "):
                if compiler_spec is None:
                    continue
                comp_global, comp_subs, comp_sub_opts = compiler_spec
                rest = seg[len("openride-compiler "):].strip()
                tokens = re.sub(r"[\[\]]", " ", rest).split()
                if not tokens:
                    continue
                sub = tokens[0]
                if sub not in comp_subs:
                    errors.append(
                        f"{doc_name}:{line_no} : sous-commande openride-compiler inconnue '{sub}'"
                    )
                    continue
                allowed_opts = comp_global | comp_sub_opts.get(sub, set())
                for tok in tokens[1:]:
                    if tok.startswith("--"):
                        opt_name = tok.split("=")[0]
                        if opt_name not in allowed_opts:
                            errors.append(
                                f"{doc_name}:{line_no} : option '{opt_name}' inconnue pour 'openride-compiler {sub}'"
                            )

            elif seg.startswith("python -m openride_core.tools."):
                rest = seg[len("python -m openride_core.tools."):].strip()
                tokens = re.sub(r"[\[\]]", " ", rest).split()
                if not tokens:
                    continue
                tool_mod = tokens[0]
                tool_file = CORE_TOOLS_DIR / f"{tool_mod}.py"
                if not tool_file.is_file():
                    errors.append(
                        f"{doc_name}:{line_no} : module outil openride_core.tools.{tool_mod} introuvable"
                    )
                    continue
                if tool_mod not in tool_help_cache:
                    tool_help_cache[tool_mod] = _get_tool_help_text(tool_mod)
                help_txt = tool_help_cache[tool_mod]

                # Sous-commandes éventuelles si l'outil en déclare ({list,check,install})
                m_sub = re.search(r"\{([a-z0-9_,-]+)\}", help_txt)
                sub_choices = set(m_sub.group(1).split(",")) if m_sub else set()
                known_opts = set(re.findall(r"--[a-zA-Z0-9_-]+", help_txt))

                for tok in tokens[1:]:
                    if tok == "|":
                        continue
                    if tok.startswith("--"):
                        opt_name = tok.split("=")[0]
                        if opt_name not in known_opts:
                            errors.append(
                                f"{doc_name}:{line_no} : option '{opt_name}' inconnue pour "
                                f"'python -m openride_core.tools.{tool_mod}'"
                            )
                    elif sub_choices and tok.islower() and tok.isalpha() and tok not in sub_choices:
                        errors.append(
                            f"{doc_name}:{line_no} : sous-commande '{tok}' inconnue pour "
                            f"'python -m openride_core.tools.{tool_mod}'"
                        )

    return errors


# --- 4. Statut des lots dans 00_INDEX.md ---------------------------------------------

def check_lots_index(index_text: str, lots_dir: Path = LOTS_DIR) -> list[str]:
    """Vérifie la cohérence entre 00_INDEX.md et les fichiers LOT_*.md."""
    errors: list[str] = []
    referenced_files: set[str] = set()

    for line_no, line in enumerate(index_text.splitlines(), start=1):
        m = re.match(r"^\|\s*\[[^\]]+\]\((LOT_[^)]+\.md)\)\s*\|(.*)\|$", line.strip())
        if not m:
            continue
        lot_filename = m.group(1)
        referenced_files.add(lot_filename)
        cols = [c.strip() for c in m.group(2).split("|")]
        status_col = cols[-1] if cols else ""
        lot_path = lots_dir / lot_filename
        if not lot_path.is_file():
            errors.append(f"00_INDEX.md:{line_no} : fichier {lot_filename} absent de docs/lots/")
            continue
        if "Livré" in status_col:
            lot_text = lot_path.read_text(encoding="utf-8")
            if not re.search(r"^##\s+.*Livraison", lot_text, flags=re.MULTILINE):
                errors.append(
                    f"00_INDEX.md:{line_no} : {lot_filename} est noté 'Livré' mais n'a pas de section '## ... Livraison'"
                )

    for disk_file in sorted(lots_dir.glob("LOT_*.md")):
        if disk_file.name not in referenced_files:
            errors.append(f"docs/lots/{disk_file.name} : cahier absent du tableau de 00_INDEX.md")

    return errors


# --- 5. Validité des schémas JSON ----------------------------------------------------

def check_json_schemas(contracts_dir: Path = CONTRACTS_DIR) -> list[str]:
    """Vérifie que chaque fichier *.schema.json de docs/contracts/ est un JSON Schema valide."""
    errors: list[str] = []
    schema_files = sorted(contracts_dir.rglob("*.schema.json"))
    if not schema_files:
        return [f"Aucun fichier *.schema.json trouvé dans {contracts_dir}"]

    for sf in schema_files:
        try:
            schema = json.loads(sf.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
        except Exception as exc:
            errors.append(f"{sf.relative_to(contracts_dir)} : schéma JSON invalide : {exc}")
    return errors


# === Tests positifs et négatifs ======================================================

def test_srs_config_matches_defaults_and_negative() -> None:
    srs_text = SRS_PATH.read_text(encoding="utf-8")
    assert check_srs_config_example(srs_text) == []

    # Test négatif : modifier une valeur par défaut ou ajouter une clé inconnue fait échouer
    tampered = srs_text.replace("port_state = 5005", "port_state = 9999\ncle_inconnue = 1")
    errs = check_srs_config_example(tampered)
    assert any("port_state" in e for e in errs)
    assert any("cle_inconnue" in e for e in errs)


def test_claude_md_architecture_modules_and_negative() -> None:
    claude_text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert check_claude_architecture_modules(claude_text) == []

    # Test négatif : citer un module inexistant ou omettre session.py fait échouer
    tampered = claude_text.replace("`session.py`", "`module_fantome_inexistant.py`")
    errs = check_claude_architecture_modules(tampered)
    assert any("module_fantome_inexistant.py" in e for e in errs)
    assert any("session.py" in e for e in errs)


def test_readme_and_claude_cli_commands_and_negative() -> None:
    readme_text = README_PATH.read_text(encoding="utf-8")
    claude_text = CLAUDE_MD_PATH.read_text(encoding="utf-8")

    assert check_cli_commands_in_markdown(readme_text, "README.md") == []
    assert check_cli_commands_in_markdown(claude_text, "CLAUDE.md") == []

    # Critère 3 : ajouter une option fictive --inexistante dans une ligne du README fait échouer
    tampered_readme = readme_text.replace(
        "openride-core recover",
        "openride-core recover --inexistante",
    )
    errs = check_cli_commands_in_markdown(tampered_readme, "README.md")
    assert any("--inexistante" in e for e in errs)


def test_lots_index_status_and_negative(tmp_path: Path) -> None:
    index_text = INDEX_PATH.read_text(encoding="utf-8")
    assert check_lots_index(index_text, LOTS_DIR) == []

    # Test négatif : marquer un lot non livré comme 'Livré' sans section Livraison fait échouer
    fake_lot = tmp_path / "LOT_Z9_fictif.md"
    fake_lot.write_text("# Lot Z9\n\nSans section de livraison.\n", encoding="utf-8")
    fake_index = "| [Z9](LOT_Z9_fictif.md) | Lot fictif | Python | — | Petite | **Livré le 23 octobre** |\n"
    errs = check_lots_index(fake_index, tmp_path)
    assert any("LOT_Z9_fictif.md" in e and "Livraison" in e for e in errs)


def test_contracts_json_schemas_and_negative(tmp_path: Path) -> None:
    assert check_json_schemas(CONTRACTS_DIR) == []

    # Test négatif : schéma avec un type invalide
    bad_schema = tmp_path / "bad.schema.json"
    bad_schema.write_text('{"type": "type_inexistant_json_schema"}', encoding="utf-8")
    errs = check_json_schemas(tmp_path)
    assert len(errs) == 1
    assert "bad.schema.json" in errs[0]
