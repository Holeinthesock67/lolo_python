"""Contenus installables depuis le menu « Réglages › Contenus » (lot O25 ; contrat IPC révision 1.5).

Le joueur n'a besoin d'aucune commande pour remplir sa bibliothèque : chaque contenu est un élément du
message `contents` (`list_contents`), installé par `install_content`, toujours sans rien écraser.

- `starter` (« Contenus de départ ») : les entraînements livrés (`core/workouts/`), les deux plans de
  départ (`core/plans/`) et les quatre parcours de démonstration des biomes (`openride-core
  demo-biomes`, lot U19). Installé seul au premier lancement (`run --first-run`), puis proposé dans
  le menu pour une installation existante. Rien n'est téléchargé.

- `routes:cols_celebres` (pack « Cols célèbres », lot O29) : construit depuis OpenStreetMap par le
  compilateur (`route-pack-build cols_celebres --install`), puis compilé (`build-all`) ; télécharge.
- `archive:N` (lot O29) : archives `.zip` trouvées dans Téléchargements, sur le Bureau ou dans
  `~/OpenRide/Import` : pack de thème ou de biomes (`theme.json`, `theme-install`) ou pack de parcours
  (`pack.toml`, `route-pack-install` puis `build-all`). Rien n'est téléchargé.
- `theme:NOM` (lot O29) : thèmes déjà installés dans `~/OpenRide/Themes`, avec leur taille et leur
  dernière utilisation (information : un thème se choisit dans « Réglages › Graphisme »).

Le message porte aussi la place libre sur le disque et celle des thèmes face à leur plafond
(`[render] theme_library_gb`). Le core ne dépend pas du compilateur : il l'appelle en sous-processus.

État d'un élément : `missing` (rien d'installé), `partial`, `installed` ou `installing` (avec
`progress_pct`). Une seule installation à la fois ; elle tourne dans un fil (`ContentJob.run`), le
core n'en lit que l'avancement.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

STARTER_ID = "starter"
COLS_ID = "routes:cols_celebres"
COLS_PACK = "cols_celebres"
STATES = ("missing", "partial", "installed", "installing")
MAX_ITEMS = 32
MAX_ARCHIVES = 12
THEME_USE_FILE = ".utilisation.json"
MB = 1024 * 1024
STEP_TIMEOUT_S = 3600.0   # construction du pack des cols : réseau lent compris


@dataclass
class ContentDirs:
    """Dossiers de destination : bibliothèque d'entraînements, plans et parcours compilés ; traces à
    compiler, thèmes et dossier personnel où chercher les archives (lot O29)."""
    workouts: Path
    plans: Path
    routes: Path
    gpx: Path | None = None
    themes: Path | None = None
    home: Path | None = None
    themes_max_gb: float = 5.0


class ContentError(Exception):
    """Contenu inconnu ou installation impossible ; message lisible."""


# --- contenus de départ ---------------------------------------------------------------------------

def _builtin_workouts() -> list[Path]:
    from .plans import BUILTIN_WORKOUTS_DIR
    from .workout import WORKOUT_SUFFIXES

    if not BUILTIN_WORKOUTS_DIR.is_dir():
        return []
    return sorted(p for p in BUILTIN_WORKOUTS_DIR.iterdir() if p.suffix.lower() in WORKOUT_SUFFIXES)


def _builtin_plans() -> list[Path]:
    from .plans import BUILTIN_PLANS_DIR

    return sorted(BUILTIN_PLANS_DIR.glob("*.toml")) if BUILTIN_PLANS_DIR.is_dir() else []


def _demo_names() -> list[str]:
    """Parcours de démonstration des biomes ; [] si le générateur de l'engine est introuvable."""
    from .demo_world import biome_demo_names

    try:
        return biome_demo_names()
    except (FileNotFoundError, ImportError):
        return []


