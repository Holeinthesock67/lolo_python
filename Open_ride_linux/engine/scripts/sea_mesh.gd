extends RefCounted

## Mer animée, écume et plages (lot U9, série U, version 3.0), sans aucun nœud : fonctions pures utilisables
## dans une tâche de fond (osm_streamer.gd).
##
## - Mer : aires `sea` de la couche eau (lot U3, format §8), triangulées avec leurs îles en trous par la
##   triangulation de water_mesh.gd, posées SURFACE_OFFSET_M au-dessus de leur niveau (le MNT vaut 0 sur la mer :
##   sans écart, mer et terrain scintillaient, risque noté au lot U3). Couleur de sommet (sRGB) d'après `water`
##   des biomes au centre de l'aire, mêlés selon leurs poids (le biome `coast` sur le littoral, le biome dominant
##   ailleurs) ; shaders/sea.gdshader anime les vagues (normales seulement, aucun déplacement).
## - Horizon : anneau plat (`build_horizon`) qui prolonge la mer jusqu'au-delà du brouillard, HORIZON_BELOW_M
##   sous la mer : sous les aires `sea`, au-dessus du lointain abaissé de 2 m (terrain_tiles.gd FAR_DROP_M).
##   Son trou central (HORIZON_HOLE_M) laisse le proche aux seules aires `sea` chargées.
## - Écume : ruban côté mer de chaque ligne de côte (couche `coast`, la mer à droite du sens des points, soit
##   la normale (−dz, dx) dans le repère x est, z sud), large de FOAM_WIDTH_M selon le rivage ; UV.x : distance
##   le long de la côte, UV.y : 0 au rivage, 1 au large ; COLOR.r : part de la bande toujours couverte
##   (FOAM_MIN_M / FOAM_WIDTH_M). shaders/sea_foam.gdshader fait aller et venir l'écume entre les deux.
## - Plages : polygones `beaches` drapés sur le terrain (`height_at`), découpés à la maille de 10 m du terrain
##   proche pour le suivre au plus près, BEACH_ABOVE_M au-dessus ; couleur de sommet sable ou galets.
## - `shore_distance` : distance au rivage le plus proche, pour le son des vagues (lot U11).
## Pas de class_name : charger par preload("res://scripts/sea_mesh.gd").

const WaterMesh := preload("res://scripts/water_mesh.gd")

const SURFACE_OFFSET_M := 0.2
const HORIZON_BELOW_M := 1.0
const HORIZON_HOLE_M := 1500.0
const HORIZON_RADIUS_M := 30000.0
const HORIZON_SEGMENTS := 48
const FOAM_ABOVE_M := 0.04
## Bande d'écume : largeur totale et part toujours couverte, par sorte de rivage (cahier U9 : 2 à 6 m le long
## du sable et des galets, plus large au pied des falaises).
const FOAM_WIDTH_M := {"sand": 6.0, "shingle": 6.0, "rock": 4.0, "cliff": 12.0}
const FOAM_MIN_M := {"sand": 2.0, "shingle": 2.0, "rock": 2.0, "cliff": 6.0}
const FOAM_MAX_MITER := 2.0
const BEACH_ABOVE_M := 0.12
const BEACH_CELL_M := 10.0          # maille du terrain proche (terrain_tiles.gd LEVELS.near.cell)
## Couleurs (sRGB) : sable du sol plat du biome `coast` du thème par défaut ; galets gris.
const BEACH_COLORS := {"sand": Color("#c2ae86"), "shingle": Color("#8d877d")}
const DEFAULT_SEA_COLOR := Color("#2a8a9a")   # `water` du biome coast du thème par défaut


## Aires de la couche eau séparées : `{sea: [...], inland: [...]}` (ordre gardé).
static func split_areas(areas: Array) -> Dictionary:
	var out := {"sea": [], "inland": []}
	for a in areas:
		if typeof(a) == TYPE_DICTIONARY and str(a.get("kind", "")) == "sea":
			out["sea"].append(a)
		else:
			out["inland"].append(a)
	return out


## Couleur `water` (sRGB) d'un biome du thème, ou null.
static func _theme_water(theme: Dictionary, biome: String) -> Variant:
	var biomes = theme.get("biomes", null)
	if typeof(biomes) != TYPE_DICTIONARY or typeof(biomes.get(biome, null)) != TYPE_DICTIONARY:
		return null
	var water = biomes[biome].get("water", null)
	if typeof(water) != TYPE_DICTIONARY or typeof(water.get("color", null)) != TYPE_STRING:
		return null
	var hex: String = water["color"]
	return Color.html(hex) if Color.html_is_valid(hex) else null


