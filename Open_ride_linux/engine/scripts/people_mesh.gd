extends RefCounted

## Maillages des personnages du décor (spectateurs P15, passants P21) et des cyclistes (bots O7 : coureur
## casqué et vélo), construits par code, sans texture (Lot Y14, refaits par le Lot Y21) : corps en tubes
## profilés à normales lissées (mollet, genou, cuisse, hanches, taille, poitrine, épaules arrondies, bras
## en deux segments articulés au coude, mains en moufle avec pouce, chaussures à bout rond, tête avec
## mâchoire, nez, oreilles, yeux, sourcils et bouche), pièces de tenue montrées selon la tenue (cheveux
## longs, casquette, chapeau, jupe, téléphone), drapeau, pancarte, chien et banc.
## Deux niveaux de détail (`lod`) : 0 de près, 1 au loin (moins de côtés, sans les petites pièces).
## Pas de class_name : charger par preload("res://scripts/people_mesh.gd").
##
## Données par sommet lues par shaders/crowd.gdshader :
## - CUSTOM0.x : zone (REGION_*), qui choisit la couleur : haut (couleur d'instance), peau, cheveux,
##   pantalon, chaussures, hampe, métal, pancarte ;
## - CUSTOM0.y : 1 sous le genou (pliage du genou) et sous le coude (avant-bras, main, téléphone) ; sur le
##   vélo, pièce qui tourne : PART_CRANK (pédalier), PART_FRONT_WHEEL, PART_REAR_WHEEL ; CUSTOM0.z : 1 sur
##   les bras, la hampe, le drapeau et la pancarte du porteur ; CUSTOM0.w : EXTRA_* ;
## - UV.y : 1 sur les bras libres ; UV.x : poids du drapeau (0 à la hampe, 1 au bout) ;
## - UV2.x : ±1 sur chaque jambe (patte du chien, en diagonale) ; UV2.y : 1 sur le bras qui salue.
## Tenue : `outfit(skin, hair, trousers, style, bottom, hat, gesture)` donne INSTANCE_CUSTOM.w (indices dans
## les palettes ci-dessous, passées au shader par `apply_palettes`, bits STYLE_*, bas BOTTOM_*, coiffe
## HAT_* et geste d'encouragement GESTURE_*).
## Personnage debout de 1,75 m, pieds à y = 0, face vers +z ; hanche à HIP_Y, genou à KNEE_Y, épaule à
## SHOULDER_Y, coude à ELBOW_Y (pivots des articulations du shader, passés par `apply_palettes`).

const REGION_TOP := 0
const REGION_SKIN := 1
const REGION_HAIR := 2
const REGION_TROUSERS := 3
const REGION_SHOES := 4
const REGION_POLE := 5
const REGION_METAL := 6
const REGION_SIGN := 7
const REGION_ARM := 8      # peau du bras (manche longue de la veste selon la tenue)

## CUSTOM0.w : pièce montrée selon la tenue (cheveux longs, coiffe, jupe, téléphone) ou motif propre
## (casque à aérations, drapeau, pancarte), lu par le shader.
const EXTRA_LONG_HAIR := 1
const EXTRA_HELMET := 2
const EXTRA_CAP := 3
const EXTRA_SUN_HAT := 4
const EXTRA_SKIRT := 5
const EXTRA_PHONE := 6
const EXTRA_FLAG := 7
const EXTRA_SIGN := 8
## Bits de style de la tenue : cheveux longs, haut à bande, veste ouverte à manches longues ; un coureur a
## toujours son maillot à bande.
const STYLE_LONG_HAIR := 1
const STYLE_STRIPE := 2
const STYLE_JACKET := 4
const STYLES := 8
## Bas : pantalon, short (mollets nus), jupe.
const BOTTOM_TROUSERS := 0
const BOTTOM_SHORTS := 1
const BOTTOM_SKIRT := 2
const BOTTOMS := 3
## Coiffe : aucune, casquette, chapeau de soleil.
const HAT_NONE := 0
const HAT_CAP := 1
const HAT_SUN := 2
const HATS := 3
## Geste quand la personne encourage (et attitude au calme, `GESTURE % 4` : bras le long du corps, bras
## croisés, mains sur les hanches, mains jointes devant), joué par crowd.gdshader.
const GESTURE_ARMS_UP := 0
const GESTURE_CLAP := 1
const GESTURE_FIST := 2
const GESTURE_SHOUT := 3
const GESTURE_PHONE := 4
const GESTURE_HOP_CLAP := 5
const GESTURE_WAVE := 6
const GESTURE_BOTH_FISTS := 7
const GESTURES := 8

