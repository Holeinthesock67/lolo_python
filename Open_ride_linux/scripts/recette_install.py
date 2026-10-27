#!/usr/bin/env python3
"""Recette de l'installation sur un système propre (lot X29, recette 1.0 lignes 1 et 2).

Lance `scripts/recette_install/check_install.sh` dans un compte vierge, avec le code du dépôt tel
qu'il est commité (HEAD de la branche courante, publié dans un dépôt d'origine temporaire) :

    scripts/recette_install.py                     # conteneur Ubuntu 24.04 neuf (docker), sans Bluetooth
    scripts/recette_install.py --mode home         # HOME temporaire sur ce PC (sans docker)
    scripts/recette_install.py --mode home --sans-pip   # essai rapide : venv actuel, pas de pip

Le script vérifié fait ce que fait un nouvel utilisateur : clone, `install.sh` sans terminal,
commandes, configuration, raccourcis de bureau et icône, premier démarrage (compilation des
parcours, core sur le trainer simulé), puis données de l'utilisateur, nouveau commit sur l'origine,
`update.sh` et `install.sh` relancé : le code avance, parcours, séances et `config.toml` restent
identiques. Le second compte du PC reste un essai à la main (docs/OUTILS_DE_TEST.md).

Variables : GODOT (Godot 4.3, défaut ~/Applications/godot/…). En conteneur, les variables de
mandataire (HTTPS_PROXY…) sont transmises ; `--ca-bundle` ajoute un certificat racine.
Journal et résumé : `~/OpenRide/recettes_install/<date>_<heure>/`. Code de sortie : 0 si tout passe,
1 sinon, 2 si docker ou Godot manque.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]          # Open_ride_linux/
REPO = PROJECT.parent
CHECK = PROJECT / "scripts" / "recette_install" / "check_install.sh"
DEFAULT_OUT = Path.home() / "OpenRide" / "recettes_install"
DEFAULT_GODOT = Path.home() / "Applications" / "godot" / "Godot_v4.3-stable_linux.x86_64"
DEFAULT_IMAGE = "ubuntu:24.04"
APT_PACKAGES = ("python3", "python3-venv", "python3-pip", "git", "ca-certificates", "desktop-file-utils",
                "libfontconfig1", "libgl1", "libxi6", "libxrandr2", "libxcursor1", "libxinerama1")
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")


def make_origin(tmp: Path) -> Path:
    """Dépôt d'origine nu dont la branche « recette » est le HEAD actuel (ce qui est commité, pas l'arbre
    de travail ; marche aussi sur un HEAD détaché, comme dans l'intégration continue)."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                          check=True).stdout.strip()
    origin = tmp / "origin.git"
    subprocess.run(["git", "clone", "--quiet", "--bare", str(REPO), str(origin)], check=True)
    subprocess.run(["git", "-C", str(origin), "update-ref", "refs/heads/recette", head], check=True)
    subprocess.run(["git", "-C", str(origin), "symbolic-ref", "HEAD", "refs/heads/recette"], check=True)
    return origin


def summarize(log_text: str) -> tuple[list[str], str]:
    lines = [ln for ln in log_text.splitlines() if ln.startswith(("[OK]", "[ÉCHEC]"))]
    result = next((ln for ln in reversed(log_text.splitlines()) if ln.startswith("RÉSULTAT")), "RÉSULTAT : ?")
    return lines, result


