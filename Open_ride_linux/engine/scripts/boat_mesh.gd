extends RefCounted

## Maillages des bateaux (Lot P29), construits par code avec le Builder de people_mesh.gd et les pièces de
## vehicle_mesh.gd, mêmes zones de couleur (VEH_*, shaders/vehicle.gdshader) : voilier `sailboat` (sa voile
## `sail` à part, qui pivote autour du mât), barque `rowboat` et son rameur, pédalo `pedalo` et deux
## personnes, canoë `canoe` (deux pagayeurs), kayak `kayak`, péniche `barge`, ferry `ferry`, porte-conteneurs
## `cargo` ; sillage `wake` (shaders/wake.gdshader).
## Pas de class_name : charger par preload("res://scripts/boat_mesh.gd").
##
## Repère : ligne de flottaison à y = 0, avant vers -z, axe au milieu en x. Les coques sont des sections en
## travers (demi-largeur, pont, quille) le long de z, pointues à l'étrave, à tableau ou pointues à l'arrière ;
## œuvres vives en seconde zone sous la flottaison. Personnes en pièces simples (zones peau, sombre et gilet
## de la seconde couleur), comme le motard de vehicle_mesh.gd.
## Sillage : ruban à plat de z = 0 à z = 1 (longueur donnée par l'échelle du nœud en z, largeur par x),
## UV.y de 0 (poupe) à 1 (bout), UV.x en travers.

