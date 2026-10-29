"""Fiches des parcours (lot O15) : fiche calculée, fiche saisie (`<trace>.toml`), tri et filtres.

Module pur (bibliothèque standard seulement), lu sur les colonnes de `route.json` (`alt_m`,
`ds_m`, `length_m`, `n`). **Copie exacte** dans `compiler/src/openride_compiler/route_stats.py`
pour que le repli du compilateur, sans le core, donne la même fiche ;
`compiler/tests/test_catalog_parity.py` vérifie que les deux fichiers restent identiques.

Barème (documenté aussi dans `docs/contracts/world_format_v1.md`, champ `stats`) :
- dénivelés : altitudes lissées de `alt_m`, une variation n'est comptée qu'au-delà de 1 m
  (hystérésis) pour ne pas cumuler le bruit ;
- pente maximale : sur 100 m de distance horizontale ;
- montée : portion où l'altitude monte sans redescendre de plus de 20 m sous son point haut ;
  la montée principale est celle du plus grand dénivelé, retenue à partir de 500 m et 20 m ;
- catégorie de la montée, d'après le produit longueur (m) × pente moyenne (%) : 4 dès 8 000,
  3 dès 16 000, 2 dès 32 000, 1 dès 64 000, HC dès 80 000 ;
- durée estimée à puissance constante : vitesse d'équilibre sur chaque tronçon de 100 m
  (cycliste et vélo de 84 kg, CdA 0,32 m², Crr 0,004, rendement 0,97, air 1,225 kg/m³), vitesse
  plafonnée à 20 m/s en descente ;
- durée à une autre puissance (la FTP de la configuration) : interpolée dans `durations_s`,
  durées rangées de 100 à 400 W par pas de 25 W ;
- difficulté de 1 à 5 : 5 si montée HC ou plus de 2 000 m de dénivelé positif, 4 si catégorie 1
  ou 1 200 m, 3 si catégorie 2 ou 600 m, 2 si catégorie 3 ou 4 ou 200 m, sinon 1.

Comparaison à Garmin Connect (lot X31, recette 1.0 ligne 22) : `compare_garmin` met en face des valeurs
lues dans Garmin Connect la pente maximale (même fenêtre glissante, 100 m par défaut), le dénivelé positif
et la longueur du parcours ; tolérances ± 1 point, ± 5 % et ± 1 %.

Fiche saisie : `load_library` lit et contrôle un `<trace>.toml` (`name`, `description`, `region`,
`tags`, `credits`) ; une région ne contient jamais de coordonnées.
"""

from __future__ import annotations

import math
import re
import tomllib
from pathlib import Path
from typing import Any

STATS_VERSION = 1
GAIN_THRESHOLD_M = 1.0
MAX_GRADE_WINDOW_M = 100.0
CLIMB_DROP_M = 20.0
CLIMB_MIN_LENGTH_M = 500.0
CLIMB_MIN_GAIN_M = 20.0
CATEGORIES = ((80000.0, "HC"), (64000.0, "1"), (32000.0, "2"), (16000.0, "3"), (8000.0, "4"))
DURATION_CHUNK_M = 100.0
MASS_KG = 84.0
CDA_M2 = 0.32
CRR = 0.004
EFFICIENCY = 0.97
RHO = 1.225
G = 9.81
V_DESCENT_MAX = 20.0
DURATION_POWERS_W = tuple(range(100, 401, 25))
GARMIN_GRADE_TOL_PT = 1.0
GARMIN_GAIN_TOL = 0.05
GARMIN_LENGTH_TOL = 0.01


def _positions(route: dict[str, Any]) -> list[float]:
    """Abscisses `s` des points : i × ds_m, sauf le dernier à length_m (format §4)."""
    n, ds, length = int(route["n"]), float(route["ds_m"]), float(route["length_m"])
    return [i * ds for i in range(n - 1)] + [length]


def gain_loss(alt: list[float], threshold: float = GAIN_THRESHOLD_M) -> tuple[float, float]:
    gain = loss = 0.0
    ref = alt[0]
    for a in alt[1:]:
        if a - ref >= threshold:
            gain += a - ref
            ref = a
        elif ref - a >= threshold:
            loss += ref - a
            ref = a
    return gain, loss


