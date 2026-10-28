extends RefCounted

## Maillage 3D des bâtiments extrudés (Lot L1, SRS §8 « Bâtiments », Format .world v1 §3, §6 et §9),
## sans aucun nœud ni affichage, et habillage (Lot Y8 : toits à pans, matières et ouvertures pour le shader).
## Pas de class_name : charger par preload("res://scripts/building_mesh.gd").
##
## Méthode :
## - Orientation : l'anneau extérieur `outer` est orienté avec une aire algébrique positive dans le plan (x, z)
##   (convention antihoraire du compilateur §6 : 0,5 × ∑(x_i z_{i+1} − x_{i+1} z_i) > 0) ; un anneau reçu dans
##   le sens opposé (horaire) est retourné et comptabilisé dans `reversed_rings`. Les trous (`holes`) sont
##   orientés dans le sens opposé (aire algébrique négative).
## - Murs : un quadrilatère (4 sommets, 2 triangles, arêtes vives) par segment de `outer` et de chaque trou,
##   de `base_y - skirt` jusqu'au toit ; un segment est coupé là où le pan du toit qui le surmonte change
##   (pignons, croupes). La normale horizontale (dz, 0, −dx) / |(dx, dz)| pointe vers l'extérieur du bâtiment
##   pour `outer` et vers l'intérieur de la cour pour chaque trou.
## - Toit (Lot Y8) : le contour est triangulé comme un toit plat (`Geometry2D.triangulate_polygon` ; avec
##   trou(s), chaque trou, trié par abscisse maximale décroissante, est relié à l'anneau courant par un pont
##   sans intersection). Les triangles sont ensuite découpés par les pans (plans) du toit et relevés : la
##   hauteur du toit est le minimum des plans, nulle au bord du rectangle orienté du contour. Forme (plat, deux
##   pans, croupes) et pente viennent de building_styles.gd (style de la variante, famille du type OSM, forme
##   du contour). La couche ne donne que `flat` (non renseigné) ou `gabled` (deux pans imposés).
## - Couleurs : choisies de façon déterministe dans `buildings.walls` et `buildings.roofs` du thème (enduit,
##   tuiles) ou dans les palettes des matières de building_styles.gd, à partir d'un hachage FNV-1a 32 bits de
##   `id` (aucun appel à randi()) ; `hint.colour` d'OSM remplace la couleur du mur. L'alpha porte la graine du
##   bâtiment. UV : mètres sur chaque face ; UV2 : longueur du segment de mur et code d'habillage, lus par
##   `shaders/building.gdshader` (fenêtres, volets, briques, colombages, tuiles…).

const BuildingStyles := preload("res://scripts/building_styles.gd")

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


## Rectangle orienté d'aire minimale de l'anneau (calipers tournants sur l'enveloppe convexe) :
## {center, axis (grand côté, unitaire), half_len, half_width}.
static func oriented_box(ring: PackedVector2Array) -> Dictionary:
	var hull := Geometry2D.convex_hull(ring)
	var best := {}
	var best_area := INF
	var n := hull.size()
	for i in range(n):
		var e := hull[(i + 1) % n] - hull[i]
		if e.length_squared() <= DUP_EPS * DUP_EPS:
			continue
		var d := e.normalized()
		var p := Vector2(-d.y, d.x)
		var min_d := INF
		var max_d := -INF
		var min_p := INF
		var max_p := -INF
		for q in hull:
			var a := q.dot(d)
			var b := q.dot(p)
			min_d = minf(min_d, a)
			max_d = maxf(max_d, a)
			min_p = minf(min_p, b)
			max_p = maxf(max_p, b)
		var area := (max_d - min_d) * (max_p - min_p)
		if area < best_area - 1e-6:
			best_area = area
			var center := d * (min_d + max_d) * 0.5 + p * (min_p + max_p) * 0.5
			if max_d - min_d >= max_p - min_p:
				best = {"center": center, "axis": d, "half_len": (max_d - min_d) * 0.5, "half_width": (max_p - min_p) * 0.5}
			else:
				best = {"center": center, "axis": p, "half_len": (max_p - min_p) * 0.5, "half_width": (max_d - min_d) * 0.5}
	return best


