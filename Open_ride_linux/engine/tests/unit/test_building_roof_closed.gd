extends SceneTree

## Toits fermés (fil « Fermer les toits des maisons », retour d'essai du 21/11 : « maison avec toit pas fermé »).
## Cause : le haut d'un mur n'était coupé au faîtage que si les deux pans y étaient les plus bas à 1e-6 m près ;
## les plans du toit sont rangés en flottants 32 bits, la coupe se perdait et le pignon restait plat sous le toit.
## Ce test maille un à un des bâtiments de toutes les formes (rectangles tournés, quadrilatères quelconques, L, T,
## U, cours intérieures, contours étoilés tirés au hasard), loin de l'origine, dans tous les styles et toutes les
## familles, et exige un toit fermé (tests/roof_seal.gd) : empreinte couverte, aucun jour entre mur et toit.
## Lancement : godot --headless --path engine --script res://tests/unit/test_building_roof_closed.gd

const BuildingMesh := preload("res://scripts/building_mesh.gd")
const BuildingStyles := preload("res://scripts/building_styles.gd")
const RoofSeal := preload("res://tests/roof_seal.gd")

const FAMILIES := ["house", "apartments", "farm", "church", "retail", "industrial"]

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


static func _ring(points: Array, offset: Vector2 = Vector2.ZERO, angle: float = 0.0) -> PackedVector2Array:
	var r := PackedVector2Array()
	for p in points:
		r.append(Vector2(p[0], p[1]).rotated(angle) + offset)
	return r


## Formes fixes : la régression du 21/11 (quadrilatère non rectangle, pignon sur un petit côté oblique) en tête.
func _shapes() -> Array:
	return [
		["quadrilatere_oblique", [[0, 0], [28, 3], [26, 13], [-2, 10]], []],
		["rectangle", [[0, 0], [30, 0], [30, 10], [0, 10]], []],
		["barre_longue", [[0, 0], [60, 0], [60, 12], [0, 12]], []],
		["L", [[0, 0], [20, 0], [20, 8], [8, 8], [8, 20], [0, 20]], []],
		["L_large", [[0, 0], [20, 0], [20, 14], [16, 14], [16, 18], [0, 18]], []],
		["T", [[0, 0], [24, 0], [24, 8], [16, 8], [16, 18], [8, 18], [8, 8], [0, 8]], []],
		["U", [[0, 0], [20, 0], [20, 14], [15, 14], [15, 5], [5, 5], [5, 14], [0, 14]], []],
		["trapeze", [[0, 0], [25, 0], [22, 9], [3, 11]], []],
		["encoche", [[0, 0], [30, 0], [30, 10], [16, 10], [15, 9.5], [14, 10], [0, 10]], []],
		["presque_alignes", [[0, 0], [10, 0], [20, 0.02], [30, 0], [30, 10], [0, 10]], []],
		["cour", [[0, 0], [30, 0], [30, 24], [0, 24]], [[[8, 6], [8, 18], [22, 18], [22, 6]]]],
	]


## Contours tirés au hasard (graine fixe) : quadrilatères déformés et polygones étoilés de 5 à 9 sommets.
func _random_shapes(n: int) -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = 2111
	var out := []
	for k in range(n):
		var pts := []
		if k % 2 == 0:
			var w := rng.randf_range(6.0, 30.0)
			var d := rng.randf_range(5.0, 14.0)
			for c in [[0.0, 0.0], [w, 0.0], [w, d], [0.0, d]]:
				pts.append([c[0] + rng.randf_range(-1.5, 1.5), c[1] + rng.randf_range(-1.5, 1.5)])
		else:
			var m := rng.randi_range(5, 9)
			var r0 := rng.randf_range(5.0, 12.0)
			for j in range(m):
				var a := TAU * (j + rng.randf_range(-0.2, 0.2)) / m
				var r := r0 * rng.randf_range(0.7, 1.0)
				pts.append([cos(a) * r * 1.6, sin(a) * r])
		out.append(["hasard_%d" % k, pts, []])
	return out


