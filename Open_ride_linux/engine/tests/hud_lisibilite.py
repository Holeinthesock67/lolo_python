"""Lisibilité du HUD à 2 m et débordements des panneaux (lot X22), sur une capture de `visual_check.py`.

`info` est la ligne `screenshot {…}` de l'engine en `--test-mode` : rectangles en pixels de l'image
(`widgets`), visibilité et textes des éléments du HUD. L'image est tout objet qui a `width`, `height`
et `pixel(x, y)` → (r, g, b) (l'`Image` de visual_check.py).

- **Hauteur des chiffres** principaux (puissance, vitesse, cadence, FC, pente) mesurée dans la capture,
  ramenée à un écran de 1080 lignes : au moins 28 px, environ 7 mm sur un écran de 24 pouces, lisible à 2 m.
- **Contraste** texte/fond mesuré dans la capture, au sens des WCAG 2 : au moins 4,5:1 pour les valeurs,
  3:1 pour les étiquettes (libellés des métriques, encart des bots, blocs segment et bonus, vent).
- **Débordements** : panneaux du HUD dans l'écran et sans chevauchement entre eux (colonnes, vent, abri,
  blocs segment et bonus, encart des bots, profil d'altitude) ; libellés et valeurs des colonnes gauche et
  droite dans leur colonne (cible ERG longue « 152 W (98 %) »).

Chaque fonction `*_checks` rend une liste de (nom, réussi, détail) ; `visual_check.py --lisibilite` les
range dans son rapport. Bibliothèque standard seulement.
"""

from __future__ import annotations

from typing import Any, Iterable

REF_HEIGHT = 1080                 # hauteurs ramenées à un écran de 1080 lignes
DIGIT_MIN_PX = 28                 # chiffres principaux : environ 7 mm sur un 24 pouces, lisibles à 2 m
VALUE_CONTRAST = 4.5              # WCAG 2, texte courant
LABEL_CONTRAST = 3.0              # WCAG 2, grand texte et éléments d'interface
VALUES = ("power", "speed", "cadence", "hr", "grade")
LABELS = ("power_caption", "speed_caption", "cadence_caption", "hr_caption", "grade_caption",
          "bots_line1", "bots_line2", "bots_jerseys",
          "segment_title", "segment_main", "bonus_held", "wind_speed", "wind_level")
# Panneaux qui ne doivent ni sortir de l'écran ni se chevaucher (le contenu d'un panneau le recouvre, d'où
# des panneaux seulement).
PANELS = ("panel_left", "panel_right", "panel", "wind", "draft", "segment_panel", "bonus_panel", "bots_panel",
          "profile")
# Libellés et valeurs de chaque colonne : ils doivent rester dans le rectangle de la colonne.
COLUMNS = {"panel_left": ("power", "power_caption", "cadence", "cadence_caption", "hr", "hr_caption",
                          "target", "target_caption"),
           "panel_right": ("speed", "speed_caption", "grade", "grade_caption", "gear", "distance", "time")}
TEXT_SHARE = 0.5                  # pixel de texte : au moins la moitié de l'écart entre le fond et le texte