## Plans du toit : chaque plan est Vector3(a, b, c), hauteur au-dessus des murs a·x + b·z + c ; la surface
## du toit est le minimum des plans (fonction concave affine par morceaux, nulle au bord du rectangle orienté).
## Toit plat : un plan nul ; à deux pans : deux plans de part et d'autre du faîtage ; à croupes : quatre.
static func roof_planes(shape: String, pitch_deg: float, box: Dictionary) -> Array[Vector3]:
	var planes: Array[Vector3] = []
	if shape == BuildingStyles.SHAPE_FLAT or box.is_empty() or pitch_deg <= 0.0:
		planes.append(Vector3.ZERO)
		return planes
	var s := tan(deg_to_rad(pitch_deg))
	var c: Vector2 = box["center"]
	var d: Vector2 = box["axis"]
	var p := Vector2(-d.y, d.x)
	var hw: float = box["half_width"]
	var hl: float = box["half_len"]
	# s × (hw − p·(x − c)) et s × (hw + p·(x − c))
	planes.append(Vector3(-s * p.x, -s * p.y, s * (hw + p.dot(c))))
	planes.append(Vector3(s * p.x, s * p.y, s * (hw - p.dot(c))))
	if shape == BuildingStyles.SHAPE_HIPPED:
		planes.append(Vector3(-s * d.x, -s * d.y, s * (hl + d.dot(c))))
		planes.append(Vector3(s * d.x, s * d.y, s * (hl - d.dot(c))))
	return planes


static func _plane_at(pl: Vector3, q: Vector2) -> float:
	return pl.x * q.x + pl.y * q.y + pl.z


static func roof_height(planes: Array[Vector3], q: Vector2) -> float:
	var h := INF
	for pl in planes:
		h = minf(h, _plane_at(pl, q))
	return maxf(h, 0.0)


## Garde la partie du polygone convexe `poly` où g(q) = gx·x + gz·z + gc ≤ 0 (Sutherland-Hodgman).
static func _clip_half(poly: PackedVector2Array, g: Vector3) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n := poly.size()
	for i in range(n):
		var a := poly[i]
		var b := poly[(i + 1) % n]
		var ga := _plane_at(g, a)
		var gb := _plane_at(g, b)
		if ga <= 1e-9:
			out.append(a)
		if (ga < -1e-9 and gb > 1e-9) or (ga > 1e-9 and gb < -1e-9):
			out.append(a.lerp(b, ga / (ga - gb)))
	return out


## Code d'habillage lu par building.gdshader dans UV2.y : matière du mur, ouvertures, matière du toit,
## partie (0 mur, 1 toit) et hauteur des murs au quart de mètre (fenêtres sous l'égout seulement).
static func dress_code(dress: Dictionary, is_roof: bool, height_m: float) -> float:
	var eave_q := clampi(roundi(height_m * 4.0), 0, 4000)
	return float(int(dress["wall"]) + 8 * int(dress["windows"]) + 64 * int(dress["roof"]) + 512 * int(is_roof) + 1024 * eave_q)


