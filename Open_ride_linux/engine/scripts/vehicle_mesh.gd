extends RefCounted

## Maillages des véhicules du décor (Lot P25), construits par code avec le Builder de people_mesh.gd (Y14),
## sans texture : berline `car_a`, citadine haute `car_b`, utilitaire `van`, camion porteur `truck`, autocar
## `bus`, moto et son pilote `moto`, tracteur `tractor` et tracteur qui herse un champ `tractor_field`.
## Pas de class_name : charger par preload("res://scripts/vehicle_mesh.gd").
##
## Repère : sol à y = 0, avant vers -z (traffic_model.gd `world_transform`), axe au milieu en x. Les caisses
## sont un profil de côté (z, y) extrudé en largeur, rétréci au-dessus de la ligne de caisse, avec les passages
## de roue découpés dans le bas ; vitres, phares, feux, calandre, pare-chocs, rétroviseurs et plaques en pièces
## posées dessus.
## CUSTOM0.x : zone lue par shaders/vehicle.gdshader (VEH_*) : peinture (couleur du véhicule), vitre, noir
## (pneus, calandre, pare-chocs, passages de roue), métal (jantes, échappement), phare (allumé par les feux),
## feu arrière, clair (plaques, climatisation), seconde couleur (caisse du camion, bande de l'autocar, blouson du
## motard, jantes du tracteur).
## - `build_body(kind)` : caisse sans les roues (véhicules proches de traffic_renderer.gd, roues à part qui
##   tournent) ; `build_wheel(kind, i)` : une roue, centrée sur son axe (x) ; `wheel_list(kind)` : leurs places.
## - `build_full(kind)` : caisse et roues fixes en un seul maillage (circulation lointaine en MultiMesh).
## - `paint(kind, index)` et `second(kind)` : couleurs.

const PeopleMesh := preload("res://scripts/people_mesh.gd")

const VEH_PAINT := 0
const VEH_GLASS := 1
const VEH_DARK := 2
const VEH_METAL := 3
const VEH_HEAD := 4
const VEH_TAIL := 5
const VEH_LIGHT := 6
const VEH_SECOND := 7
const WHEEL_SIDES := 12
const ARCH_STEPS := 7
const GLASS_OUT_M := 0.008        # vitres de côté posées juste devant la tôle

const KINDS := ["car_a", "car_b", "van", "truck", "bus", "moto", "tractor", "tractor_field"]

## Roues : [x, y, z, rayon, largeur] ; x > 0 : une roue de chaque côté, x = 0 : une roue au milieu (moto).
const WHEELS := {
	"car_a": [[0.78, 0.32, -1.35, 0.32, 0.21], [0.78, 0.32, 1.35, 0.32, 0.21]],
	"car_b": [[0.76, 0.3, -1.25, 0.3, 0.2], [0.76, 0.3, 1.2, 0.3, 0.2]],
	"van": [[0.86, 0.35, -1.75, 0.35, 0.23], [0.86, 0.35, 1.6, 0.35, 0.23]],
	"truck": [[1.0, 0.5, -3.3, 0.5, 0.32], [0.99, 0.5, 2.0, 0.5, 0.5], [0.99, 0.5, 3.3, 0.5, 0.5]],
	"bus": [[1.02, 0.5, -3.4, 0.5, 0.3], [0.995, 0.5, 2.9, 0.5, 0.48]],
	"moto": [[0.0, 0.31, -0.72, 0.31, 0.13], [0.0, 0.31, 0.68, 0.31, 0.15]],
	"tractor": [[0.72, 0.45, -1.35, 0.45, 0.28], [0.82, 0.8, 0.75, 0.8, 0.45]],
	"tractor_field": [[0.72, 0.45, -1.35, 0.45, 0.28], [0.82, 0.8, 0.75, 0.8, 0.45]],
}
## Roue à crampons (pneus arrière du tracteur), à partir de ce rayon
const LUG_RADIUS_M := 0.6

const CAR_PAINT := [Color(0.62, 0.08, 0.08), Color(0.12, 0.2, 0.45), Color(0.86, 0.86, 0.83), Color(0.08, 0.08, 0.09),
	Color(0.55, 0.57, 0.6), Color(0.32, 0.33, 0.35), Color(0.12, 0.28, 0.18), Color(0.35, 0.5, 0.7)]
