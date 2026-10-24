"""Tests de cohérence entre la documentation et le code (Lot I1).

Contrôles :
1. Exemple `config.toml` de la SRS §11 vs valeurs par défaut de `Config`.
2. Modules `*.py` cités dans la section « Architecture » de `CLAUDE.md` vs fichiers sur disque.
3. Commandes `openride-core`, `openride-compiler` et `python -m openride_core.tools.<x>`
   citées dans `README.md` et `CLAUDE.md` vs sous-commandes et options `argparse`.
4. Statut « Livré » dans `docs/lots/00_INDEX.md` vs section « Livraison » dans chaque cahier.
5. Validité JSON Schema Draft 2020-12 de tous les schémas `docs/contracts/**/*.schema.json`.

Deuxième passe (lot J7) :
6. Caractères interdits (contrôle, U+FFFD, double encodage) dans les `*.md` et `*.json`.
7. Liens Markdown relatifs : fichier cible existant, ancre présente parmi les titres de la cible.
8. Nombres de tests du `README.md` et de `SUIVI_AVANCEMENT.md` vs tests réellement collectés.
9. Chemins du projet cités entre accents graves (`core/…`, `docs/…`, etc.) existants.

Vérification du 24 octobre :
10. Lots numérotés cités dans `README.md`, `CLAUDE.md` et `SUIVI_AVANCEMENT.md` présents dans `00_INDEX.md`.
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
SUIVI_PATH = REPO_ROOT / "docs" / "SUIVI_AVANCEMENT.md"

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
    # Le vrai analyseur du core : une sous-commande ajoutée est connue sans copie à tenir à jour.
    from openride_core.__main__ import build_parser
    return build_parser()



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


# Citation d'un ou plusieurs lots numérotés : « lot K6 », « lots I3 et I4 », « lots H1 à H8 ».
_LOT_CITATION_RE = re.compile(r"\b[Ll]ots?\s+((?:[A-Z]\d+(?:\s*(?:,|et|à|puis)\s*)?)+)")


def check_cited_lots(docs: dict[str, str], index_text: str) -> list[str]:
    """Vérifie que chaque lot numéroté cité dans la documentation figure dans 00_INDEX.md.

    Sont connus les lots du tableau et ceux de la liste « À rédiger plus tard » (« - E2 : … »).
    """
    known = set(re.findall(r"^\|\s*\[([A-Z]\d*)\]\(LOT_", index_text, flags=re.MULTILINE))
    known |= set(re.findall(r"^- ([A-Z]\d+) :", index_text, flags=re.MULTILINE))
    errors: list[str] = []
    for name, text in docs.items():
        cited: set[str] = set()
        for m in _LOT_CITATION_RE.finditer(text):
            cited |= set(re.findall(r"[A-Z]\d+", m.group(1)))
        for lot_id in sorted(cited - known):
            errors.append(f"{name} : lot {lot_id} cité mais absent de docs/lots/00_INDEX.md")
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


def test_cited_lots_are_indexed_and_negative() -> None:
    index_text = INDEX_PATH.read_text(encoding="utf-8")
    docs = {
        "README.md": README_PATH.read_text(encoding="utf-8"),
        "CLAUDE.md": CLAUDE_MD_PATH.read_text(encoding="utf-8"),
        "SUIVI_AVANCEMENT.md": SUIVI_PATH.read_text(encoding="utf-8"),
    }
    assert check_cited_lots(docs, index_text) == []

    # Test négatif : un lot cité sans cahier dans l'index (cas de K6 et K7, vérification du 24 octobre)
    errs = check_cited_lots({"README.md": "lanceur (lot Z9), couches (lots Y1 et I3)"}, index_text)
    assert errs == [
        "README.md : lot Y1 cité mais absent de docs/lots/00_INDEX.md",
        "README.md : lot Z9 cité mais absent de docs/lots/00_INDEX.md",
    ]


def test_contracts_json_schemas_and_negative(tmp_path: Path) -> None:
    assert check_json_schemas(CONTRACTS_DIR) == []

    # Test négatif : schéma avec un type invalide
    bad_schema = tmp_path / "bad.schema.json"
    bad_schema.write_text('{"type": "type_inexistant_json_schema"}', encoding="utf-8")
    errs = check_json_schemas(tmp_path)
    assert len(errs) == 1
    assert "bad.schema.json" in errs[0]


# --- 6. Caractères interdits (lot J7) ------------------------------------------------

# Dossiers non versionnés ou générés, jamais parcourus.
SKIPPED_DIRS = {".git", ".godot", ".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist",
                "node_modules"}

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f�]")
# Séquences d'un texte UTF-8 relu en Latin-1 / Windows-1252 (« é », « è », « ’ » abîmés).
MOJIBAKE_RE = re.compile(r"Ã©|Ã¨|Ã |Ãª|Ã§|â€™|â€œ|â€\x9d|Â ")


def project_files(suffix: str, root: Path = REPO_ROOT) -> list[Path]:
    return sorted(
        p for p in root.rglob(f"*{suffix}")
        if p.is_file() and not any(part in SKIPPED_DIRS or part.endswith(".egg-info")
                                   for part in p.relative_to(root).parts)
    )


def check_forbidden_chars(text: str, doc_name: str) -> list[str]:
    """Caractères de contrôle (hors \n, \r, \t), U+FFFD et double encodage.

    Le double encodage est cherché hors du code entre accents graves, où un cahier peut citer
    les séquences à détecter (lot J7 §4).
    """
    errors: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        m = CONTROL_CHARS_RE.search(line)
        if m:
            errors.append(f"{doc_name}:{line_no} : caractère interdit U+{ord(m.group()):04X}")
        m = MOJIBAKE_RE.search(re.sub(r"`[^`]*`", "", line))
        if m:
            errors.append(f"{doc_name}:{line_no} : texte doublement encodé {m.group()!r}")
    return errors


# --- 7. Liens Markdown relatifs (lot J7) ---------------------------------------------

FENCE_RE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", flags=re.MULTILINE | re.DOTALL)
LINK_RE = re.compile(r"\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")


def github_anchor(title: str) -> str:
    """Ancre générée par GitHub pour un titre : minuscules, ponctuation retirée, espaces en `-`."""
    title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)       # [texte](lien) -> texte
    title = re.sub(r"<[^>]+>|[`*]", "", title).strip().lower()
    return re.sub(r"[^\w\- ]", "", title).replace(" ", "-")


def markdown_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    for m in re.finditer(r"^#{1,6}\s+(.*?)\s*#*\s*$", FENCE_RE.sub("", text), flags=re.MULTILINE):
        slug = github_anchor(m.group(1))
        n = seen.get(slug, 0)
        anchors.add(slug if n == 0 else f"{slug}-{n}")
        seen[slug] = n + 1
    return anchors


def check_markdown_links(text: str, doc_path: Path, root: Path = REPO_ROOT) -> list[str]:
    """Chaque lien relatif vise un fichier existant ; l'ancre, si présente, un titre de la cible."""
    errors: list[str] = []
    name = doc_path.relative_to(root) if doc_path.is_relative_to(root) else doc_path.name
    prose = re.sub(r"`[^`\n]*`", "", FENCE_RE.sub("", text))
    for m in LINK_RE.finditer(prose):
        target = m.group(1)
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, flags=re.IGNORECASE):
            continue                                              # https:, mailto:, ...
        path, _, anchor = target.partition("#")
        dest = (doc_path.parent / path).resolve() if path else doc_path
        if not dest.exists():
            errors.append(f"{name} : lien vers un fichier absent : {target}")
        elif anchor and dest.suffix == ".md":
            dest_text = text if dest == doc_path else dest.read_text(encoding="utf-8")
            if anchor not in markdown_anchors(dest_text):
                errors.append(f"{name} : ancre absente de {dest.name} : #{anchor}")
    return errors