def max_grade(s: list[float], alt: list[float], window: float = MAX_GRADE_WINDOW_M) -> float:
    """Plus forte pente (%) sur `window` m ; sur un parcours plus court, la pente moyenne."""
    best = -math.inf
    j = 0
    for i in range(len(s)):
        while j < len(s) - 1 and s[j] - s[i] < window:
            j += 1
        if s[j] - s[i] < window:
            break
        best = max(best, (alt[j] - alt[i]) / (s[j] - s[i]) * 100.0)
    if best == -math.inf:
        span = s[-1] - s[0]
        best = (alt[-1] - alt[0]) / span * 100.0 if span > 0 else 0.0
    return best


def climbs(s: list[float], alt: list[float]) -> list[dict[str, Any]]:
    """Montées retenues (au moins 500 m et 20 m de dénivelé), dans l'ordre du parcours."""
    found: list[tuple[int, int]] = []
    start = peak = 0
    for j in range(1, len(alt)):
        if alt[j] > alt[peak]:
            peak = j
        elif alt[peak] - alt[j] > CLIMB_DROP_M:
            found.append((start, peak))
            start = peak = j
        if alt[j] < alt[start]:
            if peak != start:
                found.append((start, peak))
            start = peak = j
    found.append((start, peak))
    out = []
    for a, b in found:
        length, gain = s[b] - s[a], alt[b] - alt[a]
        if length >= CLIMB_MIN_LENGTH_M and gain >= CLIMB_MIN_GAIN_M:
            avg = gain / length * 100.0
            out.append({"start_m": round(s[a], 1), "length_m": round(length, 1), "gain_m": round(gain, 1),
                        "avg_grade_pct": round(avg, 2), "category": category(length, avg)})
    return out


def category(length_m: float, avg_grade_pct: float) -> str | None:
    score = length_m * avg_grade_pct
    for threshold, name in CATEGORIES:
        if score >= threshold:
            return name
    return None