const PeopleMesh := preload("res://scripts/people_mesh.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const SkyMesh := preload("res://scripts/sky_mesh.gd")

const KINDS := ["sailboat", "rowboat", "pedalo", "canoe", "kayak", "barge", "ferry", "cargo"]
## Longueur et largeur hors tout (m), tirant d'eau de la coque.
const SIZE := {
	"sailboat": Vector2(8.0, 2.8), "rowboat": Vector2(4.0, 1.5), "pedalo": Vector2(2.6, 1.7),
	"canoe": Vector2(5.0, 0.85), "kayak": Vector2(3.6, 0.62), "barge": Vector2(38.5, 5.05),
	"ferry": Vector2(120.0, 22.0), "cargo": Vector2(180.0, 28.0),
}
const MAST_Z := -0.6
const MAST_TOP_M := 11.0
const SAIL_FOOT_M := 1.7
const WAKE_WIDTH := Vector2(0.5, 1.6)   # demi-largeur du sillage à la poupe et au bout, en largeurs du bateau
const SECTIONS := 12

const SAILBOAT_PAINT := [Color(0.95, 0.95, 0.94), Color(0.1, 0.16, 0.35), Color(0.75, 0.12, 0.1), Color(0.92, 0.9, 0.82)]
const SMALL_PAINT := [Color(0.85, 0.15, 0.1), Color(0.15, 0.4, 0.7), Color(0.2, 0.55, 0.3), Color(0.95, 0.75, 0.1)]
const BARGE_PAINT := [Color(0.1, 0.12, 0.14), Color(0.12, 0.25, 0.18), Color(0.45, 0.08, 0.08)]
const SHIP_PAINT := {"ferry": [Color(0.95, 0.95, 0.96)], "cargo": [Color(0.12, 0.18, 0.32), Color(0.5, 0.1, 0.08), Color(0.15, 0.3, 0.25)]}
const SECOND := {
	"sailboat": Color(0.25, 0.25, 0.3), "rowboat": Color(0.95, 0.45, 0.08), "pedalo": Color(0.95, 0.45, 0.08),
	"canoe": Color(0.95, 0.45, 0.08), "kayak": Color(0.95, 0.75, 0.1), "barge": Color(0.2, 0.3, 0.2),
	"ferry": Color(0.1, 0.25, 0.6), "cargo": Color(0.2, 0.45, 0.7),
}


## Couleurs d'un bateau : [peinture, seconde couleur] d'après son indice.
static func colors(kind: String, index: int) -> Array:
	var list: Array = SMALL_PAINT
	match kind:
		"sailboat":
			list = SAILBOAT_PAINT
		"barge":
			list = BARGE_PAINT
		"ferry", "cargo":
			list = SHIP_PAINT[kind]
	return [list[posmod(index, list.size())], SECOND.get(kind, Color(0.5, 0.5, 0.5))]


static func build(kind: String) -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	match kind:
		"sailboat":
			_sailboat(m)
		"sail":
			_sail(m)
		"rowboat":
			_rowboat(m)
		"pedalo":
			_pedalo(m)
		"canoe":
			_canoe(m)
		"kayak":
			_kayak(m)
		"barge":
			_barge(m)
		"ferry":
			_ferry(m)
		"cargo":
			_cargo(m)
		"wake":
			_wake(m)
	return m.commit()


# --- Pièces ---------------------------------------------------------------------------------------------

## Coque. `s` : `length`, `beam`, `freeboard` (pont au-dessus de l'eau), `draft`, `bow` (part de la longueur
## où l'étrave s'élargit), `stern` (largeur du tableau en part de la largeur, 0 : pointue), `sheer` (pont
## relevé à l'étrave), `top` et `bottom` (zones au-dessus et sous la flottaison), `deck` (zone du pont, -1 :
## bateau ouvert, plancher `floor` à cette hauteur).
static func _hull(m, s: Dictionary) -> void:
	var length: float = s["length"]
	var hw: float = float(s["beam"]) * 0.5
	var fb: float = s["freeboard"]
	var draft: float = s["draft"]
	var bow: float = s["bow"]
	var stern: float = s["stern"]
	var sheer: float = s.get("sheer", 0.0)
	var secs := []
	for i in range(SECTIONS + 1):
		var t := float(i) / SECTIONS
		var w := hw * (pow(sin(clampf(t / bow, 0.0, 1.0) * PI * 0.5), 0.7) if t < bow else 1.0)
		w *= lerpf(1.0, stern, smoothstep(0.55, 1.0, t))
		w = maxf(w, 0.01)
		var deck := fb + sheer * (1.0 - t) * (1.0 - t)
		var keel := -draft * (1.0 - 0.6 * (1.0 - smoothstep(0.0, 0.3, t)) - 0.3 * smoothstep(0.85, 1.0, t))
		var z := -length * 0.5 + t * length
		secs.append([z, w, deck, keel])
	var mid_y := (fb - draft) * 0.5
	for i in range(SECTIONS):
		var sa: Array = secs[i]
		var sb: Array = secs[i + 1]
		var pa := _profile(sa)
		var pb := _profile(sb)
		for j in range(pa.size() - 1):
			m.region = s["top"] if j == 0 else s["bottom"]
			for sx in [-1.0, 1.0]:
				var a := Vector3(sx * pa[j].x, pa[j].y, sa[0])
				var b := Vector3(sx * pa[j + 1].x, pa[j + 1].y, sa[0])
				var c := Vector3(sx * pb[j + 1].x, pb[j + 1].y, sb[0])
				var d := Vector3(sx * pb[j].x, pb[j].y, sb[0])
				var centre := (a + b + c + d) * 0.25
				var out := Vector3(centre.x, centre.y - mid_y, 0.0)
				_quad(m, a, b, c, d, out)
		if int(s["deck"]) >= 0:
			m.region = s["deck"]
			_quad(m, Vector3(-sa[1], sa[2], sa[0]), Vector3(sa[1], sa[2], sa[0]), Vector3(sb[1], sb[2], sb[0]),
				Vector3(-sb[1], sb[2], sb[0]), Vector3.UP)
		else:
			m.region = VehicleMesh.VEH_WOOD
			var fy: float = s["floor"]
			var ka := 0.8 * _width_at(sa, fy)
			var kb := 0.8 * _width_at(sb, fy)
			_quad(m, Vector3(-ka, fy, sa[0]), Vector3(ka, fy, sa[0]), Vector3(kb, fy, sb[0]), Vector3(-kb, fy, sb[0]), Vector3.UP)
	if stern > 0.0:
		var last: Array = secs[SECTIONS]
		var p := _profile(last)
		var c := Vector3(0.0, (float(last[2]) + float(last[3])) * 0.5, last[0])
		for j in range(p.size() - 1):
			m.region = s["top"] if j == 0 else s["bottom"]
			for sx in [-1.0, 1.0]:
				VehicleMesh._tri(m, c, Vector3(sx * p[j].x, p[j].y, last[0]), Vector3(sx * p[j + 1].x, p[j + 1].y, last[0]), Vector3.BACK)
		m.region = s["top"]
		VehicleMesh._tri(m, c, Vector3(-p[0].x, p[0].y, last[0]), Vector3(p[0].x, p[0].y, last[0]), Vector3.BACK)


## Profil d'une section [z, demi-largeur, pont, quille], côté x > 0, du pont à la quille.
static func _profile(sec: Array) -> Array:
	var w: float = sec[1]
	return [Vector2(w, sec[2]), Vector2(w * 0.97, 0.0), Vector2(w * 0.6, float(sec[3]) * 0.85), Vector2(0.0, sec[3])]


## Demi-largeur de la coque à la hauteur `y` d'une section (pour le plancher des bateaux ouverts).
static func _width_at(sec: Array, y: float) -> float:
	var p := _profile(sec)
	for j in range(p.size() - 1):
		if y <= p[j].y and y >= p[j + 1].y:
			return lerpf(p[j].x, p[j + 1].x, (p[j].y - y) / maxf(p[j].y - p[j + 1].y, 1e-4))
	return p[p.size() - 1].x


static func _quad(m, a: Vector3, b: Vector3, c: Vector3, d: Vector3, out: Vector3) -> void:
	var n := (b - a).cross(d - a)
	if n.length() < 1e-8:
		n = (c - b).cross(a - b)
	n = n.normalized()
	if n.dot(out) < 0.0:
		n = -n
	VehicleMesh._tri(m, a, b, c, n)
	VehicleMesh._tri(m, a, c, d, n)


## Personne assise au point `seat` (hanches), tournée vers -z (`facing` = 1) ou +z (-1), mains en `hands`.
static func _person(m, seat: Vector3, facing: float, hands: Array, legs_m: float = 0.45) -> void:
	var f := Vector3(0.0, 0.0, -facing)
	var neck := seat + Vector3(0.0, 0.55, 0.0)
	m.region = VehicleMesh.VEH_SECOND
	VehicleMesh._cyl(m, seat + Vector3(0.0, 0.02, 0.0), neck, Vector2(0.17, 0.12), Vector2(0.19, 0.12), 8)   # buste et gilet
	m.region = VehicleMesh.VEH_SKIN
	m.ellipsoid(neck + Vector3(0.0, 0.17, 0.0), Vector3(0.1, 0.12, 0.11))   # tête
	for i in range(2):
		var sx := -1.0 if i == 0 else 1.0
		var knee := seat + Vector3(sx * 0.1, 0.12, 0.0) + f * legs_m
		VehicleMesh._rod(m, VehicleMesh.VEH_DARK, seat + Vector3(sx * 0.1, 0.0, 0.0), knee, 0.065)   # cuisses
		VehicleMesh._rod(m, VehicleMesh.VEH_DARK, knee, knee + Vector3(0.0, -0.38, 0.0) + f * 0.1, 0.05)   # jambes
		var hand: Vector3 = hands[i]
		VehicleMesh._rod(m, VehicleMesh.VEH_SECOND, neck + Vector3(sx * 0.18, -0.06, 0.0), hand, 0.045)   # bras
		m.region = VehicleMesh.VEH_SKIN
		m.ellipsoid(hand, Vector3(0.045, 0.045, 0.045), -90.0, 3)


## Pagaie de `a` (main basse) à `b` (main haute), pale au bout `a` prolongé.
static func _paddle(m, a: Vector3, b: Vector3, double: bool) -> void:
	var d := (a - b).normalized()
	VehicleMesh._rod(m, VehicleMesh.VEH_DARK, b - d * (0.55 if double else 0.15), a + d * 0.55, 0.018, 5)
	VehicleMesh._box(m, VehicleMesh.VEH_SECOND, a + d * 0.7, Vector3(0.04, 0.18, 0.18) if absf(d.x) > 0.5 else Vector3(0.17, 0.04, 0.2))
	if double:
		VehicleMesh._box(m, VehicleMesh.VEH_SECOND, b - d * 0.7, Vector3(0.04, 0.18, 0.18) if absf(d.x) > 0.5 else Vector3(0.17, 0.04, 0.2))


# --- Bateaux --------------------------------------------------------------------------------------------

static func _sailboat(m) -> void:
	_hull(m, {"length": 8.0, "beam": 2.8, "freeboard": 0.9, "draft": 0.45, "bow": 0.42, "stern": 0.72, "sheer": 0.18,
		"top": VehicleMesh.VEH_PAINT, "bottom": VehicleMesh.VEH_SECOND, "deck": VehicleMesh.VEH_LIGHT})
	VehicleMesh._box(m, VehicleMesh.VEH_DARK, Vector3(0.0, -1.0, 0.2), Vector3(0.18, 1.2, 1.4))   # quille
	VehicleMesh._box(m, VehicleMesh.VEH_DARK, Vector3(0.0, -0.3, 3.7), Vector3(0.08, 0.9, 0.5))   # safran
	VehicleMesh._box(m, VehicleMesh.VEH_LIGHT, Vector3(0.0, 1.17, 0.0), Vector3(1.8, 0.55, 2.8))   # rouf
	VehicleMesh._pair(m, VehicleMesh.VEH_GLASS, Vector3(0.91, 1.2, 0.0), Vector3(0.03, 0.18, 1.8))   # hublots
	VehicleMesh._box(m, VehicleMesh.VEH_GLASS, Vector3(0.0, 1.22, -1.41), Vector3(1.2, 0.2, 0.03))
	VehicleMesh._box(m, VehicleMesh.VEH_DARK, Vector3(0.0, 0.92, 2.6), Vector3(1.6, 0.06, 1.9))   # cockpit
	VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(0.0, 1.4, MAST_Z), Vector3(0.0, MAST_TOP_M, MAST_Z), 0.07)   # mât
	VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(0.0, MAST_TOP_M - 0.2, MAST_Z), Vector3(0.0, 1.2, -3.85), 0.012, 4)   # étai
	SkyMesh._plate(m, VehicleMesh.VEH_LIGHT, [Vector3(0.02, 9.6, MAST_Z - 0.15), Vector3(0.02, 1.35, -3.7),
		Vector3(0.02, 1.5, MAST_Z - 0.3)], Vector3.RIGHT, 0.02)   # foc
	VehicleMesh._box(m, VehicleMesh.VEH_HEAD, Vector3(0.0, MAST_TOP_M + 0.05, MAST_Z), Vector3(0.1, 0.1, 0.1))   # feu de tête de mât
	_person(m, Vector3(0.65, 1.15, 3.0), 1.0, [Vector3(0.45, 1.25, 3.5), Vector3(0.75, 1.3, 2.6)], 0.4)   # barreur


