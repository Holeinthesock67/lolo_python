extends SceneTree

## Raccord du terrain proche au lointain (terrain_tiles.gd, blend_to_far et sink_under_near). Défaut vu en
## séance le 28 octobre (« on voit des tuiles non jointives dans le décor ») : marche d'environ 2 m là où le
## terrain proche s'arrête, et maillage lointain qui perçait le proche au creux des collines.

const TerrainTiles := preload("res://scripts/terrain_tiles.gd")

const S := TerrainTiles.SAMPLES
const N := TerrainTiles.CELLS

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_terrain_raccord : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Relief fin (proche) et relief lissé (lointain), qui s'écartent de plusieurs mètres au creux des collines.
static func _fine(x: float, z: float) -> float:
	return 400.0 + 30.0 * sin(x / 180.0) * cos(z / 210.0) + 6.0 * sin(x / 23.0 + z / 31.0)


static func _coarse(x: float, z: float) -> float:
	return 400.0 + 30.0 * sin(x / 180.0) * cos(z / 210.0)


static func _grid(level: String, ix: int, iz: int, f: Callable) -> PackedFloat32Array:
	var cell: float = TerrainTiles.LEVELS[level]["cell"]
	var size: float = TerrainTiles.LEVELS[level]["size"]
	var out := PackedFloat32Array()
	out.resize(S * S)
	for j in range(S):
		for i in range(S):
			out[j * S + i] = f.call(ix * size + i * cell, iz * size + j * cell)
	return out


func _run() -> void:
	# Deux tuiles proches côte à côte (0, 0) et (1, 0) dans la tuile lointaine (0, 0)
	var near_index := {Vector2i(0, 0): true, Vector2i(1, 0): true}
	var far := _grid("far", 0, 0, _coarse)
	var raw := {}
	for t in near_index:
		raw[t] = _grid("near", t.x, t.y, _fine)
	for k in [1.0, 2.5]:
		var drop: float = TerrainTiles.FAR_DROP_M / k
		var b0 := TerrainTiles.blend_to_far(raw[Vector2i(0, 0)], 0, 0, near_index, far, Vector2i(0, 0), k)
		var b1 := TerrainTiles.blend_to_far(raw[Vector2i(1, 0)], 1, 0, near_index, far, Vector2i(0, 0), k)
		# Bords libres (ouest, nord, sud de la tuile 0) : hauteur du lointain affiché, au millimètre
		var worst := 0.0
		for m in range(S):
			for p in [[0, m], [m, 0], [m, N]]:
				var x: float = p[0] * 10.0
				var z: float = p[1] * 10.0
				var target := TerrainTiles.mesh_height_at(far, "far", 0, 0, x, z) - drop
				worst = maxf(worst, absf(b0[p[1] * S + p[0]] - target))
		_check(worst < 0.001, "k = %.1f : bord libre posé sur le lointain affiché (écart %.4f m)" % [k, worst])
		# Bord commun des deux tuiles proches : mêmes hauteurs des deux côtés
		var seam := 0.0
		for j in range(S):
			seam = maxf(seam, absf(b0[j * S + N] - b1[j * S]))
		_check(seam < 0.0001, "k = %.1f : bord commun des tuiles proches identique après raccord (%.5f m)" % [k, seam])
		# Au-delà de EDGE_BLEND_M du bord libre, relief proche inchangé
		var i_in := int(TerrainTiles.EDGE_BLEND_M / 10.0) + 1
		var j_mid := 50
		_check(absf(b0[j_mid * S + i_in] - float(raw[Vector2i(0, 0)][j_mid * S + i_in])) < 1e-4, "k = %.1f : relief inchangé à plus de %.0f m du bord" % [k, TerrainTiles.EDGE_BLEND_M])

		# Lointain sous le proche : jamais au-dessus (affiché, marge comprise)
		var sunk := TerrainTiles.sink_under_near(far, 0, 0, near_index, func(nx: int, nz: int) -> PackedFloat32Array:
			return raw.get(Vector2i(nx, nz), PackedFloat32Array()), k)
		var poke_before := -INF
		var poke_after := -INF
		# Intérieur de la zone proche, à plus d'une maille lointaine de son bord (le bord est raccordé par blend_to_far)
		for z in range(50, 951, 10):
			for x in range(50, 1951, 10):
				var nt := TerrainTiles.tile_of("near", minf(x, 1999.0), minf(z, 999.0))
				var h_near: float = TerrainTiles.mesh_height_at(raw[nt], "near", nt.x, nt.y, x, z) * k
				poke_before = maxf(poke_before, TerrainTiles.mesh_height_at(far, "far", 0, 0, x, z) * k - TerrainTiles.FAR_DROP_M - h_near)
				poke_after = maxf(poke_after, TerrainTiles.mesh_height_at(sunk, "far", 0, 0, x, z) * k - TerrainTiles.FAR_DROP_M - h_near)
		# Sur le bord de la zone proche, le lointain ne bouge pas (il ne peut pas être sous un proche absent)
		var edge_moved := 0.0
		for m in range(0, 21):
			edge_moved = maxf(edge_moved, absf(sunk[0 * S + m] - far[0 * S + m]))
			edge_moved = maxf(edge_moved, absf(sunk[20 * S + m] - far[20 * S + m]))
		_check(poke_before > 0.5, "k = %.1f : cas d'essai valable, le lointain perçait de %.2f m" % [k, poke_before])
		_check(poke_after <= -TerrainTiles.FAR_CARVE_MARGIN_M + 0.001,
			"k = %.1f : lointain sous le proche partout (au plus %.2f m)" % [k, poke_after])
		_check(edge_moved == 0.0, "k = %.1f : sommets lointains du bord de la zone proche inchangés" % k)
	# Tuile entourée de tuiles proches : rien n'est modifié
	var full := {}
	for dj in range(-1, 2):
		for di in range(-1, 2):
			full[Vector2i(di, dj)] = true
	var same := TerrainTiles.blend_to_far(raw[Vector2i(0, 0)], 0, 0, full, far, Vector2i(0, 0))
	_check(same == raw[Vector2i(0, 0)], "tuile entourée de tuiles proches : hauteurs inchangées")
