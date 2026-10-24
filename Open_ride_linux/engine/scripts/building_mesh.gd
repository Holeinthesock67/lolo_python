extends RefCounted

## Maillage 3D des bâtiments extrudés (Lot L1, SRS §8 « Bâtiments », Format .world v1 §3, §6 et §9),
## sans aucun nœud ni affichage. Le rendu (MeshInstance3D, matériaux, niveaux de détail) reste au lot E4.
## Pas de class_name : charger par preload("res://scripts/building_mesh.gd").
##
## Méthode :
## - Orientation : l'anneau extérieur `outer` est orienté avec une aire algébrique positive dans le plan (x, z)
##   (convention antihoraire du compilateur §6 : 0,5 × ∑(x_i z_{i+1} − x_{i+1} z_i) > 0) ; un anneau reçu dans
##   le sens opposé (horaire) est retourné et comptabilisé dans `reversed_rings`. Les trous (`holes`) sont
##   orientés dans le sens opposé (aire algébrique négative).
## - Murs : un quadrilatère indépendant (4 sommets, 2 triangles, arêtes vives) par segment de `outer` et de
##   chaque trou, de `base_y` à `base_y + height_m`. La normale horizontale (dz, 0, −dx) / |(dx, dz)| pointe
##   vers l'extérieur du bâtiment pour `outer` et vers l'intérieur de la cour pour chaque trou.
## - Toit plat : sans trou, triangulation directe par `Geometry2D.triangulate_polygon`. Avec trou(s), chaque
##   trou (trié par abscisse maximale décroissante) est relié à l'anneau courant par un pont sans intersection
##   entre son sommet le plus à droite et un sommet visible du contour, puis triangulé par
##   `Geometry2D.triangulate_polygon`.
## - Couleurs : choisies de façon déterministe dans `buildings.walls` et `buildings.roofs` du thème à partir
##   d'un hachage FNV-1a 32 bits de `id` (aucun appel à randi()).

const DEFAULT_WALL_COLORS := ["#d9c9a3", "#e6d8b8", "#cdb48a"]
const DEFAULT_ROOF_COLORS := ["#a65a3a", "#4d535c"]
const ALLOWED_ROOFS := ["flat", "gabled"]

const MIN_RING_AREA := 1e-3
const DUP_EPS := 1e-4
const BRIDGE_EPS := 1e-5
const MASK32 := 0xFFFFFFFF


## FNV-1a 32 bits sur les octets UTF-8 : hachage déterministe indépendant de la plateforme.
static func hash_string(text: String) -> int:
	var h := 0x811C9DC5
	for byte in text.to_utf8_buffer():
		h = ((h ^ byte) * 0x01000193) & MASK32
	return h


static func _mix(h: int) -> int:
	h = h & MASK32
	h ^= h >> 16
	h = (h * 0x85EBCA6B) & MASK32
	h ^= h >> 13
	h = (h * 0xC2B2AE35) & MASK32
	h ^= h >> 16
	return h


