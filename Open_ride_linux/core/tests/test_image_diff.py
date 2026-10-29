"""Écart perceptuel des tests graphiques (lot X20) : SSIM par blocs, masques, vignettes, références du dépôt."""

import importlib.util
import random
import sys
from pathlib import Path

import pytest

ENGINE_TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
spec = importlib.util.spec_from_file_location("image_diff", ENGINE_TESTS / "image_diff.py")
idf = importlib.util.module_from_spec(spec)
sys.modules["image_diff"] = idf
spec.loader.exec_module(idf)

GOLDEN = ENGINE_TESTS / "golden" / "xvfb" / "low"


def scene(w=160, h=96, obj_x=40, seed=1) -> "idf.Image":
    """Ciel dégradé, sol texturé et un objet sombre de 24 × 24 pixels à `obj_x`."""
    px = bytearray()
    for y in range(h):
        for x in range(w):
            if obj_x <= x < obj_x + 24 and 50 <= y < 74:
                px += bytes((30, 30, 40))
            elif y < h // 2:
                px += bytes((120 + 60 * y // h, 170 + 30 * y // h, 235))
            else:
                g = 90 + (x * 7 + y * 13 + seed) % 40          # texture du sol, indépendante de l'objet
                px += bytes((g // 2, g, g // 3))
    return idf.Image(w, h, bytes(px))


def noisy(img, amp=2, seed=7):
    rng = random.Random(seed)
    return idf.Image(img.width, img.height, bytes(max(0, min(255, v + rng.randint(-amp, amp))) for v in img.rgb))


def test_identical_noise_and_moved_object():
    a = scene()
    assert idf.ssim(a, a).score == pytest.approx(1.0)
    assert idf.ssim(a, noisy(a)).score > 0.98
    moved = idf.ssim(a, scene(obj_x=90))
    assert moved.score < 0.95 and moved.worst < 0.5


def test_mask_ignores_a_zone():
    a, b = scene(), scene(obj_x=90)
    masks = [(40, 48, 64, 80), (88, 48, 120, 80)]
    res = idf.ssim(a, b, masks)
    assert res.score == pytest.approx(1.0) and res.masked > 0


def test_resize_vignette_and_format():
    a = scene(w=1280, h=720, obj_x=600)
    v = idf.vignette(a)
    assert (v.width, v.height) == (640, 360)
    assert idf.compare(v, a).score > 0.99            # capture pleine taille face à sa vignette
    with pytest.raises(ValueError, match="format différent"):
        idf.compare(v, scene(w=1024, h=600))


def test_png_round_trip_and_map(tmp_path):
    a, b = scene(), scene(obj_x=90)
    idf.write_png(tmp_path / "a.png", a)
    assert idf.read_png(tmp_path / "a.png") == a
    res = idf.ssim(a, b)
    m = idf.ssim_map(a, res, [(0, 0, 8, 8)])
    x, y = 96, 56                                     # bloc de l'objet déplacé : rouge vif
    r, g, bl = m.pixel(x, y)
    assert r > g + 100 and r > bl + 100
    assert m.pixel(2, 2)[2] > m.pixel(2, 2)[0]       # masque en bleu


def test_command_line_codes(tmp_path, capsys):
    a, b = scene(), scene(obj_x=90)
    idf.write_png(tmp_path / "a.png", a)
    idf.write_png(tmp_path / "b.png", b)
    assert idf.main([str(tmp_path / "a.png"), str(tmp_path / "a.png")]) == 0
    assert idf.main([str(tmp_path / "a.png"), str(tmp_path / "b.png"), "--carte", str(tmp_path / "c.png")]) == 1
    assert (tmp_path / "c.png").is_file() and "[ÉCHEC] SSIM" in capsys.readouterr().out
    assert idf.main([str(tmp_path / "a.png"), str(tmp_path / "b.png"), "--masque", "32,40,112,80"]) == 0
    (tmp_path / "x.png").write_bytes(b"pas un png")
    assert idf.main([str(tmp_path / "a.png"), str(tmp_path / "x.png")]) == 2


def test_repository_references_detect_a_changed_sky(tmp_path):
    """Les vignettes Xvfb `low` du dépôt (scènes figées) : une modification volontaire du ciel fait échouer
    la comparaison au seuil de la CI et donne la carte des écarts."""
    refs = sorted(GOLDEN.glob("*.png"))
    assert {p.stem for p in refs} >= {"vue_fixe", "pause", "menu_accueil", "bilan"}
    ref = idf.read_png(GOLDEN / "vue_fixe.png")
    assert (ref.width, ref.height) == (640, 360)
    px = bytearray(ref.rgb)
    for y in range(60, 170):                          # ciel au-dessus de l'horizon, gris uni
        for x in range(ref.width):
            i = (y * ref.width + x) * 3
            px[i:i + 3] = bytes((150, 150, 150))
    res = idf.compare(ref, idf.Image(ref.width, ref.height, bytes(px)))
    assert res.score < 0.97
    idf.write_png(tmp_path / "carte.png", idf.ssim_map(ref, res))
    assert idf.read_png(tmp_path / "carte.png").width == 640
