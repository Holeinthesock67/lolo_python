extends RefCounted

## Maillages des personnages du décor (spectateurs P15, passants P21) et des cyclistes (bots O7 : coureur
## casqué et vélo), construits par code, sans
## texture (Lot Y14) : corps en prismes effilés à normales lissées (jambes en cuisse et tibia, bassin,
## buste, épaules, cou, tête, cheveux, bras en manche et avant-bras, mains, chaussures), chien et banc.
## Pas de class_name : charger par preload("res://scripts/people_mesh.gd").
##
## Données par sommet lues par shaders/crowd.gdshader :
## - CUSTOM0.x : zone (REGION_*), qui choisit la couleur : haut (couleur d'instance), peau, cheveux,
##   pantalon, chaussures, hampe, métal ;
## - CUSTOM0.y : 1 sous le genou (pliage du genou) ; sur le vélo, pièce qui tourne : PART_CRANK (pédalier),
##   PART_FRONT_WHEEL, PART_REAR_WHEEL ; CUSTOM0.z : 1 sur le bras, la hampe et le drapeau du
##   porte-drapeau ;
## - UV.y : 1 sur les bras libres ; UV.x : poids du drapeau (0 à la hampe, 1 au bout) ;
## - UV2.x : ±1 sur chaque jambe (patte du chien, en diagonale) ; UV2.y : 1 sur le bras qui salue.
## Tenue : `outfit(skin, hair, trousers)` donne INSTANCE_CUSTOM.w (indices dans les palettes ci-dessous,
## passées au shader par `apply_palettes`).
## Personnage debout de 1,75 m, pieds à y = 0, face vers +z ; hanche à HIP_Y, genou à KNEE_Y, épaule à
## SHOULDER_Y (pivots des articulations du shader, passés par `apply_palettes`).

const REGION_TOP := 0
const REGION_SKIN := 1
const REGION_HAIR := 2
const REGION_TROUSERS := 3
const REGION_SHOES := 4
const REGION_POLE := 5
const REGION_METAL := 6

const PART_CRANK := 1
const PART_FRONT_WHEEL := 2
const PART_REAR_WHEEL := 3

const HIP_Y := 0.92
const KNEE_Y := 0.5
const SHOULDER_Y := 1.42
const SHOULDER_X := 0.235
const LEG_X := 0.09
const SIDES := 8

## Vélo, dans le repère du coureur (origine au sol sous la hanche, face vers +z) : boîtier de pédalier,
## manivelle, axes des roues, rayon des roues, cintre.
const BB := Vector3(0.0, 0.3, 0.2)
const CRANK_M := 0.17
const FRONT_AXLE := Vector3(0.0, 0.34, 0.8)
const REAR_AXLE := Vector3(0.0, 0.34, -0.21)
const WHEEL_M := 0.34
const BAR := Vector3(0.0, 0.97, 0.76)
const RIDER_OUTFIT_TROUSERS := 1   # cuissard noir

const SKIN_TONES := [Color(0.93, 0.78, 0.66), Color(0.85, 0.68, 0.55), Color(0.68, 0.5, 0.36), Color(0.43, 0.3, 0.21)]
const HAIR_COLORS := [Color(0.06, 0.05, 0.05), Color(0.2, 0.12, 0.07), Color(0.36, 0.23, 0.12),
	Color(0.72, 0.6, 0.34), Color(0.58, 0.58, 0.58), Color(0.48, 0.22, 0.09)]
const TROUSER_COLORS := [Color(0.18, 0.25, 0.4), Color(0.08, 0.08, 0.09), Color(0.62, 0.55, 0.42),
	Color(0.36, 0.36, 0.38), Color(0.38, 0.36, 0.24), Color(0.12, 0.14, 0.26)]
const SHOE_COLOR := Color(0.12, 0.1, 0.09)
const POLE_COLOR := Color(0.6, 0.5, 0.36)
const METAL_COLOR := Color(0.7, 0.71, 0.73)