## Murs d'un anneau : un quadrilatère par morceau de segment, de `base_y - skirt` jusqu'au toit (le haut suit
## les pignons et les croupes : chaque segment est coupé là où le plan du toit le plus bas change).
## UV : u le long du segment depuis son début, v hauteur au-dessus de `base_y` (mètres) ; UV2 : longueur du
## segment et code d'habillage.
static func _append_wall_ring(ring: PackedVector2Array, base_y: float, wall_base_y: float, top_y: float,
		planes: Array[Vector3], wall_color: Color, code: float, out: Dictionary) -> void:
	var vertices: PackedVector3Array = out["vertices"]
	var normals: PackedVector3Array = out["normals"]
	var colors: PackedColorArray = out["colors"]
	var uvs: PackedVector2Array = out["uvs"]
	var uvs2: PackedVector2Array = out["uvs2"]
	var indices: PackedInt32Array = out["indices"]
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
		# Coupures : changements du plan le plus bas le long du segment
		var cuts: Array[float] = [0.0, 1.0]
		for a in range(planes.size()):
			for b in range(a + 1, planes.size()):
				var g0 := _plane_at(planes[a], p0) - _plane_at(planes[b], p0)
				var g1 := _plane_at(planes[a], p1) - _plane_at(planes[b], p1)
				if (g0 < 0.0 and g1 > 0.0) or (g0 > 0.0 and g1 < 0.0):
					cuts.append(g0 / (g0 - g1))
		if cuts.size() > 2:
			cuts.sort()
		for c in range(cuts.size() - 1):
			var t0: float = cuts[c]
			var t1: float = cuts[c + 1]
			if (t1 - t0) * seg_len <= 1e-3:
				continue
			var q0 := p0.lerp(p1, t0)
			var q1 := p0.lerp(p1, t1)
			var y0 := top_y + roof_height(planes, q0)
			var y1 := top_y + roof_height(planes, q1)
			var v_base := vertices.size()
			vertices.append(Vector3(q0.x, wall_base_y, q0.y))
			vertices.append(Vector3(q1.x, wall_base_y, q1.y))
			vertices.append(Vector3(q1.x, y1, q1.y))
			vertices.append(Vector3(q0.x, y0, q0.y))
			uvs.append(Vector2(t0 * seg_len, wall_base_y - base_y))
			uvs.append(Vector2(t1 * seg_len, wall_base_y - base_y))
			uvs.append(Vector2(t1 * seg_len, y1 - base_y))
			uvs.append(Vector2(t0 * seg_len, y0 - base_y))
			for _k in range(4):
				normals.append(normal)
				colors.append(wall_color)
				uvs2.append(Vector2(seg_len, code))
			# Sens horaire vu de l'extérieur (convention de face avant de Godot)
			indices.append(v_base)
			indices.append(v_base + 1)
			indices.append(v_base + 2)
			indices.append(v_base)
			indices.append(v_base + 2)
			indices.append(v_base + 3)


## Toit : chaque triangle de la triangulation du contour est découpé selon les plans (zone où chaque plan est le
## plus bas), puis relevé. UV : mètres le long de l'égout et en remontant la pente (rangs de tuiles), ou (x, z)
## pour un toit plat ; UV2.y : code d'habillage.
static func _append_roof(roof_tris: Array, top_y: float, planes: Array[Vector3], roof_color: Color, code: float,
		out: Dictionary) -> void:
	var n_planes := planes.size()
	for tri in roof_tris:
		var a2: Vector2 = tri[0]
		var b2: Vector2 = tri[1]
		var c2: Vector2 = tri[2]
		var ia := _lowest_plane(planes, a2)
		# Triangle entier sous un même pan : pas de découpe
		if ia == _lowest_plane(planes, b2) and ia == _lowest_plane(planes, c2):
			_emit_roof_poly(PackedVector2Array([a2, b2, c2]), planes[ia], n_planes > 1, top_y, roof_color, code, out)
			continue
		for i in range(n_planes):
			var poly := PackedVector2Array([a2, b2, c2])
			for j in range(n_planes):
				if j != i and poly.size() >= 3:
					poly = _clip_half(poly, planes[i] - planes[j])
			if poly.size() >= 3:
				_emit_roof_poly(poly, planes[i], n_planes > 1, top_y, roof_color, code, out)


static func _lowest_plane(planes: Array[Vector3], q: Vector2) -> int:
	var best := 0
	var best_h := _plane_at(planes[0], q)
	for i in range(1, planes.size()):
		var h := _plane_at(planes[i], q)
		if h < best_h - 1e-9:
			best_h = h
			best = i
	return best