const PART_CRANK := 1
const PART_FRONT_WHEEL := 2
const PART_REAR_WHEEL := 3

const HIP_Y := 0.92
const KNEE_Y := 0.5
const SHOULDER_Y := 1.42
const SHOULDER_X := 0.205
const ELBOW_Y := 1.14
const ELBOW_X := 0.225
const LEG_X := 0.09
const SIDES := 8
## Côtés des pièces selon le niveau de détail (0 de près, 1 au loin).
const LOD_SIDES := [8, 5]

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
## Pancarte : taille et hauteur des mains qui la tiennent (bras levés de `build_sign_holder`).
const SIGN_SIZE := Vector2(0.86, 0.48)
const SIGN_HANDS_Y := 1.95
const STRAW_COLOR := Color(0.86, 0.76, 0.5)
## Deuxième couleur des drapeaux et du texte des pancartes (motifs de crowd.gdshader).
const FLAG_COLORS := [Color(0.95, 0.95, 0.95), Color(0.1, 0.25, 0.7), Color(0.85, 0.1, 0.12), Color(0.98, 0.82, 0.1),
	Color(0.1, 0.5, 0.2), Color(0.08, 0.08, 0.08)]


## INSTANCE_CUSTOM.w : indices de peau, de cheveux, de pantalon, bits de style, bas, coiffe et geste dans un
## seul nombre entier exact (moins de 2^24, exact en flottant 32 bits).
static func outfit(skin: int, hair: int, trousers: int, style: int = 0, bottom: int = 0, hat: int = 0,
		gesture: int = 0) -> float:
	var v := posmod(gesture, GESTURES)
	v = v * HATS + posmod(hat, HATS)
	v = v * BOTTOMS + posmod(bottom, BOTTOMS)
	v = v * STYLES + posmod(style, STYLES)
	v = v * TROUSER_COLORS.size() + posmod(trousers, TROUSER_COLORS.size())
	v = v * HAIR_COLORS.size() + posmod(hair, HAIR_COLORS.size())
	v = v * SKIN_TONES.size() + posmod(skin, SKIN_TONES.size())
	return float(v)


## Champs relus d'une tenue (tests, outils) : `{skin, hair, trousers, style, bottom, hat, gesture}`.
static func outfit_fields(o: float) -> Dictionary:
	var v := int(o)
	var out := {}
	for f in [["skin", SKIN_TONES.size()], ["hair", HAIR_COLORS.size()], ["trousers", TROUSER_COLORS.size()],
			["style", STYLES], ["bottom", BOTTOMS], ["hat", HATS], ["gesture", GESTURES]]:
		out[f[0]] = v % int(f[1])
		v /= int(f[1])
	return out


## Tenue tirée d'un nombre entier quelconque (numéro de personne, graine) : mêmes tenues d'une séance à
## l'autre. Environ 7 personnes sur 10 en pantalon, 2 en short, 1 en jupe (cheveux longs le plus souvent) ;
## 3 sur 10 en casquette, 1 sur 8 en chapeau ; geste tiré parmi les huit.
static func outfit_of(seed_value: int) -> float:
	var h := (seed_value * 2654435761) & 0x7FFFFFFF
	var h2 := ((h ^ (h >> 13)) * 1103515245 + 12345) & 0x7FFFFFFF
	var style := (h >> 11) % 5 & 3
	if (h2 >> 4) % 4 == 0:
		style |= STYLE_JACKET
	var r := (h2 >> 8) % 100
	var bottom := BOTTOM_TROUSERS if r < 70 else (BOTTOM_SHORTS if r < 89 else BOTTOM_SKIRT)
	if bottom == BOTTOM_SKIRT and (h2 >> 15) % 4 != 0:
		style |= STYLE_LONG_HAIR
	var rh := (h2 >> 17) % 100
	var hat := HAT_CAP if rh < 30 else (HAT_SUN if rh < 42 else HAT_NONE)
	return outfit(h % 7, (h >> 3) % 11, (h >> 7) % 13, style, bottom, hat, (h2 >> 22) % GESTURES)


