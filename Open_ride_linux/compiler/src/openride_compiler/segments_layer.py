"""Couche `segments` du `.world` (lot T3, série T ; format §8 bis, version 1.3).

Montées et sprints détectés par le core (`openride_core.segments`, lot T2), plus les segments
déclarés à la main dans `<parcours>.segments.toml`, posé à côté de la trace :

    mode = "add"          # "add" (défaut) : ajoutés aux segments détectés ; "replace" : seuls ceux-ci
    auto_sprints = true   # sprints proposés automatiquement (défaut : true)

    [[segment]]
    type = "sprint"       # "sprint" ou "climb"
    start_km = 12.4
    end_km = 12.8
    name = "Sprint du village"   # facultatif

La détection vit dans le core : sans core installé, `core_segments()` rend None et la couche
n'est pas produite (elle est facultative).
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from .errors import CompileError

LAYER_VERSION = "1.0"
LAYER_FILE = "segments.json"
MAX_SEGMENTS = 200
MANUAL_SUFFIX = ".segments.toml"
TOP_KEYS = {"mode", "auto_sprints", "segment"}
SEGMENT_KEYS = {"type", "start_km", "end_km", "name"}
MODES = ("add", "replace")
TYPES = ("sprint", "climb")
CATEGORIES = ("4", "3", "2", "1", "HC")
NAME_MAX = 48


@dataclass(frozen=True)
class ManualSpec:
    """Contenu validé d'un fichier `<parcours>.segments.toml`."""
    path: Path
    mode: str = "add"
    auto_sprints: bool = True
    entries: list[dict] = field(default_factory=list)


def manual_path(track: Path, stem: str) -> Path:
    """Fichier manuel d'une trace : `<nom sans extension>.segments.toml` dans le même dossier."""
    return Path(track).parent / f"{stem}{MANUAL_SUFFIX}"


def core_segments() -> ModuleType | None:
    """Module de détection du core, ou None s'il n'est pas installé."""
    try:
        from openride_core import segments
    except ImportError:
        return None
    return segments


def load_manual(path: Path, length_m: float | None = None) -> ManualSpec:
    """Lit et valide un fichier manuel ; refus clair avec le nom du fichier et le numéro du segment."""
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CompileError(f"{path.name} : fichier illisible ({exc})") from exc
    unknown = sorted(set(data) - TOP_KEYS)
    if unknown:
        raise CompileError(f"{path.name} : clé inconnue {', '.join(unknown)}")
    mode = data.get("mode", "add")
    if mode not in MODES:
        raise CompileError(f"{path.name} : mode {mode!r} inconnu (add ou replace)")
    auto_sprints = data.get("auto_sprints", True)
    if not isinstance(auto_sprints, bool):
        raise CompileError(f"{path.name} : auto_sprints doit valoir true ou false")
    items = data.get("segment", [])
    if not isinstance(items, list):
        raise CompileError(f"{path.name} : « segment » doit être une liste [[segment]]")
    entries: list[dict] = []
    for k, item in enumerate(items, 1):
        where = f"{path.name}, segment {k}"
        if not isinstance(item, dict):
            raise CompileError(f"{where} : table attendue")
        bad = sorted(set(item) - SEGMENT_KEYS)
        if bad:
            raise CompileError(f"{where} : clé inconnue {', '.join(bad)}")
        missing = [key for key in ("type", "start_km", "end_km") if key not in item]
        if missing:
            raise CompileError(f"{where} : {', '.join(missing)} manquant")
        if item["type"] not in TYPES:
            raise CompileError(f"{where} : type {item['type']!r} inconnu (sprint ou climb)")
        s0, s1 = item["start_km"], item["end_km"]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (s0, s1)):
            raise CompileError(f"{where} : start_km et end_km doivent être des nombres")
        limit = None if length_m is None else length_m / 1000.0 + 1e-5
        if not 0.0 <= s0 < s1 or (limit is not None and s1 > limit):
            longueur = "" if length_m is None else f" de {length_m / 1000:.3f} km"
            raise CompileError(f"{where} : {s0}–{s1} km hors du parcours{longueur} ou vide")
        name = item.get("name")
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise CompileError(f"{where} : name doit être un texte non vide")
        entries.append({"type": item["type"], "start_km": float(s0), "end_km": float(s1),
                        **({"name": name.strip()[:NAME_MAX]} if name else {})})
    return ManualSpec(path, mode, auto_sprints, entries)


def route_profile(core: ModuleType, route: dict):
    """Profil du core lu sur une couche route (abscisses s_i = i·ds_m, la dernière = length_m)."""
    n, ds = int(route["n"]), float(route["ds_m"])
    s = [i * ds for i in range(n - 1)] + [float(route["length_m"])]
    return core.Profile(s, route["alt_m"], route["grade_pct"])


def build_segments(route: dict, manual: ManualSpec | None = None,
                   core: ModuleType | None = None) -> list[dict]:
    """Segments du parcours (`Segment.to_dict()`), détectés puis complétés par le fichier manuel."""
    core = core or core_segments()
    if core is None:
        raise CompileError("couche segments : le core OpenRide (openride_core) n'est pas installé")
    profile = route_profile(core, route)
    try:
        auto = core.detect_segments(profile, auto_sprints=manual.auto_sprints if manual else True)
        segs = auto
        if manual is not None:
            segs = core.merge_manual(auto, core.manual_segments(profile, manual.entries), manual.mode)
    except core.SegmentError as exc:
        where = manual.path.name if manual is not None else "détection"
        raise CompileError(f"{where} : {exc}") from exc
    if len(segs) > MAX_SEGMENTS:
        raise CompileError(f"couche segments : {len(segs)} segments, au plus {MAX_SEGMENTS}")
    return [seg.to_dict() for seg in segs]


def segments_manifest(segments: list[dict]) -> dict:
    return {"present": True, "version": LAYER_VERSION, "file": LAYER_FILE, "count": len(segments),
            "manual_count": sum(1 for s in segments if s["source"] == "manual")}


def segments_text(segments: list[dict]) -> str:
    """Contenu de `segments.json`, identique octet pour octet pour les mêmes segments."""
    return json.dumps({"version": LAYER_VERSION, "segments": segments}, indent=1,
                      ensure_ascii=False) + "\n"


def write_segments(folder: Path, segments: list[dict]) -> None:
    (Path(folder) / LAYER_FILE).write_text(segments_text(segments), encoding="utf-8")


def replace_segments(world: Path, segments: list[dict]) -> None:
    """Réécrit `segments.json` d'un `.world` existant de façon atomique."""
    tmp = Path(world) / f".{LAYER_FILE}.tmp-{os.getpid()}"
    try:
        tmp.write_text(segments_text(segments), encoding="utf-8")
        os.replace(tmp, Path(world) / LAYER_FILE)
    finally:
        tmp.unlink(missing_ok=True)


def summarize(segments: list[dict]) -> str:
    """« 2 montée(s) (cat. 3 : 1, cat. 4 : 1), 1 sprint(s) » pour `info`."""
    climbs = [s for s in segments if s.get("type") == "climb"]
    sprints = sum(1 for s in segments if s.get("type") == "sprint")
    by_cat = [f"cat. {c} : {n}" for c in reversed(CATEGORIES)
              if (n := sum(1 for s in climbs if s.get("category") == c))]
    detail = f" ({', '.join(by_cat)})" if by_cat else ""
    return f"{len(climbs)} montée(s){detail}, {sprints} sprint(s)"
