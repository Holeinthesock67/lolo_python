extends RefCounted

## Eau lointaine du monde ouvert (lot EA2, `docs/lots/LOT_EA2_eau_au_loin.md`).
##
## Le générateur écrit, pour une tuile lointaine de 5 km qui touche un grand lac (plus de 1 km²),
## `water/far/tile_<ix>_<iz>.f32` : 101 × 101 float32 au pas de 50 m, comme `terrain/far/`, niveau du lac
## en chaque échantillon dans l'eau, NaN ailleurs ; le relief lointain y est abaissé à `niveau − 1 m`.
## Une cellule de 50 m dont un coin est dans l'eau reçoit un plan au niveau du lac, posé FAR_WATER_DROP_M
## sous ce niveau : au-dessus du sol abaissé (proche à −1 m, lointain encore FAR_DROP_M plus bas) et
## sous la surface des plans d'eau proches (+5 cm) ; la rive se dessine là où le relief sort du plan.
## Les cellules voisines d'une même ligne au même niveau forment une seule bande.
## Fonctions statiques, sans scène : elles tournent dans les tâches de fond du world_streamer.
## Pas de class_name (charger par preload).

const TerrainTiles := preload("res://scripts/terrain_tiles.gd")

const FAR_WATER_DROP_M := 0.5


static func tile_path(world_dir: String, ix: int, iz: int) -> String:
	return world_dir.path_join("water").path_join("far").path_join("tile_%d_%d.f32" % [ix, iz])


## Niveaux de la tuile (101 × 101), ou tableau vide sans eau lointaine.
static func load_levels(world_dir: String, ix: int, iz: int) -> PackedFloat32Array:
	var path := tile_path(world_dir, ix, iz)
	if not FileAccess.file_exists(path):
		return PackedFloat32Array()
	var bytes := FileAccess.get_file_as_bytes(path)
	var n := TerrainTiles.SAMPLES
	if bytes.size() != n * n * 4:
		push_warning("Eau lointaine ignorée (taille %d octets) : %s" % [bytes.size(), path])
		return PackedFloat32Array()
	return bytes.to_float32_array()


## Tableaux de maillage (sommets relatifs au coin de la tuile, UV en coordonnées de la séance) ;
## `display_y` : altitude affichée (relief exagéré du lot Q2), identité par défaut. Vide sans eau.
static func build_arrays(levels: PackedFloat32Array, ix: int, iz: int, display_y := Callable()) -> Array:
	var n := TerrainTiles.SAMPLES
	if levels.size() != n * n:
		return []
	var cell: float = TerrainTiles.LEVELS["far"]["cell"]
	var origin := TerrainTiles.tile_origin("far", ix, iz)
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var indices := PackedInt32Array()
	for j in range(n - 1):
		var run_start := -1
		var run_level := 0.0
		for i in range(n):
			var lv := NAN
			if i < n - 1:
				lv = _cell_level(levels, n, i, j)
			if run_start >= 0 and (is_nan(lv) or lv != run_level):
				_add_quad(vertices, normals, uvs, indices, origin, run_start * cell, i * cell, j * cell,
					(j + 1) * cell, _shown(run_level, display_y))
				run_start = -1
			if not is_nan(lv) and run_start < 0:
				run_start = i
				run_level = lv
	if vertices.is_empty():
		return []
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = vertices
	arr[Mesh.ARRAY_NORMAL] = normals
	arr[Mesh.ARRAY_TEX_UV] = uvs
	arr[Mesh.ARRAY_INDEX] = indices
	return arr


## Niveau d'une cellule : le plus haut de ses coins dans l'eau, NaN si aucun.
static func _cell_level(levels: PackedFloat32Array, n: int, i: int, j: int) -> float:
	var best := NAN
	for k in [j * n + i, j * n + i + 1, (j + 1) * n + i, (j + 1) * n + i + 1]:
		var v: float = levels[k]
		if not is_nan(v) and (is_nan(best) or v > best):
			best = v
	return best


static func _shown(level: float, display_y: Callable) -> float:
	var y := level - FAR_WATER_DROP_M
	return float(display_y.call(y)) if display_y.is_valid() else y


static func _add_quad(vertices: PackedVector3Array, normals: PackedVector3Array, uvs: PackedVector2Array,
		indices: PackedInt32Array, origin: Vector3, x0: float, x1: float, z0: float, z1: float, y: float) -> void:
	var b := vertices.size()
	for p in [Vector2(x0, z0), Vector2(x1, z0), Vector2(x0, z1), Vector2(x1, z1)]:
		vertices.append(Vector3(p.x, y, p.y))
		normals.append(Vector3.UP)
		uvs.append(Vector2(origin.x + p.x, origin.z + p.y))
	# même sens que les tuiles de terrain : (a, b, c) et (b, d, c), horaire vu du dessus
	indices.append_array(PackedInt32Array([b, b + 1, b + 2, b + 1, b + 3, b + 2]))
