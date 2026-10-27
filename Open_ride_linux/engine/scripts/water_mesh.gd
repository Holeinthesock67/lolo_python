extends RefCounted

## Maillage 3D de la couche `water` : cours d'eau en ruban (`lines`) et plans d'eau avec îles (`areas`)
## (Lot L2, SRS §13, Format .world v1 §3 et §8), sans aucun nœud ni affichage.
## Pas de class_name : charger par preload("res://scripts/water_mesh.gd").
##
## Note : la triangulation des polygones à trous (`_triangulate_with_holes`) suit la même couture par ponts
## que `building_mesh.gd` (lot L1) et pourra être factorisée après la fusion des deux lots.

const DEFAULT_WIDTH_M := 2.0
const SURFACE_OFFSET_M := 0.05
const MAX_MITER_FACTOR := 2.0
const MIN_RING_AREA := 1e-3
const DUP_EPS := 1e-4
const BRIDGE_EPS := 1e-5

# Matériau de l'eau (Lot P12) : mêmes valeurs que celui d'osm_streamer.gd (E4) ; `shimmer` ajoute les
# reflets animés de shaders/water_shimmer.gdshader, seulement si `living(preset).water_shimmer`.
const WATER_COLOR := Color(0.12, 0.32, 0.38, 1.0)
const WATER_ROUGHNESS := 0.10
const SHIMMER_FLOW_BASE_MPS := 0.05     # défilement des ondes par vent nul
const SHIMMER_FLOW_PER_STRENGTH := 0.6  # en plus, par unité de force du vent (1 = 60 km/h)


## Matériau de l'eau : sans `shimmer`, le StandardMaterial3D d'E4 inchangé ; avec, le shader de reflets.
static func make_material(shimmer: bool) -> Material:
	if not shimmer:
		var m := StandardMaterial3D.new()
		m.albedo_color = WATER_COLOR
		m.roughness = WATER_ROUGHNESS
		return m
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/water_shimmer.gdshader")
	sm.set_shader_parameter("albedo", Color(WATER_COLOR.r, WATER_COLOR.g, WATER_COLOR.b))
	sm.set_shader_parameter("roughness_base", WATER_ROUGHNESS)
	sm.set_shader_parameter("flow", Vector2.ZERO)
	return sm


## Une image : fait défiler les ondes du matériau `shimmer` dans le sens du vent (`{dir, strength}` de
## wind_model.gd). Sans effet sur le matériau sans reflets.
static func update_shimmer(mat: Material, wind: Dictionary, dt_s: float) -> void:
	if not (mat is ShaderMaterial):
		return
	var dir: Vector3 = wind.get("dir", Vector3.ZERO)
	var strength := clampf(float(wind.get("strength", 0.0)), 0.0, 1.0)
	var d2 := Vector2(dir.x, dir.z)
	d2 = d2.normalized() if d2.length() > 1e-3 else Vector2(0.7071, 0.7071)
	var raw = mat.get_shader_parameter("flow")
	var flow: Vector2 = raw if typeof(raw) == TYPE_VECTOR2 else Vector2.ZERO
	flow += d2 * (SHIMMER_FLOW_BASE_MPS + SHIMMER_FLOW_PER_STRENGTH * strength) * dt_s
	# Replié modulo 200π : tous les termes des ondes du shader avancent alors d'un multiple entier de 2π
	# (coefficients 0,6 ; 0,4 ; 1,3 ; 1,1 ; 0,7 sur 200π et 120π), donc sans saut, et la précision reste.
	flow = Vector2(fposmod(flow.x, TAU * 100.0), fposmod(flow.y, TAU * 100.0))
	mat.set_shader_parameter("flow", flow)
	mat.set_shader_parameter("strength", strength)