# --- 8. Nombres de tests dans la documentation (lot J7) ------------------------------

# (paquet, motif) : chaque motif doit figurer dans chaque document de TEST_COUNT_DOCS.
TEST_COUNT_PATTERNS: dict[str, dict[str, str]] = {
    "README.md": {
        "core": r"(\d+) tests automatiques côté core",
        "compiler": r"et (\d+) côté compilateur",
    },
    "docs/SUIVI_AVANCEMENT.md": {
        "core": r"(\d+) tests pytest passent dans le core",
        "compiler": r"et (\d+) dans le compilateur",
    },
}


def collected_test_count(package_dir: Path) -> int:
    """Nombre de tests que `pytest -q` lance dans `package_dir` (options du paquet, donc sans
    les tests `network` du compilateur)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=package_dir, capture_output=True, text=True, timeout=60,
    )
    m = re.search(r"^(\d+)(?:/\d+)? tests? collected", proc.stdout, flags=re.MULTILINE)
    if proc.returncode != 0 or m is None:
        raise RuntimeError(f"collecte impossible dans {package_dir} :\n{proc.stdout[-2000:]}")
    return int(m.group(1))


def check_test_counts(text: str, doc_name: str, actual: dict[str, int]) -> list[str]:
    errors: list[str] = []
    for package, pattern in TEST_COUNT_PATTERNS[doc_name].items():
        found = re.findall(pattern, text)
        if not found:
            errors.append(f"{doc_name} : phrase du nombre de tests {package} absente ({pattern})")
        for value in found:
            if int(value) != actual[package]:
                errors.append(f"{doc_name} : {value} tests {package} annoncés, "
                              f"écrire {actual[package]} (tests collectés)")
    return errors


# --- 9. Chemins du projet cités (lot J7) ---------------------------------------------

CITED_PATH_RE = re.compile(r"`((?:core|compiler|engine|docs|scripts)/[^`\s]+)`")

# Chemins cités volontairement absents du dépôt, avec leur motif.
CITED_PATH_EXCEPTIONS: dict[str, str] = {
    "core/.venv": "environnement virtuel local, non versionné",
}


def undelivered_lot_files(index_text: str) -> set[str]:
    """Cahiers dont le lot n'est pas « Livré » : ils citent les fichiers que le lot créera."""
    names: set[str] = set()
    for line in index_text.splitlines():
        m = re.match(r"^\|\s*\[[^\]]+\]\((LOT_[^)]+\.md)\)\s*\|(.*)\|$", line.strip())
        if m and "Livré" not in m.group(2).split("|")[-1]:
            names.add(m.group(1))
    return names


