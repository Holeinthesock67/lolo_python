extends RefCounted

## Tuiles de terrain du format .world v1 (§5) : lecture, remplacement des NaN, tableaux de maillage.
##
## Fonctions statiques sans accès à la scène : elles tournent dans les tâches de WorkerThreadPool
## (lot E1, §4.3). La création de l'ArrayMesh et du MeshInstance3D reste sur le fil principal.
## - Proche : maille 10 m, tuile 1 000 m ; lointain : maille 50 m, tuile 5 000 m ; 101 × 101 valeurs
##   float32 petit-boutistes, rangées par ligne : (i, j) à x = ix·T + i·maille, z = iz·T + j·maille.
## - Le lointain est dessiné FAR_DROP_M plus bas que ses valeurs, le proche à son altitude exacte :
##   le relief proche recouvre le lointain sans scintillement (écart voulu au format §5, voir lot E1).
## - Triangles : (a, b, c) et (b, d, c) pour la cellule a = (i, j), b = (i+1, j), c = (i, j+1),
##   d = (i+1, j+1), dans le sens horaire vu du dessus (faces avant de Godot).
## - Pas de couleur de sommet : herbe, roche et neige viennent du shader triplanaire du thème (lot E2).
## Pas de class_name (charger par preload).

const SAMPLES := 101
const CELLS := SAMPLES - 1
const FAR_DROP_M := 2.0

## Niveaux : dossier, maille, taille de tuile, décalage vertical au dessin.
const LEVELS := {
	"near": {"dir": "near", "cell": 10.0, "size": 1000.0, "y_offset": 0.0},
	"far": {"dir": "far", "cell": 50.0, "size": 5000.0, "y_offset": -FAR_DROP_M},
}


static func tile_path(world_dir: String, level: String, ix: int, iz: int) -> String:
	return world_dir.path_join("terrain").path_join(LEVELS[level]["dir"]).path_join("tile_%d_%d.f32" % [ix, iz])


## Indices (ix, iz) des tuiles présentes dans terrain/<niveau>/ (liste du dossier).
static func scan_index(world_dir: String, level: String) -> Dictionary:
	var index := {}
	var dir := DirAccess.open(world_dir.path_join("terrain").path_join(LEVELS[level]["dir"]))
	if dir == null:
		return index
	for file_name in dir.get_files():
		if not (file_name.begins_with("tile_") and file_name.ends_with(".f32")):
			continue
		var parts := file_name.trim_suffix(".f32").split("_")
		if parts.size() == 3 and parts[1].is_valid_int() and parts[2].is_valid_int():
			index[Vector2i(int(parts[1]), int(parts[2]))] = true
	return index


## Lit une tuile : 101 × 101 float32, ou tableau vide si le fichier manque ou n'a pas la bonne taille.
static func load_tile(world_dir: String, level: String, ix: int, iz: int) -> PackedFloat32Array:
	var path := tile_path(world_dir, level, ix, iz)
	if not FileAccess.file_exists(path):
		return PackedFloat32Array()
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.size() != SAMPLES * SAMPLES * 4:
		push_warning("Tuile de terrain ignorée (taille %d octets) : %s" % [bytes.size(), path])
		return PackedFloat32Array()
	return bytes.to_float32_array()   # petit-boutiste, comme toutes les plateformes visées


## Indice de la tuile qui contient (x, z) au niveau donné.
static func tile_of(level: String, x: float, z: float) -> Vector2i:
	var size: float = LEVELS[level]["size"]
	return Vector2i(floori(x / size), floori(z / size))


