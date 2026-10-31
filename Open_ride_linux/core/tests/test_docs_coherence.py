"""Tests de cohérence entre la documentation et le code (Lot I1).

Contrôles :
1. Exemple `config.toml` de la SRS §11 vs valeurs par défaut de `Config`.
2. Modules `*.py` cités dans la section « Architecture » de `CLAUDE.md` vs fichiers sur disque.
3. Commandes `openride-core`, `openride-compiler` et `python -m openride_core.tools.<x>`
   citées dans `README.md` et `CLAUDE.md` vs sous-commandes et options `argparse`.
4. Ligne d'index de chaque cahier `docs/lots/LOT_*.md` (lot X54) ; statut « Livré » vs section « Livraison ».
5. Validité JSON Schema Draft 2020-12 de tous les schémas `docs/contracts/**/*.schema.json`.

Deuxième passe (lot J7) :
6. Caractères interdits (contrôle, U+FFFD, double encodage) dans les `*.md` et `*.json`.
7. Liens Markdown relatifs : fichier cible existant, ancre présente parmi les titres de la cible.
8. Nombres de tests du `README.md` et de `SUIVI_AVANCEMENT.md` vs tests réellement collectés.
9. Chemins du projet cités entre accents graves (`core/…`, `docs/…`, etc.) existants.

Vérification du 24 octobre :
10. Lots numérotés cités dans `README.md`, `CLAUDE.md` et `SUIVI_AVANCEMENT.md` présents dans `docs/lots/`.

Lot O6 :
11. Raccourcis du tableau de `docs/GUIDE_UTILISATION.md` (§6) vs touches du code Godot et boutons du Click.
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

import index_lots   # scripts/ est dans le chemin (conftest.py)
import jsonschema
import pytest

from openride_core.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
SRS_PATH = REPO_ROOT / "docs" / "SRS_v1.1.md"
CLAUDE_MD_PATH = REPO_ROOT / "CLAUDE.md"
README_PATH = REPO_ROOT / "README.md"
LOTS_DIR = REPO_ROOT / "docs" / "lots"
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


# --- 4. Ligne d'index de chaque cahier (lot X54) ------------------------------------

def check_lots_index(lots_dir: Path = LOTS_DIR) -> list[str]:
    """Chaque cahier a sa ligne d'index, 00_INDEX.md n'en contient plus, un lot « Livré » a sa livraison."""
    errors = index_lots.check(lots_dir)
    lots, _ = index_lots.read_lots(lots_dir)
    for lot in lots:
        if "Livré" in lot.status:
            lot_text = (lots_dir / lot.filename).read_text(encoding="utf-8")
            if not re.search(r"^##\s+.*Livraison", lot_text, flags=re.MULTILINE):
                errors.append(f"docs/lots/{lot.filename} : noté 'Livré' mais sans section '## ... Livraison'")
    return errors


# Citation d'un ou plusieurs lots numérotés : « lot K6 », « lots I3 et I4 », « lots H1 à H8 ».
_LOT_CITATION_RE = re.compile(r"\b[Ll]ots?\s+((?:[A-Z]\d+(?:\s*(?:,|et|à|puis)\s*)?)+)")


def known_lot_ids(lots_dir: Path = LOTS_DIR) -> set[str]:
    """Lots qui ont un cahier, et ceux de la liste « À rédiger plus tard » de 00_INDEX.md (« - F2 : … »)."""
    known = {lot_id for p in lots_dir.glob("LOT_*.md") if (lot_id := index_lots.lot_id_of(p.name))}
    index_text = (lots_dir / "00_INDEX.md").read_text(encoding="utf-8")
    return known | set(re.findall(r"^- ([A-Z]\d+) :", index_text, flags=re.MULTILINE))


def check_cited_lots(docs: dict[str, str], known: set[str]) -> list[str]:
    """Vérifie que chaque lot numéroté cité dans la documentation a son cahier dans docs/lots/."""
    errors: list[str] = []
    for name, text in docs.items():
        cited: set[str] = set()
        for m in _LOT_CITATION_RE.finditer(text):
            cited |= set(re.findall(r"[A-Z]\d+", m.group(1)))
        for lot_id in sorted(cited - known):
            errors.append(f"{name} : lot {lot_id} cité mais absent de docs/lots/")
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

def test_srs_config_matches_defaults_and_negative(monkeypatch) -> None:
    from openride_core import config as config_mod
    monkeypatch.setattr(config_mod, "DEPART_MODE_DEFAULT", config_mod.DEPART_MODE_SHIPPED)   # valeur livrée (lot O36)
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
    assert check_lots_index(LOTS_DIR) == []

    # Tests négatifs : un lot « Livré » sans section Livraison, un cahier sans ligne d'index,
    # une ligne revenue dans 00_INDEX.md (conflits d'avant le lot X54)
    block = "\n".join(index_lots.lot_block(["Lot fictif", "Python", "—", "Petite", "**Livré le 23 octobre**"]))
    (tmp_path / "LOT_Z9_fictif.md").write_text(f"# Lot Z9\n\n{block}\n\nSans section de livraison.\n", encoding="utf-8")
    (tmp_path / "LOT_Z8_sans_ligne.md").write_text("# Lot Z8\n\nPas de ligne.\n", encoding="utf-8")
    (tmp_path / "00_INDEX.md").write_text("| [Z9](LOT_Z9_fictif.md) | a | b | c | d | Prêt |\n", encoding="utf-8")
    errs = check_lots_index(tmp_path)
    assert any("LOT_Z9_fictif.md" in e and "Livraison" in e for e in errs)
    assert any("LOT_Z8_sans_ligne.md" in e and "pas de ligne d'index" in e for e in errs)
    assert any("00_INDEX.md" in e and "--migrer" in e for e in errs)


def test_cited_lots_are_indexed_and_negative() -> None:
    known = known_lot_ids()
    docs = {
        "README.md": README_PATH.read_text(encoding="utf-8"),
        "CLAUDE.md": CLAUDE_MD_PATH.read_text(encoding="utf-8"),
        "SUIVI_AVANCEMENT.md": SUIVI_PATH.read_text(encoding="utf-8"),
    }
    assert check_cited_lots(docs, known) == []

    # Test négatif : un lot cité sans cahier (cas de K6 et K7, vérification du 24 octobre)
    errs = check_cited_lots({"README.md": "lanceur (lot Z9), couches (lots Z8 et I3)"}, known)
    assert errs == [
        "README.md : lot Z8 cité mais absent de docs/lots/",
        "README.md : lot Z9 cité mais absent de docs/lots/",
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


# --- 8. Nombres de tests dans la documentation (lots J7 et X52) -------------------------

# Plus aucun nombre de tests écrit en dur (lot X52) : ils changeaient à chaque fusion et mettaient toutes les PR
# ouvertes en conflit. `python3 scripts/recompte_tests.py` les compte ; la CI les écrit dans son résumé.
from recompte_tests import DOCUMENTS, hard_counts  # noqa: E402


# --- 9. Chemins du projet cités (lot J7) ---------------------------------------------

CITED_PATH_RE = re.compile(r"`((?:core|compiler|engine|docs|scripts)/[^`\s]+)`")

# Chemins cités volontairement absents du dépôt, avec leur motif.
CITED_PATH_EXCEPTIONS: dict[str, str] = {
    "core/.venv": "environnement virtuel local, non versionné",
}


def undelivered_lot_files(lots_dir: Path = LOTS_DIR) -> set[str]:
    """Cahiers dont le lot n'est pas « Livré » : ils citent les fichiers que le lot créera."""
    lots, _ = index_lots.read_lots(lots_dir)
    return {lot.filename for lot in lots if "Livré" not in lot.status}


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


