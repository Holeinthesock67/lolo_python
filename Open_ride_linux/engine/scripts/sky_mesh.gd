extends RefCounted

## Maillages du ciel (Lot P26), construits par code avec le Builder de people_mesh.gd et les pièces de
## vehicle_mesh.gd, mêmes zones de couleur (VEH_*, shaders/vehicle.gdshader) : avion de ligne `airliner`
## (à l'échelle réelle, 38 m), traînées de condensation `contrail` (shaders/contrail.gdshader), hélicoptère
## `helicopter` et son rotor `rotor`, parapente `paraglider` (voile en caissons, suspentes, pilote),
## montgolfière `balloon` (enveloppe en fuseaux de deux couleurs, nacelle, flamme du brûleur).
## Pas de class_name : charger par preload("res://scripts/sky_mesh.gd").
##
## Repère : avant vers -z, y vers le haut. Avion et hélicoptère : origine au milieu du fuselage ; rotor :
## origine sur son axe ; parapente : origine au pilote ; montgolfière : origine sous la nacelle.
## Traînée : deux rubans en croix derrière chaque réacteur, de z = 0 à z = 1 (longueur donnée par l'échelle
## du nœud en z), UV.y de 0 (réacteur) à 1 (bout), UV.x en travers.

const PeopleMesh := preload("res://scripts/people_mesh.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")

const KINDS := ["airliner", "helicopter", "paraglider", "balloon"]
const ENGINE_X := 5.8
const ENGINE_Y := -1.6
const ENGINE_REAR_Z := -1.0
const CONTRAIL_WIDTH_M := Vector2(1.5, 30.0)   # demi-largeur au réacteur, au bout
const ROTOR_Y := 3.35
const ROTOR_RADIUS_M := 5.3
const WING_RADIUS_M := 6.5
const WING_CELLS := 11
const BALLOON_TOP_M := 26.3
const BURNER_Y := 4.6

const AIRLINER_PAINT := [Color(0.93, 0.93, 0.94), Color(0.95, 0.95, 0.96), Color(0.9, 0.9, 0.92)]
const AIRLINER_TAIL := [Color(0.08, 0.16, 0.42), Color(0.75, 0.1, 0.1), Color(0.95, 0.55, 0.1)]
const HELICOPTER_PAINT := [Color(0.85, 0.12, 0.1), Color(0.95, 0.8, 0.1), Color(0.15, 0.3, 0.55)]
const WING_PAINT := [Color(0.95, 0.35, 0.08), Color(0.1, 0.45, 0.8), Color(0.85, 0.1, 0.35), Color(0.2, 0.65, 0.25)]
const WING_SECOND := [Color(0.98, 0.9, 0.2), Color(0.95, 0.95, 0.95), Color(0.15, 0.1, 0.35), Color(0.98, 0.85, 0.1)]
const BALLOON_PAINT := [Color(0.85, 0.12, 0.1), Color(0.15, 0.35, 0.75), Color(0.98, 0.75, 0.1), Color(0.2, 0.6, 0.3)]
const BALLOON_SECOND := [Color(0.98, 0.85, 0.15), Color(0.95, 0.95, 0.95), Color(0.85, 0.15, 0.1), Color(0.95, 0.95, 0.9)]


## Couleurs d'un engin : [peinture, seconde couleur] d'après son indice.
static func colors(kind: String, index: int) -> Array:
	match kind:
		"airliner":
			return [AIRLINER_PAINT[posmod(index, AIRLINER_PAINT.size())], AIRLINER_TAIL[posmod(index, AIRLINER_TAIL.size())]]
		"helicopter":
			return [HELICOPTER_PAINT[posmod(index, HELICOPTER_PAINT.size())], Color(0.9, 0.9, 0.9)]
		"paraglider":
			return [WING_PAINT[posmod(index, WING_PAINT.size())], WING_SECOND[posmod(index, WING_SECOND.size())]]
		_:
			return [BALLOON_PAINT[posmod(index, BALLOON_PAINT.size())], BALLOON_SECOND[posmod(index, BALLOON_SECOND.size())]]


static func build(kind: String) -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	match kind:
		"airliner":
			_airliner(m)
		"helicopter":
			_helicopter(m)
		"rotor":
			_rotor(m)
		"paraglider":
			_paraglider(m)
		"balloon":
			_balloon(m)
		"contrail":
			_contrail(m)
	return m.commit()


