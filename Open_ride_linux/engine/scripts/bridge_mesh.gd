extends RefCounted

## Ponts dessinés (lot EA4, série EA, format §8 septies, depuis 1.9) : tablier, garde-corps et piles.
##
## Entrée : éléments de la couche `bridges` (osm_layers.gd), coordonnées absolues du repère (monde vivant :
## déjà ramenées du coin du carré) et altitudes affichées (relief exagéré appliqué par l'appelant).
## - Tablier : dalle de DECK_DEPTH_M sous la chaussée, dessus à DECK_TOP_DROP_M sous l'axe (la chaussée et ses
##   bas-côtés du ruban de route restent au-dessus), bords à `half_width_m` + DECK_EXTRA_M de l'axe.
## - Garde-corps sur chaque bord du tablier : bordure en béton de CURB_H_M (épaisseur PARAPET_W_M, sa face
##   extérieure prolonge la rive du tablier), main courante métallique à PARAPET_H_M et montants tous les
##   POST_STEP_M : le regard passe entre la bordure et la lisse (vue sur la vallée depuis la selle).
## - Bouts du tablier fermés (culées) ; piles en caisson de PIER_ALONG_M × PIER_ACROSS_M, du dessous du tablier
##   au pied `base_y`, tournées comme la chaussée au plus près.
## - Facettes à normales plates (sommets propres à chaque face), couleur par sommet, un seul matériau.
## Calcul pur, dans la tâche de fond d'un tronçon (osm_streamer.gd). Pas de class_name (charger par preload).

const DECK_TOP_DROP_M := 0.12
const DECK_DEPTH_M := 1.0
const DECK_EXTRA_M := 0.9          # au-delà de la demi-chaussée : bas-côté (0,5 m) et garde-corps
const PARAPET_H_M := 1.0          # haut de la main courante au-dessus de la chaussée
const PARAPET_W_M := 0.3          # bordure en béton
const CURB_H_M := 0.3
const RAIL_TOP_M := PARAPET_H_M
const RAIL_H_M := 0.08
const RAIL_W_M := 0.08
const POST_STEP_M := 2.5
const POST_W_M := 0.08
const PIER_ALONG_M := 1.2
const PIER_ACROSS_M := 4.0

const DECK_COLOR := Color(0.60, 0.59, 0.56)
const PARAPET_COLOR := Color(0.70, 0.69, 0.66)
const PIER_COLOR := Color(0.52, 0.51, 0.49)
const RAIL_COLOR := Color(0.33, 0.35, 0.38)


static func make_material() -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.vertex_color_is_srgb = true
	mat.roughness = 0.9
	mat.metallic = 0.0
	mat.cull_mode = BaseMaterial3D.CULL_BACK
	return mat


## Construit les ponts. Renvoie {vertices, normals, colors, indices, built, skipped, piers}.
static func build(items: Array) -> Dictionary:
	var out := {
		"vertices": PackedVector3Array(), "normals": PackedVector3Array(), "colors": PackedColorArray(),
		"indices": PackedInt32Array(), "built": 0, "skipped": 0, "piers": 0,
	}
	for item in items:
		if typeof(item) != TYPE_DICTIONARY:
			out["skipped"] = int(out["skipped"]) + 1
			continue
		var pts := _points(item.get("points", []))
		if pts.size() < 2:
			out["skipped"] = int(out["skipped"]) + 1
			continue
		var hw := float(item.get("half_width_m", 3.0))
		_deck(out, pts, hw)
		for p in item.get("piers", []):
			if typeof(p) == TYPE_ARRAY and (p as Array).size() >= 4:
				if _pier(out, pts, Vector3(float(p[0]), float(p[2]), float(p[1])), float(p[3])):
					out["piers"] = int(out["piers"]) + 1
		out["built"] = int(out["built"]) + 1
	return out


static func _points(raw) -> PackedVector3Array:
	var pts := PackedVector3Array()
	if typeof(raw) != TYPE_ARRAY:
		return pts
	for p in raw:
		if typeof(p) != TYPE_ARRAY or (p as Array).size() < 3:
			continue
		var v := Vector3(float(p[0]), float(p[2]), float(p[1]))
		if pts.is_empty() or Vector2(v.x, v.z).distance_to(Vector2(pts[-1].x, pts[-1].z)) > 0.01:
			pts.append(v)
	return pts