const TRACTOR_PAINT := [Color(0.2, 0.45, 0.15), Color(0.7, 0.1, 0.07), Color(0.12, 0.25, 0.6), Color(0.85, 0.42, 0.08)]
const BUS_PAINT := [Color(0.9, 0.9, 0.88), Color(0.9, 0.84, 0.6), Color(0.15, 0.3, 0.65), Color(0.2, 0.5, 0.3)]
const SECOND := {
	"car_a": Color(0.5, 0.5, 0.5), "car_b": Color(0.5, 0.5, 0.5), "van": Color(0.5, 0.5, 0.5),
	"truck": Color(0.86, 0.86, 0.84), "bus": Color(0.12, 0.2, 0.45), "moto": Color(0.1, 0.1, 0.11),
	"tractor": Color(0.85, 0.7, 0.12), "tractor_field": Color(0.85, 0.7, 0.12),
}


static func paint(kind: String, index: int) -> Color:
	var pal: Array = CAR_PAINT
	if kind == "tractor" or kind == "tractor_field":
		pal = TRACTOR_PAINT
	elif kind == "bus":
		pal = BUS_PAINT
	return pal[posmod(index, pal.size())]


static func second(kind: String) -> Color:
	return SECOND.get(kind, SECOND["car_a"])


## Places des roues : [{pos: Vector3, radius, width}], dans l'ordre de `build_wheel`.
static func wheel_list(kind: String) -> Array:
	var out := []
	for w in WHEELS.get(kind, []):
		var xs := [0.0] if float(w[0]) == 0.0 else [-float(w[0]), float(w[0])]
		for x in xs:
			out.append({"pos": Vector3(x, float(w[1]), float(w[2])), "radius": float(w[3]), "width": float(w[4])})
	return out


static func build_body(kind: String) -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	_body(m, kind)
	return m.commit()


static func build_full(kind: String) -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	_body(m, kind)
	for w in wheel_list(kind):
		_wheel(m, w["pos"], w["radius"], w["width"], _rim_region(kind))
	return m.commit()


## Roue `i` de `wheel_list(kind)`, centrée sur l'origine, axe selon x.
static func build_wheel(kind: String, i: int) -> ArrayMesh:
	var w: Dictionary = wheel_list(kind)[i]
	var m := PeopleMesh.Builder.new()
	_wheel(m, Vector3.ZERO, w["radius"], w["width"], _rim_region(kind))
	return m.commit()


static func _rim_region(kind: String) -> int:
	return VEH_SECOND if kind == "tractor" or kind == "tractor_field" else VEH_METAL


static func _body(m, kind: String) -> void:
	match kind:
		"car_a":
			_car_a(m)
		"car_b":
			_car_b(m)
		"van":
			_van(m)
		"truck":
			_truck(m)
		"bus":
			_bus(m)
		"moto":
			_moto(m)
		"tractor":
			_tractor(m)
		"tractor_field":
			_tractor(m)
			_harrow(m)


# --- Pièces ---------------------------------------------------------------------------------------------

## Triangle dont l'ordre des sommets suit la normale `n` (même sens que les faces de Builder.box).
static func _tri(m, a: Vector3, b: Vector3, c: Vector3, n: Vector3) -> void:
	if (b - a).cross(c - a).dot(n) > 0.0:
		var t := b
		b = c
		c = t
	m.vertex(a, n)
	m.vertex(b, n)
	m.vertex(c, n)