## Grand-voile et bôme : origine au pied du mât, la voile s'étend vers +z (le nœud pivote autour de y).
static func _sail(m) -> void:
	SkyMesh._plate(m, VehicleMesh.VEH_LIGHT, [Vector3(0.0, MAST_TOP_M - 0.5 - SAIL_FOOT_M, 0.08), Vector3(0.0, 0.05, 3.4),
		Vector3(0.0, 0.05, 0.08)], Vector3.RIGHT, 0.02)
	VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(0.0, 0.0, 0.05), Vector3(0.0, 0.0, 3.55), 0.05)   # bôme


static func _rowboat(m) -> void:
	_hull(m, {"length": 4.0, "beam": 1.5, "freeboard": 0.45, "draft": 0.22, "bow": 0.34, "stern": 0.6, "sheer": 0.12,
		"top": VehicleMesh.VEH_PAINT, "bottom": VehicleMesh.VEH_PAINT, "deck": -1, "floor": -0.05})
	for z in [-0.9, 0.2, 1.4]:
		VehicleMesh._box(m, VehicleMesh.VEH_WOOD, Vector3(0.0, 0.22, z), Vector3(1.3, 0.05, 0.28))   # bancs
	VehicleMesh._pair(m, VehicleMesh.VEH_WOOD, Vector3(0.72, 0.46, 0.0), Vector3(0.06, 0.05, 3.6))   # plat-bord
	var lock := 0.74
	_person(m, Vector3(0.0, 0.27, 0.25), -1.0, [Vector3(-0.42, 0.55, -0.2), Vector3(0.42, 0.55, -0.2)], 0.5)   # rameur vers l'arrière
	for sx in [-1.0, 1.0]:
		var a := Vector3(sx * 0.32, 0.55, -0.2)
		var b := Vector3(sx * (lock + 1.9), -0.02, 0.35)
		VehicleMesh._rod(m, VehicleMesh.VEH_WOOD, a, b, 0.025, 5)   # avirons
		VehicleMesh._box(m, VehicleMesh.VEH_WOOD, b + Vector3(sx * 0.2, -0.01, 0.06), Vector3(0.45, 0.03, 0.14))


