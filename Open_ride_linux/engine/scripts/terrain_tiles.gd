extends RefCounted

## Tuiles de terrain du format .world v1 (§5) : lecture, remplacement des NaN, tableaux de maillage.
##
## Fonctions statiques sans accès à la scène : elles tournent dans les tâches de WorkerThreadPool
## (lot E1, §4.3). La création de l'ArrayMesh et du MeshInstance3D reste sur le fil principal.
## - Proche : maille 10 m, tuile 1 000 m ; lointain : maille 50 m, tuile 5 000 m ; 101 × 101 valeurs
##   float32 petit-boutistes, rangées par ligne : (i, j) à x = ix·T + i·maille, z = iz·T + j·maille.
## - Le lointain est dessiné FAR_DROP_M plus bas que ses valeurs, le proche à son altitude exacte :
##   le relief proche recouvre le lointain sans scintillement (écart voulu au format §5, voir lot E1).
##   Là où le proche s'arrête, il rejoint le lointain sur EDGE_BLEND_M (blend_to_far) ; sous le proche, le
##   lointain est enfoncé pour ne jamais le percer (sink_under_near).
## - Triangles : (a, b, c) et (b, d, c) pour la cellule a = (i, j), b = (i+1, j), c = (i, j+1),
##   d = (i+1, j+1), dans le sens horaire vu du dessus (faces avant de Godot).
## - Pas de couleur de sommet : herbe, roche et neige viennent du shader triplanaire du thème (lot E2).
## Pas de class_name (charger par preload).

const SAMPLES := 101
const CELLS := SAMPLES - 1
const FAR_DROP_M := 2.0
## Terrain lointain abaissé sous la route (carve_under_route) : demi-largeur dégagée autour de
## l'axe (chaussée de 6 m et bas-côtés de 0,5 m) et marge sous l'altitude de la route.
const ROAD_CLEAR_HALF_M := 4.0
const FAR_CARVE_MARGIN_M := 0.5
## Hauteur des jupes des tuiles proches (_add_skirts) : plus que FAR_DROP_M et la marge sous le proche.
const SKIRT_M := 3.0
## Largeur du raccord du terrain proche au lointain là où le proche s'arrête (blend_to_far).
const EDGE_BLEND_M := 50.0

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


## Abaisse le terrain sous la route (niveau lointain) : tout sommet d'une cellule que touche la
## chaussée (± ROAD_CLEAR_HALF_M autour de l'axe) passe sous l'altitude de la route moins
## `margin`. Sans cela, la maille de 50 m, non fondue avec la route par le compilateur, dépassait
## la route à la corde des virages et sur les flancs raides malgré FAR_DROP_M (défaut vu au banc
## simulé le 25 octobre : jusqu'à 8 cm au-dessus de la chaussée sur le village simulé, bien plus
## dans une vallée encaissée). Chaque tuile traite aussi les points de route proches de ses bords :
## les sommets partagés de deux tuiles voisines reçoivent la même valeur.
## Exécutable dans une tâche de fond.
## Applique l'exagération visuelle du relief (Lot Q2) : alt_orig + (h − alt_orig) × k.
static func scale_heights(heights: PackedFloat32Array, alt_orig: float, visual_grade_scale: float) -> PackedFloat32Array:
	if visual_grade_scale == 1.0 or heights.is_empty():
		return heights
	var out := PackedFloat32Array()
	out.resize(heights.size())
	for idx in range(heights.size()):
		var h := heights[idx]
		out[idx] = alt_orig + (h - alt_orig) * visual_grade_scale if not is_nan(h) else h
	return out