## Altitude du maillage d'une tuile en (x, z), interpolée sur le triangle qui contient le point
## (même découpage que build_arrays). `heights` sans NaN ; y_offset non compris.
static func mesh_height_at(heights: PackedFloat32Array, level: String, ix: int, iz: int, x: float, z: float) -> float:
	var cell: float = LEVELS[level]["cell"]
	var size: float = LEVELS[level]["size"]
	var fi := clampf((x - ix * size) / cell, 0.0, CELLS)
	var fj := clampf((z - iz * size) / cell, 0.0, CELLS)
	var i := mini(int(fi), CELLS - 1)
	var j := mini(int(fj), CELLS - 1)
	var u := fi - i
	var v := fj - j
	var a := heights[j * SAMPLES + i]
	var b := heights[j * SAMPLES + i + 1]
	var c := heights[(j + 1) * SAMPLES + i]
	var d := heights[(j + 1) * SAMPLES + i + 1]
	if u + v <= 1.0:
		return a + u * (b - a) + v * (c - a)
	return d + (1.0 - u) * (c - d) + (1.0 - v) * (b - d)


## Altitude de la route au point de route le plus proche de (x, z) (format §10, dernier recours).
static func nearest_route_alt(route, x: float, z: float) -> float:
	var best := INF
	var alt := 0.0
	for k in range(route.n):
		var dx: float = route.x[k] - x
		var dz: float = route.z[k] - z
		var d := dx * dx + dz * dz
		if d < best:
			best = d
			alt = route.alt_m[k]
	return alt


## Remplace les NaN : moyenne des voisins valides (8 voisins, valeurs d'origine) ; sans voisin
## valide, `fallback.call(x, z)` (valeur lointaine au même endroit, puis route la plus proche).
static func fill_nan(heights: PackedFloat32Array, level: String, ix: int, iz: int, fallback: Callable) -> PackedFloat32Array:
	var out := heights.duplicate()
	var cell: float = LEVELS[level]["cell"]
	var size: float = LEVELS[level]["size"]
	for j in range(SAMPLES):
		for i in range(SAMPLES):
			if not is_nan(heights[j * SAMPLES + i]):
				continue
			var total := 0.0
			var count := 0
			for dj in range(-1, 2):
				for di in range(-1, 2):
					var ni := i + di
					var nj := j + dj
					if (di == 0 and dj == 0) or ni < 0 or nj < 0 or ni >= SAMPLES or nj >= SAMPLES:
						continue
					var h := heights[nj * SAMPLES + ni]
					if not is_nan(h):
						total += h
						count += 1
			if count > 0:
				out[j * SAMPLES + i] = total / count
			else:
				out[j * SAMPLES + i] = float(fallback.call(ix * size + i * cell, iz * size + j * cell))
	return out


## Lit une tuile et remplace ses NaN (valeur lointaine, puis altitude de la route la plus proche).
## Exécutable dans une tâche de fond. Tableau vide si la tuile manque.
static func load_filled(world_dir: String, level: String, ix: int, iz: int, route) -> PackedFloat32Array:
	var raw := load_tile(world_dir, level, ix, iz)
	if raw.is_empty():
		return raw
	var far_cache := {}
	var fallback := func(x: float, z: float) -> float:
		if level == "near":
			var t := tile_of("far", x, z)
			if not far_cache.has(t):
				far_cache[t] = load_tile(world_dir, "far", t.x, t.y)
			var far: PackedFloat32Array = far_cache[t]
			if not far.is_empty():
				var h := mesh_height_at(far, "far", t.x, t.y, x, z)
				if not is_nan(h):
					return h
		return nearest_route_alt(route, x, z)
	return fill_nan(raw, level, ix, iz, fallback)


