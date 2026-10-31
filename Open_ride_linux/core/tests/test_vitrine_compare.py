"""Avant/après des vitrines (lot Z3) : captures en SSIM, comptes du CSV avec tolérance, planche et rapport."""

import importlib.util
import sys
from pathlib import Path

ENGINE_TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
sys.path.insert(0, str(ENGINE_TESTS))
spec = importlib.util.spec_from_file_location("vitrine_compare", ENGINE_TESTS / "vitrine_compare.py")
vcmp = importlib.util.module_from_spec(spec)
sys.modules["vitrine_compare"] = vcmp
spec.loader.exec_module(vcmp)
idf = vcmp.image_diff

HEADER = "biome;vue;préréglage;qualite_appliquee;arbres;triangles;appels_dessin;preparation_arbres_ms;sol_luminance"


def scene(obj_x=40, w=160, h=96) -> "idf.Image":
    px = bytearray()
    for y in range(h):
        for x in range(w):
            if obj_x <= x < obj_x + 24 and 50 <= y < 74:
                px += bytes((30, 30, 40))
            elif y < h // 2:
                px += bytes((120 + 60 * y // h, 170 + 30 * y // h, 235))
            else:
                g = 90 + (x * 7 + y * 13) % 40
                px += bytes((g // 2, g, g // 3))
    return idf.Image(w, h, bytes(px))


def vitrine(folder: Path, rows: list[str], images: dict[str, "idf.Image"]) -> Path:
    folder.mkdir(parents=True)
    (folder / "vitrine_biomes.csv").write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    for name, img in images.items():
        idf.write_png(folder / name, img)
    return folder


ROWS = ["savanna;route;medium;medium;120;400000;150;3.2;0.41", "savanna;haut;medium;medium;80;300000;140;2.9;0.52"]


def test_identical_vitrines_pass_and_write_sheet(tmp_path):
    before = vitrine(tmp_path / "avant", ROWS, {"savanna_route_medium.png": scene()})
    after = vitrine(tmp_path / "apres", ROWS, {"savanna_route_medium.png": scene()})
    assert vcmp.main([str(before), str(after), "--out", str(tmp_path / "ecarts")]) == 0
    assert (tmp_path / "ecarts" / "planche_avant_apres.png").is_file()
    assert (tmp_path / "ecarts" / "savanna_route_medium_ecarts.png").is_file()
    assert "Vitrines avant/après" in (tmp_path / "ecarts" / "rapport.html").read_text(encoding="utf-8")
    sheet = idf.read_png(tmp_path / "ecarts" / "planche_avant_apres.png")
    assert sheet.width == 3 * vcmp.THUMB_WIDTH + 4 * vcmp.GAP


def test_moved_object_fails_on_ssim(tmp_path):
    before = vitrine(tmp_path / "avant", ROWS, {"a.png": scene(40)})
    after = vitrine(tmp_path / "apres", ROWS, {"a.png": scene(100)})
    assert vcmp.main([str(before), str(after), "--out", str(tmp_path / "e")]) == 1
    assert vcmp.main([str(before), str(after), "--out", str(tmp_path / "e"), "--seuil-ssim", "0.5"]) == 0


def test_counts_within_and_beyond_tolerance(tmp_path):
    before = vitrine(tmp_path / "avant", ROWS, {})
    within = vitrine(tmp_path / "pres", ["savanna;route;medium;medium;125;420000;151;9.9;0.40", ROWS[1]], {})
    beyond = vitrine(tmp_path / "loin", ["savanna;route;medium;medium;120;520000;150;3.2;0.41", ROWS[1]], {})
    assert vcmp.main([str(before), str(within), "--out", str(tmp_path / "e1")]) == 0   # +5 %, temps en information
    assert vcmp.main([str(before), str(beyond), "--out", str(tmp_path / "e2")]) == 1   # +30 % de triangles
    assert vcmp.main([str(before), str(beyond), "--out", str(tmp_path / "e3"), "--tolerance", "40"]) == 0


def test_small_counts_and_applied_quality(tmp_path):
    before = vitrine(tmp_path / "avant", ["polar;faune;low;low;0;1000;3;0.1;0.9"], {})
    small = vitrine(tmp_path / "petit", ["polar;faune;low;low;2;1000;5;0.1;0.9"], {})   # +2 arbres sur 0 : admis
    wrong = vitrine(tmp_path / "faux", ["polar;faune;low;medium;0;1000;3;0.1;0.9"], {})
    assert vcmp.main([str(before), str(small), "--out", str(tmp_path / "e1")]) == 0
    assert vcmp.main([str(before), str(wrong), "--out", str(tmp_path / "e2")]) == 1


def test_missing_capture_or_row_fails_new_ones_are_info(tmp_path):
    before = vitrine(tmp_path / "avant", ROWS, {"a.png": scene(), "b.png": scene()})
    gone = vitrine(tmp_path / "moins", ROWS[:1], {"a.png": scene()})
    more = vitrine(tmp_path / "plus", [*ROWS, "jungle;route;medium;medium;300;1;1;1;1"],
                   {"a.png": scene(), "b.png": scene(), "c.png": scene()})
    assert vcmp.main([str(before), str(gone), "--out", str(tmp_path / "e1")]) == 1
    assert vcmp.main([str(before), str(more), "--out", str(tmp_path / "e2")]) == 0


def test_key_columns_and_nothing_to_compare(tmp_path):
    header = HEADER.split(";")
    rows = [dict(zip(header, r.split(";"))) for r in ROWS]
    assert vcmp.key_columns(header, rows) == ["biome", "vue", "préréglage"]
    sols = ["paire", "preset", "qualite_appliquee", "triangles"]
    assert vcmp.key_columns(sols, [dict(zip(sols, ["a__b", "low", "low", "10"]))]) == ["paire", "preset"]
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    assert vcmp.main([str(tmp_path / "x"), str(tmp_path / "y")]) == 2