static func carve_under_route(heights: PackedFloat32Array, level: String, ix: int, iz: int, route,
		margin: float = FAR_CARVE_MARGIN_M) -> PackedFloat32Array:
	if route == null or route.n < 2:
		return heights
	var out := heights.duplicate()
	var cell: float = LEVELS[level]["cell"]
	var size: float = LEVELS[level]["size"]
	var x0 := ix * size
	var z0 := iz * size
	var pad := cell + ROAD_CLEAR_HALF_M
	for k in range(route.n):
		# Point de route et milieu du segment suivant (route échantillonnée à ds ≤ maille / 2).
		for f in [0.0, 0.5]:
			if f > 0.0 and k + 1 >= route.n:
				continue
			var k1: int = mini(k + 1, route.n - 1)
			var px: float = lerpf(route.x[k], route.x[k1], f)
			var pz: float = lerpf(route.z[k], route.z[k1], f)
			if px < x0 - pad or px > x0 + size + pad or pz < z0 - pad or pz > z0 + size + pad:
				continue
			# Hauteur affichée de la route (relief exagéré, lot Q2) : `heights` est déjà à cette échelle.
			var alt: float = route.display_y(minf(route.alt_m[k], route.alt_m[k1])) - margin
			var i0 := clampi(floori((px - x0 - ROAD_CLEAR_HALF_M) / cell), 0, CELLS)
			var i1 := clampi(floori((px - x0 + ROAD_CLEAR_HALF_M) / cell) + 1, 0, CELLS)
			var j0 := clampi(floori((pz - z0 - ROAD_CLEAR_HALF_M) / cell), 0, CELLS)
			var j1 := clampi(floori((pz - z0 + ROAD_CLEAR_HALF_M) / cell) + 1, 0, CELLS)
			for j in range(j0, j1 + 1):
				for i in range(i0, i1 + 1):
					var idx := j * SAMPLES + i
					if out[idx] > alt:
						out[idx] = alt
	return out


## Distance (m) du point (x, z) à la zone sans terrain proche (tuiles absentes de `near_index`), cherchée
## dans les tuiles voisines de celle du point ; INF si elle est à plus d'une tuile. Fonction du seul point :
## deux tuiles voisines donnent la même valeur à leurs sommets communs.
static func distance_to_uncovered(near_index: Dictionary, x: float, z: float) -> float:
	var size: float = LEVELS["near"]["size"]
	var t := tile_of("near", x, z)
	var best := INF
	for dj in range(-1, 2):
		for di in range(-1, 2):
			var n := Vector2i(t.x + di, t.y + dj)
			if near_index.has(n):
				continue
			var dx := maxf(maxf(n.x * size - x, 0.0), x - (n.x + 1) * size)
			var dz := maxf(maxf(n.y * size - z, 0.0), z - (n.y + 1) * size)
			best = minf(best, Vector2(dx, dz).length())
	return best


## Raccord du terrain proche au lointain là où le proche s'arrête (bord sans tuile proche voisine) : sur
## EDGE_BLEND_M, les hauteurs passent à celles du maillage lointain affiché (FAR_DROP_M plus bas, `far` déjà
## abaissé sous la route). Sans cela, une marche d'environ 2 m (FAR_DROP_M et maille de 50 m) dessinait le
## contour des tuiles proches dans le paysage (« tuiles non jointives », 28 octobre).
## `far` : hauteurs de la tuile lointaine `far_tile` qui contient la tuile proche ; `visual_grade_scale` : la
## chute de FAR_DROP_M est appliquée après l'exagération du relief (build_arrays). Exécutable dans une tâche de fond.
static func blend_to_far(heights: PackedFloat32Array, ix: int, iz: int, near_index: Dictionary,
		far: PackedFloat32Array, far_tile: Vector2i, visual_grade_scale: float = 1.0) -> PackedFloat32Array:
	if far.is_empty():
		return heights
	var cell: float = LEVELS["near"]["cell"]
	var size: float = LEVELS["near"]["size"]
	# Tuile entourée de tuiles proches : rien à raccorder
	var alone := false
	for dj in range(-1, 2):
		for di in range(-1, 2):
			alone = alone or not near_index.has(Vector2i(ix + di, iz + dj))
	if not alone:
		return heights
	var drop := FAR_DROP_M / maxf(visual_grade_scale, 0.01)
	var out := heights.duplicate()
	for j in range(SAMPLES):
		for i in range(SAMPLES):
			var x := ix * size + i * cell
			var z := iz * size + j * cell
			var d := distance_to_uncovered(near_index, x, z)
			if d >= EDGE_BLEND_M:
				continue
			var k := smoothstep(0.0, EDGE_BLEND_M, d)
			var target := mesh_height_at(far, "far", far_tile.x, far_tile.y, x, z) - drop
			var idx := j * SAMPLES + i
			out[idx] = lerpf(target, out[idx], k)
	return out