## INSTANCE_CUSTOM.w : indices de peau, de cheveux et de pantalon dans un seul nombre entier exact.
static func outfit(skin: int, hair: int, trousers: int) -> float:
	return float(posmod(skin, SKIN_TONES.size()) + SKIN_TONES.size() * (posmod(hair, HAIR_COLORS.size())
		+ HAIR_COLORS.size() * posmod(trousers, TROUSER_COLORS.size())))


## Tenue tirée d'un nombre entier quelconque (numéro de personne, graine) : mêmes tenues d'une séance à l'autre.
static func outfit_of(seed_value: int) -> float:
	var h := (seed_value * 2654435761) & 0x7FFFFFFF
	return outfit(h % 7, (h >> 3) % 11, (h >> 7) % 13)


## Palettes et pivots des articulations, à poser une fois sur le matériau de crowd.gdshader.
static func apply_palettes(mat: ShaderMaterial) -> void:
	mat.set_shader_parameter("skin_tones", _vec3s(SKIN_TONES))
	mat.set_shader_parameter("hair_colors", _vec3s(HAIR_COLORS))
	mat.set_shader_parameter("trouser_colors", _vec3s(TROUSER_COLORS))
	mat.set_shader_parameter("shoe_color", Vector3(SHOE_COLOR.r, SHOE_COLOR.g, SHOE_COLOR.b))
	mat.set_shader_parameter("pole_color", Vector3(POLE_COLOR.r, POLE_COLOR.g, POLE_COLOR.b))
	mat.set_shader_parameter("metal_color", Vector3(METAL_COLOR.r, METAL_COLOR.g, METAL_COLOR.b))
	mat.set_shader_parameter("joints", Vector4(HIP_Y, KNEE_Y, SHOULDER_Y, SHOULDER_X))
	mat.set_shader_parameter("bike", Vector4(BB.y, BB.z, CRANK_M, WHEEL_M))
	mat.set_shader_parameter("axles", Vector4(FRONT_AXLE.y, FRONT_AXLE.z, REAR_AXLE.y, REAR_AXLE.z))


static func _vec3s(colors: Array) -> PackedVector3Array:
	var out := PackedVector3Array()
	for c in colors:
		out.append(Vector3(c.r, c.g, c.b))
	return out


## Écrit les sommets d'un maillage : un appelant par pièce, mêmes données de sommet pour toute la pièce.
class Builder:
	var st := SurfaceTool.new()
	var region := 0
	var shin := 0.0
	var holder := 0.0
	var uv := Vector2.ZERO
	var uv2 := Vector2.ZERO
	var xform := Transform3D.IDENTITY   # appliquée aux points et aux normales de la pièce

	func _init() -> void:
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		st.set_custom_format(0, SurfaceTool.CUSTOM_RGBA_FLOAT)

	func vertex(p: Vector3, n: Vector3, flag_w: float = -1.0) -> void:
		st.set_normal((xform.basis * n).normalized())
		st.set_uv(Vector2(uv.x if flag_w < 0.0 else flag_w, uv.y))
		st.set_uv2(uv2)
		st.set_color(Color.WHITE)
		st.set_custom(0, Color(float(region), shin, holder, 0.0))
		st.add_vertex(xform * p)

	## Prisme effilé de `a` à `b` (axe quelconque), section elliptique (rayons x et z du repère de la pièce)
	## `ra` en bas et `rb` en haut, bouts fermés ; normales lissées sur le pourtour.
	func prism(a: Vector3, b: Vector3, ra: Vector2, rb: Vector2, sides: int = SIDES) -> void:
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
			for v in [a0, b1, b0, a0, a1, b1]:
				vertex(v[0], v[1])
			# Bouts
			vertex(a, -axis); vertex(a0[0], -axis); vertex(a1[0], -axis)
			vertex(b, axis); vertex(b1[0], axis); vertex(b0[0], axis)

	## Ellipsoïde de centre `c` et de rayons `r`, limité aux anneaux d'élévation entre `from_deg` et 90°.
	func ellipsoid(c: Vector3, r: Vector3, from_deg: float = -90.0, rings: int = 6) -> void:
		var lat0 := deg_to_rad(from_deg)
		for j in range(rings):
			var t0 := lerpf(lat0, PI * 0.5, float(j) / rings)
			var t1 := lerpf(lat0, PI * 0.5, float(j + 1) / rings)
			for i in range(SIDES):
				var p0 := TAU * float(i) / SIDES
				var p1 := TAU * float(i + 1) / SIDES
				var q := []
				for tp in [[t0, p0], [t0, p1], [t1, p1], [t1, p0]]:
					var n := Vector3(cos(tp[0]) * sin(tp[1]), sin(tp[0]), cos(tp[0]) * cos(tp[1]))
					q.append([c + n * r, (n / r).normalized()])
				for k in [0, 2, 1, 0, 3, 2]:
					vertex(q[k][0], q[k][1])

	## Pavé de centre `c` et de taille `size`, faces plates.
	func box(c: Vector3, size: Vector3) -> void:
		var h := size * 0.5
		var faces := [[Vector3.RIGHT, Vector3.UP, Vector3.BACK], [Vector3.LEFT, Vector3.UP, Vector3.FORWARD],
			[Vector3.UP, Vector3.BACK, Vector3.RIGHT], [Vector3.DOWN, Vector3.FORWARD, Vector3.RIGHT],
			[Vector3.BACK, Vector3.UP, Vector3.LEFT], [Vector3.FORWARD, Vector3.UP, Vector3.RIGHT]]
		for f in faces:
			var n: Vector3 = f[0]
			var a: Vector3 = f[1]
			var b: Vector3 = f[2]
			var center: Vector3 = c + n * h
			var ea := a * h
			var eb := b * h
			var p := [center - ea - eb, center - ea + eb, center + ea + eb, center + ea - eb]
			for k in [0, 1, 2, 0, 2, 3]:
				vertex(p[k], n)

	func commit() -> ArrayMesh:
		return st.commit()


