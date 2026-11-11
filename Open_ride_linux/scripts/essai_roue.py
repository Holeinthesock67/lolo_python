"""Essai d'installation d'un paquet par sa roue, hors du dépôt (lot J4).

Utilisé par `core/tests/test_packaging.py` et `compiler/tests/test_packaging.py` :

1. copie du paquet (`pyproject.toml` et `src/`) dans un dossier temporaire, pour que la construction
   n'écrive rien dans le dépôt (`build/`, `*.egg-info`) ;
2. `pip wheel --no-deps --no-build-isolation --no-index` : aucune connexion réseau ;
3. environnement virtuel temporaire sans pip, roue installée avec `--no-deps` par le pip courant
   (`pip --python`) ;
4. les dépendances déclarées sont prises dans l'environnement courant par un fichier `.pth` qui
   ne liste que ses dossiers `site-packages` : les `.pth` qu'ils contiennent (installations
   éditables du dépôt) ne sont pas lus, donc seul le paquet de la roue est importable.

Les sous-processus ont `RUSTUP_HOME` et `CARGO_HOME` dans le dossier de travail : pip lance
`rustc --version` pour son en-tête User-Agent (même avec `--no-index`), et le relais `rustc` de
rustup, sans `RUSTUP_HOME` (machines GitHub, PC sans variable), crée `~/.rustup/settings.toml`
dans le HOME temporaire de la suite.

`construire_et_installer` renvoie le dossier `bin/` de l'environnement (python et commandes).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

IGNORES = shutil.ignore_patterns("__pycache__", "*.egg-info", "build", "*.pyc")


def env_sans_reseau(travail: Path) -> dict[str, str]:
    """Environnement des sous-processus : pas de réseau, et rien d'écrit hors de `travail`."""
    env = dict(os.environ)
    env.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONNOUSERSITE="1",
               RUSTUP_HOME=str(travail / "rustup"), CARGO_HOME=str(travail / "cargo"))
    env.pop("PYTHONPATH", None)
    return env


def _run(cmd: list[str], cwd: Path) -> None:
    res = subprocess.run(cmd, cwd=cwd, env=env_sans_reseau(cwd), capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise RuntimeError(f"échec de {' '.join(cmd)} :\n{res.stdout}\n{res.stderr}")


def construire_et_installer(paquet_dir: Path, travail: Path) -> Path:
    """Construit la roue de `paquet_dir` et l'installe dans un environnement neuf sous `travail`."""
    source = travail / "source"
    source.mkdir(parents=True)
    shutil.copy2(paquet_dir / "pyproject.toml", source / "pyproject.toml")
    shutil.copytree(paquet_dir / "src", source / "src", ignore=IGNORES)

    roues = travail / "roues"
    _run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-index",
          "-w", str(roues), str(source)], cwd=travail)
    (roue,) = roues.glob("*.whl")

    env_dir = travail / "venv"
    venv.EnvBuilder(with_pip=False).create(env_dir)
    bin_dir = env_dir / ("Scripts" if os.name == "nt" else "bin")
    python = bin_dir / ("python.exe" if os.name == "nt" else "python")
    _run([sys.executable, "-m", "pip", "--python", str(python), "install", "--no-deps", "--no-index",
          str(roue)], cwd=travail)

    site_venv = Path(subprocess.check_output(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], text=True).strip())
    deps = [p for p in sys.path if Path(p).name in ("site-packages", "dist-packages") and Path(p).is_dir()]
    (site_venv / "_openride_dependances.pth").write_text("\n".join(deps) + "\n", encoding="utf-8")
    return bin_dir


def lancer(bin_dir: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Lance une commande de l'environnement (`python` ou une commande du paquet) depuis `cwd`."""
    exe = bin_dir / args[0]
    if os.name == "nt" and not exe.exists():
        exe = exe.with_suffix(".exe")
    return subprocess.run([str(exe), *args[1:]], cwd=cwd, env=env_sans_reseau(bin_dir.parent.parent),
                          capture_output=True, text=True, timeout=300)
