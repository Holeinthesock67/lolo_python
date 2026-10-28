extends RefCounted

## Maillages des véhicules du décor (lots P13 et P25), construits par code avec le Builder de people_mesh.gd
## (Y14), sans texture : berline `car_a`, petite voiture haute `car_b`, camionnette `van`, camion porteur
## `truck`, autobus `bus`, moto et son pilote `moto`, tracteur `tractor`, tracteur et charrue `tractor_plough`,
## et `far`, boîte d'un mètre de côté pour les véhicules lointains (mise à l'échelle par KINDS).
## Pas de class_name : charger par preload("res://scripts/vehicle_mesh.gd").
##
## Avant vers -z (convention de traffic_model.world_transform), roues au sol à y = 0, centre en x = 0 et
## au milieu de la longueur (tracteur et charrue : origine au milieu du tracteur, charrue derrière). Données par sommet lues par shaders/vehicle.gdshader :
## - CUSTOM0.x : zone (VEH_*), qui choisit la couleur : peinture (couleur d'instance), vitres, pneus,
##   plastique noir, métal, phares, feux arrière, teinte d'appoint du modèle (caisse du camion, carrosserie
##   du bus, jantes du tracteur), blanc (plaques, girouette), gyrophare ;
## - CUSTOM0.y : 1 sur une roue, qui tourne autour de son axe ; UV2 = (y, z) de cet axe.
## KINDS : demi-largeur, longueur, hauteur et rayon des roues (arrière du tracteur) de chaque modèle (une seule source pour traffic_model.gd,
## les véhicules lointains et les tests).
## Matériaux partagés : `material(kind)` donne le même ShaderMaterial à la route du parcours et aux véhicules
## lointains ; `set_lights(level)` allume ou éteint les phares de tous les véhicules par un seul paramètre
## (`lights_on`), sans nœud de lumière ni matériau par véhicule (lot P25).

const PeopleMesh := preload("res://scripts/people_mesh.gd")
const VehicleShader := preload("res://shaders/vehicle.gdshader")

const VEH_PAINT := 0
const VEH_GLASS := 1
const VEH_TYRE := 2
const VEH_TRIM := 3
const VEH_CHROME := 4
const VEH_HEAD := 5
const VEH_TAIL := 6
const VEH_ACCENT := 7
const VEH_LIGHT := 8
const VEH_BEACON := 9

const KINDS := {
	"car_a": {"half_width": 0.9, "length": 4.3, "height": 1.49, "wheel_r": 0.32},
	"car_b": {"half_width": 0.9, "length": 3.9, "height": 1.6, "wheel_r": 0.3},
	"van": {"half_width": 1.0, "length": 5.0, "height": 2.3, "wheel_r": 0.36},
	"truck": {"half_width": 1.25, "length": 9.5, "height": 3.4, "wheel_r": 0.5},
	"bus": {"half_width": 1.25, "length": 12.0, "height": 3.3, "wheel_r": 0.5},
	"moto": {"half_width": 0.4, "length": 2.1, "height": 1.7, "wheel_r": 0.31},
	"tractor": {"half_width": 1.1, "length": 3.6, "height": 2.85, "wheel_r": 0.8},
	"tractor_plough": {"half_width": 1.1, "length": 7.7, "height": 2.85, "wheel_r": 0.8},
}
## Teinte d'appoint (VEH_ACCENT) de chaque modèle.
const ACCENT := {
	"car_a": Color(0.1, 0.1, 0.11), "car_b": Color(0.1, 0.1, 0.11), "van": Color(0.1, 0.1, 0.11),
	"truck": Color(0.9, 0.9, 0.88), "bus": Color(0.9, 0.88, 0.8), "moto": Color(0.1, 0.1, 0.11),
	"tractor": Color(0.86, 0.68, 0.12), "tractor_plough": Color(0.86, 0.68, 0.12), "far": Color(0.1, 0.1, 0.11),
}
const SIDES := 12
## Peintures : palette de P13 et deux teintes de plus pour les voitures, camionnettes et motos ; blanc ou
## gris clair pour les camions et les bus ; vert, rouge ou bleu pour les tracteurs.
const PALETTE := [Color(0.62, 0.08, 0.08), Color(0.12, 0.2, 0.45), Color(0.85, 0.85, 0.82), Color(0.18, 0.18, 0.2),
	Color(0.55, 0.57, 0.6), Color(0.86, 0.6, 0.12)]