## Personnage debout ; `with_flag` : bras droit levé devant qui tient une hampe et un drapeau ;
## `helmet` : casque de cycliste à la couleur du haut (coureur, animation « pédale » du shader).
static func build_person(with_flag: bool, helmet: bool = false) -> ArrayMesh:
	var m := Builder.new()
	for sx in [-1.0, 1.0]:
		m.uv2 = Vector2(sx, 0.0)
		m.region = REGION_SHOES
		m.shin = 1.0
		m.box(Vector3(sx * LEG_X, 0.035, 0.03), Vector3(0.085, 0.07, 0.24))
		m.region = REGION_SKIN if helmet else REGION_TROUSERS   # coureur : cuissard court, mollets nus
		m.prism(Vector3(sx * LEG_X, 0.08, 0.0), Vector3(sx * LEG_X, KNEE_Y, 0.0), Vector2(0.05, 0.055), Vector2(0.06, 0.065))
		m.shin = 0.0
		m.region = REGION_TROUSERS
		m.prism(Vector3(sx * LEG_X, KNEE_Y, 0.0), Vector3(sx * (LEG_X + 0.005), HIP_Y, 0.0), Vector2(0.06, 0.065), Vector2(0.085, 0.09))
	m.uv2 = Vector2.ZERO
	m.prism(Vector3(0.0, 0.86, 0.0), Vector3(0.0, 1.0, 0.0), Vector2(0.17, 0.11), Vector2(0.165, 0.105))   # bassin
	m.region = REGION_TOP
	m.prism(Vector3(0.0, 0.98, 0.0), Vector3(0.0, SHOULDER_Y, 0.0), Vector2(0.16, 0.1), Vector2(0.2, 0.115))   # buste
	m.prism(Vector3(0.0, SHOULDER_Y, 0.0), Vector3(0.0, 1.48, 0.0), Vector2(0.2, 0.115), Vector2(0.1, 0.08))   # épaules
	m.region = REGION_SKIN
	m.prism(Vector3(0.0, 1.46, 0.0), Vector3(0.0, 1.54, 0.0), Vector2(0.045, 0.045), Vector2(0.045, 0.045), 6)   # cou
	m.ellipsoid(Vector3(0.0, 1.63, 0.01), Vector3(0.088, 0.112, 0.1))   # tête
	m.box(Vector3(0.0, 1.615, 0.105), Vector3(0.025, 0.04, 0.03))      # nez
	m.region = REGION_HAIR
	m.ellipsoid(Vector3(0.0, 1.648, -0.012), Vector3(0.096, 0.112, 0.106), -5.0, 4)   # cheveux
	if helmet:
		m.region = REGION_TOP
		m.ellipsoid(Vector3(0.0, 1.665, -0.02), Vector3(0.108, 0.115, 0.135), 5.0, 4)
	for sx in [-1.0, 1.0]:
		var holds: bool = with_flag and sx > 0.0
		m.uv = Vector2(0.0, 0.0 if holds else 1.0)
		m.uv2 = Vector2(0.0, 1.0 if sx > 0.0 and not holds else 0.0)
		m.holder = 1.0 if holds else 0.0
		# Porte-drapeau : bras droit levé vers l'avant (rotation autour de l'épaule)
		var pivot := Vector3(sx * SHOULDER_X, SHOULDER_Y, 0.0)
		m.xform = Transform3D(Basis(Vector3.RIGHT, -1.9), Vector3.ZERO).translated_local(-pivot).translated(pivot) if holds else Transform3D.IDENTITY
		m.region = REGION_TOP
		m.prism(Vector3(sx * SHOULDER_X, SHOULDER_Y, 0.0), Vector3(sx * 0.25, 1.15, 0.0), Vector2(0.05, 0.05), Vector2(0.045, 0.045))
		m.region = REGION_SKIN
		m.prism(Vector3(sx * 0.25, 1.15, 0.0), Vector3(sx * 0.255, 0.92, 0.0), Vector2(0.038, 0.038), Vector2(0.032, 0.032), 6)
		m.box(Vector3(sx * 0.255, 0.87, 0.0), Vector3(0.045, 0.09, 0.07))   # main
		m.xform = Transform3D.IDENTITY
		if holds:
			var hand: Vector3 = Transform3D(Basis(Vector3.RIGHT, -1.9), Vector3.ZERO).translated_local(-pivot).translated(pivot) * Vector3(0.255, 0.87, 0.0)
			m.uv = Vector2.ZERO
			m.region = REGION_POLE
			m.prism(hand - Vector3(0.0, 0.25, 0.0), hand + Vector3(0.0, 0.95, 0.0), Vector2(0.015, 0.015), Vector2(0.012, 0.012), 4)
			m.region = REGION_TOP
			var top := hand + Vector3(0.0, 0.93, 0.0)
			_flag_cloth(m, top, 0.65, 0.42)
	m.holder = 0.0
	return m.commit()