def starter_parts(dirs: ContentDirs) -> dict[str, tuple[int, int]]:
    """Par partie (`workouts`, `plans`, `routes`) : (présents, livrés)."""
    workouts = _builtin_workouts()
    plans = _builtin_plans()
    demos = _demo_names()
    return {
        "workouts": (sum((dirs.workouts / p.name).exists() for p in workouts), len(workouts)),
        "plans": (sum((dirs.plans / p.name).exists() for p in plans), len(plans)),
        "routes": (sum((dirs.routes / f"{n}.world" / "manifest.json").is_file() for n in demos), len(demos)),
    }


def _state_of(parts: dict[str, tuple[int, int]]) -> str:
    have = sum(h for h, _ in parts.values())
    total = sum(t for _, t in parts.values())
    if total and have >= total:
        return "installed"
    return "partial" if have else "missing"


def starter_detail(parts: dict[str, tuple[int, int]]) -> str:
    w, p, r = parts["workouts"][1], parts["plans"][1], parts["routes"][1]
    text = f"{w} entraînements, {p} plans de départ"
    return text + (f", {r} parcours de démonstration des biomes" if r else "")


def install_starter(dirs: ContentDirs, progress: Callable[[int], None] = lambda pct: None) -> str:
    """Copie ce qui manque des contenus de départ ; renvoie le compte rendu affiché au menu."""
    from .plans import install_builtin
    from .tools.workouts import install_builtin_workouts

    copied, _kept = install_builtin_workouts(dirs.workouts)
    progress(20)
    plans_copied, _ = install_builtin(dirs.plans, dirs.workouts)
    new_plans = [n for n in plans_copied if n.endswith(".toml")]
    copied += [n for n in plans_copied if not n.endswith(".toml")]
    progress(40)
    routes, note = install_biome_demos(dirs.routes)
    progress(100)
    parts = [f"{len(copied)} entraînement(s)", f"{len(new_plans)} plan(s)", f"{len(routes)} parcours"]
    text = "Ajouté : " + ", ".join(parts) + "."
    return text + (f" {note}" if note else "")


def install_biome_demos(routes_dir: Path) -> tuple[list[str], str]:
    """Écrit les parcours de démonstration des biomes qui manquent (jamais d'écrasement) ;
    renvoie leurs noms et une remarque ("" si tout va bien)."""
    from .demo_world import write_biome_demo_worlds

    names = _demo_names()
    missing = [n for n in names if not (routes_dir / f"{n}.world" / "manifest.json").is_file()]
    if not names:
        return [], "Parcours de démonstration : générateur de l'engine introuvable."
    if not missing:
        return [], ""
    routes_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=routes_dir.parent, prefix=".demo-biomes-") as tmp:
        try:
            write_biome_demo_worlds(Path(tmp))
        except ImportError:
            return [], "Parcours de démonstration : compilateur absent (scripts/install.sh)."
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            return [], f"Parcours de démonstration impossibles : {exc}."
        for n in missing:
            src = Path(tmp) / f"{n}.world"
            dst = routes_dir / f"{n}.world"
            if src.is_dir():
                if dst.exists():   # dossier incomplet d'un essai précédent : remplacé
                    shutil.rmtree(dst)
                shutil.move(str(src), dst)
    return missing, ""


# --- packs, archives et thèmes (lot O29) ---------------------------------------------------------

def _dir_bytes(path: Path) -> int:
    total = 0
    for f in path.rglob("*"):
        try:
            if f.is_file() and not f.is_symlink():
                total += f.stat().st_size
        except OSError:
            continue
    return total


def _mb(n: int | float) -> float:
    return round(n / MB, 1)


def _compiler_package() -> Path | None:
    """Dossier du paquet du compilateur, sans l'importer (le core n'en dépend pas)."""
    import importlib.util

    spec = importlib.util.find_spec("openride_compiler")
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(list(spec.submodule_search_locations)[0])


def _pack_name(pack_toml: Path) -> str:
    try:
        return str(tomllib.loads(pack_toml.read_text(encoding="utf-8")).get("name", ""))
    except (OSError, ValueError):
        return ""