const HEAVY_PAINT := [Color(0.92, 0.92, 0.9), Color(0.76, 0.77, 0.79)]
const TRACTOR_PAINT := [Color(0.2, 0.45, 0.15), Color(0.7, 0.12, 0.1), Color(0.15, 0.3, 0.6)]

static var lights_level := 0.0
static var _materials := {}


## Matériau partagé d'un modèle (KINDS ou `far`) : shaders/vehicle.gdshader, teinte d'appoint du modèle.
static func material(kind: String) -> ShaderMaterial:
	if not _materials.has(kind):
		var mat := ShaderMaterial.new()
		mat.shader = VehicleShader
		mat.set_shader_parameter("accent", ACCENT.get(kind, ACCENT["far"]))
		mat.set_shader_parameter("lights_on", lights_level)
		_materials[kind] = mat
	return _materials[kind]


## Peinture d'un véhicule de sorte `kind` et d'indice de couleur `index` (tirage du modèle).
static func paint(kind: String, index: int) -> Color:
	match kind:
		"truck", "bus":
			return HEAVY_PAINT[posmod(index, HEAVY_PAINT.size())]
		"tractor", "tractor_plough":
			return TRACTOR_PAINT[posmod(index, TRACTOR_PAINT.size())]
	return PALETTE[posmod(index, PALETTE.size())]


## MultiMeshInstance3D de `capacity` véhicules d'un modèle (KINDS ou `far`), au matériau partagé ; aucun
## affiché (`visible_instance_count` = 0). INSTANCE_CUSTOM = (peinture, angle des roues) : `custom`.
static func make_instance(kind: String, capacity: int) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = build(kind)
	mm.instance_count = capacity
	mm.visible_instance_count = 0
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "Vehicles_" + kind
	mmi.multimesh = mm
	mmi.material_override = material(kind)
	return mmi


## INSTANCE_CUSTOM d'un véhicule : peinture et angle des roues (radians).
static func custom(paint_color: Color, wheel_angle: float) -> Color:
	return Color(paint_color.r, paint_color.g, paint_color.b, fposmod(wheel_angle, TAU))


## Phares et feux de tous les véhicules : 0 éteints, 1 allumés.
static func set_lights(level: float) -> void:
	lights_level = clampf(level, 0.0, 1.0)
	for mat in _materials.values():
		(mat as ShaderMaterial).set_shader_parameter("lights_on", lights_level)


## Maillage d'un modèle de KINDS ou `far`.
static func build(kind: String) -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
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
			_tractor(m, false)
		"tractor_plough":
			_tractor(m, true)
		_:
			_far(m)
	return m.commit()


# ---------------------------------------------------------------------------------------------------
# Pièces

## Quadrilatère plat p0-p1-p2-p3, normale tournée à l'opposé de `inside`.
static func _quad(m, p0: Vector3, p1: Vector3, p2: Vector3, p3: Vector3, inside: Vector3) -> void:
	var n := (p1 - p0).cross(p2 - p0)
	if n.length_squared() < 1e-10:
		n = (p2 - p0).cross(p3 - p0)
	n = n.normalized()
	if n.dot((p0 + p1 + p2 + p3) * 0.25 - inside) < 0.0:
		n = -n
	for p in [p0, p1, p2, p0, p2, p3]:
		m.vertex(p, n)


## Coque de sections trapézoïdales le long de z : `sections` = [[z, y_bas, y_haut, demi-largeur en bas,
## demi-largeur en haut], …] dans l'ordre de z ; flancs, dessus et dessous plats, bouts fermés.
static func _hull(m, sections: Array) -> void:
	var c := Vector3.ZERO
	for s in sections:
		c += Vector3(0.0, (float(s[1]) + float(s[2])) * 0.5, float(s[0]))
	c /= sections.size()
	var corners := func(s: Array) -> Array:
		var z := float(s[0])
		return [Vector3(-float(s[3]), float(s[1]), z), Vector3(float(s[3]), float(s[1]), z),
			Vector3(float(s[4]), float(s[2]), z), Vector3(-float(s[4]), float(s[2]), z)]
	for i in range(sections.size() - 1):
		var a: Array = corners.call(sections[i])
		var b: Array = corners.call(sections[i + 1])
		var mid := Vector3(0.0, c.y, (float(sections[i][0]) + float(sections[i + 1][0])) * 0.5)
		for k in range(4):
			var k2 := (k + 1) % 4
			_quad(m, a[k], a[k2], b[k2], b[k], mid)
	var first: Array = corners.call(sections[0])
	var last: Array = corners.call(sections[sections.size() - 1])
	_quad(m, first[0], first[1], first[2], first[3], c)
	_quad(m, last[0], last[1], last[2], last[3], c)