## Plaque plane d'épaisseur `thick` : contour convexe `poly` (points dans le plan de normale `n`).
static func _plate(m, region: int, poly: Array, n: Vector3, thick: float) -> void:
	m.region = region
	var h := n.normalized() * thick * 0.5
	for side in [1.0, -1.0]:
		for i in range(1, poly.size() - 1):
			VehicleMesh._tri(m, poly[0] + h * side, poly[i] + h * side, poly[i + 1] + h * side, n * side)
	var c := Vector3.ZERO
	for p in poly:
		c += p
	c /= poly.size()
	for i in range(poly.size()):
		var a: Vector3 = poly[i]
		var b: Vector3 = poly[(i + 1) % poly.size()]
		var mid := (a + b) * 0.5
		var en := (mid - c) - n.normalized() * (mid - c).dot(n.normalized())
		VehicleMesh._tri(m, a + h, b + h, b - h, en)
		VehicleMesh._tri(m, a + h, b - h, a - h, en)


## Surface de révolution autour de y : profil [[rayon, y], …] de bas en haut ; fuseaux de zone alternée
## (`regions`), normales lissées.
static func _revolve(m, profile: Array, sides: int, regions: Array) -> void:
	for i in range(sides):
		m.region = regions[i % regions.size()]
		var a0 := TAU * float(i) / sides
		var a1 := TAU * float(i + 1) / sides
		for j in range(profile.size() - 1):
			var r0 := float(profile[j][0])
			var y0 := float(profile[j][1])
			var r1 := float(profile[j + 1][0])
			var y1 := float(profile[j + 1][1])
			var slope := Vector2(y1 - y0, -(r1 - r0)).normalized()   # normale du profil (radiale, y)
			var q := []
			for v in [[r0, y0, a0], [r0, y0, a1], [r1, y1, a1], [r1, y1, a0]]:
				var dir := Vector3(sin(v[2]), 0.0, cos(v[2]))
				q.append([dir * float(v[0]) + Vector3(0.0, float(v[1]), 0.0), (dir * slope.x + Vector3(0.0, slope.y, 0.0)).normalized()])
			for tri in [[0, 1, 2], [0, 2, 3]]:
				var p0: Vector3 = q[tri[0]][0]
				var p1: Vector3 = q[tri[1]][0]
				var p2: Vector3 = q[tri[2]][0]
				var order: Array = tri
				if (p1 - p0).cross(p2 - p0).dot(q[tri[0]][1] + q[tri[1]][1] + q[tri[2]][1]) > 0.0:
					order = [tri[0], tri[2], tri[1]]
				for k in order:
					m.vertex(q[k][0], q[k][1])


static func _airliner(m) -> void:
	m.region = VehicleMesh.VEH_PAINT
	VehicleMesh._cyl(m, Vector3(0.0, 0.0, -15.5), Vector3(0.0, 0.0, 14.0), Vector2(2.0, 2.0), Vector2(2.0, 2.0), 12)   # fuselage
	m.region = VehicleMesh.VEH_PAINT
	m.ellipsoid(Vector3(0.0, 0.0, -15.5), Vector3(2.0, 2.0, 3.4), -90.0, 6)   # nez (moitié avant vue de loin)
	m.region = VehicleMesh.VEH_PAINT
	VehicleMesh._cyl(m, Vector3(0.0, 0.0, 14.0), Vector3(0.0, 0.9, 20.5), Vector2(2.0, 2.0), Vector2(0.35, 0.5), 12)   # cône arrière
	VehicleMesh._box(m, VehicleMesh.VEH_GLASS, Vector3(0.0, 0.85, -17.6), Vector3(1.8, 0.45, 0.9))   # pare-brise
	VehicleMesh._pair(m, VehicleMesh.VEH_DARK, Vector3(1.98, 0.45, -1.0), Vector3(0.05, 0.28, 27.0))   # hublots
	for sx in [-1.0, 1.0]:
		_plate(m, VehicleMesh.VEH_PAINT, [Vector3(sx * 1.8, -0.9, -4.0), Vector3(sx * 17.5, -0.1, 4.6),
			Vector3(sx * 17.5, -0.1, 6.4), Vector3(sx * 1.8, -0.9, 4.0)], Vector3.UP, 0.35)   # ailes en flèche
		VehicleMesh._box(m, VehicleMesh.VEH_SECOND, Vector3(sx * 17.6, 0.6, 5.6), Vector3(0.2, 1.6, 1.6))   # ailettes
		VehicleMesh._box(m, VehicleMesh.VEH_HEAD, Vector3(sx * 17.75, -0.1, 5.2), Vector3(0.12, 0.2, 0.3))  # feux à éclats
		m.region = VehicleMesh.VEH_PAINT
		VehicleMesh._cyl(m, Vector3(sx * ENGINE_X, ENGINE_Y, -5.0), Vector3(sx * ENGINE_X, ENGINE_Y, ENGINE_REAR_Z),
			Vector2(0.95, 0.95), Vector2(0.75, 0.75), 10)   # réacteurs
		m.region = VehicleMesh.VEH_DARK
		VehicleMesh._cyl(m, Vector3(sx * ENGINE_X, ENGINE_Y, -5.02), Vector3(sx * ENGINE_X, ENGINE_Y, -4.9),
			Vector2(0.8, 0.8), Vector2(0.8, 0.8), 10)   # entrée d'air
		_plate(m, VehicleMesh.VEH_PAINT, [Vector3(sx * 0.4, 1.0, 15.5), Vector3(sx * 6.2, 1.4, 19.2),
			Vector3(sx * 6.2, 1.4, 20.4), Vector3(sx * 0.4, 1.0, 19.6)], Vector3.UP, 0.25)   # empennage
	_plate(m, VehicleMesh.VEH_SECOND, [Vector3(0.0, 1.6, 13.5), Vector3(0.0, 7.6, 18.4), Vector3(0.0, 7.6, 20.4),
		Vector3(0.0, 1.6, 20.0)], Vector3.RIGHT, 0.3)   # dérive aux couleurs de la compagnie
	VehicleMesh._box(m, VehicleMesh.VEH_TAIL, Vector3(0.0, -2.05, 2.0), Vector3(0.3, 0.12, 0.3))   # feu anticollision