def check_cited_paths(text: str, doc_name: str, root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for m in CITED_PATH_RE.finditer(line):
            cited = m.group(1)
            if re.search(r"[*<>{}…]|\.\.\.", cited):
                continue                                          # motif ou gabarit, pas un chemin
            path = re.sub(r":\d+(-\d+)?$", "", cited).rstrip("/.,;")
            if path not in CITED_PATH_EXCEPTIONS and not (root / path).exists():
                errors.append(f"{doc_name}:{line_no} : chemin cité absent : {cited}")
    return errors


# === Tests du lot J7 =================================================================

def test_no_forbidden_chars_and_negative() -> None:
    files = project_files(".md") + project_files(".json")
    assert len(files) > 20
    errors: list[str] = []
    for f in files:
        errors += check_forbidden_chars(f.read_text(encoding="utf-8"), str(f.relative_to(REPO_ROOT)))
    assert errors == []

    for bad in ("retour\barrière", "remplacé �", "rÃ©glage", "lâ€™IPC"):
        assert len(check_forbidden_chars(f"ligne 1\n{bad}\n", "faux.md")) == 1
    assert check_forbidden_chars("tab\tet `Ã©` cité\r\n", "faux.md") == []


def test_markdown_links_and_negative(tmp_path: Path) -> None:
    errors: list[str] = []
    for f in project_files(".md"):
        errors += check_markdown_links(f.read_text(encoding="utf-8"), f)
    assert errors == []

    (tmp_path / "cible.md").write_text("# Titre\n\n## 2. Prérequis et « suite » ici\n", encoding="utf-8")
    doc = tmp_path / "doc.md"
    ok = "[a](cible.md) [b](cible.md#2-prérequis-et--suite--ici) [c](#local) [d](https://x.org/y.md)\n# Local\n"
    doc.write_text(ok, encoding="utf-8")
    assert check_markdown_links(ok, doc, tmp_path) == []
    errs = check_markdown_links("[a](absent.md) [b](cible.md#nulle-part) `[c](ignoré.md)`\n", doc, tmp_path)
    assert len(errs) == 2
    assert any("absent.md" in e for e in errs) and any("#nulle-part" in e for e in errs)


def test_github_anchors() -> None:
    assert github_anchor("9. Livraison (23 octobre 2026)") == "9-livraison-23-octobre-2026"
    assert github_anchor("Lots `H`, I et J") == "lots-h-i-et-j"
    assert markdown_anchors("# A\n## A\n```\n# pas un titre\n```\n") == {"a", "a-1"}


def test_documented_test_counts_and_negative() -> None:
    actual = {"core": collected_test_count(REPO_ROOT / "core")}
    try:
        import openride_compiler  # noqa: F401
    except ImportError:
        pytest.skip("openride-compiler non installé : nombre de tests du compilateur inconnu")
    actual["compiler"] = collected_test_count(REPO_ROOT / "compiler")

    errors: list[str] = []
    for doc_name in TEST_COUNT_PATTERNS:
        errors += check_test_counts((REPO_ROOT / doc_name).read_text(encoding="utf-8"), doc_name, actual)
    assert errors == []

    text = "231 tests automatiques côté core (dont x) et 123 côté compilateur"
    errs = check_test_counts(text, "README.md", {"core": 230, "compiler": 123})
    assert errs == ["README.md : 231 tests core annoncés, écrire 230 (tests collectés)"]
    assert len(check_test_counts("aucun nombre", "README.md", {"core": 1, "compiler": 1})) == 2


def test_cited_paths_exist_and_negative() -> None:
    skipped = undelivered_lot_files(INDEX_PATH.read_text(encoding="utf-8"))
    assert "LOT_J4_paquetage_autonome.md" in skipped
    errors: list[str] = []
    for f in project_files(".md"):
        if f.parent == LOTS_DIR and f.name in skipped:
            continue
        errors += check_cited_paths(f.read_text(encoding="utf-8"), str(f.relative_to(REPO_ROOT)))
    assert errors == []

    text = "`core/src/openride_core/session.py:12` `docs/lots/` `core/tests/test_*.py` `core/absent.py`\n"
    assert check_cited_paths(text, "faux.md") == ["faux.md:1 : chemin cité absent : core/absent.py"]