## Panneau mince (vitre, plaque, bande) : quadrilatère de `zone`, décalé de 1 cm vers l'extérieur.
static func _panel(m, region: int, p0: Vector3, p1: Vector3, p2: Vector3, p3: Vector3, inside: Vector3) -> void:
	var n := (p1 - p0).cross(p2 - p0).normalized()
	if n.dot((p0 + p1 + p2 + p3) * 0.25 - inside) < 0.0:
		n = -n
	var off := n * 0.012
	var keep: int = m.region
	m.region = region
	_quad(m, p0 + off, p1 + off, p2 + off, p3 + off, inside)
	m.region = keep


## Paire de roues de rayon `r` et de largeur `w`, axe en (y = r, z), centres à ± x : pneu, jante et deux
## rayons croisés qui montrent la rotation.
static func _axle(m, x: float, z: float, r: float, w: float, rim_region: int = VEH_CHROME) -> void:
	m.shin = 1.0
	m.uv2 = Vector2(r, z)
	for sx: float in ([0.0] if x == 0.0 else [-1.0, 1.0]):
		var cx := sx * x
		m.region = VEH_TYRE
		m.prism(Vector3(cx - w * 0.5, r, z), Vector3(cx + w * 0.5, r, z), Vector2(r, r), Vector2(r, r), SIDES)
		m.region = rim_region
		var face := cx + (w * 0.5 + 0.005) * (1.0 if sx >= 0.0 else -1.0)
		var inner := cx + (w * 0.5 - 0.03) * (1.0 if sx >= 0.0 else -1.0)
		m.prism(Vector3(inner, r, z), Vector3(face, r, z), Vector2(r * 0.6, r * 0.6), Vector2(r * 0.6, r * 0.6), 8)
		for a in [0.0, PI * 0.5]:
			m.xform = Transform3D.IDENTITY.translated(Vector3(0.0, r, z)) * Transform3D(Basis(Vector3.RIGHT, a), Vector3.ZERO) \
				* Transform3D.IDENTITY.translated(Vector3(0.0, -r, -z))
			m.region = VEH_TRIM
			m.box(Vector3(face + 0.005 * signf(face - cx), r, z), Vector3(0.012, r * 1.15, r * 0.09))
		m.xform = Transform3D.IDENTITY
	m.shin = 0.0
	m.uv2 = Vector2.ZERO


## Phares avant (à z = `zf`) et feux arrière (à z = `zr`), à ± x, hauteurs `yf` et `yr`.
static func _lights(m, x: float, zf: float, yf: float, zr: float, yr: float, size := Vector2(0.34, 0.14)) -> void:
	for sx: float in [-1.0, 1.0]:
		m.region = VEH_HEAD
		m.box(Vector3(sx * x, yf, zf), Vector3(size.x, size.y, 0.05))
		m.region = VEH_TAIL
		m.box(Vector3(sx * x, yr, zr), Vector3(size.x * 0.8, size.y, 0.05))


## Pare-chocs avant et arrière, plaques blanches.
static func _bumpers(m, half_w: float, zf: float, zr: float, y: float) -> void:
	m.region = VEH_TRIM
	m.box(Vector3(0.0, y, zf - 0.04), Vector3(half_w * 2.0 - 0.1, 0.17, 0.12))
	m.box(Vector3(0.0, y, zr + 0.04), Vector3(half_w * 2.0 - 0.1, 0.17, 0.12))
	m.region = VEH_LIGHT
	m.box(Vector3(0.0, y + 0.02, zf - 0.105), Vector3(0.5, 0.11, 0.01))
	m.box(Vector3(0.0, y + 0.02, zr + 0.105), Vector3(0.5, 0.11, 0.01))


## Rétroviseurs à ± x, devant le pare-brise.
static func _mirrors(m, x: float, y: float, z: float) -> void:
	m.region = VEH_TRIM
	for sx: float in [-1.0, 1.0]:
		m.box(Vector3(sx * x, y, z), Vector3(0.1, 0.12, 0.2))