## Palettes et pivots des articulations, à poser une fois sur le matériau de crowd.gdshader.
static func apply_palettes(mat: ShaderMaterial) -> void:
	mat.set_shader_parameter("skin_tones", _vec3s(SKIN_TONES))
	mat.set_shader_parameter("hair_colors", _vec3s(HAIR_COLORS))
	mat.set_shader_parameter("trouser_colors", _vec3s(TROUSER_COLORS))
	mat.set_shader_parameter("flag_colors", _vec3s(FLAG_COLORS))
	mat.set_shader_parameter("shoe_color", Vector3(SHOE_COLOR.r, SHOE_COLOR.g, SHOE_COLOR.b))
	mat.set_shader_parameter("pole_color", Vector3(POLE_COLOR.r, POLE_COLOR.g, POLE_COLOR.b))
	mat.set_shader_parameter("metal_color", Vector3(METAL_COLOR.r, METAL_COLOR.g, METAL_COLOR.b))
	mat.set_shader_parameter("straw_color", Vector3(STRAW_COLOR.r, STRAW_COLOR.g, STRAW_COLOR.b))
	mat.set_shader_parameter("joints", Vector4(HIP_Y, KNEE_Y, SHOULDER_Y, SHOULDER_X))
	mat.set_shader_parameter("elbow", Vector2(ELBOW_Y, ELBOW_X))
	mat.set_shader_parameter("sign_rect", sign_rect())
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
	var extra := 0.0                    # CUSTOM0.w : EXTRA_*
	var uv := Vector2.ZERO
	var uv2 := Vector2.ZERO
	var sides := SIDES                  # côtés par défaut des prismes, tubes et ellipsoïdes
	var xform := Transform3D.IDENTITY   # appliquée aux points et aux normales de la pièce

	func _init() -> void:
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		st.set_custom_format(0, SurfaceTool.CUSTOM_RGBA_FLOAT)

	func vertex(p: Vector3, n: Vector3, flag_w: float = -1.0, weight_y: float = -1.0) -> void:
		st.set_normal((xform.basis * n).normalized())
		st.set_uv(Vector2(uv.x if flag_w < 0.0 else flag_w, uv.y if weight_y < 0.0 else weight_y))
		st.set_uv2(uv2)
		st.set_color(Color.WHITE)
		st.set_custom(0, Color(float(region), shin, holder, extra))
		st.add_vertex(xform * p)

	## Repère (u, w) perpendiculaire à l'axe : u suit x pour un axe presque vertical.
	func _frame(axis: Vector3) -> Array:
		var ref := Vector3.FORWARD if absf(axis.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT
		var u := axis.cross(ref).normalized()
		var w := axis.cross(u).normalized()
		if absf(axis.y) > 0.7:
			u = Vector3.RIGHT
			w = axis.cross(u).normalized()
			u = w.cross(axis).normalized()
		return [u, w]

	## Prisme effilé de `a` à `b` (axe quelconque), section elliptique (rayons x et z du repère de la pièce)
	## `ra` en bas et `rb` en haut, bouts fermés ; normales lissées sur le pourtour. `wb` ≥ 0 : UV.y au bout `b`
	## (UV.y de la pièce au bout `a`), pour un cou qui plie progressivement (animaux).
	func prism(a: Vector3, b: Vector3, ra: Vector2, rb: Vector2, p_sides: int = 0, wb: float = -1.0) -> void:
		var n_sides := p_sides if p_sides > 0 else sides
		var axis := (b - a).normalized()
		var fr := _frame(axis)
		var u: Vector3 = fr[0]
		var w: Vector3 = fr[1]
		var ring := func(c: Vector3, r: Vector2, i: int) -> Array:
			var t := TAU * float(i) / n_sides
			var d := u * cos(t) * r.x + w * sin(t) * r.y
			var n := (u * cos(t) / maxf(r.x, 1e-4) + w * sin(t) / maxf(r.y, 1e-4)).normalized()
			return [c + d, n]
		for i in range(n_sides):
			var a0: Array = ring.call(a, ra, i)
			var a1: Array = ring.call(a, ra, i + 1)
			var b0: Array = ring.call(b, rb, i)
			var b1: Array = ring.call(b, rb, i + 1)
			for v in [[a0, -1.0], [b1, wb], [b0, wb], [a0, -1.0], [a1, -1.0], [b1, wb]]:
				vertex(v[0][0], v[0][1], -1.0, v[1])
			# Bouts
			vertex(a, -axis); vertex(a0[0], -axis); vertex(a1[0], -axis)
			vertex(b, axis, -1.0, wb); vertex(b1[0], axis, -1.0, wb); vertex(b0[0], axis, -1.0, wb)

	## Tube profilé de `a` à `b` : `profile` = `[[t, rx, rz], …]` (t de 0 en `a` à 1 en `b`, rayons de la
	## section elliptique), anneaux reliés sans bouchon intermédiaire, bouts fermés si `caps`. Normales
	## tenant compte de la pente du profil (mollet, taille, poitrine lisses).
	func tube(a: Vector3, b: Vector3, profile: Array, caps: bool = true, p_sides: int = 0) -> void:
		var n_sides := p_sides if p_sides > 0 else sides
		var axis := b - a
		var length := axis.length()
		axis = axis / maxf(length, 1e-6)
		var fr := _frame(axis)
		var u: Vector3 = fr[0]
		var w: Vector3 = fr[1]
		var rings := []
		for k in range(profile.size()):
			var t := float(profile[k][0])
			var rx := float(profile[k][1])
			var rz := float(profile[k][2])
			var k0: int = maxi(k - 1, 0)
			var k1: int = mini(k + 1, profile.size() - 1)
			var dt := maxf((float(profile[k1][0]) - float(profile[k0][0])) * length, 1e-4)
			var slope := ((float(profile[k1][1]) + float(profile[k1][2])) - (float(profile[k0][1]) + float(profile[k0][2]))) * 0.5 / dt
			var c := a + axis * (t * length)
			var ring := []
			for i in range(n_sides + 1):
				var th := TAU * float(i % n_sides) / n_sides
				var d := u * cos(th) * rx + w * sin(th) * rz
				var radial := (u * cos(th) / maxf(rx, 1e-4) + w * sin(th) / maxf(rz, 1e-4)).normalized()
				ring.append([c + d, (radial - axis * slope).normalized()])
			rings.append([c, ring])
		for k in range(rings.size() - 1):
			var r0: Array = rings[k][1]
			var r1: Array = rings[k + 1][1]
			for i in range(n_sides):
				for v in [r0[i], r1[i + 1], r1[i], r0[i], r0[i + 1], r1[i + 1]]:
					vertex(v[0], v[1])
		if caps:
			var first: Array = rings[0]
			var last: Array = rings[rings.size() - 1]
			for i in range(n_sides):
				vertex(first[0], -axis); vertex(first[1][i][0], -axis); vertex(first[1][i + 1][0], -axis)
				vertex(last[0], axis); vertex(last[1][i + 1][0], axis); vertex(last[1][i][0], axis)

	## Ellipsoïde de centre `c` et de rayons `r`, limité aux anneaux d'élévation entre `from_deg` et 90°.
	func ellipsoid(c: Vector3, r: Vector3, from_deg: float = -90.0, rings: int = 6) -> void:
		var lat0 := deg_to_rad(from_deg)
		for j in range(rings):
			var t0 := lerpf(lat0, PI * 0.5, float(j) / rings)
			var t1 := lerpf(lat0, PI * 0.5, float(j + 1) / rings)
			for i in range(sides):
				var p0 := TAU * float(i) / sides
				var p1 := TAU * float(i + 1) / sides
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
## `helmet` : casque de cycliste à la couleur du haut (coureur, animation « pédale » du shader) ;
## `lod` : 0 de près, 1 au loin (sans visage fin, pouces, téléphone ni oreilles).
static func build_person(with_flag: bool, helmet: bool = false, lod: int = 0) -> ArrayMesh:
	var m := Builder.new()
	m.sides = LOD_SIDES[clampi(lod, 0, LOD_SIDES.size() - 1)]
	_legs_and_body(m, helmet, lod)
	_head(m, helmet, lod)
	for sx in [-1.0, 1.0]:
		var holds: bool = with_flag and sx > 0.0
		if holds:
			# Porte-drapeau : bras droit levé vers l'avant (rotation autour de l'épaule), coude tendu
			var pivot := Vector3(sx * SHOULDER_X, SHOULDER_Y, 0.0)
			var raise := Transform3D(Basis(Vector3.RIGHT, -1.9), Vector3.ZERO).translated_local(-pivot).translated(pivot)
			m.holder = 1.0
			m.uv = Vector2.ZERO
			_arm(m, sx, helmet, lod, raise, false)
			var hand: Vector3 = raise * Vector3(sx * (ELBOW_X + 0.01), 0.87, 0.0)
			m.region = REGION_POLE
			m.prism(hand - Vector3(0.0, 0.25, 0.0), hand + Vector3(0.0, 0.95, 0.0), Vector2(0.015, 0.015), Vector2(0.012, 0.012), 4)
			m.region = REGION_TOP
			m.extra = EXTRA_FLAG
			_flag_cloth(m, hand + Vector3(0.0, 0.93, 0.0), 0.7, 0.46)
			m.extra = 0.0
			m.holder = 0.0
		else:
			m.uv = Vector2(0.0, 1.0)
			m.uv2 = Vector2(0.0, 1.0 if sx > 0.0 else 0.0)
			_arm(m, sx, helmet, lod, Transform3D.IDENTITY, sx > 0.0 and lod == 0 and not helmet)
	m.uv = Vector2.ZERO
	m.uv2 = Vector2.ZERO
	return m.commit()


## Porteur de pancarte : deux bras levés qui tiennent une pancarte au-dessus de la tête, face à la route
## (CUSTOM0.z = 1 et EXTRA_SIGN sur les bras et la pancarte : balancement commun au milieu des épaules).
static func build_sign_holder(lod: int = 0) -> ArrayMesh:
	var m := Builder.new()
	m.sides = LOD_SIDES[clampi(lod, 0, LOD_SIDES.size() - 1)]
	_legs_and_body(m, false, lod)
	_head(m, false, lod)
	m.holder = 1.0
	m.extra = EXTRA_SIGN
	var hands := []
	for sx in [-1.0, 1.0]:
		var pivot := Vector3(sx * SHOULDER_X, SHOULDER_Y, 0.0)
		# Bras levé (rotation autour de z vers l'extérieur puis en avant), coude légèrement plié vers l'intérieur
		var up := Transform3D(Basis(Vector3.BACK, sx * 2.78) * Basis(Vector3.RIGHT, -0.12), Vector3.ZERO).translated_local(-pivot).translated(pivot)
		_arm(m, sx, false, lod, up, false)
		hands.append(up * Vector3(sx * (ELBOW_X + 0.01), 0.87, 0.0))
	var mid: Vector3 = (hands[0] + hands[1]) * 0.5
	var r := sign_rect(mid)
	m.region = REGION_SIGN
	m.box(Vector3(0.0, (r.y + r.w) * 0.5, mid.z + 0.03), Vector3(r.z - r.x, r.w - r.y, 0.025))
	m.region = REGION_POLE
	m.box(mid + Vector3(0.0, -0.005, 0.0), Vector3((r.z - r.x) * 0.92, 0.03, 0.03))   # latte tenue à deux mains
	m.holder = 0.0
	m.extra = 0.0
	return m.commit()


## Cadre de la pancarte (x min, y min, x max, y max) au-dessus des mains `mid` du porteur : motif du shader
## (`sign_rect`, posé par `apply_palettes`).
static func sign_rect(mid: Vector3 = Vector3(0.0, SIGN_HANDS_Y, 0.0)) -> Vector4:
	return Vector4(-SIGN_SIZE.x * 0.5, mid.y - 0.01, SIGN_SIZE.x * 0.5, mid.y - 0.01 + SIGN_SIZE.y)


## Jambes, chaussures, bassin, buste, épaules et cou (y compris la jupe et la ceinture, selon la tenue).
static func _legs_and_body(m: Builder, helmet: bool, lod: int) -> void:
	for sx in [-1.0, 1.0]:
		var x: float = sx * LEG_X
		m.uv2 = Vector2(sx, 0.0)
		m.shin = 1.0
		m.region = REGION_SHOES
		if lod == 0:
			m.ellipsoid(Vector3(x, 0.035, 0.045), Vector3(0.05, 0.055, 0.125), 0.0, 4)   # chaussure à bout rond
			m.tube(Vector3(x, 0.03, -0.02), Vector3(x, 0.1, -0.02), [[0.0, 0.05, 0.065], [1.0, 0.045, 0.055]], true)   # tige
		else:
			m.box(Vector3(x, 0.045, 0.035), Vector3(0.09, 0.08, 0.24))
		m.region = REGION_METAL if not helmet else REGION_SHOES
		m.box(Vector3(x, 0.007, 0.045), Vector3(0.088, 0.014, 0.235))   # semelle
		if helmet:
			m.region = REGION_METAL
			m.prism(Vector3(x, 0.07, 0.0), Vector3(x, 0.17, 0.0), Vector2(0.044, 0.048), Vector2(0.046, 0.05))   # chaussette
		# Tibia : cheville fine, mollet bombé en arrière, genou
		m.region = REGION_SKIN if helmet else REGION_TROUSERS   # coureur : cuissard court, mollets nus
		m.tube(Vector3(x, 0.07, 0.0), Vector3(x, KNEE_Y, 0.0), [[0.0, 0.036, 0.04], [0.3, 0.045, 0.054],
			[0.62, 0.055, 0.064], [0.85, 0.052, 0.056], [1.0, 0.054, 0.056]], true)
		m.shin = 0.0
		m.region = REGION_TROUSERS
		m.tube(Vector3(x, KNEE_Y - 0.01, 0.0), Vector3(sx * (LEG_X + 0.008), HIP_Y, 0.0), [[0.0, 0.056, 0.06],
			[0.35, 0.068, 0.075], [0.8, 0.084, 0.092], [1.0, 0.088, 0.094]], true)
	m.uv2 = Vector2.ZERO
	m.region = REGION_TROUSERS
	m.tube(Vector3(0.0, 0.84, 0.0), Vector3(0.0, 1.02, 0.0), [[0.0, 0.15, 0.1], [0.45, 0.172, 0.112], [1.0, 0.152, 0.1]], true)   # bassin
	if not helmet:
		m.region = REGION_TROUSERS
		m.extra = EXTRA_SKIRT
		m.tube(Vector3(0.0, 0.56, 0.0), Vector3(0.0, 1.0, 0.0), [[0.0, 0.25, 0.2], [0.55, 0.205, 0.16], [1.0, 0.158, 0.108]], false)   # jupe
		m.extra = 0.0
	# Buste : taille, poitrine, épaules arrondies jusqu'au cou
	m.region = REGION_TOP
	m.tube(Vector3(0.0, 0.97, 0.0), Vector3(0.0, 1.5, 0.0), [[0.0, 0.155, 0.103], [0.12, 0.148, 0.098],
		[0.35, 0.156, 0.104], [0.62, 0.178, 0.118], [0.8, 0.19, 0.115], [0.88, 0.178, 0.105],
		[0.95, 0.13, 0.088], [1.0, 0.07, 0.062]], true)
	if lod == 0 and not helmet:
		m.prism(Vector3(0.0, 1.46, 0.0), Vector3(0.0, 1.505, 0.0), Vector2(0.066, 0.06), Vector2(0.06, 0.056))   # col
		m.region = REGION_SHOES
		m.tube(Vector3(0.0, 0.965, 0.0), Vector3(0.0, 1.005, 0.0), [[0.0, 0.158, 0.106], [1.0, 0.157, 0.105]], false)   # ceinture


## Cou, tête (crâne, mâchoire, nez, oreilles, yeux, sourcils, bouche), cheveux et coiffes.
static func _head(m: Builder, helmet: bool, lod: int) -> void:
	m.region = REGION_SKIN
	m.prism(Vector3(0.0, 1.45, 0.0), Vector3(0.0, 1.56, 0.005), Vector2(0.044, 0.042), Vector2(0.042, 0.042), 6)   # cou
	m.ellipsoid(Vector3(0.0, 1.648, 0.0), Vector3(0.086, 0.1, 0.098), -90.0, 6 if lod == 0 else 4)   # crâne
	if lod == 0:
		m.ellipsoid(Vector3(0.0, 1.59, 0.022), Vector3(0.068, 0.058, 0.074), -90.0, 4)   # mâchoire et menton
		m.prism(Vector3(0.0, 1.648, 0.094), Vector3(0.0, 1.61, 0.118), Vector2(0.012, 0.01), Vector2(0.017, 0.014), 4)   # nez
		for sx in [-1.0, 1.0]:
			m.ellipsoid(Vector3(sx * 0.087, 1.635, -0.005), Vector3(0.014, 0.03, 0.02), -90.0, 3)   # oreilles
		m.region = REGION_SHOES
		if helmet:
			m.box(Vector3(0.0, 1.655, 0.094), Vector3(0.17, 0.034, 0.02))   # lunettes
		else:
			for sx in [-1.0, 1.0]:
				m.box(Vector3(sx * 0.032, 1.655, 0.09), Vector3(0.02, 0.013, 0.01))   # yeux
			m.box(Vector3(0.0, 1.585, 0.093), Vector3(0.034, 0.008, 0.008))   # bouche
			m.region = REGION_HAIR
			for sx in [-1.0, 1.0]:
				m.box(Vector3(sx * 0.034, 1.677, 0.09), Vector3(0.03, 0.008, 0.01))   # sourcils
	m.region = REGION_HAIR
	m.ellipsoid(Vector3(0.0, 1.66, -0.01), Vector3(0.093, 0.1, 0.103), -10.0, 4 if lod == 0 else 3)   # cheveux
	if helmet:
		m.region = REGION_TOP
		m.extra = EXTRA_HELMET
		m.ellipsoid(Vector3(0.0, 1.675, -0.02), Vector3(0.106, 0.112, 0.133), 5.0, 4)
		m.extra = 0.0
		return
	m.extra = EXTRA_LONG_HAIR
	m.tube(Vector3(0.0, 1.66, -0.06), Vector3(0.0, 1.44, -0.075), [[0.0, 0.09, 0.05], [0.6, 0.085, 0.045], [1.0, 0.07, 0.03]], true)   # cheveux longs
	# Casquette à la couleur du bas (visière devant) ; chapeau de soleil en paille à large bord
	m.region = REGION_TROUSERS
	m.extra = EXTRA_CAP
	m.ellipsoid(Vector3(0.0, 1.69, -0.005), Vector3(0.097, 0.075, 0.106), 0.0, 3)
	m.tube(Vector3(0.0, 1.688, 0.07), Vector3(0.0, 1.678, 0.17), [[0.0, 0.085, 0.006], [1.0, 0.07, 0.006]], true, 6)
	m.region = REGION_POLE
	m.extra = EXTRA_SUN_HAT
	m.tube(Vector3(0.0, 1.69, 0.0), Vector3(0.0, 1.7, 0.0), [[0.0, 0.2, 0.2], [1.0, 0.19, 0.19]], true)   # bord
	m.tube(Vector3(0.0, 1.69, -0.005), Vector3(0.0, 1.79, -0.005), [[0.0, 0.1, 0.108], [0.7, 0.095, 0.1], [1.0, 0.07, 0.075]], true)   # calotte
	m.extra = 0.0


## Bras du côté `sx` : manche, coude, avant-bras, main en moufle et pouce (CUSTOM0.y = 1 sous le coude),
## transformé par `xform` (bras levé du porteur) ; `phone` : téléphone dans la main (montré par le geste).
static func _arm(m: Builder, sx: float, helmet: bool, lod: int, xform: Transform3D, phone: bool) -> void:
	m.xform = xform
	var shoulder := Vector3(sx * SHOULDER_X, SHOULDER_Y, 0.0)
	var elbow := Vector3(sx * ELBOW_X, ELBOW_Y, 0.0)
	var wrist := Vector3(sx * (ELBOW_X + 0.01), 0.915, 0.012)
	m.region = REGION_TOP
	m.ellipsoid(shoulder + Vector3(-sx * 0.005, -0.012, 0.0), Vector3(0.052, 0.054, 0.056), -90.0, 4 if lod == 0 else 3)   # épaule
	m.tube(shoulder, Vector3(sx * (SHOULDER_X + 0.01), 1.28, 0.0), [[0.0, 0.054, 0.056], [1.0, 0.049, 0.05]], false)   # manche
	m.region = REGION_ARM
	m.tube(Vector3(sx * (SHOULDER_X + 0.01), 1.29, 0.0), elbow, [[0.0, 0.044, 0.045], [1.0, 0.038, 0.04]], false)
	m.ellipsoid(elbow, Vector3(0.038, 0.038, 0.04), -90.0, 3)   # coude
	m.shin = 1.0
	m.tube(elbow, wrist, [[0.0, 0.037, 0.04], [0.35, 0.036, 0.04], [1.0, 0.026, 0.028]], false)   # avant-bras
	m.region = REGION_SHOES if helmet else REGION_SKIN   # coureur : gants
	m.ellipsoid(Vector3(sx * (ELBOW_X + 0.01), 0.865, 0.014), Vector3(0.024, 0.055, 0.042), -90.0, 4 if lod == 0 else 3)   # main
	if lod == 0:
		m.prism(Vector3(sx * (ELBOW_X + 0.0), 0.9, 0.04), Vector3(sx * (ELBOW_X - 0.008), 0.865, 0.06), Vector2(0.011, 0.011), Vector2(0.01, 0.01), 4)   # pouce
	if phone:
		m.region = REGION_SHOES
		m.extra = EXTRA_PHONE
		m.box(Vector3(sx * (ELBOW_X - 0.005), 0.84, 0.045), Vector3(0.012, 0.13, 0.068))
		m.extra = 0.0
	m.shin = 0.0
	m.xform = Transform3D.IDENTITY


## Drapeau : toile de `length` × `height` qui part de la hampe vers +z (vers la route, vue de face par le
## cycliste qui arrive), en 6 bandes (ondulation du shader en x) ; UV.x de 0 à la hampe à 1 au bout et
## UV2.y de 0 en haut à 1 en bas : coordonnées du motif (crowd.gdshader).
static func _flag_cloth(m: Builder, top: Vector3, length: float, height: float) -> void:
	var cols := 6
	for i in range(cols):
		var x0 := length * float(i) / cols
		var x1 := length * float(i + 1) / cols
		var a := top + Vector3(0.0, 0.0, x0)
		var b := top + Vector3(0.0, 0.0, x1)
		var c := top + Vector3(0.0, -height, x1)
		var d := top + Vector3(0.0, -height, x0)
		var f0 := x0 / length
		var f1 := x1 / length
		for side in [[Vector3.RIGHT, [[a, f0], [b, f1], [c, f1], [a, f0], [c, f1], [d, f0]]],
				[Vector3.LEFT, [[a, f0], [c, f1], [b, f1], [a, f0], [d, f0], [c, f1]]]]:
			for v in side[1]:
				m.uv2 = Vector2(0.0, (top.y - v[0].y) / height)   # 0 en haut, 1 en bas (motif)
				m.vertex(v[0], side[0], v[1])
	m.uv2 = Vector2.ZERO


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
	# Bidon sur le tube oblique, dérailleur, chaîne (haut et bas), cassette
	var down := (head_low - BB).normalized()
	var bottle_at := BB + down * 0.22 + Vector3(0.0, 0.04, -0.035)
	m.region = REGION_METAL
	m.prism(bottle_at, bottle_at + down * 0.2, Vector2(0.034, 0.034), Vector2(0.03, 0.03), 8)
	m.region = REGION_SHOES
	m.box(REAR_AXLE + Vector3(0.06, -0.08, 0.0), Vector3(0.02, 0.07, 0.05))
	for dy in [0.1, -0.1]:
		m.prism(BB + Vector3(0.06, dy, 0.0), REAR_AXLE + Vector3(0.06, dy * 0.5, 0.0), Vector2(0.006, 0.006), Vector2(0.006, 0.006), 3)
	m.shin = float(PART_REAR_WHEEL)
	m.region = REGION_METAL
	m.ellipsoid(REAR_AXLE + Vector3(0.055, 0.0, 0.0), Vector3(0.015, 0.05, 0.05), -90.0, 3)
	m.shin = 0.0
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