## Terrain lointain enfoncé sous le proche, juste ce qu'il faut : pour chaque maille lointaine (50 m) couverte
## d'une tuile proche, on mesure de combien le maillage lointain affiché passe au-dessus du proche aux
## échantillons proches de la maille (10 m), moins `margin` (FAR_DROP_M compris, relief exagéré compris), puis
## chaque sommet descend du plus fort de ces dépassements sur ses mailles voisines. Comme un point de maille
## est une moyenne pondérée de ses quatre sommets, il passe alors sous le proche. Sur une pente régulière, le
## lointain est déjà sous le proche et ne bouge pas : la règle précédente (sommet posé sous le plus bas du
## proche à ± 50 m) creusait le lointain de plusieurs dizaines de mètres sur les flancs (relief ×2,5), et ce
## lointain se voit au-delà du rayon des tuiles proches (coutures en zigzag et bandes grises, 29 octobre).
## Seuls les sommets dont les quatre mailles sont couvertes bougent : le bord de la zone proche garde son
## raccord exact (blend_to_far). Sur le bord de la tuile lointaine, seuls les échantillons du bord comptent :
## ils ne dépendent que des sommets du bord, communs aux deux tuiles, qui reçoivent donc la même valeur.
## `near_tile(ix, iz)` : hauteurs brutes d'une tuile proche (NaN admis). Exécutable dans une tâche de fond.
static func sink_under_near(heights: PackedFloat32Array, ix: int, iz: int, near_index: Dictionary,
		near_tile: Callable, visual_grade_scale: float = 1.0, margin: float = FAR_CARVE_MARGIN_M) -> PackedFloat32Array:
	if near_index.is_empty():
		return heights
	var cell: float = LEVELS["far"]["cell"]
	var size: float = LEVELS["far"]["size"]
	var n_cell: float = LEVELS["near"]["cell"]
	var n_size: float = LEVELS["near"]["size"]
	var lift := (FAR_DROP_M - margin) / maxf(visual_grade_scale, 0.01)
	var steps := roundi(cell / n_cell)   # échantillons proches par maille lointaine
	var x0 := ix * size
	var z0 := iz * size
	# Tuile proche qui contient chaque maille lointaine (les grilles sont alignées) ; vide si non couverte
	var cache := {}
	var cell_near := func(ci: int, cj: int) -> PackedFloat32Array:
		var nt := tile_of("near", x0 + (ci + 0.5) * cell, z0 + (cj + 0.5) * cell)
		if not near_index.has(nt):
			return PackedFloat32Array()
		if not cache.has(nt):
			cache[nt] = near_tile.call(nt.x, nt.y)
		return cache[nt]
	# Dépassement du lointain sur le proche, par maille : intérieur (tous les échantillons) et bords de tuile
	var excess := PackedFloat32Array()
	excess.resize(CELLS * CELLS)
	excess.fill(NAN)   # NaN : maille non couverte
	var edge_excess := {}   # Vector2i(sommet) -> dépassement le long du bord de la tuile lointaine
	for cj in range(CELLS):
		for ci in range(CELLS):
			var near: PackedFloat32Array = cell_near.call(ci, cj)
			if near.is_empty():
				continue
			var nt := tile_of("near", x0 + (ci + 0.5) * cell, z0 + (cj + 0.5) * cell)
			var bi := roundi((x0 + ci * cell - nt.x * n_size) / n_cell)
			var bj := roundi((z0 + cj * cell - nt.y * n_size) / n_cell)
			var a := heights[cj * SAMPLES + ci]
			var b := heights[cj * SAMPLES + ci + 1]
			var c := heights[(cj + 1) * SAMPLES + ci]
			var d := heights[(cj + 1) * SAMPLES + ci + 1]
			var e := -INF
			for sj in range(steps + 1):
				for si in range(steps + 1):
					var hn := near[(bj + sj) * SAMPLES + bi + si]
					if is_nan(hn):
						continue
					var u := float(si) / steps
					var v := float(sj) / steps
					var hf := a + u * (b - a) + v * (c - a) if u + v <= 1.0 else d + (1.0 - u) * (c - d) + (1.0 - v) * (b - d)
					var ex := hf - hn - lift
					e = maxf(e, ex)
					# Échantillons posés sur un bord de la tuile lointaine : ne dépendent que de ses deux sommets
					var on_edge := (ci == 0 and si == 0) or (ci == CELLS - 1 and si == steps) \
							or (cj == 0 and sj == 0) or (cj == CELLS - 1 and sj == steps)
					if on_edge and ex > 0.0:
						for vk in [Vector2i(ci + (1 if si == steps else 0), cj + (1 if sj == steps else 0)),
								Vector2i(ci + (0 if si == 0 else 1), cj + (0 if sj == 0 else 1))]:
							if vk.x == 0 or vk.x == CELLS or vk.y == 0 or vk.y == CELLS:
								edge_excess[vk] = maxf(float(edge_excess.get(vk, 0.0)), ex)
			excess[cj * CELLS + ci] = e
	var out := heights
	var copied := false
	for j in range(SAMPLES):
		for i in range(SAMPLES):
			# Les quatre mailles autour du sommet doivent être couvertes, voisines de l'autre tuile comprises
			var covered := true
			for dj in [-0.5, 0.5]:
				for di in [-0.5, 0.5]:
					covered = covered and near_index.has(tile_of("near", x0 + (i + di) * cell, z0 + (j + dj) * cell))
			if not covered:
				continue
			var drop := 0.0
			if i == 0 or i == CELLS or j == 0 or j == CELLS:
				# Bord de la tuile lointaine : échantillons du bord seulement (la tuile voisine trouve la même valeur)
				drop = float(edge_excess.get(Vector2i(i, j), 0.0))
			else:
				for dj in [-1, 0]:
					for di in [-1, 0]:
						drop = maxf(drop, excess[(j + dj) * CELLS + i + di])
			if drop > 0.0:
				if not copied:
					out = heights.duplicate()
					copied = true
				out[j * SAMPLES + i] -= drop
	return out


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
static func build_arrays(heights: PackedFloat32Array, level: String, edges: Dictionary = {},
		visual_grade_scale: float = 1.0, alt_orig: float = 0.0) -> Array:
	# Exagération du relief (lot Q2) : h' = alt_orig + (h − alt_orig) × k, appliquée au sommet et aux pentes
	# sans copier les hauteurs ; à k = 1,0, kk = 1 et y_scaled_offset = 0 donnent exactement les valeurs d'avant.
	var kk := visual_grade_scale
	var y_scaled_offset := alt_orig * (1.0 - kk)
	var h_data := heights
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
			var h := h_data[j * SAMPLES + i]
			# Pente en x : différence centrée, voisine au bord si elle existe, sinon d'un seul côté.
			var h_w := h_data[j * SAMPLES + i - 1] if i > 0 else (west[j] if west.size() == SAMPLES else NAN)
			var h_e := h_data[j * SAMPLES + i + 1] if i < CELLS else (east[j] if east.size() == SAMPLES else NAN)
			var h_n := h_data[(j - 1) * SAMPLES + i] if j > 0 else (north[i] if north.size() == SAMPLES else NAN)
			var h_s := h_data[(j + 1) * SAMPLES + i] if j < CELLS else (south[i] if south.size() == SAMPLES else NAN)
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
			var normal := Vector3(-dhdx * kk, 1.0, -dhdz * kk).normalized()
			var idx := j * SAMPLES + i
			vertices[idx] = Vector3(i * cell, h * kk + y_scaled_offset + y_offset, j * cell)
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
	if level == "near":
		_add_skirts(vertices, normals, indices)
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices
	return arrays