## Couleur de la mer en (x, z) : `water` des biomes du modèle (biome_model.gd) mêlés selon leurs poids ; sans
## modèle actif, celle du biome `coast` du thème, puis DEFAULT_SEA_COLOR.
static func sea_color(theme: Dictionary, biome_model, x: float, z: float) -> Color:
	if biome_model != null:
		var weights: Dictionary = biome_model.weights_at(x, z)
		var acc := Color(0, 0, 0, 0)
		var total := 0.0
		for b in weights:
			var w := float(weights[b])
			if w <= 0.0:
				continue
			var c: Color = biome_model.params(str(b))["water"]["color"]
			acc += c * w
			total += w
		if total > 0.0:
			var out := acc / total
			out.a = 1.0
			return out
	var coast = _theme_water(theme, "coast")
	return coast if coast != null else DEFAULT_SEA_COLOR


## Couleur (sRGB) du sable des plages : premier sol `flat` du biome `coast` du thème, ou null (BEACH_COLORS).
static func sand_color(theme: Dictionary) -> Variant:
	var biomes = theme.get("biomes", null)
	if typeof(biomes) != TYPE_DICTIONARY or typeof(biomes.get("coast", null)) != TYPE_DICTIONARY:
		return null
	var ground = biomes["coast"].get("ground", null)
	if typeof(ground) != TYPE_DICTIONARY or typeof(ground.get("layers", null)) != TYPE_ARRAY:
		return null
	for layer in ground["layers"]:
		if typeof(layer) == TYPE_DICTIONARY and str(layer.get("role", "")) == "flat" \
				and typeof(layer.get("color", null)) == TYPE_STRING and Color.html_is_valid(layer["color"]):
			return Color.html(layer["color"])
	return null


static func _ring_center(raw: Variant) -> Vector2:
	var r := Rect2()
	var first := true
	if typeof(raw) == TYPE_ARRAY:
		for p in raw:
			if typeof(p) == TYPE_ARRAY and (p as Array).size() >= 2:
				var q := Vector2(float(p[0]), float(p[1]))
				r = Rect2(q, Vector2.ZERO) if first else r.expand(q)
				first = false
	return r.get_center()


## Maillage de la mer : aires `sea` triangulées (îles en trous), SURFACE_OFFSET_M au-dessus de `level_y`,
## couleur de sommet `color_at.call(x, z)` au centre de chaque aire. Renvoie {vertices, normals, colors,
## indices, built, skipped, color} (`color` : celle de la première aire construite, pour l'horizon).
static func build_sea(areas: Array, color_at: Callable) -> Dictionary:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var indices := PackedInt32Array()
	var built := 0
	var skipped := 0
	var first_color = null
	for a in areas:
		var one := WaterMesh.build_areas([a])
		if int(one["built"]) == 0:
			skipped += 1
			continue
		var c := _ring_center((a as Dictionary).get("outer", null))
		var col: Color = color_at.call(c.x, c.y)
		if first_color == null:
			first_color = col
		var base := vertices.size()
		for v in (one["vertices"] as PackedVector3Array):
			vertices.append(v + Vector3(0.0, SURFACE_OFFSET_M, 0.0))
			normals.append(Vector3.UP)
			colors.append(col)
		for i in (one["indices"] as PackedInt32Array):
			indices.append(base + i)
		built += 1
	return {"vertices": vertices, "normals": normals, "colors": colors, "indices": indices,
		"built": built, "skipped": skipped, "color": first_color if first_color != null else DEFAULT_SEA_COLOR}


## Anneau plat de l'horizon autour de l'origine (à placer au centre voulu), à la hauteur `y`, de couleur `color`.
static func build_horizon(y: float, color: Color, hole_m: float = HORIZON_HOLE_M,
		radius_m: float = HORIZON_RADIUS_M) -> Dictionary:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var indices := PackedInt32Array()
	for i in range(HORIZON_SEGMENTS):
		var a := TAU * i / HORIZON_SEGMENTS
		var d := Vector2(cos(a), sin(a))
		vertices.append(Vector3(d.x * hole_m, y, d.y * hole_m))
		vertices.append(Vector3(d.x * radius_m, y, d.y * radius_m))
		for _k in 2:
			normals.append(Vector3.UP)
			colors.append(color)
	for i in range(HORIZON_SEGMENTS):
		var i0 := 2 * i
		var i1 := 2 * ((i + 1) % HORIZON_SEGMENTS)
		indices.append_array([i0, i0 + 1, i1, i1, i0 + 1, i1 + 1])
	indices = _orient_up(vertices, indices)
	return {"vertices": vertices, "normals": normals, "colors": colors, "indices": indices,
		"built": HORIZON_SEGMENTS}