static func _contrail(m) -> void:
	m.region = VehicleMesh.VEH_LIGHT
	for sx in [-1.0, 1.0]:
		var o := Vector3(sx * ENGINE_X, ENGINE_Y, 0.0)
		for axis: Vector3 in [Vector3.RIGHT, Vector3.UP]:
			var n: Vector3 = Vector3.UP if axis == Vector3.RIGHT else Vector3.RIGHT
			# Deux demi-rubans bord → axe : UV.x suit la largeur sans se tordre dans le trapèze
			var tip := Vector3(0.0, 0.0, 1.0)
			for side: float in [-1.0, 1.0]:
				var u := 0.0 if side < 0.0 else 1.0
				var a0 := o + axis * side * CONTRAIL_WIDTH_M.x
				var b0 := o + axis * side * CONTRAIL_WIDTH_M.y + tip
				var quad := [[a0, u, 0.0], [o, 0.5, 0.0], [o + tip, 0.5, 1.0], [a0, u, 0.0], [o + tip, 0.5, 1.0], [b0, u, 1.0]]
				if side > 0.0:
					quad = [quad[0], quad[2], quad[1], quad[3], quad[5], quad[4]]
				for v in quad:
					m.vertex(v[0], n, v[1], v[2])


static func _helicopter(m) -> void:
	m.region = VehicleMesh.VEH_PAINT
	m.ellipsoid(Vector3(0.0, 1.6, -1.2), Vector3(1.15, 1.25, 2.4))   # cabine
	m.region = VehicleMesh.VEH_GLASS
	m.ellipsoid(Vector3(0.0, 1.85, -2.6), Vector3(1.0, 0.95, 1.15), -20.0, 5)   # verrière
	m.region = VehicleMesh.VEH_PAINT
	VehicleMesh._cyl(m, Vector3(0.0, 2.0, 0.8), Vector3(0.0, 2.45, 7.6), Vector2(0.5, 0.5), Vector2(0.2, 0.25), 8)   # poutre de queue
	_plate(m, VehicleMesh.VEH_PAINT, [Vector3(0.0, 2.2, 6.8), Vector3(0.0, 3.6, 7.8), Vector3(0.0, 3.6, 8.3),
		Vector3(0.0, 2.2, 7.9)], Vector3.RIGHT, 0.12)   # dérive
	_plate(m, VehicleMesh.VEH_DARK, [Vector3(0.16, 3.0, 7.4), Vector3(0.16, 3.1, 8.6), Vector3(0.16, 2.5, 8.7),
		Vector3(0.16, 2.4, 7.5)], Vector3.RIGHT, 0.03)   # rotor de queue (disque flou)
	VehicleMesh._box(m, VehicleMesh.VEH_PAINT, Vector3(0.0, 2.95, -0.6), Vector3(1.0, 0.5, 2.0))   # capot moteur
	VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(0.0, 3.1, -0.6), Vector3(0.0, ROTOR_Y, -0.6), 0.1)   # mât
	for sx in [-1.0, 1.0]:
		VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(sx * 0.95, 0.05, -3.0), Vector3(sx * 0.95, 0.05, 1.6), 0.05)   # patins
		for z in [-2.0, 0.6]:
			VehicleMesh._rod(m, VehicleMesh.VEH_METAL, Vector3(sx * 0.95, 0.05, z), Vector3(sx * 0.6, 0.7, z), 0.04)
	VehicleMesh._box(m, VehicleMesh.VEH_TAIL, Vector3(0.0, 3.25, 0.6), Vector3(0.16, 0.1, 0.16))   # feu à éclats
	VehicleMesh._box(m, VehicleMesh.VEH_HEAD, Vector3(0.0, 0.35, -3.0), Vector3(0.25, 0.12, 0.12))   # phare