## Cylindre effilé de `a` à `b`, section elliptique (`ra` au bout `a`, `rb` au bout `b`), bouts fermés,
## pourtour à normales lissées ; même repère de section que Builder.prism, faces dans le sens de leurs normales.
static func _cyl(m, a: Vector3, b: Vector3, ra: Vector2, rb: Vector2, sides: int) -> void:
	var axis := (b - a).normalized()
	var ref := Vector3.FORWARD if absf(axis.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT
	var u := axis.cross(ref).normalized()
	var w := axis.cross(u).normalized()
	if absf(axis.y) > 0.7:
		u = Vector3.RIGHT
		w = axis.cross(u).normalized()
		u = w.cross(axis).normalized()
	var ring := func(c: Vector3, r: Vector2, i: int) -> Array:
		var t := TAU * float(i) / sides
		var d := u * cos(t) * r.x + w * sin(t) * r.y
		var n := (u * cos(t) / maxf(r.x, 1e-4) + w * sin(t) / maxf(r.y, 1e-4)).normalized()
		return [c + d, n]
	for i in range(sides):
		var a0: Array = ring.call(a, ra, i)
		var a1: Array = ring.call(a, ra, i + 1)
		var b0: Array = ring.call(b, rb, i)
		var b1: Array = ring.call(b, rb, i + 1)
		var fn: Vector3 = a0[1] + a1[1]
		for tri in [[a0, b1, b0], [a0, a1, b1]]:
			var p0: Vector3 = tri[0][0]
			var p1: Vector3 = tri[1][0]
			var p2: Vector3 = tri[2][0]
			if (p1 - p0).cross(p2 - p0).dot(fn) > 0.0:
				tri = [tri[0], tri[2], tri[1]]
			for v in tri:
				m.vertex(v[0], v[1])
		_tri(m, a, a0[0], a1[0], -axis)
		_tri(m, b, b0[0], b1[0], axis)


static func _box(m, region: int, c: Vector3, size: Vector3) -> void:
	m.region = region
	m.box(c, size)


static func _rod(m, region: int, a: Vector3, b: Vector3, r: float, sides: int = 6) -> void:
	m.region = region
	_cyl(m, a, b, Vector2(r, r), Vector2(r, r), sides)


## Demi-largeur de la caisse à la hauteur `y` : `hw` jusqu'à la ligne de caisse, puis rétrécie jusqu'au toit.
static func _half_width(s: Dictionary, y: float) -> float:
	var belt: float = s["belt"]
	if y <= belt:
		return s["hw"]
	return lerpf(s["hw"], s["hw"] * float(s["roof_k"]), clampf((y - belt) / maxf(float(s["top_y"]) - belt, 0.01), 0.0, 1.0))


## Caisse extrudée (voir l'en-tête). `s` : `top` [[z, y, zone de l'arête suivante], …] de l'avant bas à
## l'arrière bas ; `floor` hauteur du bas de caisse ; `arches` [[z, rayon, y de l'axe], …] ; `hw`, `belt`,
## `roof_k` ; `glass` contours [[z, y], …] des vitres de côté ; `panels` [[zone, contour], …] autres
## pièces plates de côté (bande de l'autocar).
static func _hull(m, s: Dictionary) -> void:
	var pts := PackedVector2Array()   # (z, y)
	var regions: Array[int] = []
	var top_y := -INF
	for p in s["top"]:
		pts.append(Vector2(float(p[0]), float(p[1])))
		regions.append(int(p[2]) if p.size() > 2 else VEH_DARK)
		top_y = maxf(top_y, float(p[1]))
	s["top_y"] = top_y
	var floor_y: float = s["floor"]
	var arches: Array = s.get("arches", []).duplicate()
	arches.sort_custom(func(a, b): return float(a[0]) > float(b[0]))   # de l'arrière vers l'avant
	regions[regions.size() - 1] = VEH_DARK
	for a in arches:
		var zc := float(a[0])
		var r := float(a[1])
		var wy := float(a[2])
		pts.append(Vector2(zc + r, floor_y))
		regions.append(VEH_DARK)
		for i in range(ARCH_STEPS + 1):
			var t := PI * float(i) / ARCH_STEPS
			pts.append(Vector2(zc + r * cos(t), maxf(wy + r * sin(t), floor_y)))
			regions.append(VEH_DARK)
		pts.append(Vector2(zc - r, floor_y))
		regions.append(VEH_DARK)
	# Points confondus retirés (bas de caisse à la hauteur de l'axe d'une roue)
	var clean := PackedVector2Array()
	var clean_regions: Array[int] = []
	for i in range(pts.size()):
		if clean.is_empty() or clean[clean.size() - 1].distance_to(pts[i]) > 1e-4:
			clean.append(pts[i])
			clean_regions.append(regions[i])
		else:
			clean_regions[clean_regions.size() - 1] = regions[i]
	pts = clean
	regions = clean_regions
	var area := 0.0
	for i in range(pts.size()):
		var a2 := pts[i]
		var b2 := pts[(i + 1) % pts.size()]
		area += a2.x * b2.y - b2.x * a2.y
	var orient := 1.0 if area > 0.0 else -1.0
	# Côtés
	m.region = VEH_PAINT
	var idx := Geometry2D.triangulate_polygon(pts)
	for side in [-1.0, 1.0]:
		var n := Vector3(side, 0.0, 0.0)
		for t in range(0, idx.size(), 3):
			var q := []
			for j in range(3):
				var p := pts[idx[t + j]]
				q.append(Vector3(side * _half_width(s, p.y), p.y, p.x))
			_tri(m, q[0], q[1], q[2], n)
	# Pourtour : une bande par arête, de la zone de l'arête
	for i in range(pts.size()):
		var a3 := pts[i]
		var b3 := pts[(i + 1) % pts.size()]
		var e := b3 - a3
		if e.length() < 1e-5:
			continue
		var n2 := Vector2(e.y, -e.x).normalized() * orient
		var n := Vector3(0.0, n2.y, n2.x)
		m.region = regions[i]
		var la := Vector3(-_half_width(s, a3.y), a3.y, a3.x)
		var ra := Vector3(_half_width(s, a3.y), a3.y, a3.x)
		var lb := Vector3(-_half_width(s, b3.y), b3.y, b3.x)
		var rb := Vector3(_half_width(s, b3.y), b3.y, b3.x)
		_tri(m, la, lb, rb, n)
		_tri(m, la, rb, ra, n)
	for g in s.get("glass", []):
		_side_panel(m, s, VEH_GLASS, g, GLASS_OUT_M)
	for p in s.get("panels", []):
		_side_panel(m, s, int(p[0]), p[1], GLASS_OUT_M * 0.5)


static func _side_panel(m, s: Dictionary, region: int, poly: Array, out_m: float) -> void:
	var pts := PackedVector2Array()
	for p in poly:
		pts.append(Vector2(float(p[0]), float(p[1])))
	var idx := Geometry2D.triangulate_polygon(pts)
	m.region = region
	for side in [-1.0, 1.0]:
		var n := Vector3(side, 0.0, 0.0)
		for t in range(0, idx.size(), 3):
			var q := []
			for j in range(3):
				var p := pts[idx[t + j]]
				q.append(Vector3(side * (_half_width(s, p.y) + out_m), p.y, p.x))
			_tri(m, q[0], q[1], q[2], n)


## Roue d'axe x centrée sur `c` : pneu, flanc, jante et moyeu ; crampons au-delà de LUG_RADIUS_M.
static func _wheel(m, c: Vector3, r: float, w: float, rim_region: int) -> void:
	var hx := Vector3(w * 0.5, 0.0, 0.0)
	m.region = VEH_DARK
	_cyl(m, c - hx, c + hx, Vector2(r, r), Vector2(r, r), WHEEL_SIDES)
	m.region = rim_region
	var rx := Vector3(w * 0.5 + 0.006, 0.0, 0.0)
	_cyl(m, c - rx, c + rx, Vector2(r * 0.6, r * 0.6), Vector2(r * 0.6, r * 0.6), WHEEL_SIDES)
	m.region = VEH_METAL
	var hub := Vector3(w * 0.5 + 0.02, 0.0, 0.0)
	_cyl(m, c - hub, c + hub, Vector2(r * 0.16, r * 0.16), Vector2(r * 0.16, r * 0.16), 6)
	if r >= LUG_RADIUS_M:
		m.region = VEH_DARK
		var lugs := 16
		for i in range(lugs):
			var a := TAU * float(i) / lugs
			var saved: Transform3D = m.xform
			m.xform = saved * Transform3D(Basis(Vector3.RIGHT, a), c)
			m.box(Vector3(0.0, r - 0.02, 0.0), Vector3(w * 0.9, 0.05, 0.09))
			m.xform = saved


## Deux pièces symétriques en x.
static func _pair(m, region: int, c: Vector3, size: Vector3) -> void:
	for sx in [-1.0, 1.0]:
		_box(m, region, Vector3(sx * c.x, c.y, c.z), size)


# --- Véhicules ------------------------------------------------------------------------------------------

static func _car_a(m) -> void:
	_hull(m, {
		"top": [[-2.2, 0.3, VEH_PAINT], [-2.24, 0.62, VEH_PAINT], [-1.0, 0.84, VEH_GLASS], [-0.3, 1.4, VEH_PAINT],
			[0.8, 1.42, VEH_GLASS], [1.62, 0.98, VEH_PAINT], [2.18, 0.94, VEH_PAINT], [2.22, 0.3]],
		"floor": 0.3, "arches": [[-1.35, 0.37, 0.32], [1.35, 0.37, 0.32]],
		"hw": 0.9, "belt": 0.95, "roof_k": 0.78,
		"glass": [[[-0.76, 0.98], [-0.35, 1.33], [0.1, 1.34], [0.1, 0.98]],
			[[0.2, 0.98], [0.2, 1.34], [0.78, 1.34], [1.38, 0.98]]],
	})
	_pair(m, VEH_HEAD, Vector3(0.6, 0.55, -2.235), Vector3(0.4, 0.12, 0.06))
	_box(m, VEH_DARK, Vector3(0.0, 0.47, -2.23), Vector3(0.72, 0.14, 0.05))      # calandre
	_box(m, VEH_DARK, Vector3(0.0, 0.34, -2.23), Vector3(1.82, 0.12, 0.1))       # pare-chocs avant
	_box(m, VEH_LIGHT, Vector3(0.0, 0.35, -2.285), Vector3(0.5, 0.1, 0.02))      # plaque avant
	_pair(m, VEH_TAIL, Vector3(0.64, 0.82, 2.2), Vector3(0.38, 0.12, 0.06))
	_box(m, VEH_DARK, Vector3(0.0, 0.36, 2.23), Vector3(1.82, 0.14, 0.1))        # pare-chocs arrière
	_box(m, VEH_LIGHT, Vector3(0.0, 0.62, 2.215), Vector3(0.5, 0.1, 0.02))       # plaque arrière
	_pair(m, VEH_PAINT, Vector3(0.97, 1.0, -0.72), Vector3(0.12, 0.09, 0.16))    # rétroviseurs
	_pair(m, VEH_DARK, Vector3(0.905, 0.82, 0.15), Vector3(0.012, 0.03, 2.4))   # baguette de porte


static func _car_b(m) -> void:
	_hull(m, {
		"top": [[-1.95, 0.32, VEH_PAINT], [-1.99, 0.66, VEH_PAINT], [-1.3, 0.86, VEH_GLASS], [-0.55, 1.5, VEH_PAINT],
			[1.5, 1.53, VEH_GLASS], [1.88, 1.02, VEH_PAINT], [1.95, 0.32]],
		"floor": 0.32, "arches": [[-1.25, 0.35, 0.3], [1.2, 0.35, 0.3]],
		"hw": 0.87, "belt": 0.98, "roof_k": 0.82,
		"glass": [[[-1.08, 1.0], [-0.62, 1.43], [0.2, 1.45], [0.2, 1.0]],
			[[0.3, 1.0], [0.3, 1.45], [1.4, 1.46], [1.55, 1.0]]],
	})
	_pair(m, VEH_HEAD, Vector3(0.58, 0.6, -1.985), Vector3(0.36, 0.13, 0.06))
	_box(m, VEH_DARK, Vector3(0.0, 0.5, -1.98), Vector3(0.66, 0.12, 0.05))
	_box(m, VEH_DARK, Vector3(0.0, 0.36, -1.98), Vector3(1.76, 0.13, 0.1))
	_box(m, VEH_LIGHT, Vector3(0.0, 0.37, -2.035), Vector3(0.5, 0.1, 0.02))
	_pair(m, VEH_TAIL, Vector3(0.7, 0.86, 1.925), Vector3(0.2, 0.26, 0.06))
	_box(m, VEH_DARK, Vector3(0.0, 0.38, 1.97), Vector3(1.76, 0.14, 0.1))
	_box(m, VEH_LIGHT, Vector3(0.0, 0.62, 1.93), Vector3(0.5, 0.1, 0.02))
	_pair(m, VEH_PAINT, Vector3(0.94, 1.05, -0.98), Vector3(0.12, 0.09, 0.15))
	_box(m, VEH_DARK, Vector3(0.0, 1.56, 0.5), Vector3(1.2, 0.04, 1.6))          # barres de toit
	_pair(m, VEH_DARK, Vector3(0.875, 0.82, 0.0), Vector3(0.012, 0.03, 2.2))


static func _van(m) -> void:
	_hull(m, {
		"top": [[-2.5, 0.36, VEH_PAINT], [-2.55, 0.78, VEH_PAINT], [-2.0, 1.08, VEH_GLASS], [-1.42, 1.98, VEH_PAINT],
			[-1.15, 2.28, VEH_PAINT], [2.45, 2.3, VEH_PAINT], [2.5, 0.36]],
		"floor": 0.36, "arches": [[-1.75, 0.4, 0.35], [1.6, 0.4, 0.35]],
		"hw": 1.0, "belt": 1.15, "roof_k": 0.93,
		"glass": [[[-1.86, 1.2], [-1.5, 1.85], [-0.8, 1.88], [-0.8, 1.2]]],
	})
	_pair(m, VEH_HEAD, Vector3(0.7, 0.7, -2.54), Vector3(0.4, 0.16, 0.06))
	_box(m, VEH_DARK, Vector3(0.0, 0.6, -2.55), Vector3(0.9, 0.2, 0.05))
	_box(m, VEH_DARK, Vector3(0.0, 0.42, -2.55), Vector3(2.0, 0.16, 0.12))
	_box(m, VEH_LIGHT, Vector3(0.0, 0.43, -2.615), Vector3(0.5, 0.1, 0.02))
	_pair(m, VEH_TAIL, Vector3(0.9, 0.9, 2.495), Vector3(0.12, 0.4, 0.05))
	_pair(m, VEH_GLASS, Vector3(0.45, 1.85, 2.5), Vector3(0.7, 0.4, 0.03))      # vitres des portes arrière
	_box(m, VEH_DARK, Vector3(0.0, 1.3, 2.51), Vector3(0.03, 1.8, 0.02))         # jointure des portes
	_box(m, VEH_DARK, Vector3(0.0, 0.42, 2.52), Vector3(2.0, 0.16, 0.1))
	_box(m, VEH_LIGHT, Vector3(0.0, 0.62, 2.515), Vector3(0.5, 0.1, 0.02))
	_pair(m, VEH_DARK, Vector3(1.07, 1.6, -1.85), Vector3(0.1, 0.25, 0.15))
	_pair(m, VEH_DARK, Vector3(1.005, 1.1, 0.6), Vector3(0.012, 0.9, 0.02))     # porte coulissante
	_pair(m, VEH_DARK, Vector3(1.005, 1.6, 0.6), Vector3(0.012, 0.03, 2.6))     # rail de la porte


static func _truck(m) -> void:
	_hull(m, {
		"top": [[-4.5, 0.45, VEH_PAINT], [-4.55, 1.35, VEH_PAINT], [-4.5, 1.55, VEH_GLASS], [-4.35, 2.75, VEH_PAINT],
			[-4.15, 2.98, VEH_PAINT], [-2.25, 3.0, VEH_PAINT], [-2.2, 0.45]],
		"floor": 0.45, "arches": [[-3.3, 0.56, 0.5]],
		"hw": 1.22, "belt": 1.6, "roof_k": 0.95,
		"glass": [[[-4.25, 1.65], [-4.15, 2.6], [-3.2, 2.62], [-3.2, 1.65]]],
	})
	_box(m, VEH_SECOND, Vector3(0.0, 2.25, 1.15), Vector3(2.5, 2.5, 6.7))        # caisse
	_box(m, VEH_DARK, Vector3(0.0, 2.25, 4.505), Vector3(0.03, 2.4, 0.02))       # portes arrière
	_box(m, VEH_DARK, Vector3(0.0, 0.75, 1.0), Vector3(1.0, 0.35, 6.9))          # châssis
	_pair(m, VEH_METAL, Vector3(1.2, 0.7, -0.7), Vector3(0.05, 0.12, 2.6))       # protection latérale
	_pair(m, VEH_HEAD, Vector3(0.85, 0.72, -4.55), Vector3(0.38, 0.18, 0.06))
	_box(m, VEH_DARK, Vector3(0.0, 1.05, -4.56), Vector3(1.4, 0.5, 0.04))        # calandre
	_box(m, VEH_DARK, Vector3(0.0, 0.52, -4.57), Vector3(2.44, 0.22, 0.12))
	_box(m, VEH_LIGHT, Vector3(0.0, 0.52, -4.64), Vector3(0.5, 0.11, 0.02))
	_box(m, VEH_DARK, Vector3(0.0, 0.6, 4.45), Vector3(2.3, 0.12, 0.1))          # barre anti-encastrement
	_pair(m, VEH_TAIL, Vector3(0.95, 0.85, 4.47), Vector3(0.3, 0.14, 0.06))
	_box(m, VEH_LIGHT, Vector3(0.0, 0.85, 4.47), Vector3(0.5, 0.11, 0.03))
	_pair(m, VEH_METAL, Vector3(1.38, 2.2, -4.2), Vector3(0.08, 0.45, 0.12))     # rétroviseurs
	_pair(m, VEH_DARK, Vector3(0.99, 1.05, 2.65), Vector3(0.5, 0.06, 1.95))      # garde-boue arrière


static func _bus(m) -> void:
	_hull(m, {
		"top": [[-6.0, 0.35, VEH_PAINT], [-6.05, 1.05, VEH_GLASS], [-5.95, 2.85, VEH_PAINT], [-5.75, 3.08, VEH_PAINT],
			[5.8, 3.1, VEH_PAINT], [6.0, 2.9, VEH_PAINT], [6.02, 0.35]],
		"floor": 0.35, "arches": [[-3.4, 0.58, 0.5], [2.9, 0.58, 0.5]],
		"hw": 1.275, "belt": 1.15, "roof_k": 0.97,
		"glass": [[[-5.6, 1.2], [-5.6, 2.6], [5.6, 2.62], [5.6, 1.2]],
			[[-5.5, 0.5], [-5.5, 1.15], [-4.4, 1.15], [-4.4, 0.5]]],
		"panels": [[VEH_SECOND, [[-5.9, 0.75], [-5.9, 0.98], [-4.5, 0.98], [-4.5, 0.75]]],
			[VEH_SECOND, [[-4.3, 0.75], [-4.3, 0.98], [5.9, 0.98], [5.9, 0.75]]]],
	})
	for i in range(7):   # montants entre les vitres
		_pair(m, VEH_PAINT, Vector3(1.27, 1.9, -4.0 + 1.6 * i), Vector3(0.02, 1.4, 0.1))
	_pair(m, VEH_HEAD, Vector3(0.95, 0.62, -6.03), Vector3(0.4, 0.16, 0.06))
	_box(m, VEH_DARK, Vector3(0.0, 0.42, -6.06), Vector3(2.5, 0.18, 0.1))
	_box(m, VEH_LIGHT, Vector3(0.0, 0.62, -6.07), Vector3(0.5, 0.11, 0.02))
	_box(m, VEH_HEAD, Vector3(0.0, 2.68, -5.96), Vector3(1.6, 0.24, 0.04))       # girouette
	_pair(m, VEH_TAIL, Vector3(1.1, 1.0, 6.02), Vector3(0.15, 0.5, 0.06))
	_box(m, VEH_GLASS, Vector3(0.0, 2.3, 6.01), Vector3(2.0, 0.8, 0.03))
	_box(m, VEH_DARK, Vector3(0.0, 0.42, 6.05), Vector3(2.5, 0.18, 0.1))
	_box(m, VEH_LIGHT, Vector3(0.0, 0.7, 6.035), Vector3(0.5, 0.11, 0.02))
	_pair(m, VEH_METAL, Vector3(1.4, 2.5, -5.9), Vector3(0.08, 0.4, 0.1))
	_box(m, VEH_LIGHT, Vector3(0.0, 3.22, 0.5), Vector3(1.6, 0.25, 2.2))         # climatisation


static func _moto(m) -> void:
	for sx in [-1.0, 1.0]:
		_rod(m, VEH_METAL, Vector3(sx * 0.07, 0.31, -0.72), Vector3(sx * 0.07, 0.98, -0.5), 0.025)   # fourche
		_rod(m, VEH_DARK, Vector3(sx * 0.09, 0.31, 0.68), Vector3(sx * 0.09, 0.47, 0.05), 0.03)    # bras oscillant
	m.region = VEH_HEAD
	m.ellipsoid(Vector3(0.0, 0.96, -0.6), Vector3(0.09, 0.09, 0.06), -90.0, 4)
	m.region = VEH_PAINT
	m.ellipsoid(Vector3(0.0, 0.96, -0.2), Vector3(0.17, 0.13, 0.28), -60.0, 4)   # réservoir
	_box(m, VEH_PAINT, Vector3(0.0, 0.66, -0.72), Vector3(0.12, 0.04, 0.4))       # garde-boue avant
	_box(m, VEH_METAL, Vector3(0.0, 0.5, -0.1), Vector3(0.32, 0.32, 0.45))        # moteur
	_rod(m, VEH_DARK, Vector3(0.0, 0.62, -0.5), Vector3(0.0, 0.9, 0.35), 0.04)    # cadre
	_box(m, VEH_DARK, Vector3(0.0, 0.94, 0.25), Vector3(0.26, 0.09, 0.55))        # selle
	_box(m, VEH_PAINT, Vector3(0.0, 0.97, 0.62), Vector3(0.18, 0.1, 0.25))        # coque arrière
	_box(m, VEH_TAIL, Vector3(0.0, 0.97, 0.75), Vector3(0.12, 0.06, 0.03))
	_rod(m, VEH_METAL, Vector3(0.17, 0.4, 0.0), Vector3(0.2, 0.55, 0.7), 0.05)   # échappement
	_rod(m, VEH_DARK, Vector3(-0.38, 1.08, -0.45), Vector3(0.38, 1.08, -0.45), 0.02)   # guidon
	# Pilote, penché sur le guidon
	for sx in [-1.0, 1.0]:
		_rod(m, VEH_DARK, Vector3(sx * 0.13, 1.02, 0.22), Vector3(sx * 0.2, 0.86, -0.2), 0.07)   # cuisses
		_rod(m, VEH_DARK, Vector3(sx * 0.2, 0.86, -0.2), Vector3(sx * 0.2, 0.45, 0.05), 0.055)  # jambes
		_box(m, VEH_DARK, Vector3(sx * 0.2, 0.42, 0.0), Vector3(0.1, 0.08, 0.24))               # bottes
		_rod(m, VEH_SECOND, Vector3(sx * 0.2, 1.5, -0.05), Vector3(sx * 0.36, 1.1, -0.45), 0.05) # bras
	m.region = VEH_SECOND
	_cyl(m, Vector3(0.0, 1.02, 0.22), Vector3(0.0, 1.55, -0.05), Vector2(0.17, 0.12), Vector2(0.2, 0.12), 8)
	m.region = VEH_PAINT
	m.ellipsoid(Vector3(0.0, 1.72, -0.1), Vector3(0.14, 0.15, 0.16))              # casque
	_box(m, VEH_GLASS, Vector3(0.0, 1.71, -0.245), Vector3(0.18, 0.08, 0.04))      # visière


static func _tractor(m) -> void:
	_box(m, VEH_DARK, Vector3(0.0, 0.65, -0.4), Vector3(0.7, 0.4, 2.6))           # châssis
	_box(m, VEH_PAINT, Vector3(0.0, 1.2, -1.15), Vector3(0.95, 0.7, 1.5))         # capot
	m.region = VEH_PAINT
	_cyl(m, Vector3(0.0, 1.55, -1.9), Vector3(0.0, 1.55, -0.4), Vector2(0.475, 0.08), Vector2(0.475, 0.08), 8)   # dessus arrondi
	_box(m, VEH_DARK, Vector3(0.0, 1.15, -1.905), Vector3(0.8, 0.55, 0.02))       # calandre
	_pair(m, VEH_HEAD, Vector3(0.33, 1.44, -1.91), Vector3(0.16, 0.1, 0.03))
	_box(m, VEH_DARK, Vector3(0.0, 0.75, -2.0), Vector3(0.9, 0.35, 0.25))         # masse avant
	_box(m, VEH_PAINT, Vector3(0.0, 1.25, 0.55), Vector3(1.35, 0.2, 1.5))         # plancher
	_box(m, VEH_GLASS, Vector3(0.0, 2.0, 0.55), Vector3(1.3, 1.3, 1.45))          # cabine vitrée
	for sx in [-1.0, 1.0]:
		for z in [-0.18, 1.28]:
			_box(m, VEH_PAINT, Vector3(sx * 0.66, 2.0, z), Vector3(0.07, 1.32, 0.07))   # montants
	_box(m, VEH_PAINT, Vector3(0.0, 2.72, 0.55), Vector3(1.5, 0.14, 1.65))        # toit
	_box(m, VEH_DARK, Vector3(0.0, 1.62, 0.85), Vector3(0.45, 0.25, 0.4))         # siège
	_pair(m, VEH_PAINT, Vector3(0.82, 1.65, 0.75), Vector3(0.5, 0.06, 1.3))       # garde-boue
	_pair(m, VEH_PAINT, Vector3(0.82, 1.4, 1.38), Vector3(0.5, 0.5, 0.06))
	_pair(m, VEH_TAIL, Vector3(0.82, 1.55, 1.42), Vector3(0.12, 0.1, 0.04))
	_rod(m, VEH_DARK, Vector3(0.35, 1.5, -0.75), Vector3(0.35, 2.55, -0.75), 0.04)   # échappement
	_box(m, VEH_HEAD, Vector3(0.0, 2.82, 0.0), Vector3(0.12, 0.08, 0.12))          # gyrophare


## Herse portée derrière le tracteur des champs : attelage, deux poutres, dents.
static func _harrow(m) -> void:
	for sx in [-1.0, 1.0]:
		_rod(m, VEH_METAL, Vector3(sx * 0.3, 0.6, 1.3), Vector3(sx * 0.5, 0.55, 2.4), 0.04)
	_rod(m, VEH_METAL, Vector3(0.0, 1.2, 1.3), Vector3(0.0, 0.75, 2.4), 0.04)
	for z in [2.5, 3.1]:
		_box(m, VEH_SECOND, Vector3(0.0, 0.5, z), Vector3(3.0, 0.12, 0.18))
		for i in range(9):
			_box(m, VEH_METAL, Vector3(-1.4 + 0.35 * i, 0.22, z), Vector3(0.04, 0.44, 0.04))