static func _pedalo(m) -> void:
	for sx in [-1.0, 1.0]:
		m.region = VehicleMesh.VEH_PAINT
		VehicleMesh._cyl(m, Vector3(sx * 0.6, 0.0, -1.3), Vector3(sx * 0.6, 0.02, 1.2), Vector2(0.2, 0.15), Vector2(0.28, 0.25), 8)   # flotteurs
	VehicleMesh._box(m, VehicleMesh.VEH_LIGHT, Vector3(0.0, 0.32, 0.1), Vector3(1.5, 0.12, 1.9))   # plateforme
	VehicleMesh._box(m, VehicleMesh.VEH_PAINT, Vector3(0.0, 0.6, 0.55), Vector3(1.3, 0.5, 0.12))   # dossier
	VehicleMesh._box(m, VehicleMesh.VEH_LIGHT, Vector3(0.0, 1.4, 0.2), Vector3(1.6, 0.05, 1.4))   # toit
	for sx in [-0.62, 0.62]:
		VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(sx, 0.38, 0.75), Vector3(sx, 1.38, 0.75), 0.025)
		VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(sx, 0.38, -0.4), Vector3(sx, 1.38, -0.4), 0.025)
	for x in [-0.33, 0.33]:
		_person(m, Vector3(x, 0.45, 0.4), 1.0, [Vector3(x - 0.15, 0.62, 0.05), Vector3(x + 0.15, 0.62, 0.05)], 0.5)