## Droite horizontale (unitaire) de l'axe au point i : moyenne des normales des segments voisins.
static func _rights(pts: PackedVector3Array) -> PackedVector3Array:
	var out := PackedVector3Array()
	var n := pts.size()
	for i in range(n):
		var a := pts[maxi(i - 1, 0)]
		var b := pts[mini(i + 1, n - 1)]
		var d := Vector2(b.x - a.x, b.z - a.z)
		if d.length() < 1e-6:
			d = Vector2(0.0, -1.0)
		d = d.normalized()
		out.append(Vector3(-d.y, 0.0, d.x))
	return out


## Quadrilatère a, b, c, d (dans l'ordre du contour), normale plate tournée du côté de `outward` ; triangles
## dans le sens horaire vu de ce côté (face avant de Godot).
static func _quad(out: Dictionary, a: Vector3, b: Vector3, c: Vector3, d: Vector3, col: Color, outward: Vector3) -> void:
	var nrm := (b - a).cross(c - a)
	if nrm.length() < 1e-9:
		nrm = (c - a).cross(d - a)
	if nrm.length() < 1e-9:
		return
	nrm = nrm.normalized()
	var quad := [a, b, c, d]
	if nrm.dot(outward) < 0.0:
		nrm = -nrm
	else:
		quad = [a, d, c, b]   # contour inversé : sens horaire vu de l'extérieur
	var verts: PackedVector3Array = out["vertices"]
	var normals: PackedVector3Array = out["normals"]
	var colors: PackedColorArray = out["colors"]
	var idx: PackedInt32Array = out["indices"]
	var base := verts.size()
	for v in quad:
		verts.append(v)
		normals.append(nrm)
		colors.append(col)
	idx.append_array(PackedInt32Array([base, base + 1, base + 2, base, base + 2, base + 3]))
	out["vertices"] = verts
	out["normals"] = normals
	out["colors"] = colors
	out["indices"] = idx


static func _deck(out: Dictionary, pts: PackedVector3Array, hw: float) -> void:
	var rights := _rights(pts)
	var w := hw + DECK_EXTRA_M
	var wi := w - PARAPET_W_M
	var up := Vector3.UP
	var top := -DECK_TOP_DROP_M
	var bot := top - DECK_DEPTH_M
	var curb := CURB_H_M
	var wr := w - PARAPET_W_M * 0.5           # axe de la lisse et des montants, au milieu de la bordure
	var r0h := RAIL_W_M * 0.5
	for i in range(pts.size() - 1):
		var p0 := pts[i]
		var p1 := pts[i + 1]
		var r0 := rights[i]
		var r1 := rights[i + 1]
		var rm := (r0 + r1).normalized()
		# Dessus (sous la chaussée), dessous
		_quad(out, p0 - r0 * wi + up * top, p0 + r0 * wi + up * top, p1 + r1 * wi + up * top, p1 - r1 * wi + up * top, DECK_COLOR, up)
		_quad(out, p0 - r0 * w + up * bot, p0 + r0 * w + up * bot, p1 + r1 * w + up * bot, p1 - r1 * w + up * bot, DECK_COLOR, -up)
		for side in [-1.0, 1.0]:
			var o0: Vector3 = r0 * side
			var o1: Vector3 = r1 * side
			var out_dir: Vector3 = rm * side
			# Rive extérieure (du dessous du tablier au haut de la bordure)
			_quad(out, p0 + o0 * w + up * bot, p1 + o1 * w + up * bot, p1 + o1 * w + up * curb, p0 + o0 * w + up * curb, DECK_COLOR, out_dir)
			# Bordure en béton : dessus et face intérieure
			_quad(out, p0 + o0 * wi + up * curb, p0 + o0 * w + up * curb, p1 + o1 * w + up * curb, p1 + o1 * wi + up * curb, PARAPET_COLOR, up)
			_quad(out, p0 + o0 * wi + up * top, p1 + o1 * wi + up * top, p1 + o1 * wi + up * curb, p0 + o0 * wi + up * curb, PARAPET_COLOR, -out_dir)
			# Lisse métallique (main courante) : caisson de RAIL_W_M sur RAIL_H_M, le regard passe dessous
			var lo := RAIL_TOP_M - RAIL_H_M
			for f in [[wr - r0h, wr + r0h, RAIL_TOP_M, RAIL_TOP_M, up], [wr - r0h, wr + r0h, lo, lo, -up],
					[wr + r0h, wr + r0h, lo, RAIL_TOP_M, out_dir], [wr - r0h, wr - r0h, lo, RAIL_TOP_M, -out_dir]]:
				var ia: float = f[0]
				var ib: float = f[1]
				var ya: float = f[2]
				var yb: float = f[3]
				_quad(out, p0 + o0 * ia + up * ya, p0 + o0 * ib + up * yb, p1 + o1 * ib + up * yb, p1 + o1 * ia + up * ya, RAIL_COLOR, f[4])
	_posts(out, pts, rights, wr)
	# Bouts fermés : tranche du tablier et de la bordure (culées)
	var n := pts.size()
	for end in [0, n - 1]:
		var p := pts[end]
		var r := rights[end]
		var nb := pts[1] if end == 0 else pts[n - 2]
		var away := Vector3(p.x - nb.x, 0.0, p.z - nb.z).normalized()
		_quad(out, p - r * w + up * bot, p + r * w + up * bot, p + r * w + up * top, p - r * w + up * top, DECK_COLOR, away)
		for side in [-1.0, 1.0]:
			var o: Vector3 = r * side
			_quad(out, p + o * wi + up * top, p + o * w + up * top, p + o * w + up * curb, p + o * wi + up * curb, PARAPET_COLOR, away)