## Polygone convexe du pan `pl`, en éventail, face vers le haut ; `underside` : le même retourné (dessous du
## débord, vu d'en bas sous l'égout).
static func _emit_roof_poly(poly: PackedVector2Array, pl: Vector3, underside: bool, top_y: float, roof_color: Color,
		code: float, out: Dictionary) -> void:
	var n := poly.size()
	var area2 := 0.0
	for k in range(n):
		var p0 := poly[k]
		var p1 := poly[(k + 1) % n]
		area2 += p0.x * p1.y - p1.x * p0.y
	if absf(area2) <= 1e-7:
		return
	var vertices: PackedVector3Array = out["vertices"]
	var normals: PackedVector3Array = out["normals"]
	var colors: PackedColorArray = out["colors"]
	var uvs: PackedVector2Array = out["uvs"]
	var uvs2: PackedVector2Array = out["uvs2"]
	var indices: PackedInt32Array = out["indices"]
	var normal := Vector3(-pl.x, 1.0, -pl.y).normalized()
	var grad := Vector2(pl.x, pl.y)
	var flat := grad.length_squared() <= 1e-12
	var up := Vector2.ZERO if flat else grad.normalized()
	var along := Vector2(-up.y, up.x)
	var stretch := sqrt(1.0 + grad.length_squared())
	var passes := 2 if underside else 1
	for pass_i in range(passes):
		var base := vertices.size()
		for q in poly:
			vertices.append(Vector3(q.x, top_y + _plane_at(pl, q), q.y))
			normals.append(normal if pass_i == 0 else -normal)
			colors.append(roof_color)
			uvs.append(q if flat else Vector2(q.dot(along), q.dot(up) * stretch))
			uvs2.append(Vector2(0.0, code))
		# Dans Godot, Plane(A, B, C).normal pointe vers +y quand (b - a) × (c - a) > 0 en (x, z)
		var up_facing := (area2 > 0.0) == (pass_i == 0)
		for k in range(1, n - 1):
			indices.append(base)
			indices.append(base + (k if up_facing else k + 1))
			indices.append(base + (k + 1 if up_facing else k))


static func _unit(h: int, salt: int) -> float:
	return float(_mix(h ^ salt)) / 4294967296.0


static func _pick(palette: Array[Color], u: float) -> Color:
	return palette[mini(int(u * palette.size()), palette.size() - 1)]


