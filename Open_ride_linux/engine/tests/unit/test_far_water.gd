extends SceneTree

## Tests unitaires sans écran de l'eau lointaine du monde ouvert (lot EA2, `far_water.gd`) : bandes par
## ligne, niveau posé sous la surface proche et au-dessus du sol abaissé, relief exagéré, fichier lu.
## Lancement : godot --headless --path engine --script res://tests/unit/test_far_water.gd

const FarWater := preload("res://scripts/far_water.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## 101 × 101 NaN, avec un bloc d'échantillons [i0, i1) × [j0, j1) au niveau `level`.
func _levels(i0: int, i1: int, j0: int, j1: int, level: float) -> PackedFloat32Array:
	var n := TerrainTiles.SAMPLES
	var out := PackedFloat32Array()
	out.resize(n * n)
	out.fill(NAN)
	for j in range(j0, j1):
		for i in range(i0, i1):
			out[j * n + i] = level
	return out


func _area(arr: Array) -> float:
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
	var a := 0.0
	for t in range(0, idx.size(), 3):
		a += 0.5 * (v[idx[t + 1]] - v[idx[t]]).cross(v[idx[t + 2]] - v[idx[t]]).length()
	return a


func _test_block() -> void:
	var arr := FarWater.build_arrays(_levels(20, 30, 40, 50, 100.0), 2, -1)
	_check(not arr.is_empty(), "un lac donne un maillage")
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	# cellules dont un coin est dans l'eau : 11 × 11, une bande par ligne
	_check(v.size() == 11 * 4, "une bande par ligne (%d sommets)" % v.size())
	_check(absf(_area(arr) - 121.0 * 2500.0) < 1.0, "aire des cellules mouillées (%.0f m²)" % _area(arr))
	var flat := true
	for p in v:
		flat = flat and absf(p.y - (100.0 - FarWater.FAR_WATER_DROP_M)) < 1e-4
	_check(flat, "plan au niveau du lac moins %.1f m" % FarWater.FAR_WATER_DROP_M)
	_check(FarWater.FAR_WATER_DROP_M > 0.05 and FarWater.FAR_WATER_DROP_M < 1.0,
		"entre la surface proche (+5 cm) et le sol abaissé (−1 m)")
	var uv: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV]
	_check(uv[0] == Vector2(2 * 5000.0 + 19 * 50.0, -5000.0 + 39 * 50.0), "UV en coordonnées de la séance")
	var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
	var up := true
	for t in range(0, idx.size(), 3):
		var nrm := (v[idx[t + 2]] - v[idx[t]]).cross(v[idx[t + 1]] - v[idx[t]])
		up = up and nrm.y > 0.0
	_check(up, "faces tournées vers le haut (sens des tuiles de terrain)")


func _test_two_levels_and_relief() -> void:
	var lv := _levels(10, 20, 10, 12, 50.0)
	var n := TerrainTiles.SAMPLES
	for i in range(22, 30):
		lv[10 * n + i] = 80.0
	var arr := FarWater.build_arrays(lv, 0, 0, func(y: float) -> float: return 2.0 * y)
	var ys := {}
	for p in (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array):
		ys[snappedf(p.y, 0.01)] = true
	_check(ys.has(snappedf(2.0 * (50.0 - FarWater.FAR_WATER_DROP_M), 0.01))
		and ys.has(snappedf(2.0 * (80.0 - FarWater.FAR_WATER_DROP_M), 0.01)),
		"deux lacs, deux niveaux, relief exagéré appliqué")


func _test_empty_and_file() -> void:
	_check(FarWater.build_arrays(_levels(0, 0, 0, 0, 1.0), 0, 0).is_empty(), "sans eau : rien")
	_check(FarWater.build_arrays(PackedFloat32Array([1.0]), 0, 0).is_empty(), "taille fausse : rien")
	var dir := OS.get_user_data_dir().path_join("test_far_water.world")
	DirAccess.make_dir_recursive_absolute(dir.path_join("water/far"))
	_check(FarWater.load_levels(dir, 7, 7).is_empty(), "fichier absent : rien")
	var lv := _levels(5, 6, 5, 6, 321.5)
	var f := FileAccess.open(FarWater.tile_path(dir, 1, -2), FileAccess.WRITE)
	f.store_buffer(lv.to_byte_array())
	f.close()
	var got := FarWater.load_levels(dir, 1, -2)
	_check(got.size() == lv.size() and got[5 * TerrainTiles.SAMPLES + 5] == 321.5 and is_nan(got[0]),
		"water/far/tile_1_-2.f32 relu (NaN hors de l'eau)")
	DirAccess.remove_absolute(FarWater.tile_path(dir, 1, -2))


func _init() -> void:
	_test_block()
	_test_two_levels_and_relief()
	_test_empty_and_file()
	print("test_far_water : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