def test_no_hard_coded_test_counts_and_negative() -> None:
    errors: list[str] = []
    for doc_name in DOCUMENTS:
        errors += hard_counts((REPO_ROOT / doc_name).read_text(encoding="utf-8"), doc_name)
    assert errors == []
    assert len(hard_counts("231 tests automatiques côté core et 7 tests de rendu", "README.md")) == 2


def test_cited_paths_exist_and_negative() -> None:
    skipped = undelivered_lot_files()
    assert "LOT_J4_paquetage_autonome.md" in skipped
    errors: list[str] = []
    for f in project_files(".md"):
        if f.parent == LOTS_DIR and f.name in skipped:
            continue
        errors += check_cited_paths(f.read_text(encoding="utf-8"), str(f.relative_to(REPO_ROOT)))
    assert errors == []

    text = "`core/src/openride_core/session.py:12` `docs/lots/` `core/tests/test_*.py` `core/absent.py`\n"
    assert check_cited_paths(text, "faux.md") == ["faux.md:1 : chemin cité absent : core/absent.py"]


# === Tests du lot O6 : raccourcis du guide d'utilisation =============================

GUIDE_PATH = REPO_ROOT / "docs" / "GUIDE_UTILISATION.md"
KEY_MAP_PATH = REPO_ROOT / "engine" / "scripts" / "key_map.gd"
CLICK_PY_PATH = CORE_SRC_DIR / "zwift_click.py"

KEY_NAMES = {   # nom de la touche écrit dans le guide : constante Godot (lot O17, clavier = Click)
    "+": "KEY_PLUS", "=": "KEY_EQUAL", "-": "KEY_MINUS", "A": "KEY_A", "Y": "KEY_Y", "Z": "KEY_Z",
    "Entrée": "KEY_ENTER", "Échap": "KEY_ESCAPE", "Page haut": "KEY_PAGEUP", "Page bas": "KEY_PAGEDOWN",
    "Gauche": "KEY_LEFT", "Droite": "KEY_RIGHT", "Haut": "KEY_UP", "Bas": "KEY_DOWN",
}
# Bouton d'une ligne du tableau « Au clavier » : préfixe de ses événements (flèches : une famille de quatre).
KEY_TABLE_BUTTONS = {"« + »": ("PLUS",), "« − » ou B": ("MINUS",), "A": ("A",), "Y": ("Y",), "Z": ("Z",),
                     "Flèches": ("LEFT", "RIGHT", "UP", "DOWN")}