static func _line_points(raw: Variant) -> PackedVector2Array:
	var out := PackedVector2Array()
	if typeof(raw) != TYPE_ARRAY:
		return out
	for p in raw:
		if typeof(p) != TYPE_ARRAY or (p as Array).size() < 2:
			continue
		var q := Vector2(float(p[0]), float(p[1]))
		if out.is_empty() or out[out.size() - 1].distance_to(q) > 1e-3:
			out.append(q)
	return out


## Côté mer d'un segment (a → b) : la mer est à droite du sens des points (format §8 quinquies), soit la
## normale (−dz, dx) dans le repère x est, z sud.
static func sea_side(a: Vector2, b: Vector2) -> Vector2:
	var d := (b - a).normalized()
	return Vector2(-d.y, d.x)


## Ruban d'écume côté mer des lignes de côte, à `sea_y` + FOAM_ABOVE_M. Renvoie {vertices, normals, colors,
## uvs, indices, built}.
static func build_foam(lines: Array, sea_y: float) -> Dictionary:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var uvs := PackedVector2Array()
	var indices := PackedInt32Array()
	var built := 0
	var y := sea_y + SURFACE_OFFSET_M + FOAM_ABOVE_M
	for l in lines:
		if typeof(l) != TYPE_DICTIONARY:
			continue
		var pts := _line_points(l.get("points", null))
		var n := pts.size()
		if n < 2:
			continue
		var shore := str(l.get("shore", "rock"))
		var width: float = FOAM_WIDTH_M.get(shore, FOAM_WIDTH_M["rock"])
		var min_frac: float = float(FOAM_MIN_M.get(shore, FOAM_MIN_M["rock"])) / width
		var col := Color(min_frac, 0.0, 0.0, 1.0)
		var base := vertices.size()
		var along := 0.0
		for i in range(n):
			var nrm: Vector2
			if i == 0:
				nrm = sea_side(pts[0], pts[1])
			elif i == n - 1:
				nrm = sea_side(pts[n - 2], pts[n - 1])
			else:
				var n0 := sea_side(pts[i - 1], pts[i])
				var n1 := sea_side(pts[i], pts[i + 1])
				var mid := n0 + n1
				if mid.length() < 1e-4:
					nrm = n1
				else:
					mid = mid.normalized()
					nrm = mid / maxf(mid.dot(n1), 1.0 / FOAM_MAX_MITER)   # onglet borné
			if i > 0:
				along += pts[i].distance_to(pts[i - 1])
			var out := pts[i] + nrm * width
			vertices.append(Vector3(pts[i].x, y, pts[i].y))
			vertices.append(Vector3(out.x, y, out.y))
			uvs.append(Vector2(along, 0.0))
			uvs.append(Vector2(along, 1.0))
			for _k in 2:
				normals.append(Vector3.UP)
				colors.append(col)
		for i in range(n - 1):
			var s0 := base + 2 * i
			var s1 := s0 + 2
			# Rivage, large, rivage suivant puis large, large suivant (vus du dessus, sens de water_mesh.gd si la
			# mer est à droite : vérifié par test_sea_mesh.gd sur la normale des triangles).
			indices.append_array([s0, s1, s0 + 1, s1, s1 + 1, s0 + 1])
		built += 1
	indices = _orient_up(vertices, indices)
	return {"vertices": vertices, "normals": normals, "colors": colors, "uvs": uvs, "indices": indices,
		"built": built}


## Met chaque triangle dans le sens de water_mesh.gd (normale géométrique Plane(a, b, c) vers le haut).
static func _orient_up(vertices: PackedVector3Array, src: PackedInt32Array) -> PackedInt32Array:
	var indices := src.duplicate()
	for t in range(0, indices.size(), 3):
		var a := vertices[indices[t]]
		var b := vertices[indices[t + 1]]
		var c := vertices[indices[t + 2]]
		if (b - a).cross(c - a).length_squared() < 1e-12:
			continue
		if Plane(a, b, c).normal.y < 0.0:
			var tmp := indices[t + 1]
			indices[t + 1] = indices[t + 2]
			indices[t + 2] = tmp
	return indices