## Montants du garde-corps tous les POST_STEP_M (bouts compris), de la bordure à la lisse, des deux côtés.
static func _posts(out: Dictionary, pts: PackedVector3Array, rights: PackedVector3Array, wr: float) -> void:
	var up := Vector3.UP
	var h := POST_W_M * 0.5
	var next := 0.0
	var acc := 0.0
	for i in range(pts.size() - 1):
		var a := pts[i]
		var b := pts[i + 1]
		var seg := Vector2(b.x - a.x, b.z - a.z).length()
		if seg < 1e-6:
			continue
		var fwd := Vector3(b.x - a.x, 0.0, b.z - a.z) / seg
		var last := i == pts.size() - 2
		while next <= acc + seg + (1e-6 if last else -1e-6):
			var t := clampf((next - acc) / seg, 0.0, 1.0)
			var c := a.lerp(b, t)
			var r := rights[i].lerp(rights[i + 1], t).normalized()
			for side in [-1.0, 1.0]:
				var m: Vector3 = c + r * side * wr
				var corners := [m - fwd * h - r * h, m + fwd * h - r * h, m + fwd * h + r * h, m - fwd * h + r * h]
				for k in range(4):
					var p: Vector3 = corners[k]
					var q: Vector3 = corners[(k + 1) % 4]
					var mid := (p + q) * 0.5 - m
					_quad(out, p + up * CURB_H_M, q + up * CURB_H_M, q + up * (RAIL_TOP_M - RAIL_H_M), p + up * (RAIL_TOP_M - RAIL_H_M), RAIL_COLOR, mid)
			next += POST_STEP_M
		acc += seg


## Pile en caisson sous le point `at` (y : chaussée) jusqu'à `base_y`, tournée comme le segment d'axe le plus proche.
static func _pier(out: Dictionary, pts: PackedVector3Array, at: Vector3, base_y: float) -> bool:
	var top_y := at.y - DECK_TOP_DROP_M - DECK_DEPTH_M
	if not (is_finite(base_y) and top_y - base_y > 0.2):
		return false
	var best := INF
	var dir := Vector2(0.0, -1.0)
	var q := Vector2(at.x, at.z)
	for i in range(pts.size() - 1):
		var a := Vector2(pts[i].x, pts[i].z)
		var b := Vector2(pts[i + 1].x, pts[i + 1].z)
		var c := Geometry2D.get_closest_point_to_segment(q, a, b)
		var dd := c.distance_to(q)
		if dd < best and a.distance_to(b) > 1e-6:
			best = dd
			dir = (b - a).normalized()
	var f := Vector3(dir.x, 0.0, dir.y) * (PIER_ALONG_M * 0.5)
	var r := Vector3(-dir.y, 0.0, dir.x) * (PIER_ACROSS_M * 0.5)
	var c0 := Vector3(at.x, 0.0, at.z)
	var corners := [c0 - f - r, c0 + f - r, c0 + f + r, c0 - f + r]   # contour vu de dessus
	for i in range(4):
		var a: Vector3 = corners[i]
		var b: Vector3 = corners[(i + 1) % 4]
		var mid := (a + b) * 0.5 - c0
		_quad(out, Vector3(a.x, base_y, a.z), Vector3(b.x, base_y, b.z), Vector3(b.x, top_y, b.z), Vector3(a.x, top_y, a.z), PIER_COLOR, mid)
	return true