MENU_ACTIONS = ("Élément suivant", "Élément précédent", "Sauter de cinq vers le bas", "Sauter de cinq vers le haut",
                "Valider", "Revenir (sur l'écran de pause : reprendre)")


def guide_tables(text: str) -> dict[str, list[tuple[str, ...]]]:
    """Tableaux de la section « Commandes » du guide : titre en gras -> lignes (cellules, sans l'en-tête)."""
    section = text.split("## 6.", 1)[1].split("\n## ", 1)[0]
    tables: dict[str, list[tuple[str, ...]]] = {}
    current = ""
    header = False
    for line in section.splitlines():
        title = re.match(r"\*\*(.+?)\*\*$", line)
        if title:
            current, header = title.group(1), True
            tables[current] = []
        elif current and line.startswith("|") and not line.startswith("| ---"):
            if header:
                header = False   # première ligne du tableau : en-tête
                continue
            tables[current].append(tuple(c.strip() for c in line.strip("|").split("|")))
    return tables


def cited_keys(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def key_map_tables(key_map: str) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Tables de key_map.gd : touche mesurée -> bouton, touche fixe -> événement, Maj+touche -> événement."""
    def table(name: str) -> dict[str, str]:
        body = key_map.split(f"const {name} := {{", 1)[1].split("}", 1)[0]
        return dict(re.findall(r"(KEY_\w+): \"(\w+)\"", body))
    return table("MEASURED"), table("FIXED"), table("SHIFT_LONG")


def check_guide_shortcuts(guide: str, key_map: str, click_py: str) -> list[str]:
    errors: list[str] = []
    tables = guide_tables(guide)
    measured, fixed, shift_long = key_map_tables(key_map)
    click_buttons = set(re.findall(r'"([A-Z]+)": \d+', click_py.split("KEYPAD_BITS", 1)[1].split("}", 1)[0]))
    menu_rows = tables.get("Dans les menus", [])
    if tuple(r[0] for r in menu_rows) != MENU_ACTIONS:
        errors.append(f"tableau « Dans les menus » : actions {[r[0] for r in menu_rows]}, attendues {MENU_ACTIONS}")
    for title, rows in tables.items():
        if title == "Au clavier":
            continue
        for row in rows:
            for button in re.findall(r"\b([ABYZ])\b", re.sub(r"« [^»]+ »", "", row[-1])):
                if button not in click_buttons:
                    errors.append(f"{title} : le bouton {button} n'existe pas dans KEYPAD_BITS")
    key_rows = tables.get("Au clavier", [])
    if [r[0] for r in key_rows] != list(KEY_TABLE_BUTTONS):
        errors.append(f"tableau « Au clavier » : boutons {[r[0] for r in key_rows]}, attendus {list(KEY_TABLE_BUTTONS)}")
    for row in key_rows:
        prefixes = KEY_TABLE_BUTTONS.get(row[0], ("?",))
        for name in cited_keys(row[1]):
            const = KEY_NAMES.get(name, "")
            got = measured.get(const) or fixed.get(const, "").rsplit("_", 1)[0]
            if got not in prefixes:
                errors.append(f"clavier : la touche `{name}` ne double pas le bouton {row[0]} dans key_map.gd")
        for name in cited_keys(row[2]):
            shift = name.startswith("Maj+")
            const = KEY_NAMES.get(name.removeprefix("Maj+"), "")
            if (shift_long if shift else fixed).get(const) != f"{prefixes[0]}_LONG":
                errors.append(f"clavier : `{name}` ne fait pas l'appui long de {row[0]} dans key_map.gd")
    return errors


def test_guide_shortcuts_match_code_and_negative() -> None:
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    key_map = KEY_MAP_PATH.read_text(encoding="utf-8")
    click_py = CLICK_PY_PATH.read_text(encoding="utf-8")
    assert list(guide_tables(guide)) == ["Dans les menus", "Pendant la séance, en Session libre",
                                         "Pendant la séance, en ERG", "Au clavier"]
    assert check_guide_shortcuts(guide, key_map, click_py) == []

    wrong = guide.replace("`Page bas`", "`Page haut`", 1)   # Page haut fait + long, pas − long
    assert any("Page haut" in e for e in check_guide_shortcuts(wrong, key_map, click_py))
    wrong = guide.replace("| Y | `Y` ou `Échap` |", "| Y | `Y` ou `Entrée` |", 1)
    assert any("Entrée" in e for e in check_guide_shortcuts(wrong, key_map, click_py))
    wrong = guide.replace("| Flèches | `Gauche`", "| Flèches | `P`", 1)   # plus de touche P
    assert any("`P`" in e for e in check_guide_shortcuts(wrong, key_map, click_py))
    assert any("bouton Z" in e for e in check_guide_shortcuts(guide, key_map, click_py.replace('"Z": 7,', "")))
    assert check_guide_shortcuts(guide, key_map.replace('KEY_Z: "Z_LONG"', ""), click_py) != []