## Rotor principal à quatre pales, axe y à l'origine (le nœud tourne autour de y).
static func _rotor(m) -> void:
	for i in range(4):
		var a := TAU * float(i) / 4.0
		var saved: Transform3D = m.xform
		m.xform = saved * Transform3D(Basis(Vector3.UP, a), Vector3.ZERO)
		VehicleMesh._box(m, VehicleMesh.VEH_DARK, Vector3(0.0, 0.0, -ROTOR_RADIUS_M * 0.5), Vector3(0.32, 0.05, ROTOR_RADIUS_M))
		m.xform = saved
	VehicleMesh._box(m, VehicleMesh.VEH_METAL, Vector3.ZERO, Vector3(0.5, 0.2, 0.5))


static func _paraglider(m) -> void:
	var centre := Vector3(0.0, 1.5, 0.0)
	var span := deg_to_rad(64.0)
	for i in range(WING_CELLS):
		var a := lerpf(-span, span, (i + 0.5) / WING_CELLS)
		var saved: Transform3D = m.xform
		m.xform = saved * Transform3D(Basis(Vector3.BACK, -a), centre + Vector3(sin(a), cos(a), 0.0) * WING_RADIUS_M)
		m.region = VehicleMesh.VEH_PAINT if i % 2 == 0 else VehicleMesh.VEH_SECOND
		m.box(Vector3(0.0, 0.0, 0.2), Vector3(2.0 * WING_RADIUS_M * sin(span / WING_CELLS) + 0.02, 0.32, 2.6))
		m.xform = saved
	for a in [-span * 0.85, -span * 0.35, span * 0.35, span * 0.85]:
		var tip := centre + Vector3(sin(a), cos(a), 0.0) * (WING_RADIUS_M - 0.16)
		VehicleMesh._rod(m, VehicleMesh.VEH_DARK, Vector3(signf(a) * 0.2, 0.55, -0.1), tip + Vector3(0.0, 0.0, -0.4), 0.015, 3)   # suspentes
		VehicleMesh._rod(m, VehicleMesh.VEH_DARK, Vector3(signf(a) * 0.2, 0.55, 0.2), tip + Vector3(0.0, 0.0, 0.9), 0.015, 3)
	# Pilote assis dans sa sellette
	VehicleMesh._box(m, VehicleMesh.VEH_DARK, Vector3(0.0, 0.0, 0.15), Vector3(0.5, 0.45, 0.9))
	VehicleMesh._rod(m, VehicleMesh.VEH_SECOND, Vector3(0.0, 0.15, 0.15), Vector3(0.0, 0.75, 0.1), 0.18, 6)
	for sx in [-1.0, 1.0]:
		VehicleMesh._rod(m, VehicleMesh.VEH_DARK, Vector3(sx * 0.12, 0.05, -0.2), Vector3(sx * 0.12, -0.25, -0.75), 0.07)
	m.region = VehicleMesh.VEH_PAINT
	m.ellipsoid(Vector3(0.0, 0.95, 0.08), Vector3(0.15, 0.16, 0.17))   # casque


static func _balloon(m) -> void:
	var profile := [[2.2, 5.0], [4.5, 8.0], [7.5, 12.0], [9.0, 16.0], [9.2, 19.0], [8.2, 22.5], [5.5, 25.2], [0.01, BALLOON_TOP_M]]
	_revolve(m, profile, 16, [VehicleMesh.VEH_PAINT, VehicleMesh.VEH_SECOND])
	VehicleMesh._box(m, VehicleMesh.VEH_DARK, Vector3(0.0, 0.55, 0.0), Vector3(1.4, 1.1, 1.4))   # nacelle
	VehicleMesh._box(m, VehicleMesh.VEH_LIGHT, Vector3(0.0, 1.12, 0.0), Vector3(1.5, 0.06, 1.5))   # bord
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			VehicleMesh._rod(m, VehicleMesh.VEH_DARK, Vector3(sx * 0.68, 1.1, sz * 0.68), Vector3(sx * 1.55, 5.0, sz * 1.55), 0.025, 3)
	VehicleMesh._box(m, VehicleMesh.VEH_METAL, Vector3(0.0, 3.4, 0.0), Vector3(0.5, 0.35, 0.5))   # brûleur
	m.region = VehicleMesh.VEH_HEAD
	m.ellipsoid(Vector3(0.0, BURNER_Y, 0.0), Vector3(0.22, 0.6, 0.22), -90.0, 4)   # flamme