## Jupes des tuiles proches : chaque bord descend de SKIRT_M (faces des deux côtés, normale du bord pour un
## éclairage de sol). Deux tuiles voisines ont les mêmes hauteurs au bord, mais chaque maillage a sa propre
## transformation : la carte graphique peut laisser entre elles des pixels non couverts, qui montrent le
## lointain plus bas (pointillés sombres en escalier sur les flancs, PC du 29 octobre). Les jupes bouchent
## aussi la marche vers le lointain là où la tuile voisine n'est pas chargée. Les sommets de la grille gardent
## leurs indices (j × SAMPLES + i) : les jupes sont ajoutées après.
static func _add_skirts(vertices: PackedVector3Array, normals: PackedVector3Array, indices: PackedInt32Array) -> void:
	var sides := [
		range(0, SAMPLES),                                          # nord (j = 0)
		range(CELLS * SAMPLES, SAMPLES * SAMPLES),                  # sud (j = CELLS)
		range(0, SAMPLES * SAMPLES, SAMPLES),                       # ouest (i = 0)
		range(CELLS, SAMPLES * SAMPLES, SAMPLES),                   # est (i = CELLS)
	]
	for side in sides:
		var top: Array = side
		var base := vertices.size()
		for idx in top:
			vertices.append(vertices[idx] - Vector3(0.0, SKIRT_M, 0.0))
			normals.append(normals[idx])
		for m in range(top.size() - 1):
			var a: int = top[m]
			var b: int = top[m + 1]
			var c := base + m
			var d := base + m + 1
			indices.append_array(PackedInt32Array([a, b, c, b, d, c, a, c, b, b, c, d]))


## Origine (coin nord-ouest) d'une tuile dans le repère du monde.
static func tile_origin(level: String, ix: int, iz: int) -> Vector3:
	var size: float = LEVELS[level]["size"]
	return Vector3(ix * size, 0.0, iz * size)
