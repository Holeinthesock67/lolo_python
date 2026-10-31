"""Contenus installables depuis le menu « Réglages › Contenus » (lot O25 ; contrat IPC révision 1.5).

Le joueur n'a besoin d'aucune commande pour remplir sa bibliothèque : chaque contenu est un élément du
message `contents` (`list_contents`), installé par `install_content`, toujours sans rien écraser.

- `starter` (« Contenus de départ ») : les entraînements livrés (`core/workouts/`), les deux plans de
  départ (`core/plans/`) et les quatre parcours de démonstration des biomes (`openride-core
  demo-biomes`, lot U19). Installé seul au premier lancement (`run --first-run`), puis proposé dans
  le menu pour une installation existante. Rien n'est téléchargé.

État d'un élément : `missing` (rien d'installé), `partial`, `installed` ou `installing` (avec
`progress_pct`). Une seule installation à la fois ; elle tourne dans un fil (`ContentJob.run`), le
core n'en lit que l'avancement.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

STARTER_ID = "starter"
STATES = ("missing", "partial", "installed", "installing")


@dataclass
class ContentDirs:
    """Dossiers de destination : bibliothèque d'entraînements, plans et parcours compilés."""
    workouts: Path
    plans: Path
    routes: Path


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

    @property
    def busy(self) -> bool:
        return self.job is not None and not self.job.done

    def items(self) -> list[dict[str, Any]]:
        parts = starter_parts(self.dirs)
        item = {"id": STARTER_ID, "kind": "starter", "label": "Contenus de départ",
                "detail": starter_detail(parts), "state": _state_of(parts), "network": False,
                "size_mb": None, "progress_pct": None}
        if self.busy and self.job.id == STARTER_ID:
            item["state"] = "installing"
            item["progress_pct"] = self.job.progress_pct
        return [item]

    def message(self, cmd_id: int) -> dict[str, Any]:
        return {"type": "contents", "v": 1, "request_cmd_id": cmd_id, "items": self.items(),
                "busy": self.job.id if self.busy else None, "message": self.last_message}

    def start(self, content_id: str) -> ContentJob:
        """Réserve l'installation ; ContentError si l'élément est inconnu ou si une autre tourne."""
        if content_id != STARTER_ID:
            raise ContentError(f"contenu inconnu : {content_id}")
        if self.busy:
            raise ContentError("une installation est déjà en cours")
        self.job = ContentJob(content_id)
        self.last_message = ""
        return self.job

    def run(self, job: ContentJob) -> None:
        """Corps de l'installation (dans un fil) ; ne lève jamais."""
        try:
            job.message = install_starter(self.dirs, job.set_progress)
        except (OSError, ValueError) as exc:
            job.failed = True
            job.message = f"Installation impossible : {exc}"
        job.set_progress(100)
        job.done = True
        self.last_message = job.message