## Drapeau : toile de `length` × `height` qui part de la hampe vers +z (vers la route, vue de face par le
## cycliste qui arrive), en 4 bandes (ondulation du shader en x).
static func _flag_cloth(m: Builder, top: Vector3, length: float, height: float) -> void:
	var cols := 4
	for i in range(cols):
		var x0 := length * float(i) / cols
		var x1 := length * float(i + 1) / cols
		var a := top + Vector3(0.0, 0.0, x0)
		var b := top + Vector3(0.0, 0.0, x1)
		var c := top + Vector3(0.0, -height, x1)
		var d := top + Vector3(0.0, -height, x0)
		var f0 := x0 / length
		var f1 := x1 / length
		for v in [[a, f0], [b, f1], [c, f1], [a, f0], [c, f1], [d, f0]]:
			m.vertex(v[0], Vector3.RIGHT, v[1])
		for v in [[a, f0], [c, f1], [b, f1], [a, f0], [d, f0], [c, f1]]:
			m.vertex(v[0], Vector3.LEFT, v[1])


## Chien : corps, poitrail, cou, tête, museau, oreilles, queue et quatre pattes (UV2.x = ±1 en diagonale
## pour le trot ; pivots des pattes à 0,34 m), face vers +z, robe à la couleur d'instance.
static func build_dog() -> ArrayMesh:
	var m := Builder.new()
	m.region = REGION_TOP
	m.prism(Vector3(0.0, 0.45, -0.28), Vector3(0.0, 0.47, 0.26), Vector2(0.11, 0.12), Vector2(0.12, 0.14))   # corps
	m.prism(Vector3(0.0, 0.47, 0.24), Vector3(0.0, 0.6, 0.34), Vector2(0.07, 0.07), Vector2(0.06, 0.06), 6)   # cou
	m.ellipsoid(Vector3(0.0, 0.64, 0.38), Vector3(0.08, 0.075, 0.09))   # tête
	m.prism(Vector3(0.0, 0.62, 0.44), Vector3(0.0, 0.6, 0.53), Vector2(0.045, 0.04), Vector2(0.03, 0.03), 6)   # museau
	for sx in [-1.0, 1.0]:
		m.box(Vector3(sx * 0.055, 0.72, 0.36), Vector3(0.035, 0.07, 0.05))   # oreilles
	m.prism(Vector3(0.0, 0.5, -0.28), Vector3(0.0, 0.62, -0.46), Vector2(0.022, 0.022), Vector2(0.012, 0.012), 4)   # queue
	for leg in [[-1.0, 1.0], [1.0, 1.0], [-1.0, -1.0], [1.0, -1.0]]:
		m.uv2 = Vector2(leg[0] * leg[1], 0.0)
		var p := Vector3(leg[0] * 0.07, 0.0, leg[1] * 0.2)
		m.prism(p + Vector3(0.0, 0.02, 0.0), p + Vector3(0.0, 0.4, 0.0), Vector2(0.025, 0.025), Vector2(0.035, 0.04), 6)
	return m.commit()