static func _canoe(m) -> void:
	_hull(m, {"length": 5.0, "beam": 0.85, "freeboard": 0.32, "draft": 0.14, "bow": 0.4, "stern": 0.0, "sheer": 0.14,
		"top": VehicleMesh.VEH_PAINT, "bottom": VehicleMesh.VEH_PAINT, "deck": -1, "floor": -0.06})
	VehicleMesh._pair(m, VehicleMesh.VEH_WOOD, Vector3(0.39, 0.32, 0.0), Vector3(0.04, 0.04, 4.2))   # plat-bords
	for z in [-1.4, 1.4]:
		_person(m, Vector3(0.0, 0.08, z), 1.0, [Vector3(0.3, 0.2, z - 0.25), Vector3(0.22, 0.85, z + 0.05)], 0.5)
		_paddle(m, Vector3(0.38, -0.1, z - 0.3), Vector3(0.22, 0.85, z + 0.05), false)


static func _kayak(m) -> void:
	_hull(m, {"length": 3.6, "beam": 0.62, "freeboard": 0.22, "draft": 0.12, "bow": 0.45, "stern": 0.0, "sheer": 0.05,
		"top": VehicleMesh.VEH_PAINT, "bottom": VehicleMesh.VEH_PAINT, "deck": VehicleMesh.VEH_PAINT})
	m.region = VehicleMesh.VEH_DARK
	m.ellipsoid(Vector3(0.0, 0.23, 0.2), Vector3(0.24, 0.04, 0.42), 0.0, 3)   # hiloire
	_person(m, Vector3(0.0, 0.12, 0.3), 1.0, [Vector3(-0.32, 0.55, -0.05), Vector3(0.32, 0.55, -0.05)], 0.6)
	_paddle(m, Vector3(-0.32, 0.55, -0.05), Vector3(0.32, 0.55, -0.05), true)