## Plages drapées sur le terrain : chaque triangle du polygone (trous compris) découpé aux cases de BEACH_CELL_M,
## sommets à `height_at.call(x, z)` + BEACH_ABOVE_M, couleur BEACH_COLORS[kind] (sable : `sand_color` si
## donnée). Renvoie {vertices, normals, colors, uvs, indices, built, skipped}.
static func build_beaches(beaches: Array, height_at: Callable, sand_color: Variant = null) -> Dictionary:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var uvs := PackedVector2Array()
	var indices := PackedInt32Array()
	var built := 0
	var skipped := 0
	var cache := {}
	for b in beaches:
		if typeof(b) != TYPE_DICTIONARY:
			skipped += 1
			continue
		var kind := str(b.get("kind", "sand"))
		var col: Color = BEACH_COLORS.get(kind, BEACH_COLORS["sand"])
		if kind == "sand" and sand_color is Color:
			col = sand_color
		var flat := WaterMesh.build_areas([{"id": str(b.get("id", "plage")), "outer": b.get("outer", null),
			"holes": b.get("holes", []), "level_y": 0.0}])
		if int(flat["built"]) == 0:
			skipped += 1
			continue
		var fv: PackedVector3Array = flat["vertices"]
		var fi: PackedInt32Array = flat["indices"]
		for t in range(0, fi.size(), 3):
			var tri := PackedVector2Array([Vector2(fv[fi[t]].x, fv[fi[t]].z), Vector2(fv[fi[t + 1]].x, fv[fi[t + 1]].z),
				Vector2(fv[fi[t + 2]].x, fv[fi[t + 2]].z)])
			for piece in _clip_to_cells(tri):
				var base := vertices.size()
				for q in piece:
					var key := Vector2i(roundi(q.x * 100.0), roundi(q.y * 100.0))
					if not cache.has(key):
						cache[key] = float(height_at.call(q.x, q.y)) + BEACH_ABOVE_M
					vertices.append(Vector3(q.x, cache[key], q.y))
					normals.append(Vector3.UP)
					colors.append(col)
					uvs.append(q)
				for k in range(1, piece.size() - 1):
					indices.append_array([base, base + k, base + k + 1])
		built += 1
	indices = _orient_up(vertices, indices)
	normals = _smooth_normals(vertices, indices)
	return {"vertices": vertices, "normals": normals, "colors": colors, "uvs": uvs, "indices": indices,
		"built": built, "skipped": skipped}


## Morceaux convexes d'un triangle découpé aux cases de BEACH_CELL_M (polygones d'au moins 3 points).
static func _clip_to_cells(tri: PackedVector2Array) -> Array:
	var lo := Vector2(minf(tri[0].x, minf(tri[1].x, tri[2].x)), minf(tri[0].y, minf(tri[1].y, tri[2].y)))
	var hi := Vector2(maxf(tri[0].x, maxf(tri[1].x, tri[2].x)), maxf(tri[0].y, maxf(tri[1].y, tri[2].y)))
	var out := []
	var c := BEACH_CELL_M
	for i in range(floori(lo.x / c), floori(hi.x / c) + 1):
		for j in range(floori(lo.y / c), floori(hi.y / c) + 1):
			var cell := PackedVector2Array([Vector2(i * c, j * c), Vector2((i + 1) * c, j * c),
				Vector2((i + 1) * c, (j + 1) * c), Vector2(i * c, (j + 1) * c)])
			for piece in Geometry2D.intersect_polygons(tri, cell):
				if (piece as PackedVector2Array).size() >= 3 and absf(WaterMesh.signed_area(piece)) > 1e-4:
					out.append(piece)
	return out


## Normales lissées par sommet (moyenne des faces qui le touchent, même position), vers le haut.
static func _smooth_normals(vertices: PackedVector3Array, indices: PackedInt32Array) -> PackedVector3Array:
	var normals := PackedVector3Array()
	normals.resize(vertices.size())
	var acc := {}
	for t in range(0, indices.size(), 3):
		var a := vertices[indices[t]]
		var b := vertices[indices[t + 1]]
		var c := vertices[indices[t + 2]]
		var fn := (b - a).cross(c - a)
		if fn.y < 0.0:
			fn = -fn
		for k in 3:
			var v := vertices[indices[t + k]]
			var key := Vector2i(roundi(v.x * 100.0), roundi(v.z * 100.0))
			acc[key] = acc.get(key, Vector3.ZERO) + fn
	for i in range(vertices.size()):
		var key := Vector2i(roundi(vertices[i].x * 100.0), roundi(vertices[i].z * 100.0))
		var n: Vector3 = acc.get(key, Vector3.UP)
		normals[i] = n.normalized() if n.length_squared() > 1e-12 else Vector3.UP
	return normals


## Lignes de côte d'une liste `lines` (couche coast) en polylignes x, z.
static func shore_polylines(lines: Array) -> Array:
	var out := []
	for l in lines:
		if typeof(l) == TYPE_DICTIONARY:
			var pts := _line_points(l.get("points", null))
			if pts.size() >= 2:
				out.append(pts)
	return out


## Distance (m) de (x, z) au rivage le plus proche parmi `polylines` (shore_polylines) ; INF sans rivage.
static func shore_distance(polylines: Array, x: float, z: float) -> float:
	var p := Vector2(x, z)
	var best := INF
	for pl in polylines:
		var pts: PackedVector2Array = pl
		for i in range(pts.size() - 1):
			var q := Geometry2D.get_closest_point_to_segment(p, pts[i], pts[i + 1])
			best = minf(best, p.distance_to(q))
	return best