## Banc des personnes assises : assise à 0,42 m, dossier, deux pieds, sous la personne (bois à la couleur d'instance).
static func build_bench() -> ArrayMesh:
	var m := Builder.new()
	m.region = REGION_TOP
	for k in range(3):
		m.box(Vector3(0.0, 0.42, -0.18 + k * 0.13), Vector3(1.3, 0.04, 0.11))   # lattes de l'assise
	for k in range(2):
		m.box(Vector3(0.0, 0.62 + k * 0.14, -0.27), Vector3(1.3, 0.1, 0.03))    # dossier
	for sx in [-0.55, 0.55]:
		m.box(Vector3(sx, 0.2, -0.05), Vector3(0.06, 0.4, 0.36))
		m.box(Vector3(sx, 0.6, -0.27), Vector3(0.05, 0.4, 0.04))
	return m.commit()


## Vélo de route : cadre (tubes à la couleur d'instance), fourche, roues (pneu, jante, quatre rayons pour
## voir tourner), pédalier et pédales, selle, cintre. Pièces tournantes repérées par CUSTOM0.y (PART_*).
static func build_bike() -> ArrayMesh:
	var m := Builder.new()
	var saddle := Vector3(0.0, 0.88, -0.03)
	var head_top := Vector3(0.0, 0.86, 0.66)
	var head_low := Vector3(0.0, 0.7, 0.7)
	m.region = REGION_TOP
	var r := Vector2(0.018, 0.018)
	m.prism(BB, saddle - Vector3(0.0, 0.06, 0.0), r, r, 6)            # tube de selle
	m.prism(saddle - Vector3(0.0, 0.1, 0.0), head_top, r, r, 6)       # tube horizontal
	m.prism(BB, head_low, Vector2(0.022, 0.022), r, 6)                # tube oblique
	m.prism(head_low, head_top, Vector2(0.022, 0.022), Vector2(0.022, 0.022), 6)   # douille
	for sx in [-1.0, 1.0]:
		var o := Vector3(sx * 0.05, 0.0, 0.0)
		m.prism(BB + o * 0.5, REAR_AXLE + o, Vector2(0.01, 0.01), Vector2(0.01, 0.01), 4)                    # bases
		m.prism(saddle - Vector3(0.0, 0.1, 0.0), REAR_AXLE + o, Vector2(0.01, 0.01), Vector2(0.01, 0.01), 4)  # haubans
		m.region = REGION_METAL
		m.prism(head_low, FRONT_AXLE + o, Vector2(0.012, 0.012), Vector2(0.009, 0.009), 4)                   # fourche
		m.region = REGION_TOP
	m.region = REGION_SHOES
	m.prism(saddle - Vector3(0.0, 0.0, 0.1), saddle + Vector3(0.0, 0.02, 0.15), Vector2(0.04, 0.012), Vector2(0.015, 0.01), 6)   # selle
	m.region = REGION_METAL
	m.prism(saddle - Vector3(0.0, 0.07, 0.0), saddle, Vector2(0.011, 0.011), Vector2(0.011, 0.011), 4)   # tige de selle
	m.prism(head_top, BAR + Vector3(0.0, -0.01, -0.02), Vector2(0.014, 0.014), Vector2(0.014, 0.014), 4)   # potence
	m.region = REGION_SHOES
	m.prism(BAR + Vector3(-0.21, 0.0, 0.0), BAR + Vector3(0.21, 0.0, 0.0), Vector2(0.014, 0.014), Vector2(0.014, 0.014), 6)   # cintre
	for sx in [-1.0, 1.0]:
		m.prism(BAR + Vector3(sx * 0.2, 0.0, 0.0), BAR + Vector3(sx * 0.2, -0.12, 0.06), Vector2(0.013, 0.013), Vector2(0.013, 0.013), 4)   # cocottes
	for wheel in [[FRONT_AXLE, PART_FRONT_WHEEL], [REAR_AXLE, PART_REAR_WHEEL]]:
		m.shin = float(wheel[1])
		_wheel(m, wheel[0])
	# Pédalier : manivelles vers le bas à droite, vers le haut à gauche ; pédales au bout
	m.shin = float(PART_CRANK)
	m.region = REGION_METAL
	m.prism(BB + Vector3(-0.07, 0.0, 0.0), BB + Vector3(0.07, 0.0, 0.0), Vector2(0.03, 0.03), Vector2(0.03, 0.03), 8)   # plateau (moyeu)
	m.ellipsoid(BB + Vector3(0.06, 0.0, 0.0), Vector3(0.006, 0.1, 0.1))   # plateau
	for sx in [-1.0, 1.0]:
		var end := BB + Vector3(sx * 0.08, -sx * CRANK_M, 0.0)
		m.prism(BB + Vector3(sx * 0.08, 0.0, 0.0), end, Vector2(0.012, 0.012), Vector2(0.01, 0.01), 4)
		m.region = REGION_SHOES
		m.box(end + Vector3(sx * 0.05, 0.0, 0.0), Vector3(0.08, 0.02, 0.09))
		m.region = REGION_METAL
	m.shin = 0.0
	return m.commit()