static func _is_number(v: Variant) -> bool:
	return (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and is_finite(float(v))


static func _parse_palette(raw: Variant, fallback: Array) -> Array[Color]:
	var out: Array[Color] = []
	if typeof(raw) == TYPE_ARRAY:
		for item in raw:
			if typeof(item) == TYPE_COLOR:
				out.append(item)
			elif typeof(item) == TYPE_STRING and Color.html_is_valid(item):
				out.append(Color.html(item))
	if out.is_empty():
		for hex in fallback:
			out.append(Color.html(hex))
	return out


## Couleur du mur et couleur du toit tirées de `id` de façon déterministe.
static func colors_for_id(id: String, wall_palette: Array[Color], roof_palette: Array[Color]) -> Array[Color]:
	var h := hash_string(id)
	var wall_idx := posmod(_mix(h ^ 0x27D4EB2D), wall_palette.size())
	var roof_idx := posmod(_mix(h ^ 0x165667B1), roof_palette.size())
	return [wall_palette[wall_idx], roof_palette[roof_idx]]


## Aire algébrique 2D dans le plan (x, z) : > 0 pour un contour extérieur antihoraire (§6).
static func signed_area(ring: PackedVector2Array) -> float:
	var n := ring.size()
	if n < 3:
		return 0.0
	var acc := 0.0
	for i in range(n):
		var a := ring[i]
		var b := ring[(i + 1) % n]
		acc += a.x * b.y - b.x * a.y
	return 0.5 * acc


## Convertit et nettoie un anneau [[x, z], ...] (supprime les doublons consécutifs et la fermeture).
static func _extract_ring(raw: Variant) -> Variant:
	if typeof(raw) != TYPE_ARRAY:
		return null
	var arr: Array = raw
	if arr.size() < 3:
		return null
	var cleaned := PackedVector2Array()
	for pt in arr:
		if typeof(pt) != TYPE_ARRAY or (pt as Array).size() != 2:
			return null
		if not _is_number(pt[0]) or not _is_number(pt[1]):
			return null
		var v := Vector2(float(pt[0]), float(pt[1]))
		if cleaned.is_empty() or cleaned[cleaned.size() - 1].distance_to(v) > DUP_EPS:
			cleaned.append(v)
	if cleaned.size() >= 2 and cleaned[0].distance_to(cleaned[cleaned.size() - 1]) <= DUP_EPS:
		cleaned.resize(cleaned.size() - 1)
	if cleaned.size() < 3:
		return null
	return cleaned


static func _ccw(a: Vector2, b: Vector2, c: Vector2) -> float:
	return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


static func _point_on_segment(p: Vector2, a: Vector2, b: Vector2, eps: float = 1e-5) -> bool:
	var ab := b - a
	var len_sq := ab.length_squared()
	if len_sq <= eps * eps:
		return p.distance_to(a) <= eps
	var cross := absf(_ccw(a, b, p)) / sqrt(len_sq)
	if cross > eps:
		return false
	var dot := (p - a).dot(ab)
	return dot >= -eps and dot <= len_sq + eps


## Vrai si les segments fermés [a, b] et [c, d] se croisent ou se touchent (hors sommet commun d'arêtes adjacentes).
static func _segments_intersect_proper_or_touch(a: Vector2, b: Vector2, c: Vector2, d: Vector2) -> bool:
	var d1 := _ccw(a, b, c)
	var d2 := _ccw(a, b, d)
	var d3 := _ccw(c, d, a)
	var d4 := _ccw(c, d, b)
	if ((d1 > 0.0 and d2 < 0.0) or (d1 < 0.0 and d2 > 0.0)) and ((d3 > 0.0 and d4 < 0.0) or (d3 < 0.0 and d4 > 0.0)):
		return true
	if _point_on_segment(c, a, b) or _point_on_segment(d, a, b) or _point_on_segment(a, c, d) or _point_on_segment(b, c, d):
		return true
	return false


static func _is_self_intersecting(ring: PackedVector2Array) -> bool:
	var n := ring.size()
	if n < 4:
		return false
	for i in range(n):
		var a := ring[i]
		var b := ring[(i + 1) % n]
		for j in range(i + 1, n):
			var c := ring[j]
			var d := ring[(j + 1) % n]
			# Arêtes adjacentes : ne partagent que leur sommet commun
			if j == i + 1:
				if _point_on_segment(d, a, b) or _point_on_segment(a, c, d):
					return true
				continue
			if i == 0 and j == n - 1:
				if _point_on_segment(c, a, b) or _point_on_segment(b, c, d):
					return true
				continue
			if _segments_intersect_proper_or_touch(a, b, c, d):
				return true
	return false


static func _point_strictly_in_ring(p: Vector2, ring: PackedVector2Array) -> bool:
	var n := ring.size()
	for i in range(n):
		if _point_on_segment(p, ring[i], ring[(i + 1) % n], 1e-4):
			return false
	return Geometry2D.is_point_in_polygon(p, ring)


static func _rings_touch_or_cross(r1: PackedVector2Array, r2: PackedVector2Array) -> bool:
	var n1 := r1.size()
	var n2 := r2.size()
	for i in range(n1):
		var a := r1[i]
		var b := r1[(i + 1) % n1]
		for j in range(n2):
			var c := r2[j]
			var d := r2[(j + 1) % n2]
			if _segments_intersect_proper_or_touch(a, b, c, d):
				return true
	return false


static func _reverse_ring(ring: PackedVector2Array) -> PackedVector2Array:
	var n := ring.size()
	var out := PackedVector2Array()
	out.resize(n)
	for i in range(n):
		out[i] = ring[n - 1 - i]
	return out


## Vérifie si le segment ouvert ]a, b[ coupe une arête d'un anneau.
static func _bridge_intersects_ring(a: Vector2, b: Vector2, ring: PackedVector2Array) -> bool:
	var n := ring.size()
	for i in range(n):
		var c := ring[i]
		var d := ring[(i + 1) % n]
		if a.distance_to(c) <= DUP_EPS or a.distance_to(d) <= DUP_EPS or b.distance_to(c) <= DUP_EPS or b.distance_to(d) <= DUP_EPS:
			continue
		if _segments_intersect_proper_or_touch(a, b, c, d):
			return true
	return false


## Relie chaque trou (orienté avec signed_area < 0) au contour extérieur (signed_area > 0) par un pont
## sans intersection, puis triangule le polygone résultant avec Geometry2D.triangulate_polygon.
## Renvoie un tableau de [Vector2, Vector2, Vector2] ou un tableau vide en cas d'échec.
static func _triangulate_with_holes(outer: PackedVector2Array, holes: Array[PackedVector2Array]) -> Array:
	if holes.is_empty():
		var idx := Geometry2D.triangulate_polygon(outer)
		if idx.is_empty() or idx.size() % 3 != 0:
			return []
		var tris := []
		for t in range(0, idx.size(), 3):
			tris.append([outer[idx[t]], outer[idx[t + 1]], outer[idx[t + 2]]])
		return tris

	# Trie les trous par abscisse maximale décroissante
	var hole_order: Array[Dictionary] = []
	for h_i in range(holes.size()):
		var h := holes[h_i]
		var best_k := 0
		for k in range(1, h.size()):
			if h[k].x > h[best_k].x or (is_equal_approx(h[k].x, h[best_k].x) and h[k].y < h[best_k].y):
				best_k = k
		hole_order.append({"hole": h, "right_idx": best_k, "max_x": h[best_k].x})
	hole_order.sort_custom(func(a, b): return a["max_x"] > b["max_x"])

	var poly := outer.duplicate()
	var all_rings: Array[PackedVector2Array] = [outer]
	for h in holes:
		all_rings.append(h)

	for item in hole_order:
		var hole: PackedVector2Array = item["hole"]
		var h_idx: int = item["right_idx"]
		var h_pt: Vector2 = hole[h_idx]

		# Cherche un sommet de `poly` visible depuis `h_pt` sans couper aucun anneau
		var best_o := -1
		var best_score := INF
		for o_i in range(poly.size()):
			var o_pt := poly[o_i]
			if o_pt.distance_to(h_pt) <= DUP_EPS:
				continue
			var blocked := false
			if _bridge_intersects_ring(h_pt, o_pt, poly):
				blocked = true
			if not blocked:
				for r in all_rings:
					if _bridge_intersects_ring(h_pt, o_pt, r):
						blocked = true
						break
			if blocked:
				continue
			var mid := (h_pt + o_pt) * 0.5
			if not Geometry2D.is_point_in_polygon(mid, outer):
				continue
			var in_any_hole := false
			for h_other in holes:
				if Geometry2D.is_point_in_polygon(mid, h_other):
					in_any_hole = true
					break
			if in_any_hole:
				continue
			# Privilégie les sommets à droite de h_pt et proches
			var penalty := 0.0 if o_pt.x >= h_pt.x - 1e-4 else 1e6
			var score := penalty + h_pt.distance_to(o_pt)
			if score < best_score:
				best_score = score
				best_o = o_i

		if best_o < 0:
			return []

		var o_pt := poly[best_o]
		var dir := (o_pt - h_pt).normalized()
		# Léger décalage perpendiculaire du brin retour du pont pour éviter deux sommets confondus
		var perp := Vector2(-dir.y, dir.x) * BRIDGE_EPS

		var merged := PackedVector2Array()
		for i in range(best_o + 1):
			merged.append(poly[i])
		for k in range(hole.size()):
			merged.append(hole[(h_idx + k) % hole.size()])
		merged.append(h_pt + perp)
		merged.append(o_pt + perp)
		for i in range(best_o + 1, poly.size()):
			merged.append(poly[i])
		poly = merged

	var indices := Geometry2D.triangulate_polygon(poly)
	if indices.is_empty() or indices.size() % 3 != 0:
		return []
	var out_tris := []
	for t in range(0, indices.size(), 3):
		var a := poly[indices[t]]
		var b := poly[indices[t + 1]]
		var c := poly[indices[t + 2]]
		var area2 := absf(_ccw(a, b, c))
		if area2 <= 1e-7:
			continue
		out_tris.append([a, b, c])
	return out_tris


static func _append_wall_ring(
	ring: PackedVector2Array,
	base_y: float,
	top_y: float,
	wall_color: Color,
	vertices: PackedVector3Array,
	normals: PackedVector3Array,
	colors: PackedColorArray,
	indices: PackedInt32Array
) -> void:
	var n := ring.size()
	for i in range(n):
		var p0 := ring[i]
		var p1 := ring[(i + 1) % n]
		var dx := p1.x - p0.x
		var dz := p1.y - p0.y
		var seg_len := sqrt(dx * dx + dz * dz)
		if seg_len <= DUP_EPS:
			continue
		# Avec `outer` d'aire > 0 (et `hole` d'aire < 0), (dz, 0, -dx) pointe vers l'extérieur (ou dans la cour).
		var normal := Vector3(dz / seg_len, 0.0, -dx / seg_len)
		var v_base := vertices.size()
		vertices.append(Vector3(p0.x, base_y, p0.y))
		vertices.append(Vector3(p1.x, base_y, p1.y))
		vertices.append(Vector3(p1.x, top_y, p1.y))
		vertices.append(Vector3(p0.x, top_y, p0.y))
		for _k in range(4):
			normals.append(normal)
			colors.append(wall_color)
		# Sens horaire vu de l'extérieur (convention de face avant de Godot)
		indices.append(v_base)
		indices.append(v_base + 1)
		indices.append(v_base + 2)
		indices.append(v_base)
		indices.append(v_base + 2)
		indices.append(v_base + 3)


## Construit les tableaux de maillage pour la liste de bâtiments d'un tronçon.
static func build(buildings: Array, theme: Dictionary) -> Dictionary:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var indices := PackedInt32Array()
	var errors := PackedStringArray()
	var built := 0
	var skipped := 0
	var reversed_rings := 0
	var gabled_as_flat := 0

	var b_theme: Dictionary = {}
	if typeof(theme) == TYPE_DICTIONARY and typeof(theme.get("buildings", null)) == TYPE_DICTIONARY:
		b_theme = theme["buildings"]
	var wall_palette := _parse_palette(b_theme.get("walls", null), DEFAULT_WALL_COLORS)
	var roof_palette := _parse_palette(b_theme.get("roofs", null), DEFAULT_ROOF_COLORS)

	for idx_b in range(buildings.size()):
		var item = buildings[idx_b]
		if typeof(item) != TYPE_DICTIONARY:
			skipped += 1
			errors.append("bâtiment #%d : élément non dictionnaire" % idx_b)
			continue
		var b: Dictionary = item
		var id_raw = b.get("id", null)
		var b_id := str(id_raw) if (typeof(id_raw) == TYPE_STRING and not (id_raw as String).is_empty()) else ""
		if b_id.is_empty():
			skipped += 1
			errors.append("bâtiment #%d : identifiant `id` manquant ou vide" % idx_b)
			continue

		var base_y_raw = b.get("base_y", null)
		var height_raw = b.get("height_m", null)
		if not _is_number(base_y_raw) or not _is_number(height_raw) or float(height_raw) <= 0.0:
			skipped += 1
			errors.append("%s : `base_y` ou `height_m` invalide" % b_id)
			continue
		var base_y := float(base_y_raw)
		var height_m := float(height_raw)
		var top_y := base_y + height_m

		var roof_kind := str(b.get("roof", "flat"))
		if b.has("roof") and not (roof_kind in ALLOWED_ROOFS):
			skipped += 1
			errors.append("%s : type de toit %s inconnu" % [b_id, roof_kind])
			continue

		var outer_var = _extract_ring(b.get("outer", null))
		if outer_var == null:
			skipped += 1
			errors.append("%s : anneau `outer` invalide (moins de 3 points numériques distincts)" % b_id)
			continue
		var outer: PackedVector2Array = outer_var
		var area_outer := signed_area(outer)
		if absf(area_outer) < MIN_RING_AREA:
			skipped += 1
			errors.append("%s : anneau `outer` d'aire nulle ou quasi nulle" % b_id)
			continue
		if _is_self_intersecting(outer):
			skipped += 1
			errors.append("%s : anneau `outer` auto-intersecté" % b_id)
			continue

		var was_reversed := false
		if area_outer < 0.0:
			outer = _reverse_ring(outer)
			was_reversed = true

		var holes_raw = b.get("holes", [])
		if typeof(holes_raw) != TYPE_ARRAY:
			skipped += 1
			errors.append("%s : champ `holes` invalide" % b_id)
			continue

		var holes: Array[PackedVector2Array] = []
		var hole_invalid := false
		for h_raw in holes_raw:
			var h_var = _extract_ring(h_raw)
			if h_var == null:
				hole_invalid = true
				errors.append("%s : trou invalide (moins de 3 points)" % b_id)
				break
			var h_ring: PackedVector2Array = h_var
			var area_h := signed_area(h_ring)
			if absf(area_h) < MIN_RING_AREA or _is_self_intersecting(h_ring):
				hole_invalid = true
				errors.append("%s : trou dégénéré ou auto-intersecté" % b_id)
				break
			# Chaque sommet du trou doit être strictement dans `outer` et aucune arête ne doit toucher `outer`
			for pt in h_ring:
				if not _point_strictly_in_ring(pt, outer):
					hole_invalid = true
					break
			if hole_invalid or _rings_touch_or_cross(outer, h_ring):
				hole_invalid = true
				errors.append("%s : trou hors de `outer` ou touchant le bord" % b_id)
				break
			for prev_h in holes:
				if _rings_touch_or_cross(prev_h, h_ring) or Geometry2D.is_point_in_polygon(h_ring[0], prev_h) or Geometry2D.is_point_in_polygon(prev_h[0], h_ring):
					hole_invalid = true
					break
			if hole_invalid:
				errors.append("%s : trous qui se chevauchent ou se touchent" % b_id)
				break
			if area_h > 0.0:
				h_ring = _reverse_ring(h_ring)
			holes.append(h_ring)

		if hole_invalid:
			skipped += 1
			continue

		var roof_tris := _triangulate_with_holes(outer, holes)
		if roof_tris.is_empty():
			skipped += 1
			errors.append("%s : triangulation du toit impossible" % b_id)
			continue

		if was_reversed:
			reversed_rings += 1
		if roof_kind == "gabled":
			gabled_as_flat += 1

		var pair := colors_for_id(b_id, wall_palette, roof_palette)
		var wall_color := pair[0]
		var roof_color := pair[1]

		_append_wall_ring(outer, base_y, top_y, wall_color, vertices, normals, colors, indices)
		for h_ring in holes:
			_append_wall_ring(h_ring, base_y, top_y, wall_color, vertices, normals, colors, indices)

		for tri in roof_tris:
			var a2: Vector2 = tri[0]
			var b2: Vector2 = tri[1]
			var c2: Vector2 = tri[2]
			# Dans Godot, Plane(A, B, C).normal pointe vers +y quand (b - a) × (c - a) > 0 en (x, z)
			if _ccw(a2, b2, c2) < 0.0:
				var tmp := b2
				b2 = c2
				c2 = tmp
			var r_base := vertices.size()
			vertices.append(Vector3(a2.x, top_y, a2.y))
			vertices.append(Vector3(b2.x, top_y, b2.y))
			vertices.append(Vector3(c2.x, top_y, c2.y))
			for _k in range(3):
				normals.append(Vector3.UP)
				colors.append(roof_color)
			indices.append(r_base)
			indices.append(r_base + 1)
			indices.append(r_base + 2)

		built += 1

	return {
		"vertices": vertices,
		"normals": normals,
		"colors": colors,
		"indices": indices,
		"built": built,
		"skipped": skipped,
		"errors": errors,
		"reversed_rings": reversed_rings,
		"gabled_as_flat": gabled_as_flat,
	}