## Tuile plate à une altitude donnée (tuile manquante sans niveau lointain, format §10).
static func flat_heights(alt: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(SAMPLES * SAMPLES)
	out.fill(alt)
	return out


## Colonne (i fixe) ou ligne (j fixe) d'une tuile voisine, utile au calcul des normales au bord.
static func _edge(world_dir: String, level: String, ix: int, iz: int, column: int, row: int) -> PackedFloat32Array:
	var data := load_tile(world_dir, level, ix, iz)
	var out := PackedFloat32Array()
	if data.is_empty():
		return out
	for k in range(SAMPLES):
		out.append(data[k * SAMPLES + column] if column >= 0 else data[row * SAMPLES + k])
	return out


## Valeurs des tuiles voisines juste au-delà de chaque bord (i = −1, i = 101, j = −1, j = 101) :
## comme les bords sont partagés, ce sont les colonnes ou lignes 99 et 1 des voisines.
## Une entrée vide signifie « voisine absente » (différence d'un seul côté).
static func load_neighbour_edges(world_dir: String, level: String, ix: int, iz: int) -> Dictionary:
	if world_dir == "":
		return {}
	return {
		"west": _edge(world_dir, level, ix - 1, iz, CELLS - 1, -1),
		"east": _edge(world_dir, level, ix + 1, iz, 1, -1),
		"north": _edge(world_dir, level, ix, iz - 1, -1, CELLS - 1),
		"south": _edge(world_dir, level, ix, iz + 1, -1, 1),
	}


## Tableaux de maillage (Mesh.ARRAY_MAX) d'une tuile, en coordonnées locales à son coin (ix·T, iz·T).
## `edges` : valeurs voisines (load_neighbour_edges) ; une valeur NaN ou absente donne une
## différence d'un seul côté.
static func build_arrays(heights: PackedFloat32Array, level: String, edges: Dictionary = {}) -> Array:
	var cell: float = LEVELS[level]["cell"]
	var y_offset: float = LEVELS[level]["y_offset"]
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	vertices.resize(SAMPLES * SAMPLES)
	normals.resize(SAMPLES * SAMPLES)
	var west: PackedFloat32Array = edges.get("west", PackedFloat32Array())
	var east: PackedFloat32Array = edges.get("east", PackedFloat32Array())
	var north: PackedFloat32Array = edges.get("north", PackedFloat32Array())
	var south: PackedFloat32Array = edges.get("south", PackedFloat32Array())
	for j in range(SAMPLES):
		for i in range(SAMPLES):
			var h := heights[j * SAMPLES + i]
			# Pente en x : différence centrée, voisine au bord si elle existe, sinon d'un seul côté.
			var h_w := heights[j * SAMPLES + i - 1] if i > 0 else (west[j] if west.size() == SAMPLES else NAN)
			var h_e := heights[j * SAMPLES + i + 1] if i < CELLS else (east[j] if east.size() == SAMPLES else NAN)
			var h_n := heights[(j - 1) * SAMPLES + i] if j > 0 else (north[i] if north.size() == SAMPLES else NAN)
			var h_s := heights[(j + 1) * SAMPLES + i] if j < CELLS else (south[i] if south.size() == SAMPLES else NAN)
			var dhdx: float
			if is_nan(h_w):
				dhdx = (h_e - h) / cell
			elif is_nan(h_e):
				dhdx = (h - h_w) / cell
			else:
				dhdx = (h_e - h_w) / (2.0 * cell)
			var dhdz: float
			if is_nan(h_n):
				dhdz = (h_s - h) / cell
			elif is_nan(h_s):
				dhdz = (h - h_n) / cell
			else:
				dhdz = (h_s - h_n) / (2.0 * cell)
			var normal := Vector3(-dhdx, 1.0, -dhdz).normalized()
			var idx := j * SAMPLES + i
			vertices[idx] = Vector3(i * cell, h + y_offset, j * cell)
			normals[idx] = normal
	var indices := PackedInt32Array()
	indices.resize(CELLS * CELLS * 6)
	var w := 0
	for j in range(CELLS):
		for i in range(CELLS):
			var a := j * SAMPLES + i
			var b := a + 1
			var c := a + SAMPLES
			var d := c + 1
			indices[w] = a
			indices[w + 1] = b
			indices[w + 2] = c
			indices[w + 3] = b
			indices[w + 4] = d
			indices[w + 5] = c
			w += 6
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices
	return arrays


## Origine (coin nord-ouest) d'une tuile dans le repère du monde.
static func tile_origin(level: String, ix: int, iz: int) -> Vector3:
	var size: float = LEVELS[level]["size"]
	return Vector3(ix * size, 0.0, iz * size)