## Vitres d'une cabine : pare-brise, lunette et vitres latérales posées sur les faces d'une coque
## `[z, y_bas, y_haut, demi-largeur bas, demi-largeur haut]`, de `inset` vers l'intérieur de chaque face.
static func _cabin_glass(m, front: Array, roof_f: Array, roof_r: Array, rear: Array, inset := 0.06) -> void:
	var c := Vector3(0.0, (float(front[1]) + float(roof_f[2])) * 0.5, (float(front[0]) + float(rear[0])) * 0.5)
	var top := func(s: Array, sx: float) -> Vector3:
		return Vector3(sx * (float(s[4]) - inset), float(s[2]) - inset, float(s[0]))
	var bot := func(s: Array, sx: float) -> Vector3:
		return Vector3(sx * (float(s[3]) - inset), float(s[1]) + inset, float(s[0]))
	# Pare-brise et lunette (faces inclinées entre la ceinture et le toit)
	_panel(m, VEH_GLASS, top.call(front, -1.0) + Vector3(0.0, 0.0, 0.03), top.call(front, 1.0) + Vector3(0.0, 0.0, 0.03),
		top.call(roof_f, 1.0) + Vector3(0.0, 0.0, 0.05), top.call(roof_f, -1.0) + Vector3(0.0, 0.0, 0.05), c)
	_panel(m, VEH_GLASS, top.call(rear, -1.0) - Vector3(0.0, 0.0, 0.03), top.call(rear, 1.0) - Vector3(0.0, 0.0, 0.03),
		top.call(roof_r, 1.0) - Vector3(0.0, 0.0, 0.05), top.call(roof_r, -1.0) - Vector3(0.0, 0.0, 0.05), c)
	# Vitres latérales : de la ceinture au toit, entre les montants
	for sx: float in [-1.0, 1.0]:
		var zf := float(roof_f[0]) - 0.05
		var zr := float(roof_r[0]) + 0.05
		var yb := float(front[2]) + 0.05
		var yt := float(roof_f[2]) - 0.07
		var xb := sx * float(roof_f[3])
		var xt := sx * float(roof_f[4])
		_panel(m, VEH_GLASS, Vector3(xb, yb, zf), Vector3(xb, yb, zr), Vector3(xt, yt, zr), Vector3(xt, yt, zf), c)


# ---------------------------------------------------------------------------------------------------
# Modèles

## Berline : capot long, coffre, habitacle à pare-brise incliné.
static func _car_a(m) -> void:
	m.region = VEH_PAINT
	_hull(m, [[-2.15, 0.32, 0.64, 0.82, 0.78], [-1.98, 0.25, 0.8, 0.88, 0.85], [-1.0, 0.24, 0.87, 0.9, 0.87],
		[1.25, 0.24, 0.9, 0.9, 0.87], [2.02, 0.27, 0.93, 0.88, 0.84], [2.15, 0.36, 0.86, 0.83, 0.79]])
	var front := [-0.95, 0.85, 0.88, 0.86, 0.84]
	var roof_f := [-0.18, 0.86, 1.44, 0.84, 0.7]
	var roof_r := [0.92, 0.88, 1.46, 0.84, 0.7]
	var rear := [1.72, 0.9, 0.94, 0.85, 0.82]
	_hull(m, [front, roof_f, roof_r, rear])
	_cabin_glass(m, front, roof_f, roof_r, rear)
	m.region = VEH_TRIM
	m.box(Vector3(0.0, 0.56, -2.15), Vector3(0.75, 0.14, 0.04))   # calandre
	_mirrors(m, 0.95, 0.98, -0.78)
	_bumpers(m, 0.88, -2.15, 2.15, 0.4)
	_lights(m, 0.6, -2.13, 0.7, 2.13, 0.8)
	_axle(m, 0.8, -1.35, 0.32, 0.22)
	_axle(m, 0.8, 1.32, 0.32, 0.22)


## Petite voiture haute : capot court, hayon presque droit, toit haut.
static func _car_b(m) -> void:
	m.region = VEH_PAINT
	_hull(m, [[-1.95, 0.3, 0.72, 0.82, 0.8], [-1.78, 0.26, 0.86, 0.87, 0.85], [1.82, 0.26, 0.92, 0.87, 0.85],
		[1.95, 0.32, 0.9, 0.84, 0.82]])
	var front := [-1.35, 0.86, 0.88, 0.85, 0.83]
	var roof_f := [-0.55, 0.87, 1.55, 0.84, 0.74]
	var roof_r := [1.62, 0.9, 1.58, 0.84, 0.76]
	var rear := [1.86, 0.92, 1.0, 0.84, 0.82]
	_hull(m, [front, roof_f, roof_r, rear])
	_cabin_glass(m, front, roof_f, roof_r, rear)
	m.region = VEH_TRIM
	m.box(Vector3(0.0, 0.6, -1.95), Vector3(0.7, 0.16, 0.04))
	_mirrors(m, 0.93, 1.0, -1.15)
	_bumpers(m, 0.86, -1.95, 1.95, 0.4)
	_lights(m, 0.6, -1.93, 0.74, 1.93, 0.86)
	_axle(m, 0.79, -1.25, 0.3, 0.2)
	_axle(m, 0.79, 1.25, 0.3, 0.2)