## Roue : pneu et jante en anneaux de prismes, moyeu et quatre rayons en croix.
static func _wheel(m: Builder, axle: Vector3) -> void:
	var seg := 16
	for ring in [[WHEEL_M - 0.012, 0.014, REGION_SHOES], [WHEEL_M - 0.035, 0.012, REGION_METAL]]:
		m.region = ring[2]
		for i in range(seg):
			var a0 := TAU * i / seg
			var a1 := TAU * (i + 1) / seg
			var p0: Vector3 = axle + Vector3(0.0, cos(a0), sin(a0)) * ring[0]
			var p1: Vector3 = axle + Vector3(0.0, cos(a1), sin(a1)) * ring[0]
			m.prism(p0, p1, Vector2(ring[1], ring[1]), Vector2(ring[1], ring[1]), 4)
	m.region = REGION_METAL
	m.prism(axle + Vector3(-0.05, 0.0, 0.0), axle + Vector3(0.05, 0.0, 0.0), Vector2(0.02, 0.02), Vector2(0.02, 0.02), 6)
	for k in range(4):
		var a := TAU * k / 4.0 + 0.4
		m.prism(axle, axle + Vector3(0.0, cos(a), sin(a)) * (WHEEL_M - 0.04), Vector2(0.004, 0.004), Vector2(0.004, 0.004), 3)