static func _is_number(v: Variant) -> bool:
	return (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and is_finite(float(v))


static func _ccw(a: Vector2, b: Vector2, c: Vector2) -> float:
	return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


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


static func _reverse_ring(ring: PackedVector2Array) -> PackedVector2Array:
	var n := ring.size()
	var out := PackedVector2Array()
	out.resize(n)
	for i in range(n):
		out[i] = ring[n - 1 - i]
	return out


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


static func _triangulate_with_holes(outer: PackedVector2Array, holes: Array[PackedVector2Array]) -> Array:
	if holes.is_empty():
		var idx := Geometry2D.triangulate_polygon(outer)
		if idx.is_empty() or idx.size() % 3 != 0:
			return []
		var tris := []
		for t in range(0, idx.size(), 3):
			tris.append([outer[idx[t]], outer[idx[t + 1]], outer[idx[t + 2]]])
		return tris

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

		var best_o := -1
		var best_score := INF
		for o_i in range(poly.size()):
			var o_pt := poly[o_i]
			if o_pt.distance_to(h_pt) <= DUP_EPS:
				continue
			var blocked := _bridge_intersects_ring(h_pt, o_pt, poly)
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
			var penalty := 0.0 if o_pt.x >= h_pt.x - 1e-4 else 1e6
			var score := penalty + h_pt.distance_to(o_pt)
			if score < best_score:
				best_score = score
				best_o = o_i

		if best_o < 0:
			return []

		var o_pt := poly[best_o]
		var dir := (o_pt - h_pt).normalized()
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
		if absf(_ccw(a, b, c)) <= 1e-7:
			continue
		out_tris.append([a, b, c])
	return out_tris


## Construit les rubans de cours d'eau (`lines` : points [x, z, y], `width_m` à 2 m par défaut).
static func build_lines(lines: Array) -> Dictionary:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var indices := PackedInt32Array()
	var errors := PackedStringArray()
	var built := 0
	var skipped := 0

	for idx_l in range(lines.size()):
		var item = lines[idx_l]
		if typeof(item) != TYPE_DICTIONARY:
			skipped += 1
			errors.append("cours d'eau #%d : élément non dictionnaire" % idx_l)
			continue
		var l: Dictionary = item
		var l_id := str(l.get("id", "line_%d" % idx_l))
		if typeof(l.get("id", "x")) != TYPE_STRING or l_id.is_empty():
			skipped += 1
			errors.append("cours d'eau #%d : `id` manquant ou vide" % idx_l)
			continue

		var width_m := DEFAULT_WIDTH_M
		if l.has("width_m") and l["width_m"] != null:
			if not _is_number(l["width_m"]) or float(l["width_m"]) <= 0.0:
				skipped += 1
				errors.append("%s : `width_m` invalide" % l_id)
				continue
			width_m = float(l["width_m"])
		var half_w := width_m * 0.5

		var pts_raw = l.get("points", null)
		if typeof(pts_raw) != TYPE_ARRAY or (pts_raw as Array).size() < 2:
			skipped += 1
			errors.append("%s : moins de 2 points" % l_id)
			continue

		var pts_xz := PackedVector2Array()
		var pts_y := PackedFloat64Array()
		var bad_pt := false
		for pt in pts_raw:
			if typeof(pt) != TYPE_ARRAY or (pt as Array).size() != 3:
				bad_pt = true
				break
			if not _is_number(pt[0]) or not _is_number(pt[1]) or not _is_number(pt[2]):
				bad_pt = true
				break
			var xz := Vector2(float(pt[0]), float(pt[1]))
			var y := float(pt[2])
			# Ignore les points confondus consécutifs
			if not pts_xz.is_empty() and pts_xz[pts_xz.size() - 1].distance_to(xz) <= DUP_EPS:
				continue
			pts_xz.append(xz)
			pts_y.append(y)

		if bad_pt or pts_xz.size() < 2:
			skipped += 1
			errors.append("%s : points invalides ou moins de 2 points distincts" % l_id)
			continue

		var m := pts_xz.size()
		var seg_dirs := PackedVector2Array()
		var seg_lens := PackedFloat64Array()
		seg_dirs.resize(m - 1)
		seg_lens.resize(m - 1)
		for i in range(m - 1):
			var d := pts_xz[i + 1] - pts_xz[i]
			seg_lens[i] = d.length()
			seg_dirs[i] = d / seg_lens[i]

		var v_base := vertices.size()
		var cum_u := 0.0
		for i in range(m):
			if i > 0:
				cum_u += seg_lens[i - 1]
			var right_vec: Vector2
			var miter_scale := 1.0
			if i == 0:
				var d0 := seg_dirs[0]
				right_vec = Vector2(-d0.y, d0.x)
			elif i == m - 1:
				var dm := seg_dirs[m - 2]
				right_vec = Vector2(-dm.y, dm.x)
			else:
				var d_prev := seg_dirs[i - 1]
				var d_next := seg_dirs[i]
				var r_prev := Vector2(-d_prev.y, d_prev.x)
				var r_next := Vector2(-d_next.y, d_next.x)
				var avg_r := r_prev + r_next
				if avg_r.length_squared() <= 1e-8:
					right_vec = r_prev
					miter_scale = 1.0
				else:
					right_vec = avg_r.normalized()
					var cos_half := maxf(absf(right_vec.dot(r_prev)), 1.0 / MAX_MITER_FACTOR)
					miter_scale = clampf(1.0 / cos_half, 1.0, MAX_MITER_FACTOR)
				# Évite le repliement intérieur si un segment adjacent est très court
				var min_adj := minf(seg_lens[i - 1], seg_lens[i])
				if half_w * miter_scale > min_adj * 0.48:
					miter_scale = maxf(1.0, (min_adj * 0.48) / maxf(half_w, 1e-6))
					miter_scale = minf(miter_scale, MAX_MITER_FACTOR)

			var offset := right_vec * (half_w * miter_scale)
			var p := pts_xz[i]
			var y_surf := pts_y[i] + SURFACE_OFFSET_M
			var left_p := p - offset
			var right_p := p + offset

			vertices.append(Vector3(left_p.x, y_surf, left_p.y))
			vertices.append(Vector3(right_p.x, y_surf, right_p.y))
			normals.append(Vector3.UP)
			normals.append(Vector3.UP)
			uvs.append(Vector2(cum_u, 0.0))
			uvs.append(Vector2(cum_u, 1.0))

		for i in range(m - 1):
			var l0 := v_base + i * 2
			var r0 := l0 + 1
			var l1 := l0 + 2
			var r1 := l0 + 3
			# Vérifie que chaque triangle a sa normale tournée vers le haut (+y)
			var a1 := Vector2(vertices[l0].x, vertices[l0].z)
			var b1 := Vector2(vertices[l1].x, vertices[l1].z)
			var c1 := Vector2(vertices[r0].x, vertices[r0].z)
			if _ccw(a1, b1, c1) >= 0.0:
				indices.append(l0)
				indices.append(l1)
				indices.append(r0)
			else:
				indices.append(l0)
				indices.append(r0)
				indices.append(l1)

			var a2 := Vector2(vertices[r0].x, vertices[r0].z)
			var b2 := Vector2(vertices[l1].x, vertices[l1].z)
			var c2 := Vector2(vertices[r1].x, vertices[r1].z)
			if _ccw(a2, b2, c2) >= 0.0:
				indices.append(r0)
				indices.append(l1)
				indices.append(r1)
			else:
				indices.append(r0)
				indices.append(r1)
				indices.append(l1)

		built += 1

	return {
		"vertices": vertices,
		"normals": normals,
		"uvs": uvs,
		"indices": indices,
		"built": built,
		"skipped": skipped,
		"errors": errors,
	}


## Construit les surfaces planes des plans d'eau (`areas` : `outer`, `holes`, `level_y`).
static func build_areas(areas: Array) -> Dictionary:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var indices := PackedInt32Array()
	var errors := PackedStringArray()
	var built := 0
	var skipped := 0

	for idx_a in range(areas.size()):
		var item = areas[idx_a]
		if typeof(item) != TYPE_DICTIONARY:
			skipped += 1
			errors.append("plan d'eau #%d : élément non dictionnaire" % idx_a)
			continue
		var a: Dictionary = item
		var a_id := str(a.get("id", "area_%d" % idx_a))
		if typeof(a.get("id", "x")) != TYPE_STRING or a_id.is_empty():
			skipped += 1
			errors.append("plan d'eau #%d : `id` manquant ou vide" % idx_a)
			continue

		var level_raw = a.get("level_y", null)
		if not _is_number(level_raw):
			skipped += 1
			errors.append("%s : `level_y` absent ou non numérique" % a_id)
			continue
		var level_y := float(level_raw)

		var outer_var = _extract_ring(a.get("outer", null))
		if outer_var == null:
			skipped += 1
			errors.append("%s : anneau `outer` invalide" % a_id)
			continue
		var outer: PackedVector2Array = outer_var
		var area_outer := signed_area(outer)
		if absf(area_outer) < MIN_RING_AREA or _is_self_intersecting(outer):
			skipped += 1
			errors.append("%s : anneau `outer` dégénéré ou auto-intersecté" % a_id)
			continue
		if area_outer < 0.0:
			outer = _reverse_ring(outer)

		var holes_raw = a.get("holes", [])
		if typeof(holes_raw) != TYPE_ARRAY:
			skipped += 1
			errors.append("%s : champ `holes` invalide" % a_id)
			continue

		var holes: Array[PackedVector2Array] = []
		var hole_invalid := false
		for h_raw in holes_raw:
			var h_var = _extract_ring(h_raw)
			if h_var == null:
				hole_invalid = true
				errors.append("%s : île (`hole`) invalide" % a_id)
				break
			var h_ring: PackedVector2Array = h_var
			var area_h := signed_area(h_ring)
			if absf(area_h) < MIN_RING_AREA or _is_self_intersecting(h_ring):
				hole_invalid = true
				errors.append("%s : île dégénérée ou auto-intersectée" % a_id)
				break
			for pt in h_ring:
				if not _point_strictly_in_ring(pt, outer):
					hole_invalid = true
					break
			if hole_invalid or _rings_touch_or_cross(outer, h_ring):
				hole_invalid = true
				errors.append("%s : île hors de `outer` ou touchant la rive" % a_id)
				break
			for prev_h in holes:
				if _rings_touch_or_cross(prev_h, h_ring) or Geometry2D.is_point_in_polygon(h_ring[0], prev_h) or Geometry2D.is_point_in_polygon(prev_h[0], h_ring):
					hole_invalid = true
					break
			if hole_invalid:
				errors.append("%s : îles qui se chevauchent" % a_id)
				break
			if area_h > 0.0:
				h_ring = _reverse_ring(h_ring)
			holes.append(h_ring)

		if hole_invalid:
			skipped += 1
			continue

		var tris := _triangulate_with_holes(outer, holes)
		if tris.is_empty():
			skipped += 1
			errors.append("%s : triangulation du plan d'eau impossible" % a_id)
			continue

		for tri in tris:
			var p0: Vector2 = tri[0]
			var p1: Vector2 = tri[1]
			var p2: Vector2 = tri[2]
			if _ccw(p0, p1, p2) < 0.0:
				var tmp := p1
				p1 = p2
				p2 = tmp
			var base_idx := vertices.size()
			vertices.append(Vector3(p0.x, level_y, p0.y))
			vertices.append(Vector3(p1.x, level_y, p1.y))
			vertices.append(Vector3(p2.x, level_y, p2.y))
			for _k in range(3):
				normals.append(Vector3.UP)
			uvs.append(p0)
			uvs.append(p1)
			uvs.append(p2)
			indices.append(base_idx)
			indices.append(base_idx + 1)
			indices.append(base_idx + 2)

		built += 1

	return {
		"vertices": vertices,
		"normals": normals,
		"uvs": uvs,
		"indices": indices,
		"built": built,
		"skipped": skipped,
		"errors": errors,
	}