def run_home(godot: Path, tmp: Path, origin: Path, sans_pip: bool, log) -> int:
    home = tmp / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("XDG_", "VIRTUAL_ENV", "OPENRIDE_"))}
    env.update(HOME=str(home), REPO_URL=str(origin), GODOT=str(godot), PYTHONNOUSERSITE="1")
    if sans_pip:
        found = shutil.which("openride", path=f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}")
        if found is None:
            print("--sans-pip : commande openride introuvable (lancer depuis le venv du projet)")
            return 2
        bin_src = Path(found).parent
        env.update(OPENRIDE_NO_PIP="1", OPENRIDE_PYTHON=sys.executable, OPENRIDE_BIN_SRC=str(bin_src))
    proc = subprocess.run(["bash", str(CHECK)], env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    return proc.returncode


def run_docker(godot: Path, tmp: Path, origin: Path, image: str, ca_bundle: Path | None, log) -> int:
    os.chmod(tmp, 0o755)   # lisible par le compte du conteneur
    shutil.copy(CHECK, tmp / "check_install.sh")
    mounts = ["-v", f"{tmp}:/mnt/recette:ro", "-v", f"{godot.parent}:/opt/godot:ro"]
    env_args: list[str] = []
    for k in PROXY_VARS:
        if os.environ.get(k):
            env_args += ["-e", f"{k}={os.environ[k]}"]
    ca_setup = ""
    if ca_bundle is not None:
        shutil.copy(ca_bundle, tmp / "ca.crt")
        os.chmod(tmp / "ca.crt", 0o644)
        ca = "/mnt/recette/ca.crt"
        env_args += ["-e", f"PIP_CERT={ca}", "-e", f"REQUESTS_CA_BUNDLE={ca}", "-e", f"SSL_CERT_FILE={ca}",
                     "-e", f"GIT_SSL_CAINFO={ca}"]
        ca_setup = f"echo 'Acquire::https::CAInfo \"{ca}\";' > /etc/apt/apt.conf.d/99recette-ca; "
    script = (
        "set -e; export DEBIAN_FRONTEND=noninteractive; " + ca_setup
        + "apt-get update -qq && apt-get install -y -qq --no-install-recommends "
        + " ".join(APT_PACKAGES) + " > /dev/null; "
        + "useradd -m -s /bin/bash cycliste; "
        + "cp -r /mnt/recette/origin.git /srv/origin.git && chown -R cycliste /srv/origin.git; "
        + "echo \"== Ubuntu $(. /etc/os-release && echo $VERSION_ID), compte vierge cycliste, sans Bluetooth\"; "
        # su sans « - » garde l'environnement (mandataire, certificat) ; HOME devient celui de cycliste.
        + f"su cycliste -c 'cd ~ && REPO_URL=/srv/origin.git GODOT=/opt/godot/{godot.name} "
        + "bash /mnt/recette/check_install.sh'"
    )
    cmd = ["docker", "run", "--rm", "--network", "host", *mounts, *env_args, image, "bash", "-c", script]
    proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=False)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recette de l'installation sur un système propre (lot X29).")
    ap.add_argument("--mode", choices=("docker", "home"), default="docker",
                    help="docker : conteneur Ubuntu neuf (défaut) ; home : HOME temporaire sur ce PC")
    ap.add_argument("--image", default=DEFAULT_IMAGE, help=f"image du conteneur (défaut {DEFAULT_IMAGE})")
    ap.add_argument("--godot", type=Path, default=Path(os.environ.get("GODOT", DEFAULT_GODOT)))
    ap.add_argument("--sans-pip", action="store_true", help="mode home : venv actuel, sans pip (essai rapide)")
    ap.add_argument("--ca-bundle", type=Path, help="mode docker : certificat racine à faire confiance (mandataire)")
    ap.add_argument("--out", type=Path, help=f"dossier du journal (défaut : {DEFAULT_OUT}/<date>)")
    args = ap.parse_args(argv)

    godot = args.godot.expanduser().resolve()
    if not os.access(godot, os.X_OK):
        print(f"Godot introuvable : {godot} (option --godot ou variable GODOT)")
        return 2
    if args.mode == "docker" and shutil.which("docker") is None:
        print("docker introuvable : installer docker ou lancer avec --mode home")
        return 2
    out = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / f"install_{args.mode}.log"
    with tempfile.TemporaryDirectory(prefix="openride-recette-install-") as tmp_s:
        tmp = Path(tmp_s)
        origin = make_origin(tmp)
        print(f"== Recette d'installation ({args.mode}) : journal {log_path}", flush=True)
        with log_path.open("w", encoding="utf-8") as log:
            if args.mode == "home":
                rc = run_home(godot, tmp, origin, args.sans_pip, log)
            else:
                rc = run_docker(godot, tmp, origin, args.image, args.ca_bundle, log)
        if args.mode == "docker":   # fichiers du conteneur créés par root : rendus supprimables
            subprocess.run(["chmod", "-R", "u+rwX", tmp_s], check=False)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines, result = summarize(text)
    resume = "\n".join([f"Recette d'installation ({args.mode}), {datetime.now():%d/%m/%Y %H:%M}", "", *lines, "",
                        result, f"Journal : {log_path}"]) + "\n"
    (out / f"resume_{args.mode}.txt").write_text(resume, encoding="utf-8")
    print(resume, end="")
    ok = rc == 0 and bool(re.search(r"installation neuve OK", result))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