static func _barge(m) -> void:
	_hull(m, {"length": 38.5, "beam": 5.05, "freeboard": 0.9, "draft": 1.6, "bow": 0.1, "stern": 0.88, "sheer": 0.5,
		"top": VehicleMesh.VEH_PAINT, "bottom": VehicleMesh.VEH_DARK, "deck": VehicleMesh.VEH_DARK})
	VehicleMesh._box(m, VehicleMesh.VEH_SECOND, Vector3(0.0, 1.35, -3.0), Vector3(4.3, 0.9, 25.0))   # cales bâchées
	m.region = VehicleMesh.VEH_SECOND
	VehicleMesh._cyl(m, Vector3(0.0, 1.8, -15.5), Vector3(0.0, 1.8, 9.5), Vector2(1.9, 0.35), Vector2(1.9, 0.35), 6)   # arrondi de la bâche
	VehicleMesh._box(m, VehicleMesh.VEH_LIGHT, Vector3(0.0, 1.9, 13.6), Vector3(4.4, 2.0, 5.0))   # logement
	VehicleMesh._box(m, VehicleMesh.VEH_PAINT, Vector3(0.0, 3.7, 15.0), Vector3(2.6, 1.6, 2.2))   # timonerie
	VehicleMesh._box(m, VehicleMesh.VEH_GLASS, Vector3(0.0, 3.9, 13.89), Vector3(2.3, 0.7, 0.03))
	VehicleMesh._pair(m, VehicleMesh.VEH_GLASS, Vector3(1.31, 3.9, 15.0), Vector3(0.03, 0.7, 1.6))
	VehicleMesh._pair(m, VehicleMesh.VEH_GLASS, Vector3(2.21, 2.2, 13.4), Vector3(0.03, 0.5, 3.6))   # fenêtres du logement
	VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(0.0, 4.5, 16.0), Vector3(0.0, 6.2, 16.0), 0.04)   # mât de feux
	VehicleMesh._box(m, VehicleMesh.VEH_HEAD, Vector3(0.0, 6.25, 16.0), Vector3(0.15, 0.15, 0.15))
	VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(0.0, 0.9, 19.0), Vector3(0.0, 3.2, 19.0), 0.03)   # hampe du pavillon
	SkyMesh._plate(m, VehicleMesh.VEH_TAIL, [Vector3(0.0, 3.2, 19.0), Vector3(0.0, 3.2, 20.0), Vector3(0.0, 2.55, 20.0),
		Vector3(0.0, 2.55, 19.0)], Vector3.RIGHT, 0.02)
	VehicleMesh._box(m, VehicleMesh.VEH_METAL, Vector3(0.0, 1.05, -18.2), Vector3(0.6, 0.3, 0.6))   # treuil d'ancre


static func _ferry(m) -> void:
	_hull(m, {"length": 120.0, "beam": 22.0, "freeboard": 7.0, "draft": 5.0, "bow": 0.22, "stern": 0.85, "sheer": 1.5,
		"top": VehicleMesh.VEH_PAINT, "bottom": VehicleMesh.VEH_DARK, "deck": VehicleMesh.VEH_LIGHT})
	VehicleMesh._pair(m, VehicleMesh.VEH_SECOND, Vector3(10.98, 3.0, 8.0), Vector3(0.08, 1.4, 94.0))   # bande de la compagnie
	var decks := [[7.0, 20.0, -32.0, 46.0], [10.0, 19.0, -28.0, 42.0], [13.0, 17.0, -22.0, 34.0], [16.0, 12.0, -14.0, 12.0]]
	for dk in decks:
		var y0: float = dk[0]
		var w: float = dk[1]
		var z0: float = dk[2]
		var z1: float = dk[3]
		VehicleMesh._box(m, VehicleMesh.VEH_PAINT, Vector3(0.0, y0 + 1.5, (z0 + z1) * 0.5), Vector3(w, 3.0, z1 - z0))
		VehicleMesh._pair(m, VehicleMesh.VEH_GLASS, Vector3(w * 0.5 + 0.02, y0 + 1.7, (z0 + z1) * 0.5), Vector3(0.04, 1.0, (z1 - z0) - 3.0))
		VehicleMesh._box(m, VehicleMesh.VEH_GLASS, Vector3(0.0, y0 + 1.7, z0 - 0.02), Vector3(w - 3.0, 1.0, 0.04))
	VehicleMesh._box(m, VehicleMesh.VEH_GLASS, Vector3(0.0, 17.8, -14.05), Vector3(13.0, 1.2, 0.04))   # passerelle
	m.region = VehicleMesh.VEH_SECOND
	VehicleMesh._cyl(m, Vector3(0.0, 19.0, 24.0), Vector3(0.0, 26.0, 26.0), Vector2(2.6, 4.2), Vector2(2.2, 3.6), 10)   # cheminée
	VehicleMesh._box(m, VehicleMesh.VEH_DARK, Vector3(0.0, 26.1, 26.0), Vector3(4.2, 0.4, 7.0))
	for z in [-18.0, -6.0, 6.0, 18.0, 30.0]:
		VehicleMesh._pair(m, VehicleMesh.VEH_SKIN, Vector3(9.7, 12.3, z), Vector3(1.6, 1.2, 6.5))   # canots de sauvetage
	VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(0.0, 19.0, -10.0), Vector3(0.0, 27.0, -10.0), 0.25)   # mât
	VehicleMesh._box(m, VehicleMesh.VEH_HEAD, Vector3(0.0, 27.2, -10.0), Vector3(0.5, 0.5, 0.5))