## Camionnette : capot court, pare-brise incliné, caisse haute.
static func _van(m) -> void:
	m.region = VEH_PAINT
	_hull(m, [[-2.5, 0.36, 0.85, 0.92, 0.9], [-2.32, 0.3, 1.05, 0.98, 0.96], [-1.55, 0.3, 1.18, 1.0, 0.98],
		[-0.85, 0.3, 2.22, 1.0, 0.95], [2.45, 0.3, 2.3, 1.0, 0.95], [2.5, 0.36, 2.25, 0.98, 0.94]])
	var c := Vector3(0.0, 1.2, 0.0)
	_panel(m, VEH_GLASS, Vector3(-0.88, 1.24, -1.5), Vector3(0.88, 1.24, -1.5), Vector3(0.84, 2.12, -0.9), Vector3(-0.84, 2.12, -0.9), c)
	for sx: float in [-1.0, 1.0]:
		_panel(m, VEH_GLASS, Vector3(sx * 0.995, 1.28, -1.3), Vector3(sx * 0.995, 1.28, -0.35),
			Vector3(sx * 0.96, 2.0, -0.35), Vector3(sx * 0.975, 2.0, -0.85), c)
		m.region = VEH_TRIM
		m.box(Vector3(sx * 1.0, 1.02, 0.9), Vector3(0.02, 0.05, 2.6))   # rail de la porte coulissante
	m.region = VEH_TRIM
	m.box(Vector3(0.0, 0.66, -2.5), Vector3(0.9, 0.2, 0.04))
	_mirrors(m, 1.08, 1.5, -1.45)
	_bumpers(m, 0.98, -2.5, 2.5, 0.42)
	_lights(m, 0.7, -2.47, 0.82, 2.48, 1.1, Vector2(0.3, 0.18))
	_axle(m, 0.86, -1.65, 0.36, 0.24)
	_axle(m, 0.86, 1.7, 0.36, 0.24)


## Camion porteur : cabine plate, caisse fermée claire (VEH_ACCENT), châssis, trois essieux.
static func _truck(m) -> void:
	m.region = VEH_PAINT
	_hull(m, [[-4.75, 0.55, 2.7, 1.2, 1.12], [-4.57, 0.5, 2.98, 1.25, 1.16], [-2.6, 0.5, 3.02, 1.25, 1.16]])
	var c := Vector3(0.0, 1.8, -3.65)
	_panel(m, VEH_GLASS, Vector3(-1.05, 1.75, -4.75), Vector3(1.05, 1.75, -4.75), Vector3(1.0, 2.6, -4.75), Vector3(-1.0, 2.6, -4.75), c)
	for sx: float in [-1.0, 1.0]:
		_panel(m, VEH_GLASS, Vector3(sx * 1.25, 1.8, -4.4), Vector3(sx * 1.25, 1.8, -3.55),
			Vector3(sx * 1.2, 2.6, -3.55), Vector3(sx * 1.2, 2.6, -4.4), c)
		m.region = VEH_TRIM
		m.box(Vector3(sx * 1.2, 0.62, -3.25), Vector3(0.12, 0.08, 0.5))   # marchepied
	m.region = VEH_TRIM
	m.box(Vector3(0.0, 1.2, -4.78), Vector3(1.5, 0.5, 0.04))      # calandre
	m.box(Vector3(0.0, 0.78, 0.05), Vector3(1.6, 0.32, 9.3))      # châssis
	_mirrors(m, 1.3, 2.1, -4.55)
	m.region = VEH_ACCENT
	_hull(m, [[-2.45, 0.95, 3.4, 1.25, 1.25], [4.75, 0.95, 3.4, 1.25, 1.25]])
	m.region = VEH_TRIM
	m.box(Vector3(0.0, 2.17, 4.76), Vector3(0.03, 2.3, 0.02))     # joint des portes arrière
	m.box(Vector3(0.0, 0.6, 4.71), Vector3(2.3, 0.16, 0.12))
	_lights(m, 0.9, -4.77, 0.8, 4.78, 0.7, Vector2(0.3, 0.18))
	_axle(m, 1.0, -3.6, 0.5, 0.36)
	_axle(m, 1.0, 2.65, 0.5, 0.42)
	_axle(m, 1.0, 3.8, 0.5, 0.42)