func _seal(id: String, style: String, family: String, roof: String, outer: PackedVector2Array,
		holes: Array) -> PackedStringArray:
	var outer_arr := []
	for p in outer:
		outer_arr.append([p.x, p.y])
	var holes_arr := []
	for h in holes:
		var ha := []
		for p in h:
			ha.append([p.x, p.y])
		holes_arr.append(ha)
	var b := {"id": id, "outer": outer_arr, "holes": holes_arr, "base_y": 230.0, "height_m": 9.0, "roof": roof,
		"hint": {"building": family}, "style": style}
	var out := BuildingMesh.build([b], {}, 0.0, style)
	if int(out["built"]) != 1:
		return PackedStringArray(["non construit : %s" % ", ".join(out["errors"])])
	return RoofSeal.defects(out)


func _run_shapes(label: String, shapes: Array, offsets: Array, roofs: Array) -> void:
	var tested := 0
	var open := 0
	var first := ""
	for sh in shapes:
		for o in range(offsets.size()):
			var outer := _ring(sh[1], offsets[o], 0.37 * o)
			var holes := []
			for h in sh[2]:
				holes.append(_ring(h, offsets[o], 0.37 * o))
			for st in BuildingStyles.STYLES.keys():
				for fam in FAMILIES:
					for roof in roofs:
						var id := "%s_%s_%s_%s_%d" % [sh[0], st, fam, roof, o]
						var errs := _seal(id, st, fam, roof, outer, holes)
						tested += 1
						if not errs.is_empty():
							open += 1
							if first.is_empty():
								first = "%s : %s" % [id, "; ".join(errs)]
	_check(open == 0, "%s : %d bâtiments, %d toits ouverts%s" % [label, tested, open,
		"" if first.is_empty() else " (premier : %s)" % first])


## Le contrôle lui-même repère un pignon ouvert (sinon un test vert ne prouverait rien).
func _test_detects_open_gable() -> void:
	var b := {"id": "ouvert", "outer": [[0, 0], [12, 0], [12, 8], [0, 8]], "holes": [], "base_y": 0.0,
		"height_m": 6.0, "roof": "gabled", "hint": {"building": "house"}, "style": "tuile_plate"}
	var out := BuildingMesh.build([b], {}, 0.0, "tuile_plate")
	_check(RoofSeal.defects(out).is_empty(), "maison à deux pans de référence fermée")
	# Pignon aplati à la main : les sommets des murs au-dessus de l'égout redescendent à l'égout
	var v: PackedVector3Array = out["vertices"]
	var uv2: PackedVector2Array = out["uvs2"]
	for i in range(v.size()):
		if (int(uv2[i].y) & 1024) == 0 and v[i].y > 6.01:
			v[i].y = 6.0
	out["vertices"] = v
	_check(not RoofSeal.defects(out).is_empty(), "pignon aplati repéré comme toit ouvert")
	# Toit retiré
	var walls_only := out.duplicate()
	var idx: PackedInt32Array = out["indices"]
	var keep := PackedInt32Array()
	for t in range(0, idx.size(), 3):
		if (int(uv2[idx[t]].y) & 1024) == 0:
			keep.append_array([idx[t], idx[t + 1], idx[t + 2]])
	walls_only["indices"] = keep
	_check(not RoofSeal.defects(walls_only).is_empty(), "bâtiment sans toit repéré")


func _init() -> void:
	_test_detects_open_gable()
	var far := [Vector2.ZERO, Vector2(3817.5, -2264.25), Vector2(-4630.0, 5120.0)]
	_run_shapes("formes types, loin de l'origine", _shapes(), far, ["flat", "gabled"])
	_run_shapes("contours au hasard", _random_shapes(24), [Vector2(1520.0, -3307.0)], ["flat"])
	print("test_building_roof_closed : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