def steady_speed(power_w: float, grade_pct: float) -> float:
    """Vitesse d'équilibre (m/s) à puissance constante, par dichotomie."""
    theta = math.atan(grade_pct / 100.0)
    resist = MASS_KG * G * (CRR * math.cos(theta) + math.sin(theta))

    def surplus(v: float) -> float:
        return power_w * EFFICIENCY - (resist + 0.5 * RHO * CDA_M2 * v * v) * v

    if surplus(V_DESCENT_MAX) >= 0.0:
        return V_DESCENT_MAX
    lo, hi = 0.0, V_DESCENT_MAX
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if surplus(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return max(lo, 0.5)


def estimate_duration_s(route: dict[str, Any], power_w: float) -> float:
    """Durée (s) du parcours à `power_w` constante, tronçon par tronçon de 100 m."""
    if power_w <= 0:
        return 0.0
    s, alt = _positions(route), [float(a) for a in route["alt_m"]]
    total = 0.0
    i = 0
    while i < len(s) - 1:
        j = i + 1
        while j < len(s) - 1 and s[j] - s[i] < DURATION_CHUNK_M:
            j += 1
        dist = s[j] - s[i]
        if dist > 0:
            total += dist / steady_speed(power_w, (alt[j] - alt[i]) / dist * 100.0)
        i = j
    return total


def difficulty(gain_m: float, main_category: str | None) -> int:
    rank = {"HC": 5, "1": 4, "2": 3, "3": 2, "4": 2}.get(main_category or "", 1)
    by_gain = 5 if gain_m >= 2000 else 4 if gain_m >= 1200 else 3 if gain_m >= 600 else 2 if gain_m >= 200 else 1
    return max(rank, by_gain)


def compute_stats(route: dict[str, Any], power_w: float = 200.0) -> dict[str, Any]:
    """Fiche calculée (champ `stats` du manifeste)."""
    s, alt = _positions(route), [float(a) for a in route["alt_m"]]
    gain, loss = gain_loss(alt)
    found = climbs(s, alt)
    main = max(found, key=lambda c: c["gain_m"]) if found else None
    return {
        "version": STATS_VERSION,
        "distance_m": round(float(route["length_m"]), 1),
        "gain_m": round(gain, 1),
        "loss_m": round(loss, 1),
        "alt_min_m": round(min(alt), 1),
        "alt_max_m": round(max(alt), 1),
        "max_grade_pct": round(max_grade(s, alt), 1),
        "climbs": len(found),
        "main_climb": main,
        "duration_200w_s": round(estimate_duration_s(route, power_w)),
        "durations_s": {str(w): round(estimate_duration_s(route, w)) for w in DURATION_POWERS_W},
        "difficulty": difficulty(gain, main["category"] if main else None),
    }


def compare_garmin(route: dict[str, Any], max_grade_pct: float, gain_m: float, length_km: float | None = None,
                   window: float = MAX_GRADE_WINDOW_M) -> list[dict[str, Any]]:
    """Lignes {"mesure", "parcours", "garmin", "ecart", "tolerance", "ok"} face aux valeurs de Garmin Connect."""
    s, alt = _positions(route), [float(a) for a in route["alt_m"]]
    grade = max_grade(s, alt, window)
    gain = gain_loss(alt)[0]
    rows = [{"mesure": f"pente maximale sur {window:g} m (%)", "parcours": round(grade, 1), "garmin": max_grade_pct,
             "ecart": round(grade - max_grade_pct, 1), "tolerance": f"± {GARMIN_GRADE_TOL_PT:g} point",
             "ok": abs(grade - max_grade_pct) <= GARMIN_GRADE_TOL_PT},
            {"mesure": "dénivelé positif (m)", "parcours": round(gain), "garmin": gain_m, "ecart": round(gain - gain_m),
             "tolerance": f"± {GARMIN_GAIN_TOL * 100:g} %", "ok": abs(gain - gain_m) <= GARMIN_GAIN_TOL * gain_m}]
    if length_km is not None:
        km = float(route["length_m"]) / 1000.0
        rows.append({"mesure": "longueur (km)", "parcours": round(km, 2), "garmin": length_km,
                     "ecart": round(km - length_km, 2), "tolerance": f"± {GARMIN_LENGTH_TOL * 100:g} %",
                     "ok": abs(km - length_km) <= GARMIN_LENGTH_TOL * length_km})
    return rows


def stats_usable(stats: object) -> bool:
    """Vrai si la fiche rangée dans un manifeste est de la version courante (sinon : recalculer)."""
    return isinstance(stats, dict) and stats.get("version") == STATS_VERSION


def duration_at(stats: dict[str, Any] | None, power_w: float) -> int | None:
    """Durée estimée (s) à `power_w`, interpolée entre les puissances de `durations_s`."""
    table = (stats or {}).get("durations_s")
    if not isinstance(table, dict) or power_w <= 0:
        return None
    pts = sorted((float(w), float(t)) for w, t in table.items())
    if not pts:
        return None
    if power_w <= pts[0][0]:
        return round(pts[0][1])
    if power_w >= pts[-1][0]:
        return round(pts[-1][1])
    for (w0, t0), (w1, t1) in zip(pts, pts[1:]):
        if w0 <= power_w <= w1:
            return round(t0 + (t1 - t0) * (power_w - w0) / (w1 - w0))
    return None


# --- Fiche saisie -------------------------------------------------------------------------

LIBRARY_KEYS = {"name": 80, "description": 500, "region": 80, "credits": 200}
MAX_TAGS = 12
TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")
# Deux nombres décimaux à la suite (« 48.9, 7.1 ») ou une notation en degrés : refusés dans `region`.
COORD_RE = re.compile(r"-?\d{1,3}[.,]\d{2,}\s*[,; ]\s*-?\d{1,3}[.,]\d{2,}|\d+\s*°")


class LibraryError(ValueError):
    """Fiche `<trace>.toml` illisible ou invalide."""


def sidecar_path(track: Path, stem: str) -> Path:
    """Fiche saisie d'une trace : `<nom sans extension>.toml` dans le même dossier."""
    return Path(track).parent / f"{stem}.toml"


def check_library(data: object) -> dict[str, Any]:
    """Fiche saisie contrôlée et normalisée (étiquettes en minuscules, sans doublon, triées)."""
    if not isinstance(data, dict):
        raise LibraryError("la fiche doit être une table TOML")
    unknown = sorted(set(data) - set(LIBRARY_KEYS) - {"tags"})
    if unknown:
        raise LibraryError(f"clé(s) inconnue(s) : {', '.join(unknown)}")
    out: dict[str, Any] = {}
    for key, limit in LIBRARY_KEYS.items():
        if key not in data:
            continue
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            raise LibraryError(f"{key} : texte non vide attendu")
        if len(value) > limit:
            raise LibraryError(f"{key} : {limit} caractères au plus")
        out[key] = value.strip()
    if "region" in out and COORD_RE.search(out["region"]):
        raise LibraryError("region : texte libre attendu, jamais de coordonnées")
    if "tags" in data:
        tags = data["tags"]
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise LibraryError("tags : liste de textes attendue")
        norm = sorted({t.strip().lower() for t in tags})
        bad = [t for t in norm if not TAG_RE.match(t)]
        if bad:
            raise LibraryError(f"tags : étiquette invalide {bad[0]!r} (a-z, 0-9, tiret ; 30 caractères au plus)")
        if len(norm) > MAX_TAGS:
            raise LibraryError(f"tags : {MAX_TAGS} étiquettes au plus")
        out["tags"] = norm
    return out


def load_library(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise LibraryError(f"{Path(path).name} illisible : {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise LibraryError(f"{Path(path).name} : TOML invalide : {exc}") from exc
    try:
        return check_library(data)
    except LibraryError as exc:
        raise LibraryError(f"{Path(path).name} : {exc}") from exc


# --- Tri et filtres ---------------------------------------------------------------------------

SORT_KEYS = ("nom", "distance", "deniv", "pente", "duree", "difficulte")


def _sort_value(entry: Any, key: str, power_w: float) -> Any:
    st = getattr(entry, "stats", None) or {}
    if key == "nom":
        return entry.id
    if key == "distance":
        return entry.length_m
    if key == "deniv":
        return st.get("gain_m")
    if key == "pente":
        return st.get("max_grade_pct")
    if key == "duree":
        return duration_at(st, power_w)
    if key == "difficulte":
        return st.get("difficulty")
    raise ValueError(f"tri inconnu : {key} (choix : {', '.join(SORT_KEYS)})")


def query(entries: list[Any], sort: str | None = None, filters: dict[str, Any] | None = None,
          reverse: bool = False, power_w: float = 200.0) -> list[Any]:
    """Parcours filtrés puis triés ; ceux sans la valeur de tri viennent en dernier.

    Filtres : `tag` (étiquette), `region` (texte contenu, sans casse), `status`, `min_km`,
    `max_km`, `min_gain_m`, `max_gain_m`, `max_grade_pct`, `max_duration_s` (à `power_w`),
    `min_difficulty`, `max_difficulty`. Un parcours sans la donnée filtrée est écarté.
    """
    f = {k: v for k, v in (filters or {}).items() if v is not None}

    def keep(e: Any) -> bool:
        st = getattr(e, "stats", None) or {}
        lib = getattr(e, "library", None) or {}
        if "tag" in f and str(f["tag"]).lower() not in lib.get("tags", []):
            return False
        if "region" in f and str(f["region"]).casefold() not in str(lib.get("region", "")).casefold():
            return False
        if "status" in f and e.status != f["status"]:
            return False
        km = e.length_m / 1000.0 if e.length_m is not None else None
        bounds = (("min_km", km, 1), ("max_km", km, -1), ("min_gain_m", st.get("gain_m"), 1),
                  ("max_gain_m", st.get("gain_m"), -1), ("max_grade_pct", st.get("max_grade_pct"), -1),
                  ("max_duration_s", duration_at(st, power_w), -1),
                  ("min_difficulty", st.get("difficulty"), 1), ("max_difficulty", st.get("difficulty"), -1))
        for name, value, sign in bounds:
            if name in f and (value is None or (value - float(f[name])) * sign < 0):
                return False
        return True

    kept = [e for e in entries if keep(e)]
    if not sort:
        return kept
    with_value = [e for e in kept if _sort_value(e, sort, power_w) is not None]
    without = [e for e in kept if _sort_value(e, sort, power_w) is None]
    with_value.sort(key=lambda e: (_sort_value(e, sort, power_w), e.id), reverse=reverse)
    return with_value + without