## Autobus : carrosserie claire (VEH_ACCENT), bande et bas de caisse à la couleur d'instance, rangée de
## vitres, girouette blanche, deux essieux.
static func _bus(m) -> void:
	m.region = VEH_ACCENT
	_hull(m, [[-6.0, 0.36, 2.95, 1.21, 1.16], [-5.86, 0.3, 3.1, 1.25, 1.2], [5.9, 0.3, 3.1, 1.25, 1.2], [6.0, 0.36, 3.0, 1.21, 1.16]])
	var c := Vector3(0.0, 1.6, 0.0)
	_panel(m, VEH_GLASS, Vector3(-1.15, 1.0, -6.0), Vector3(1.15, 1.0, -6.0), Vector3(1.12, 2.62, -6.0), Vector3(-1.12, 2.62, -6.0), c)
	_panel(m, VEH_GLASS, Vector3(-1.05, 1.6, 6.0), Vector3(1.05, 1.6, 6.0), Vector3(1.05, 2.6, 6.0), Vector3(-1.05, 2.6, 6.0), c)
	_panel(m, VEH_LIGHT, Vector3(-0.9, 2.7, -6.0), Vector3(0.9, 2.7, -6.0), Vector3(0.9, 2.92, -6.0), Vector3(-0.9, 2.92, -6.0), c)
	for sx: float in [-1.0, 1.0]:
		var x: float = sx * 1.245
		_panel(m, VEH_GLASS, Vector3(x, 1.45, -5.2), Vector3(x, 1.45, 5.6), Vector3(x * 0.975, 2.7, 5.6), Vector3(x * 0.975, 2.7, -5.2), c)
		_panel(m, VEH_PAINT, Vector3(x, 0.4, -5.86), Vector3(x, 0.4, 5.9), Vector3(x, 0.95, 5.9), Vector3(x, 0.95, -5.86), c)
		_panel(m, VEH_PAINT, Vector3(x * 0.99, 2.78, -5.86), Vector3(x * 0.99, 2.78, 5.9), Vector3(x * 0.98, 2.92, 5.9), Vector3(x * 0.98, 2.92, -5.86), c)
		m.region = VEH_TRIM
		for z in [-2.0, 0.5, 3.0, 5.0]:
			m.box(Vector3(x * 0.995, 2.07, z), Vector3(0.03, 1.25, 0.08))   # montants entre les vitres
	# Porte avant, côté droit (vitrée sur toute la hauteur)
	_panel(m, VEH_GLASS, Vector3(1.25, 0.45, -5.6), Vector3(1.25, 0.45, -4.6), Vector3(1.25, 2.6, -4.6), Vector3(1.25, 2.6, -5.6), c)
	m.region = VEH_TRIM
	m.box(Vector3(0.0, 3.2, 1.0), Vector3(1.6, 0.2, 2.6))      # climatisation sur le toit
	_mirrors(m, 1.36, 2.4, -5.9)
	_bumpers(m, 1.2, -6.0, 6.0, 0.45)
	_lights(m, 0.95, -6.02, 0.75, 6.02, 0.9, Vector2(0.32, 0.16))
	_axle(m, 1.02, -3.9, 0.5, 0.34)
	_axle(m, 1.02, 3.3, 0.5, 0.4)