static func _cargo(m) -> void:
	_hull(m, {"length": 180.0, "beam": 28.0, "freeboard": 6.0, "draft": 9.0, "bow": 0.16, "stern": 0.8, "sheer": 2.5,
		"top": VehicleMesh.VEH_PAINT, "bottom": VehicleMesh.VEH_TAIL, "deck": VehicleMesh.VEH_DARK})
	var regions := [VehicleMesh.VEH_SECOND, VehicleMesh.VEH_WOOD, VehicleMesh.VEH_LIGHT, VehicleMesh.VEH_METAL, VehicleMesh.VEH_SKIN,
		VehicleMesh.VEH_PAINT]
	var bay := 0
	var z := -68.0
	while z < 50.0:
		for half in [-1.0, 1.0]:
			var tiers := 2 + (bay * 7 + (3 if half > 0.0 else 0)) % 3
			var k := (bay * 5 + (2 if half > 0.0 else 0)) % regions.size()
			VehicleMesh._box(m, regions[k], Vector3(half * 6.2, 6.0 + tiers * 1.3, z + 6.3), Vector3(12.2, tiers * 2.6, 12.2))
			VehicleMesh._box(m, regions[(k + 1) % regions.size()], Vector3(half * 6.2, 6.0 + tiers * 2.6 + 1.3, z + 3.2),
				Vector3(12.2, 2.6, 6.0))   # conteneurs du dessus, d'une autre couleur
		bay += 1
		z += 13.0
	VehicleMesh._box(m, VehicleMesh.VEH_LIGHT, Vector3(0.0, 13.0, 70.0), Vector3(26.0, 14.0, 14.0))   # château
	VehicleMesh._box(m, VehicleMesh.VEH_LIGHT, Vector3(0.0, 21.5, 66.0), Vector3(34.0, 3.0, 6.0))   # passerelle et ailerons
	VehicleMesh._box(m, VehicleMesh.VEH_GLASS, Vector3(0.0, 21.8, 62.97), Vector3(32.0, 1.4, 0.06))
	VehicleMesh._pair(m, VehicleMesh.VEH_GLASS, Vector3(13.03, 14.0, 70.0), Vector3(0.06, 8.0, 10.0))
	m.region = VehicleMesh.VEH_SECOND
	VehicleMesh._cyl(m, Vector3(0.0, 20.0, 75.0), Vector3(0.0, 30.0, 76.0), Vector2(3.0, 4.5), Vector2(2.6, 4.0), 10)   # cheminée
	VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(0.0, 6.0, -84.0), Vector3(0.0, 18.0, -84.0), 0.3)   # mât avant
	VehicleMesh._box(m, VehicleMesh.VEH_HEAD, Vector3(0.0, 18.2, -84.0), Vector3(0.6, 0.6, 0.6))


## Sillage : deux demi-rubans bord → axe, à 3 cm au-dessus de l'eau (voir l'en-tête).
static func _wake(m) -> void:
	m.region = VehicleMesh.VEH_LIGHT
	var o := Vector3(0.0, 0.03, 0.0)
	var tip := Vector3(0.0, 0.0, 1.0)
	for side: float in [-1.0, 1.0]:
		var u := 0.0 if side < 0.0 else 1.0
		var a0 := o + Vector3(side * WAKE_WIDTH.x, 0.0, 0.0)
		var b0 := o + Vector3(side * WAKE_WIDTH.y, 0.0, 0.0) + tip
		var quad := [[a0, u, 0.0], [o, 0.5, 0.0], [o + tip, 0.5, 1.0], [a0, u, 0.0], [o + tip, 0.5, 1.0], [b0, u, 1.0]]
		if side > 0.0:
			quad = [quad[0], quad[2], quad[1], quad[3], quad[5], quad[4]]
		for v in quad:
			m.vertex(v[0], Vector3.UP, v[1], v[2])