def _installed_pack(gpx: Path, name: str) -> Path | None:
    """Sous-dossier de `gpx` dont le `pack.toml` porte ce nom."""
    if not name or not gpx.is_dir():
        return None
    for d in sorted(p for p in gpx.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if _pack_name(d / "pack.toml") == name:
            return d
    return None


def cols_item(dirs: ContentDirs) -> dict[str, Any] | None:
    """Pack « Cols célèbres » (lot O16) ; None sans compilateur ou sans dossier des traces."""
    pkg = _compiler_package()
    if pkg is None or dirs.gpx is None:
        return None
    recipes_dir = pkg / "route_packs" / COLS_PACK
    recipes = [p for p in recipes_dir.glob("*.toml") if p.name != "pack.toml"]
    if not recipes:
        return None
    name = _pack_name(recipes_dir / "pack.toml") or "Cols célèbres"
    target = _installed_pack(dirs.gpx, name)
    have = sum(1 for p in target.glob("*.gpx")) if target else 0
    state = "installed" if have >= len(recipes) else ("partial" if have else "missing")
    return {"id": COLS_ID, "kind": "route_pack", "label": f"Pack « {name} »",
            "detail": f"{len(recipes)} montées célèbres (Alpe d'Huez, Ventoux, Teide…) construites depuis "
                      "OpenStreetMap", "state": state, "network": True,
            "size_mb": _mb(_dir_bytes(target)) if target else None, "progress_pct": None}


def _archive_kind(path: Path) -> tuple[str, str, int] | None:
    """(`theme` ou `route_pack`, nom annoncé, octets décompressés) d'une archive, None si ce n'en est pas une."""
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            names = {Path(i.filename).name: i for i in infos if not i.is_dir()}
            size = sum(i.file_size for i in infos)
            if "theme.json" in names:
                try:
                    meta = json.loads(zf.read(names["theme.json"]).decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    meta = {}
                return "theme", str(meta.get("name") or path.stem) if isinstance(meta, dict) else path.stem, size
            if "pack.toml" in names:
                try:
                    meta = tomllib.loads(zf.read(names["pack.toml"]).decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    meta = {}
                return "route_pack", str(meta.get("name") or path.stem), size
    except (OSError, zipfile.BadZipFile):
        return None
    return None


def find_archives(home: Path) -> list[dict[str, Any]]:
    """Archives de packs trouvées dans les dossiers de l'import ERG (lot N16), les plus récentes d'abord."""
    from .workout_menu import IMPORT_SOURCES

    found: list[tuple[float, dict[str, Any]]] = []
    seen: set[Path] = set()
    for rel, label in IMPORT_SOURCES:
        directory = home / rel if rel else home
        try:
            entries = [f for f in directory.iterdir() if f.suffix.lower() == ".zip" and f.is_file()]
        except OSError:
            continue
        for f in entries:
            if f in seen:
                continue
            seen.add(f)
            kind = _archive_kind(f)
            if kind:
                found.append((f.stat().st_mtime, {"path": f, "kind": kind[0], "name": kind[1],
                                                   "size": kind[2], "source": label}))
    found.sort(key=lambda t: (-t[0], t[1]["path"].name))
    return [a for _, a in found[:MAX_ARCHIVES]]


def _normalize(text: str) -> str:
    import re
    import unicodedata

    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def archive_item(index: int, a: dict[str, Any], dirs: ContentDirs) -> dict[str, Any]:
    """Élément `archive:N` ; « installé » si un thème ou un pack du même nom est déjà en place."""
    if a["kind"] == "theme":
        installed = dirs.themes is not None and (
            (dirs.themes / _normalize(a["name"])).is_dir() or (dirs.themes / _normalize(a["path"].stem)).is_dir())
        label = f"Thème « {a['name']} »"
    else:
        installed = dirs.gpx is not None and _installed_pack(dirs.gpx, a["name"]) is not None
        label = f"Pack de parcours « {a['name']} »"
    return {"id": f"archive:{index}", "kind": a["kind"], "label": label,
            "detail": f"{a['path'].name}, dans {a['source']}", "state": "installed" if installed else "missing",
            "network": False, "size_mb": _mb(a["size"]), "progress_pct": None}


def theme_items(dirs: ContentDirs) -> list[dict[str, Any]]:
    """Thèmes installés : taille et dernière utilisation (`.utilisation.json`, écrit par le lanceur)."""
    if dirs.themes is None or not dirs.themes.is_dir():
        return []
    try:
        uses = json.loads((dirs.themes / THEME_USE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        uses = {}
    out = []
    for d in sorted(p for p in dirs.themes.iterdir() if p.is_dir() and (p / "theme.json").is_file()):
        used = str(uses.get(d.name, "")) if isinstance(uses, dict) else ""
        detail = f"dernière utilisation le {used[8:10]}/{used[5:7]}/{used[:4]}" if len(used) >= 10 else "jamais utilisé"
        out.append({"id": f"theme:{d.name}", "kind": "theme", "label": f"Thème « {d.name} »",
                    "detail": detail + " ; se choisit dans Réglages › Graphisme", "state": "installed",
                    "network": False, "size_mb": _mb(_dir_bytes(d)), "progress_pct": None})
    return out


def disk_info(dirs: ContentDirs) -> dict[str, Any]:
    """Place libre sur le disque des contenus, place des thèmes et leur plafond, en Mo."""
    base = dirs.themes if dirs.themes is not None and dirs.themes.exists() else dirs.workouts
    while not base.exists() and base != base.parent:
        base = base.parent
    try:
        free = _mb(shutil.disk_usage(base).free)
    except OSError:
        free = None
    themes = _mb(_dir_bytes(dirs.themes)) if dirs.themes is not None and dirs.themes.is_dir() else 0.0
    return {"disk_free_mb": free, "themes_mb": themes, "themes_max_mb": round(dirs.themes_max_gb * 1024.0, 1)}


def _run_compiler(args: list[str], on_line: Callable[[str], None] = lambda line: None) -> str:
    """Lance le compilateur ; renvoie sa sortie d'erreur, lève ContentError s'il échoue ou manque."""
    from .launch_compile import compiler_base_cmd

    base = compiler_base_cmd()
    if base is None:
        raise ContentError("compilateur absent (scripts/install.sh)")
    proc = subprocess.Popen(base + args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        lines.append(line.rstrip())
        on_line(line.rstrip())
    code = proc.wait(timeout=STEP_TIMEOUT_S)
    if code not in (0, 1) or (code == 1 and args[0] != "route-pack-build"):
        last = next((ln for ln in reversed(lines) if ln.strip()), f"code {code}")
        raise ContentError(last.removeprefix("openride-compiler : ").strip())
    return "\n".join(lines)


def _compile_routes(dirs: ContentDirs) -> None:
    _run_compiler(["build-all", "--gpx-dir", str(dirs.gpx), "--routes-dir", str(dirs.routes)])


def install_cols(dirs: ContentDirs, progress: Callable[[int], None]) -> str:
    """Construit le pack des cols (réseau), l'installe dans les traces puis le compile."""
    pkg = _compiler_package()
    total = max(1, len([p for p in (pkg / "route_packs" / COLS_PACK).glob("*.toml") if p.name != "pack.toml"])
                if pkg else 1)
    seen = [0]

    def line(text: str) -> None:
        if text.startswith("  ") and " : " in text:   # une ligne par col construit ou refusé
            seen[0] += 1
            progress(int(80 * seen[0] / total))

    out = _run_compiler(["route-pack-build", COLS_PACK, "--install", "--gpx-dir", str(dirs.gpx)], line)
    refused = sum(1 for ln in out.splitlines() if ln.strip().startswith("refusé"))
    progress(80)
    _compile_routes(dirs)
    done = total - refused
    return f"Pack installé : {done} col(s) sur {total}" + (f", {refused} refusé(s)." if refused else ".")


def install_archive(a: dict[str, Any], dirs: ContentDirs, progress: Callable[[int], None]) -> str:
    if a["kind"] == "theme":
        args = ["theme-install", str(a["path"])]
        if dirs.themes is not None:
            args += ["--themes-dir", str(dirs.themes)]
        _run_compiler(args)
        return f"Thème « {a['name']} » installé : il se choisit dans Réglages › Graphisme."
    _run_compiler(["route-pack-install", str(a["path"]), "--gpx-dir", str(dirs.gpx)])
    progress(50)
    _compile_routes(dirs)
    return f"Pack de parcours « {a['name']} » installé et compilé."


# --- catalogue et installation en cours -----------------------------------------------------------

@dataclass
class ContentJob:
    """Installation en cours : élément, avancement, compte rendu."""
    id: str
    progress_pct: int = 0
    done: bool = False
    message: str = ""
    failed: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_progress(self, pct: int) -> None:
        with self._lock:
            self.progress_pct = max(self.progress_pct, min(100, int(pct)))


class ContentService:
    """Liste des contenus et installation unique en cours (`start` puis `run` dans un fil)."""

    def __init__(self, dirs: ContentDirs) -> None:
        self.dirs = dirs
        self.job: ContentJob | None = None
        self.last_message = ""
        self._archives: list[dict[str, Any]] = []   # archives proposées par le dernier `items()`

    @property
    def busy(self) -> bool:
        return self.job is not None and not self.job.done

    def items(self) -> list[dict[str, Any]]:
        parts = starter_parts(self.dirs)
        out = [{"id": STARTER_ID, "kind": "starter", "label": "Contenus de départ",
                "detail": starter_detail(parts), "state": _state_of(parts), "network": False,
                "size_mb": None, "progress_pct": None}]
        cols = cols_item(self.dirs)
        if cols:
            out.append(cols)
        if self.dirs.home is not None and not self.busy:   # liste figée pendant une installation
            self._archives = find_archives(self.dirs.home)
        out += [archive_item(i, a, self.dirs) for i, a in enumerate(self._archives)]
        out += theme_items(self.dirs)
        out = out[:MAX_ITEMS]
        if self.busy:
            for it in out:
                if it["id"] == self.job.id:
                    it["state"] = "installing"
                    it["progress_pct"] = self.job.progress_pct
        return out

    def message(self, cmd_id: int) -> dict[str, Any]:
        return {"type": "contents", "v": 1, "request_cmd_id": cmd_id, "items": self.items(),
                "busy": self.job.id if self.busy else None, "message": self.last_message,
                **disk_info(self.dirs)}

    def _archive(self, content_id: str) -> dict[str, Any] | None:
        try:
            return self._archives[int(content_id.split(":", 1)[1])]
        except (IndexError, ValueError):
            return None

    def start(self, content_id: str) -> ContentJob:
        """Réserve l'installation ; ContentError si l'élément est inconnu ou si une autre tourne."""
        known = content_id == STARTER_ID or (content_id == COLS_ID and cols_item(self.dirs) is not None) \
            or (content_id.startswith("archive:") and self._archive(content_id) is not None)
        if not known:
            raise ContentError(f"contenu inconnu : {content_id}")
        if self.busy:
            raise ContentError("une installation est déjà en cours")
        self.job = ContentJob(content_id)
        self.last_message = ""
        return self.job

    def run(self, job: ContentJob) -> None:
        """Corps de l'installation (dans un fil) ; ne lève jamais."""
        try:
            if job.id == STARTER_ID:
                job.message = install_starter(self.dirs, job.set_progress)
            elif job.id == COLS_ID:
                job.message = install_cols(self.dirs, job.set_progress)
            else:
                job.message = install_archive(self._archive(job.id), self.dirs, job.set_progress)
        except (ContentError, OSError, ValueError, subprocess.SubprocessError) as exc:
            job.failed = True
            job.message = f"Installation impossible : {exc}"
        job.set_progress(100)
        job.done = True
        self.last_message = job.message