## Moto et son pilote casqué (casque à la couleur d'instance, blouson sombre).
static func _moto(m) -> void:
	m.region = VEH_TRIM
	m.box(Vector3(0.0, 0.5, 0.02), Vector3(0.3, 0.32, 0.46))                                   # moteur
	m.prism(Vector3(0.0, 0.62, -0.18), Vector3(0.0, 0.6, 0.62), Vector2(0.05, 0.05), Vector2(0.05, 0.05), 6)   # cadre
	for sx: float in [-1.0, 1.0]:
		m.prism(Vector3(sx * 0.07, 0.31, -0.72), Vector3(sx * 0.07, 1.0, -0.52), Vector2(0.025, 0.025), Vector2(0.03, 0.03), 6)   # fourche
	m.prism(Vector3(-0.38, 1.02, -0.5), Vector3(0.38, 1.02, -0.5), Vector2(0.018, 0.018), Vector2(0.018, 0.018), 6)   # guidon
	m.prism(Vector3(0.0, 0.84, 0.02), Vector3(0.0, 0.88, 0.62), Vector2(0.13, 0.05), Vector2(0.12, 0.05), 8)   # selle
	m.region = VEH_PAINT
	m.ellipsoid(Vector3(0.0, 0.84, -0.2), Vector3(0.17, 0.13, 0.28))           # réservoir
	m.prism(Vector3(0.0, 0.72, 0.55), Vector3(0.0, 0.8, 0.95), Vector2(0.09, 0.03), Vector2(0.07, 0.03), 6)   # garde-boue arrière
	m.prism(Vector3(0.0, 0.66, -0.62), Vector3(0.0, 0.6, -0.9), Vector2(0.07, 0.03), Vector2(0.06, 0.03), 6)  # garde-boue avant
	m.region = VEH_CHROME
	m.prism(Vector3(0.12, 0.32, 0.0), Vector3(0.14, 0.42, 0.82), Vector2(0.04, 0.04), Vector2(0.05, 0.05), 6)   # pot
	m.region = VEH_HEAD
	m.ellipsoid(Vector3(0.0, 0.94, -0.62), Vector3(0.09, 0.08, 0.05))
	m.region = VEH_TAIL
	m.box(Vector3(0.0, 0.84, 0.94), Vector3(0.14, 0.06, 0.04))
	# Pilote : jambes pliées sur les repose-pieds, buste penché, mains au guidon, casque
	m.region = VEH_TRIM
	for sx: float in [-1.0, 1.0]:
		m.prism(Vector3(sx * 0.12, 0.92, 0.25), Vector3(sx * 0.18, 0.8, -0.14), Vector2(0.08, 0.08), Vector2(0.06, 0.06), 6)   # cuisse
		m.prism(Vector3(sx * 0.18, 0.8, -0.14), Vector3(sx * 0.17, 0.4, 0.04), Vector2(0.055, 0.055), Vector2(0.045, 0.045), 6)   # tibia
		m.box(Vector3(sx * 0.17, 0.36, 0.0), Vector3(0.09, 0.08, 0.22))          # botte
		m.prism(Vector3(sx * 0.19, 1.34, 0.0), Vector3(sx * 0.33, 1.1, -0.3), Vector2(0.05, 0.05), Vector2(0.045, 0.045), 6)   # bras
		m.prism(Vector3(sx * 0.33, 1.1, -0.3), Vector3(sx * 0.36, 1.03, -0.48), Vector2(0.04, 0.04), Vector2(0.035, 0.035), 6)   # avant-bras
	m.prism(Vector3(0.0, 0.9, 0.28), Vector3(0.0, 1.38, -0.02), Vector2(0.16, 0.11), Vector2(0.2, 0.12), 8)   # buste
	m.region = VEH_PAINT
	m.ellipsoid(Vector3(0.0, 1.56, -0.1), Vector3(0.14, 0.15, 0.16))        # casque
	m.region = VEH_GLASS
	m.ellipsoid(Vector3(0.0, 1.55, -0.2), Vector3(0.11, 0.06, 0.08), -40.0, 3)   # visière
	_axle(m, 0.0, -0.72, 0.31, 0.12)
	_axle(m, 0.0, 0.72, 0.31, 0.14)


