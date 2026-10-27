"""openride-compiler : compilation d'une trace GPX en parcours `.world` (SRS v1.1 §7)."""

from pathlib import Path as _Path


def _read_version() -> str:
    """Numéro unique de `Open_ride_linux/VERSION` (lot O2).

    Dans le dépôt (mode éditable), le fichier fait foi ; une fois installé hors du dépôt,
    la version des métadonnées du paquet, écrite depuis le même fichier.
    """
    here = _Path(__file__).resolve().parents
    if here[2].name == "compiler" and (here[3] / "VERSION").is_file():
        return (here[3] / "VERSION").read_text(encoding="utf-8").strip()
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("openride-compiler")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _read_version()