def srgb_luminance(p: tuple[int, int, int]) -> float:
    """Luminance relative des WCAG 2 (composantes sRGB linéarisées)."""
    def lin(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(p[0]) + 0.7152 * lin(p[1]) + 0.0722 * lin(p[2])


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = srgb_luminance(a), srgb_luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _box(rect: list[float], img) -> tuple[int, int, int, int]:
    x, y, w, h = rect
    return max(0, int(x)), max(0, int(y)), min(img.width, int(x + w + 0.999)), min(img.height, int(y + h + 0.999))


def measure_text(img, rect: list[float]) -> dict[str, Any] | None:
    """Texte d'un rectangle : fond (luminance médiane), couleur du texte (le 2 % le plus éloigné du fond),
    contraste WCAG entre les deux, hauteur des lignes de pixels qui contiennent du texte. None sans texte."""
    x0, y0, x1, y1 = _box(rect, img)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    rows: list[list[tuple[float, tuple[int, int, int]]]] = []
    for y in range(y0, y1):
        rows.append([(srgb_luminance(p), p) for p in (img.pixel(x, y) for x in range(x0, x1))])
    flat = sorted(v for row in rows for v, _ in row)
    bg = flat[len(flat) // 2]
    lighter = flat[int(len(flat) * 0.98)] - bg >= bg - flat[int(len(flat) * 0.02)]
    fg = flat[int(len(flat) * 0.98)] if lighter else flat[int(len(flat) * 0.02)]
    if abs(fg - bg) < 1e-3:
        return None
    cut = bg + (fg - bg) * TEXT_SHARE
    lines = [i for i, row in enumerate(rows) if any((v >= cut) if lighter else (v <= cut) for v, _ in row)]
    if not lines:
        return None
    return {"bg": bg, "fg": fg, "contrast": (max(bg, fg) + 0.05) / (min(bg, fg) + 0.05),
            "height_px": lines[-1] - lines[0] + 1, "top": y0 + lines[0]}


def readability_checks(img, info: dict[str, Any], values: Iterable[str] = VALUES,
                       labels: Iterable[str] = LABELS) -> list[tuple[str, bool, str]]:
    """Hauteur ramenée à 1080 lignes et contraste des valeurs, contraste des étiquettes visibles."""
    out: list[tuple[str, bool, str]] = []
    w = info["widgets"]
    scale = REF_HEIGHT / img.height
    for key in values:
        if key not in w or not w[key]["visible"] or not any(c.isdigit() for c in w[key]["text"]):
            continue   # « -- » sans mesure : pas de chiffre à mesurer
        m = measure_text(img, w[key]["rect"])
        if m is None:
            out.append((f"lisibilité {key}", False, "aucun texte trouvé dans le rectangle"))
            continue
        h = m["height_px"] * scale
        out.append((f"hauteur des chiffres {key}", h >= DIGIT_MIN_PX,
                    f"{h:.0f} px pour 1080 lignes (au moins {DIGIT_MIN_PX})"))
        out.append((f"contraste {key}", m["contrast"] >= VALUE_CONTRAST,
                    f"{m['contrast']:.1f}:1 (au moins {VALUE_CONTRAST:g}:1)"))
    for key in labels:
        if key not in w or not w[key]["visible"] or not w[key]["text"].strip():
            continue
        m = measure_text(img, w[key]["rect"])
        ratio = m["contrast"] if m else 1.0
        out.append((f"contraste {key}", ratio >= LABEL_CONTRAST, f"{ratio:.1f}:1 (au moins {LABEL_CONTRAST:g}:1)"))
    return out


def overlap(a: list[float], b: list[float]) -> float:
    """Aire commune de deux rectangles [x, y, w, h], en pixels."""
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def panel_checks(info: dict[str, Any], width: int, height: int,
                 panels: Iterable[str] = PANELS) -> list[tuple[str, bool, str]]:
    """Panneaux visibles dans l'écran et sans chevauchement deux à deux."""
    w = info["widgets"]
    vis = [k for k in panels if k in w and w[k]["visible"]]
    outside = [k for k in vis if w[k]["rect"][0] < -0.5 or w[k]["rect"][1] < -0.5
               or w[k]["rect"][0] + w[k]["rect"][2] > width + 0.5 or w[k]["rect"][1] + w[k]["rect"][3] > height + 0.5]
    pairs = [f"{a}/{b}" for i, a in enumerate(vis) for b in vis[i + 1:] if overlap(w[a]["rect"], w[b]["rect"]) > 1.0]
    return [("panneaux dans l'écran", not outside, "hors écran : " + ", ".join(outside) if outside else f"{len(vis)} panneaux"),
            ("panneaux sans chevauchement", not pairs, ", ".join(pairs))]


def column_checks(info: dict[str, Any], columns: dict[str, Iterable[str]] = COLUMNS) -> list[tuple[str, bool, str]]:
    """Libellés et valeurs visibles des colonnes gauche et droite contenus dans leur colonne."""
    w = info["widgets"]
    out: list[tuple[str, bool, str]] = []
    for panel, keys in columns.items():
        if panel not in w or not w[panel]["visible"]:
            continue
        px, py, pw, ph = w[panel]["rect"]
        over = []
        for k in keys:
            if k not in w or not w[k]["visible"]:
                continue
            x, y, kw, kh = w[k]["rect"]
            if x < px - 0.5 or y < py - 0.5 or x + kw > px + pw + 0.5 or y + kh > py + ph + 0.5:
                over.append(f"{k} « {w[k]['text']} »")
        out.append((f"textes dans {panel}", not over, "débordent : " + ", ".join(over) if over else ""))
    return out