## Tracteur : capot étroit, cabine vitrée sur quatre montants, grandes roues arrière à jantes jaunes,
## garde-boue, échappement vertical, gyrophare ; `plough` : charrue à trois socs attelée derrière.
static func _tractor(m, plough: bool) -> void:
	m.region = VEH_PAINT
	_hull(m, [[-1.95, 0.62, 1.22, 0.36, 0.33], [-1.8, 0.58, 1.32, 0.4, 0.37], [-0.2, 0.58, 1.38, 0.42, 0.38]])
	m.region = VEH_TRIM
	m.box(Vector3(0.0, 0.48, -0.8), Vector3(0.6, 0.35, 2.0))              # bloc moteur et pont
	m.box(Vector3(0.0, 0.9, -1.96), Vector3(0.6, 0.45, 0.03))             # calandre
	m.box(Vector3(0.0, 0.62, 0.75), Vector3(0.7, 0.4, 1.2))               # pont arrière
	m.region = VEH_PAINT
	m.box(Vector3(0.0, 1.05, 0.72), Vector3(1.0, 0.5, 1.3))               # caisse sous la cabine
	m.region = VEH_TRIM
	for c in [Vector2(-0.68, 0.05), Vector2(0.68, 0.05), Vector2(-0.68, 1.35), Vector2(0.68, 1.35)]:
		m.prism(Vector3(c.x, 1.3, c.y), Vector3(c.x * 0.97, 2.62, c.y), Vector2(0.035, 0.035), Vector2(0.035, 0.035), 6)   # montants
	m.prism(Vector3(0.3, 1.3, -1.2), Vector3(0.3, 2.35, -1.2), Vector2(0.045, 0.045), Vector2(0.045, 0.045), 6)   # échappement
	var c3 := Vector3(0.0, 1.9, 0.7)
	_panel(m, VEH_GLASS, Vector3(-0.66, 1.42, 0.05), Vector3(0.66, 1.42, 0.05), Vector3(0.64, 2.55, 0.05), Vector3(-0.64, 2.55, 0.05), c3)
	_panel(m, VEH_GLASS, Vector3(-0.66, 1.5, 1.35), Vector3(0.66, 1.5, 1.35), Vector3(0.64, 2.55, 1.35), Vector3(-0.64, 2.55, 1.35), c3)
	for sx: float in [-1.0, 1.0]:
		_panel(m, VEH_GLASS, Vector3(sx * 0.68, 1.75, 0.1), Vector3(sx * 0.68, 1.75, 1.3), Vector3(sx * 0.66, 2.55, 1.3), Vector3(sx * 0.66, 2.55, 0.1), c3)
	m.region = VEH_PAINT
	m.box(Vector3(0.0, 2.66, 0.7), Vector3(1.55, 0.1, 1.55))             # toit
	for sx: float in [-1.0, 1.0]:
		m.box(Vector3(sx * 0.92, 1.66, 0.95), Vector3(0.52, 0.07, 1.25))  # garde-boue
	m.region = VEH_BEACON
	m.ellipsoid(Vector3(0.45, 2.78, 0.95), Vector3(0.07, 0.08, 0.07), -10.0, 3)
	m.region = VEH_HEAD
	for sx: float in [-1.0, 1.0]:
		m.box(Vector3(sx * 0.22, 1.05, -1.98), Vector3(0.14, 0.1, 0.04))
		m.box(Vector3(sx * 0.62, 2.5, -0.06), Vector3(0.12, 0.1, 0.06))       # phares de travail
	m.region = VEH_TAIL
	for sx: float in [-1.0, 1.0]:
		m.box(Vector3(sx * 0.98, 1.6, 1.6), Vector3(0.12, 0.1, 0.04))
	if plough:
		m.region = VEH_TRIM
		m.prism(Vector3(0.0, 0.55, 1.5), Vector3(0.0, 0.55, 2.4), Vector2(0.06, 0.06), Vector2(0.06, 0.06), 6)   # attelage
		m.prism(Vector3(-0.2, 0.55, 2.4), Vector3(0.9, 0.55, 4.8), Vector2(0.07, 0.07), Vector2(0.07, 0.07), 6)   # âge en biais
		m.region = VEH_PAINT
		for i in range(3):
			var z := 2.9 + i * 0.85
			var x := 0.05 + i * 0.36
			m.prism(Vector3(x, 0.55, z), Vector3(x, 0.15, z + 0.1), Vector2(0.04, 0.04), Vector2(0.04, 0.04), 4)   # étançon
			m.region = VEH_CHROME
			m.box(Vector3(x - 0.08, 0.1, z + 0.12), Vector3(0.32, 0.18, 0.5))   # soc et versoir
			m.region = VEH_PAINT
		m.region = VEH_TYRE
		m.prism(Vector3(1.0, 0.3, 5.4), Vector3(1.12, 0.3, 5.4), Vector2(0.3, 0.3), Vector2(0.3, 0.3), 10)   # roue de terrage
	_axle(m, 0.8, -1.25, 0.45, 0.28, VEH_ACCENT)
	_axle(m, 0.92, 0.95, 0.8, 0.45, VEH_ACCENT)


## Boîte d'un mètre (au sol, centrée), avec deux phares devant et deux feux derrière : véhicule lointain,
## mis à l'échelle par sa demi-largeur, sa hauteur et sa longueur (KINDS).
static func _far(m) -> void:
	m.region = VEH_PAINT
	m.box(Vector3(0.0, 0.55, 0.0), Vector3(1.0, 0.7, 1.0))
	m.region = VEH_GLASS
	m.box(Vector3(0.0, 0.92, 0.05), Vector3(0.9, 0.16, 0.7))
	for sx: float in [-1.0, 1.0]:
		m.region = VEH_HEAD
		m.box(Vector3(sx * 0.32, 0.45, -0.505), Vector3(0.2, 0.12, 0.01))
		m.region = VEH_TAIL
		m.box(Vector3(sx * 0.34, 0.5, 0.505), Vector3(0.16, 0.12, 0.01))
	m.region = VEH_TYRE
	m.box(Vector3(0.0, 0.1, 0.0), Vector3(0.9, 0.2, 0.9))