## Construit les tableaux de maillage pour la liste de bâtiments d'un tronçon. `style_name` : variante
## d'architecture du contrat U1 §4.3 (building_styles.gd), la même pour tout le tronçon avant le lot U14.
static func build(buildings: Array, theme: Dictionary, skirt_m: float = 0.0,
		style_name: String = BuildingStyles.STYLE_DEFAULT) -> Dictionary:
	var out := {
		"vertices": PackedVector3Array(),
		"normals": PackedVector3Array(),
		"colors": PackedColorArray(),
		"uvs": PackedVector2Array(),
		"uvs2": PackedVector2Array(),
		"indices": PackedInt32Array(),
	}
	var errors := PackedStringArray()
	var built := 0
	var skipped := 0
	var reversed_rings := 0
	var pitched := 0

	var b_theme: Dictionary = {}
	if typeof(theme) == TYPE_DICTIONARY and typeof(theme.get("buildings", null)) == TYPE_DICTIONARY:
		b_theme = theme["buildings"]
	var wall_palette := _parse_palette(b_theme.get("walls", null), DEFAULT_WALL_COLORS)
	var roof_palette := _parse_palette(b_theme.get("roofs", null), DEFAULT_ROOF_COLORS)
	var material_palettes := {}
	for key in BuildingStyles.MATERIAL_COLORS:
		material_palettes[key] = _parse_palette(BuildingStyles.MATERIAL_COLORS[key], BuildingStyles.MATERIAL_COLORS[key])

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
		var holes_area := 0.0
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
			holes_area += absf(area_h)
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

		# Habillage (Y8) : famille du type OSM, style de la variante, tirages déterministes de l'identifiant
		var h := hash_string(b_id)
		var hint = b.get("hint", {})
		var osm_type := str(hint.get("building", "yes")) if typeof(hint) == TYPE_DICTIONARY else "yes"
		var box := oriented_box(outer)
		var box_area := 4.0 * float(box.get("half_len", 0.0)) * float(box.get("half_width", 0.0))
		var fill := (absf(area_outer) - holes_area) / box_area if box_area > 0.0 else 0.0
		# Style du bâtiment : clé `style` posée par l'engine (U14 : variante de la tuile ou biome dominant,
		# BuildingStyles.resolve), sinon celui du tronçon
		var b_style := str(b.get("style", style_name))
		var dress := BuildingStyles.dress(b_style, BuildingStyles.classify(osm_type), fill,
			2.0 * float(box.get("half_width", 0.0)), height_m, _unit(h, 0x5BD1E995), _unit(h, 0x1B873593), _unit(h, 0x68E31DA4))
		# `roof: gabled` donné par la couche : deux pans quelle que soit la forme du contour
		if roof_kind == "gabled" and not box.is_empty():
			dress = BuildingStyles.force_gabled(dress, b_style)
		var planes := roof_planes(dress["shape"], float(dress["pitch_deg"]), box)
		if planes.size() > 1:
			pitched += 1
			# Débord du toit : contour élargi, pans prolongés sous la hauteur des murs
			var wide := Geometry2D.offset_polygon(outer, BuildingStyles.EAVE_OVERHANG_M, Geometry2D.JOIN_MITER)
			if wide.size() == 1 and signed_area(wide[0]) > 0.0:
				var wide_tris := _triangulate_with_holes(wide[0], holes)
				if not wide_tris.is_empty():
					roof_tris = wide_tris

		var pair := colors_for_id(b_id, wall_palette, roof_palette)
		var wall_color := pair[0]
		var roof_color := pair[1]
		var wall_key := BuildingStyles.wall_palette_key(int(dress["wall"]), b_style)
		if not wall_key.is_empty():
			wall_color = _pick(material_palettes[wall_key], _unit(h, 0x27D4EB2D))
		var roof_key := BuildingStyles.roof_palette_key(int(dress["roof"]), b_style)
		if not roof_key.is_empty():
			roof_color = _pick(material_palettes[roof_key], _unit(h, 0x165667B1))
		var colour_tag = hint.get("colour", null) if typeof(hint) == TYPE_DICTIONARY else null
		if typeof(colour_tag) == TYPE_STRING and Color.html_is_valid(colour_tag):
			wall_color = Color.html(colour_tag)
		# Alpha : graine du bâtiment (volets, porte, salissures) lue par le shader
		wall_color.a = _unit(h, 0x2545F491)
		roof_color.a = wall_color.a

		var wall_code := dress_code(dress, false, height_m)
		var wall_base_y := base_y - skirt_m
		_append_wall_ring(outer, base_y, wall_base_y, top_y, planes, wall_color, wall_code, out)
		for h_ring in holes:
			_append_wall_ring(h_ring, base_y, wall_base_y, top_y, planes, wall_color, wall_code, out)
		_append_roof(roof_tris, top_y, planes, roof_color, dress_code(dress, true, height_m), out)

		built += 1

	out["built"] = built
	out["skipped"] = skipped
	out["errors"] = errors
	out["reversed_rings"] = reversed_rings
	out["pitched"] = pitched
	return out


## Faux relief des façades et des toits par préréglage (perturbation de la normale) : coupé en `low`, où
## restent les fenêtres, les joints et les rangs de tuiles dessinés en couleur.
const RELIEF := {"low": 0.0, "medium": 1.0, "high": 1.0}


static func apply_preset(mat: ShaderMaterial, preset: String) -> void:
	mat.set_shader_parameter("relief", float(RELIEF.get(preset.strip_edges(), 1.0)))


## Matériau des bâtiments (building.gdshader), partagé par tous les tronçons.
static func make_material() -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/building.gdshader")
	return mat
