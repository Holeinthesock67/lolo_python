extends RefCounted

## Géométrie et cinématique de l'avatar (lots V6, V7 et Y16) : un cycliste et son vélo de route construits
## par le code (aucun fichier 3D), dans le style des personnages du décor (people_mesh.gd, lot Y14) : volumes
## effilés à sections elliptiques et normales lissées, détails portés par les couleurs de sommet (cuissard et
## sa bande, gants, aérations du casque, guidoline) plutôt que par des pièces ou des matériaux en plus.
##
## Repère : mètres, Y vers le haut, l'avant du vélo vers −Z (comme bots_view.gd), X vers la droite du
## cycliste, origine au sol sous le pédalier. Les segments (cuisse, jambe, bras, avant-bras, cou) gardent une
## longueur fixe : leurs maillages sont construits une fois, axe local Y du début à la fin du segment et
## centrés (segment_transform) ; seule leur transformation change à chaque image.
##
## - Trois niveaux de détail : 0 = cycliste (≤ 6 000 triangles), 1 = intermédiaire (≤ 1 500), 2 = bots (≤ 300).
## - Jambes et bras : cinématique à deux segments dans le plan vertical (pied sur la pédale, main sur la
##   cocotte du cintre), le genou vers l'avant et le coude vers l'arrière, sans squelette importé.
## - Pédalage : l'angle du pédalier avance avec le temps et la pédale du bas recule (vers +Z) pendant que le
##   vélo avance vers −Z, comme les roues (`pedal_pos`, `spin_x`) ; la cheville bascule un peu au fil du tour.
## - Vélo : cadre, fourche, potence, cintre de route à cocottes, selle à la hauteur de la hanche, bidon,
##   transmission ; un maillage fixe (`bike`), un par roue (`wheel`, tourne autour de son axe) et un pour le
##   pédalier (`crank`, tourne autour du boîtier) ; la pédale est sous la chaussure (`shoe`).
## Pas de class_name : charger par preload("res://scripts/avatar_mesh.gd").

const AvatarModel := preload("res://scripts/avatar_model.gd")
const EquipmentMeshes := preload("res://scripts/equipment_meshes.gd")

const LOD_MAX_TRIANGLES := [6000, 1500, 300]
const CRANK_R := 0.1725
const BB := Vector3(0.0, 0.27, 0.0)          # boîtier de pédalier
const FRONT_AXLE := Vector3(0.0, 0.34, -0.59)
const REAR_AXLE := Vector3(0.0, 0.34, 0.41)
const WHEEL_R := 0.34
const PEDAL_HALF_X := 0.085
const SADDLE_Z := 0.22                       # hanche assise : en arrière du pédalier
const BAR := Vector3(0.0, 0.885, -0.58)      # mains sur les cocottes (milieu)
const BAR_HALF_X := 0.205
const BAR_CLAMP := Vector3(0.0, 0.86, -0.49) # milieu du cintre, au bout de la potence
const HEAD_TUBE_TOP := Vector3(0.0, 0.82, -0.385)
const HEAD_TUBE_LOW := Vector3(0.0, 0.677, -0.429)
const SEAT_TUBE_DIR := Vector3(0.0, 0.956, 0.292)   # tube de selle à 73°
const SEAT_CLUSTER := Vector3(0.0, 0.767, 0.152)
const ANKLE_OFFSET := Vector3(0.0, 0.075, 0.09)     # cheville au-dessus et en arrière de la cale
const SEATED_REACH := 0.96                   # hanche assise : part de la longueur de jambe au bas de la course
const STANDING_REACH := 0.99
const SEATED_LEAN := 0.88                    # inclinaison du tronc par rapport à la verticale (rad)
const STANDING_LEAN := 0.8
const BACK_DEPTH := 0.118                    # demi-épaisseur du dos à mi-hauteur (numéro de dossard)
const SHORTS_COLOR := Color(0.07, 0.07, 0.08)
const GLOVE_COLOR := Color(0.1, 0.1, 0.11)
const SHOE_COLOR := Color(0.93, 0.93, 0.94)
const SOLE_COLOR := Color(0.12, 0.12, 0.13)
const DARK := Color(0.08, 0.08, 0.09)
const COMPONENT_COLOR := Color(0.16, 0.16, 0.18)
const METAL_COLOR := Color(0.68, 0.70, 0.73)
const TYRE_COLOR := Color(0.05, 0.05, 0.06)
const DEFAULT_COLORS := {"skin": Color("c98b5e"), "hair": Color("3b2a1e"), "primary": Color("2a9d5c"),
	"secondary": Color("b8bcc4"), "helmet": Color("b8bcc4")}

## Longueurs et rayons selon la taille et la silhouette.
static func dims(settings: Dictionary) -> Dictionary:
	var hs: float = AvatarModel.height_scale(str(settings.get("height", "M")))
	var bs: float = AvatarModel.build_scale(str(settings.get("build", "medium")))
	return {
		"hs": hs, "bs": bs,
		"thigh": 0.42 * hs, "shin": 0.42 * hs, "torso": 0.52 * hs,
		"upper_arm": 0.29 * hs, "forearm": 0.28 * hs, "neck": 0.11 * hs,
		"r_thigh": 0.078 * bs, "r_shin": 0.05 * bs, "r_torso": 0.145 * bs,
		"r_arm": 0.046 * bs, "r_forearm": 0.038 * bs, "r_head": 0.092 * hs,
	}


## Pédale (centre de la cale) pour l'angle `angle` de la pédale droite : en bas à 0, en arrière à π/2, en
## haut à π, devant à 3π/2. L'angle croît avec le temps : la pédale du bas recule pendant que le vélo avance
## vers −Z, comme le bas des roues.
static func pedal_pos(angle: float, side: int) -> Vector3:
	var a := angle + (0.0 if side > 0 else PI)
	return Vector3(side * PEDAL_HALF_X, BB.y - CRANK_R * cos(a), BB.z + CRANK_R * sin(a))


## Rotation autour de X d'une pièce qui tourne dans le sens de la marche (pédalier, roues) d'un angle
## `angle` : le point du bas recule (+Z), celui du haut avance (−Z).
static func spin_x(angle: float) -> Basis:
	return Basis(Vector3.RIGHT, -angle)


## Bascule du pied (rad, positif : pointe vers le bas) : talon bas en poussant devant, pointe basse en remontant
## derrière.
static func foot_pitch(angle: float, side: int) -> float:
	var a := angle + (0.0 if side > 0 else PI)
	return 0.1 + 0.15 * sin(a)


## Repère de la chaussure : origine sur la cale, inclinée de la bascule du pied.
static func foot_transform(angle: float, side: int) -> Transform3D:
	return Transform3D(Basis(Vector3.RIGHT, -foot_pitch(angle, side)), pedal_pos(angle, side))


## Hanche : assise en arrière du pédalier, en danseuse au-dessus et plus avant (jambe presque tendue).
static func hip_pos(standing: bool, d: Dictionary) -> Vector3:
	var reach: float = float(d["thigh"]) + float(d["shin"])
	var k := STANDING_REACH if standing else SEATED_REACH
	var z := 0.10 if standing else SADDLE_Z
	var ankle_low := Vector3(0.0, BB.y - CRANK_R, BB.z) + Basis(Vector3.RIGHT, -0.1) * ANKLE_OFFSET
	var dz := z - ankle_low.z
	return Vector3(0.0, ankle_low.y + sqrt(maxf((k * reach) * (k * reach) - dz * dz, 0.01)), z)


## Genou (ou coude) d'une chaîne à deux segments de longueurs l1 et l2 entre a et c, du côté de `pole`.
static func two_bone(a: Vector3, c: Vector3, l1: float, l2: float, pole: Vector3) -> Vector3:
	var delta := c - a
	var dist := clampf(delta.length(), absf(l1 - l2) + 0.001, l1 + l2 - 0.001)
	var along := delta.normalized() if delta.length() > 0.0001 else Vector3.DOWN
	var x := (l1 * l1 - l2 * l2 + dist * dist) / (2.0 * dist)
	var h := sqrt(maxf(l1 * l1 - x * x, 0.0))
	var perp := pole - along * pole.dot(along)
	perp = perp.normalized() if perp.length() > 0.0001 else Vector3.FORWARD
	return a + along * x + perp * h


## Articulations pour l'angle de pédalier `angle` (pédale droite) : tout ce que la vue place. `frame` : la
## spécification du cadre (equipment_meshes.gd frame_spec) : assis, buste plus bas et mains plus proches sur
## les cadres aéro et contre-la-montre.
static func pose(angle: float, standing: bool, d: Dictionary, frame := {}) -> Dictionary:
	var hip := hip_pos(standing, d)
	var lean := STANDING_LEAN if standing else SEATED_LEAN + float(frame.get("lean_add", 0.0))
	var bar_half := BAR_HALF_X if standing else float(frame.get("bar_half_x", BAR_HALF_X))
	var bar_z := BAR.z if standing else float(frame.get("bar_z", BAR.z))
	var hs := float(d["hs"])
	var shoulder := hip + Vector3(0.0, cos(lean), -sin(lean)) * float(d["torso"])
	var neck := shoulder + Vector3(0.0, 0.03, 0.01) * hs
	var head := shoulder + Vector3(0.0, 0.15, -0.11) * hs
	var out := {"hip": hip, "shoulder": shoulder, "neck": neck, "head": head,
		"chin": head + Vector3(0.0, -0.075, 0.035) * hs}
	for side in [1, -1]:
		var key := "r" if side > 0 else "l"
		var hip_s := hip + Vector3(side * 0.085 * float(d["bs"]), 0.0, 0.0)
		var ankle := foot_transform(angle, side) * ANKLE_OFFSET
		out["hip_" + key] = hip_s
		out["ankle_" + key] = ankle
		out["knee_" + key] = two_bone(hip_s, ankle, float(d["thigh"]), float(d["shin"]), Vector3(0.05 * side, 0.0, -1.0))
		var sh := shoulder + Vector3(side * 0.17 * float(d["bs"]), -0.03, 0.0)
		var hand := Vector3(side * bar_half, BAR.y, bar_z)
		out["shoulder_" + key] = sh
		out["hand_" + key] = hand
		out["elbow_" + key] = two_bone(sh, hand, float(d["upper_arm"]), float(d["forearm"]), Vector3(side * 0.6, -0.3, 0.8))
	return out


## Transformation d'un segment dont l'axe Y local va de a à b, centré entre les deux.
static func segment_transform(a: Vector3, b: Vector3) -> Transform3D:
	var up := (b - a).normalized() if (b - a).length() > 0.0001 else Vector3.UP
	var axis := Vector3.UP.cross(up)
	var basis := Basis()
	if axis.length() > 0.00001:
		basis = Basis(axis.normalized(), Vector3.UP.angle_to(up))
	elif up.y < 0.0:
		basis = Basis(Vector3.RIGHT, PI)
	return Transform3D(basis, (a + b) * 0.5)


## Écrit les sommets d'un maillage avec couleur, normale lissée et UV ; `xform` s'applique à la pièce en cours.
class Geo:
	var st := SurfaceTool.new()
	var color := Color.WHITE
	var xform := Transform3D.IDENTITY

	func _init() -> void:
		st.begin(Mesh.PRIMITIVE_TRIANGLES)

	func vert(p: Vector3, n: Vector3, uv := Vector2.ZERO, c = null) -> void:
		st.set_color(color if c == null else c)
		st.set_normal((xform.basis * n).normalized())
		st.set_uv(uv)
		st.add_vertex(xform * p)

	## Tube à sections elliptiques. `rings` : [[centre, rayon selon u, rayon selon w, couleur ?], …] ; sections
	## dans le plan (u, w) ; UV : u autour, v de 0 au premier anneau à 1 au dernier. Deux anneaux au même centre
	## et de couleurs différentes font une limite nette (bande du cuissard).
	func loft(rings: Array, sides: int, u := Vector3.RIGHT, w := Vector3.BACK, caps := true) -> void:
		var n_r := rings.size()
		var lengths := [0.0]
		for i in range(1, n_r):
			lengths.append(float(lengths[i - 1]) + (rings[i][0] - rings[i - 1][0]).length())
		var total := maxf(float(lengths[n_r - 1]), 1e-4)
		# Faces avant dans le sens horaire vu de l'extérieur (convention de Godot) quel que soit le sens de (u, w)
		var flip := u.cross(w).dot(rings[n_r - 1][0] - rings[0][0]) < 0.0
		var pts := []
		for i in range(n_r):
			var r: Array = rings[i]
			var prev: Array = rings[maxi(i - 1, 0)]
			var next: Array = rings[mini(i + 1, n_r - 1)]
			var axis: Vector3 = next[0] - prev[0]
			var span := axis.length()
			axis = axis / span if span > 1e-4 else u.cross(w).normalized()
			var slope := ((float(next[1]) + float(next[2])) - (float(prev[1]) + float(prev[2]))) * 0.5 / span if span > 1e-4 else 0.0
			var c: Color = r[3] if r.size() > 3 else color
			var row := []
			for k in range(sides + 1):
				var t := TAU * float(k) / sides
				var p: Vector3 = r[0] + u * cos(t) * float(r[1]) + w * sin(t) * float(r[2])
				var nr := (u * cos(t) / maxf(float(r[1]), 1e-4) + w * sin(t) / maxf(float(r[2]), 1e-4)).normalized()
				row.append([p, (nr - axis * slope).normalized(), Vector2(float(k) / sides, float(lengths[i]) / total), c])
			pts.append(row)
		for i in range(n_r - 1):
			for k in range(sides):
				var q := [pts[i][k], pts[i][k + 1], pts[i + 1][k + 1], pts[i + 1][k]]
				for j in ([0, 1, 2, 0, 2, 3] if flip else [0, 2, 1, 0, 3, 2]):
					vert(q[j][0], q[j][1], q[j][2], q[j][3])
		if caps:
			for end in [0, n_r - 1]:
				var c0: Vector3 = rings[end][0]
				var other: Vector3 = rings[1 if end == 0 else n_r - 2][0]
				var n := (c0 - other).normalized() if (c0 - other).length() > 1e-5 else Vector3.UP
				for k in range(sides):
					var a: Array = pts[end][k]
					var b: Array = pts[end][k + 1]
					if (end == 0) != flip:
						vert(c0, n, a[2], a[3]); vert(a[0], a[1], a[2], a[3]); vert(b[0], b[1], b[2], b[3])
					else:
						vert(c0, n, a[2], a[3]); vert(b[0], b[1], b[2], b[3]); vert(a[0], a[1], a[2], a[3])

	## Tube droit de `a` à `b`, section elliptique `ra` en a et `rb` en b (x : rayon selon X, y : rayon dans le
	## plan vertical), pour les tubes du vélo (tous dans le plan YZ ou le long de X).
	func tube(a: Vector3, b: Vector3, ra: Vector2, rb: Vector2, sides: int, caps := true) -> void:
		var axis := (b - a).normalized()
		var u := Vector3.RIGHT if absf(axis.x) < 0.9 else Vector3.UP
		var w := axis.cross(u).normalized()
		u = w.cross(axis).normalized()
		loft([[a, ra.x, ra.y], [b, rb.x, rb.y]], sides, u, w, caps)

	## Tube qui suit une ligne brisée `path` de rayon constant (cintre, chaîne).
	func path_tube(path: Array, r: float, sides: int) -> void:
		var rings := []
		for p in path:
			rings.append([p, r, r])
		var axis: Vector3 = (path[path.size() - 1] - path[0]).normalized()
		var u := Vector3.RIGHT if absf(axis.x) < 0.9 else Vector3.UP
		loft(rings, sides, u, axis.cross(u).normalized())

	## Ellipsoïde de centre `c`, rayons `r`, entre les latitudes `lat0` et `lat1` (degrés) et sur `lon_span`
	## degrés de longitude centrés sur l'arrière (+Z) ; `color_at` : couleur selon la direction (sphère unité).
	func ellipsoid(c: Vector3, r: Vector3, sides: int, rings: int, lat0 := -90.0, lat1 := 90.0, color_at := Callable(), lon_span := 360.0) -> void:
		var grid := []
		for j in range(rings + 1):
			var lat := deg_to_rad(lerpf(lat0, lat1, float(j) / rings))
			var row := []
			for i in range(sides + 1):
				var lon := deg_to_rad(lon_span) * (float(i) / sides - 0.5)
				var n := Vector3(cos(lat) * sin(lon), sin(lat), cos(lat) * cos(lon))
				row.append([c + n * r, (n / r).normalized(), Vector2(float(i) / sides, float(j) / rings),
					color_at.call(n) if color_at.is_valid() else color])
			grid.append(row)
		for j in range(rings):
			for i in range(sides):
				var q := [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
				for k in [0, 2, 1, 0, 3, 2]:
					vert(q[k][0], q[k][1], q[k][2], q[k][3])

	## Anneau (tore) d'axe X centré en `c` : rayon `big`, section elliptique `small` (x : selon X, y : radial).
	func ring(c: Vector3, big: float, small: Vector2, segs: int, sides: int) -> void:
		var grid := []
		for i in range(segs + 1):
			var a := TAU * float(i) / segs
			var radial := Vector3(0.0, cos(a), sin(a))
			var row := []
			for k in range(sides + 1):
				var t := TAU * float(k) / sides
				var p := c + radial * (big + cos(t) * small.y) + Vector3.RIGHT * sin(t) * small.x
				var n := (radial * cos(t) / small.y + Vector3.RIGHT * sin(t) / small.x).normalized()
				row.append([p, n])
			grid.append(row)
		for i in range(segs):
			for k in range(sides):
				var q := [grid[i][k], grid[i + 1][k], grid[i + 1][k + 1], grid[i][k + 1]]
				for j in [0, 2, 1, 0, 3, 2]:
					vert(q[j][0], q[j][1])

	## Pavé de centre `c` et de taille `size`, faces plates.
	func box(c: Vector3, size: Vector3) -> void:
		var h := size * 0.5
		for f in [[Vector3.RIGHT, Vector3.UP, Vector3.BACK], [Vector3.LEFT, Vector3.UP, Vector3.FORWARD],
				[Vector3.UP, Vector3.BACK, Vector3.RIGHT], [Vector3.DOWN, Vector3.FORWARD, Vector3.RIGHT],
				[Vector3.BACK, Vector3.UP, Vector3.LEFT], [Vector3.FORWARD, Vector3.UP, Vector3.RIGHT]]:
			var n: Vector3 = f[0]
			var center: Vector3 = c + n * h
			var ea: Vector3 = f[1] * h
			var eb: Vector3 = f[2] * h
			var p := [center - ea - eb, center - ea + eb, center + ea + eb, center + ea - eb]
			for k in [0, 1, 2, 0, 2, 3]:
				vert(p[k], n)

	func commit() -> ArrayMesh:
		return st.commit()


## Anneaux d'un segment de longueur `length` le long de Y local (−length/2 au début, +length/2 à la fin) :
## `profile` : [[t, rayon relatif, décalage selon Z local, couleur ?], …], t de 0 (début) à 1 (fin).
static func _segment_rings(length: float, radius: float, profile: Array, default_color: Color) -> Array:
	var out := []
	for s in profile:
		var y := (float(s[0]) - 0.5) * length
		var r := radius * float(s[1])
		out.append([Vector3(0.0, y, float(s[2])), r, r, s[3] if s.size() > 3 else default_color])
	return out


static func _limb(length: float, radius: float, profile: Array, sides: int, color: Color, caps := true) -> ArrayMesh:
	var g := Geo.new()
	g.color = color
	g.loft(_segment_rings(length, radius, profile, color), sides, Vector3.RIGHT, Vector3.BACK, caps)
	return g.commit()


## Profil de la jambe (rayon relatif selon t, du genou à la cheville) : sert aussi aux chaussettes.
const SHIN_PROFILE := [[-0.06, 0.62, 0.0], [0.0, 0.95, 0.0], [0.12, 1.05, -0.006], [0.27, 1.14, -0.012],
	[0.45, 1.0, -0.006], [0.7, 0.74, 0.0], [0.9, 0.62, 0.0], [1.0, 0.6, 0.0], [1.05, 0.4, 0.0]]

static func _shin_radius(t: float) -> float:
	for i in range(SHIN_PROFILE.size() - 1):
		var a: Array = SHIN_PROFILE[i]
		var b: Array = SHIN_PROFILE[i + 1]
		if t <= float(b[0]):
			return lerpf(float(a[1]), float(b[1]), clampf((t - float(a[0])) / (float(b[0]) - float(a[0])), 0.0, 1.0))
	return float(SHIN_PROFILE[SHIN_PROFILE.size() - 1][1])


## Tronc (maillot) dans le repère du segment hanche → épaule : +Z local = le dos, X = la droite.
static func _torso(d: Dictionary, sides: int, coarse: bool) -> ArrayMesh:
	var bs := float(d["bs"])
	var L := float(d["torso"])
	var prof := [[1.12, 0.085, 0.065, 0.0], [1.07, 0.16, 0.085, 0.01], [1.0, 0.205, 0.105, 0.005],
		[0.9, 0.2, 0.115, 0.0], [0.7, 0.182, 0.118, 0.008], [0.45, 0.165, 0.114, 0.012],
		[0.2, 0.155, 0.108, 0.01], [0.04, 0.172, 0.122, 0.02]]
	if coarse:
		prof = [[1.1, 0.12, 0.08, 0.0], [0.95, 0.2, 0.11, 0.0], [0.45, 0.165, 0.114, 0.01], [0.04, 0.17, 0.12, 0.02]]
	var rings := []
	for s in prof:
		rings.append([Vector3(0.0, (float(s[0]) - 0.5) * L, float(s[3]) * bs), float(s[1]) * bs, float(s[2]) * bs])
	var g := Geo.new()
	g.loft(rings, sides)   # du haut (v = 0) vers le bas (v = 1), comme les motifs de tenue
	return g.commit()


## Cuissard (bas du tronc, sous le maillot) dans le même repère que le tronc.
static func _shorts(d: Dictionary, sides: int) -> ArrayMesh:
	var bs := float(d["bs"])
	var L := float(d["torso"])
	var g := Geo.new()
	g.color = SHORTS_COLOR
	var rings := []
	for s in [[0.12, 0.163, 0.112, 0.02], [0.0, 0.17, 0.118, 0.025], [-0.06, 0.15, 0.11, 0.03], [-0.12, 0.1, 0.07, 0.03]]:
		rings.append([Vector3(0.0, (float(s[0]) - 0.5) * L, float(s[3]) * bs), float(s[1]) * bs, float(s[2]) * bs])
	g.loft(rings, sides)
	return g.commit()


## Tête (peau) centrée sur `head` : crâne, mâchoire, nez, oreilles ; face vers −Z.
static func _head(d: Dictionary, sides: int, rings: int, skin: Color, fine: bool) -> ArrayMesh:
	var hs := float(d["hs"])
	var g := Geo.new()
	g.color = skin
	g.ellipsoid(Vector3(0.0, 0.01, 0.005) * hs, Vector3(0.078, 0.1, 0.092) * hs, sides, rings)
	if fine:
		g.ellipsoid(Vector3(0.0, -0.045, -0.03) * hs, Vector3(0.064, 0.06, 0.07) * hs, sides / 2, rings / 2 + 1)   # mâchoire
		g.tube(Vector3(0.0, 0.0, -0.088) * hs, Vector3(0.0, -0.03, -0.108) * hs, Vector2(0.012, 0.01), Vector2(0.014, 0.012), 5)   # nez
		for sx in [-1.0, 1.0]:
			g.ellipsoid(Vector3(sx * 0.078, 0.0, 0.01) * hs, Vector3(0.012, 0.03, 0.02) * hs, 6, 3)   # oreilles
	return g.commit()


## Casque de route centré sur la tête : coque allongée vers l'arrière, aérations sombres d'avant en arrière,
## bord sombre, sangles sous le menton ; visière (casque « summit »). Couleur de la coque : `shell`.
static func _helmet(d: Dictionary, sides: int, rings: int, shell: Color, visor: bool, fine: bool) -> ArrayMesh:
	var hs := float(d["hs"])
	var c := Vector3(0.0, 0.032, 0.012) * hs
	var r := Vector3(0.098, 0.093, 0.124) * hs
	var g := Geo.new()
	g.xform = Transform3D(Basis(Vector3.RIGHT, 0.22), Vector3.ZERO)   # arrière plus bas que l'avant
	g.ellipsoid(c, r, sides, rings, -22.0, 90.0, func(n: Vector3) -> Color: return DARK if n.y < -0.18 else shell)
	if fine:
		g.color = DARK
		for xo in [-0.62, -0.25, 0.25, 0.62]:   # aérations : bandes posées sur la coque
			var k := sqrt(1.0 - xo * xo)
			var path := []
			for j in range(7):
				var a := lerpf(0.35, 2.75, float(j) / 6.0)
				path.append([c + Vector3(xo * r.x, r.y * k * sin(a), -r.z * k * cos(a)) * 1.012, Vector3(xo, k * sin(a), -k * cos(a))])
			for j in range(6):
				var p0: Vector3 = path[j][0]
				var p1: Vector3 = path[j + 1][0]
				var side := Vector3.RIGHT * 0.012 * hs
				var n: Vector3 = path[j][1]
				for q in [[p0 - side, p1 - side, p1 + side], [p0 - side, p1 + side, p0 + side],
						[p0 - side, p1 + side, p1 - side], [p0 - side, p0 + side, p1 + side]]:   # deux faces
					for v in q:
						g.vert(v, n)
	g.xform = Transform3D.IDENTITY
	g.color = DARK
	if fine:
		for sx in [-1.0, 1.0]:
			g.tube(Vector3(sx * 0.08, -0.005, 0.0) * hs, Vector3(sx * 0.025, -0.1, -0.035) * hs, Vector2(0.004, 0.006), Vector2(0.004, 0.006), 3, false)
	if visor:
		g.color = shell.darkened(0.3)
		g.box(Vector3(0.0, 0.085, -0.11) * hs, Vector3(0.17, 0.01, 0.07) * hs)
	return g.commit()


## Lunettes enveloppantes centrées sur la tête : bandeau courbe devant les yeux.
static func _glasses(d: Dictionary, segs: int) -> ArrayMesh:
	var hs := float(d["hs"])
	var g := Geo.new()
	for i in range(segs):
		var a0 := lerpf(-1.25, 1.25, float(i) / segs)
		var a1 := lerpf(-1.25, 1.25, float(i + 1) / segs)
		var p0 := Vector3(sin(a0) * 0.084, 0.0, -cos(a0) * 0.1) * hs
		var p1 := Vector3(sin(a1) * 0.084, 0.0, -cos(a1) * 0.1) * hs
		var n0 := Vector3(sin(a0), 0.0, -cos(a0))
		var n1 := Vector3(sin(a1), 0.0, -cos(a1))
		var dy := Vector3(0.0, 0.019, 0.0) * hs
		var y0 := Vector3(0.0, 0.012, 0.0) * hs
		for v in [[p0 - dy, n0], [p1 + dy, n1], [p0 + dy, n0], [p0 - dy, n0], [p1 - dy, n1], [p1 + dy, n1]]:
			g.vert(v[0] + y0, v[1])
	return g.commit()


## Chaussure de vélo et pédale, origine sur la cale, pointe vers −Z : semelle sombre, dessus clair, molette.
static func _shoe(sides: int, lod: int) -> ArrayMesh:
	var g := Geo.new()
	if lod == 2:
		g.color = SOLE_COLOR
		g.box(Vector3(0.0, 0.045, 0.02), Vector3(0.09, 0.07, 0.26))
		return g.commit()
	var fine := lod == 0
	var rings := []
	for s in [[0.165, 0.028, 0.03, 0.055], [0.15, 0.042, 0.045, 0.055], [0.06, 0.046, 0.045, 0.05],
			[-0.04, 0.046, 0.03, 0.036], [-0.1, 0.034, 0.02, 0.03], [-0.122, 0.014, 0.012, 0.028]]:
		rings.append([Vector3(0.0, float(s[3]), float(s[0])), float(s[1]), float(s[2]), SHOE_COLOR])
	g.loft(rings, sides, Vector3.RIGHT, Vector3.UP)
	g.color = SOLE_COLOR
	g.box(Vector3(0.0, 0.012, 0.02), Vector3(0.085, 0.014, 0.27))   # semelle
	g.color = COMPONENT_COLOR
	g.box(Vector3(0.0, -0.002, 0.0), Vector3(0.075, 0.016, 0.08))   # pédale
	if fine:
		g.color = DARK
		g.tube(Vector3(0.048, 0.07, 0.05), Vector3(0.056, 0.07, 0.05), Vector2(0.016, 0.016), Vector2(0.016, 0.016), 6)   # molette
	return g.commit()


## Main gantée sur la cocotte, centrée sur la main (doigts autour de la cocotte, pouce dessus).
static func _hand(sides: int, fine: bool) -> ArrayMesh:
	var g := Geo.new()
	g.color = GLOVE_COLOR
	g.ellipsoid(Vector3(0.0, 0.0, 0.0), Vector3(0.04, 0.042, 0.055), sides, maxi(sides / 2, 2))
	if fine:
		g.tube(Vector3(-0.025, 0.02, 0.0), Vector3(-0.03, 0.03, -0.05), Vector2(0.012, 0.012), Vector2(0.01, 0.01), 5)
	return g.commit()


## Vélo fixe (sans roues ni pédalier) dans le repère de l'avatar : cadre à la couleur `frame` (sections de
## `fs.tube`), fourche, potence, cintre de route et cocottes, tige et selle à la hauteur de la hanche assise,
## prolongateurs du contre-la-montre, bidon, transmission (chaîne, cassette, dérailleur).
static func _bike(lod: int, d: Dictionary, fs: Dictionary, accent: Color) -> ArrayMesh:
	var g := Geo.new()
	var sides: int = [8, 4, 3][lod]
	var tube: Vector2 = fs["tube"]
	var r := Vector2(tube.x, tube.y) * 0.5
	g.color = fs["color"]
	var hip_y := hip_pos(false, d).y
	var saddle := BB + SEAT_TUBE_DIR * ((hip_y - 0.095 - BB.y) / SEAT_TUBE_DIR.y)
	if lod == 2:   # bots : cadre en quatre tubes, fourche, cintre et selle
		for t in [[BB, saddle], [SEAT_CLUSTER, HEAD_TUBE_TOP], [BB, HEAD_TUBE_LOW], [BB, REAR_AXLE], [HEAD_TUBE_LOW, FRONT_AXLE]]:
			g.tube(t[0], t[1], r, r, sides, false)
		g.color = DARK
		g.tube(BAR + Vector3(-BAR_HALF_X, 0.0, 0.0), BAR + Vector3(BAR_HALF_X, 0.0, 0.0), Vector2(0.015, 0.015), Vector2(0.015, 0.015), sides, false)
		g.box(saddle + Vector3(0.0, 0.035, 0.0), Vector3(0.1, 0.035, 0.24))
		return g.commit()
	g.tube(BB, SEAT_CLUSTER, r * 1.05, r, sides)                                   # tube de selle
	g.tube(SEAT_CLUSTER + Vector3(0.0, -0.01, 0.0), HEAD_TUBE_TOP + Vector3(0.0, -0.025, 0.0), r, r, sides)   # tube horizontal
	g.tube(BB, HEAD_TUBE_LOW + Vector3(0.0, 0.03, 0.01), r * 1.35, r * 1.25, sides)   # tube oblique
	g.tube(HEAD_TUBE_LOW, HEAD_TUBE_TOP, r * 1.25, r * 1.2, sides)                  # douille
	var fork_mid := Vector3(0.0, 0.5, -0.5)
	for sx in [-1.0, 1.0]:
		var o := Vector3(sx * 0.05, 0.0, 0.0)
		g.tube(BB + o * 0.8, REAR_AXLE + o * 1.3, r * 0.5, r * 0.4, sides, false)                       # bases
		g.tube(SEAT_CLUSTER + o * 0.4, REAR_AXLE + o * 1.3, r * 0.45, r * 0.38, sides, false)           # haubans
		g.tube(HEAD_TUBE_LOW + o * 0.6, fork_mid + o, r * 0.75, r * 0.6, sides, false)                  # fourche
		g.tube(fork_mid + o, FRONT_AXLE + o, r * 0.6, r * 0.45, sides, false)
	g.color = COMPONENT_COLOR
	g.tube(SEAT_CLUSTER, saddle, Vector2(0.0135, 0.0135), Vector2(0.0135, 0.0135), sides)          # tige de selle
	g.tube(HEAD_TUBE_TOP, HEAD_TUBE_TOP + Vector3(0.0, 0.035, 0.0), r * 1.2, r * 1.2, sides)        # entretoises
	g.tube(HEAD_TUBE_TOP + Vector3(0.0, 0.03, 0.01), BAR_CLAMP, Vector2(0.016, 0.016), Vector2(0.015, 0.015), sides)   # potence
	g.color = DARK
	var bar_half := BAR_HALF_X
	g.tube(BAR_CLAMP + Vector3(-bar_half, 0.0, 0.0), BAR_CLAMP + Vector3(bar_half, 0.0, 0.0), Vector2(0.0125, 0.0125), Vector2(0.0125, 0.0125), sides, false)
	for sx in [-1.0, 1.0]:   # cintre : du haut vers l'avant puis le bas (drops), cocotte au sommet de la courbe
		var drop := []
		var bend := [[0.86, -0.49], [0.866, -0.54], [0.85, -0.58], [0.8, -0.598], [0.75, -0.575], [0.735, -0.51]]
		if lod == 1:
			bend = [[0.86, -0.49], [0.855, -0.575], [0.77, -0.59], [0.735, -0.51]]
		for p in bend:
			drop.append(Vector3(sx * bar_half, float(p[0]), float(p[1])))
		g.path_tube(drop, 0.0125, sides)
		g.tube(Vector3(sx * bar_half, 0.868, -0.548), Vector3(sx * bar_half, 0.893, -0.615), Vector2(0.017, 0.022), Vector2(0.014, 0.016), sides)   # cocotte
		if lod == 0:
			g.tube(Vector3(sx * bar_half, 0.885, -0.61), Vector3(sx * bar_half, 0.77, -0.6), Vector2(0.006, 0.01), Vector2(0.005, 0.008), 4)   # levier
	# Selle : bec vers l'avant, arrière large
	g.loft([[saddle + Vector3(0.0, 0.03, -0.14), 0.012, 0.008], [saddle + Vector3(0.0, 0.035, -0.06), 0.03, 0.014],
		[saddle + Vector3(0.0, 0.04, 0.06), 0.068, 0.017], [saddle + Vector3(0.0, 0.045, 0.11), 0.05, 0.014]],
		sides, Vector3.RIGHT, Vector3.UP)
	if fs.get("extensions", false):
		var bz := float(fs.get("bar_z", BAR.z))
		var bh := float(fs.get("bar_half_x", BAR_HALF_X))
		for sx in [-1.0, 1.0]:
			g.tube(Vector3(sx * bh, BAR.y - 0.015, bz + 0.32), Vector3(sx * bh, BAR.y, bz), Vector2(0.012, 0.012), Vector2(0.012, 0.012), sides)
			g.box(Vector3(sx * bh, BAR.y - 0.0, bz + 0.22), Vector3(0.07, 0.03, 0.12))   # repose-coudes
	if lod == 0:
		var down := (HEAD_TUBE_LOW - BB).normalized()
		var bottle := BB + down * 0.2 + Vector3(0.0, 0.045, -0.035) * 1.0
		g.color = accent
		g.tube(bottle, bottle + down * 0.19, Vector2(0.034, 0.034), Vector2(0.032, 0.032), sides)   # bidon
		g.color = DARK
		g.tube(bottle + down * 0.19, bottle + down * 0.215, Vector2(0.018, 0.018), Vector2(0.012, 0.012), sides)
		g.color = METAL_COLOR
		g.tube(REAR_AXLE + Vector3(0.03, 0.0, 0.0), REAR_AXLE + Vector3(0.06, 0.0, 0.0), Vector2(0.05, 0.05), Vector2(0.03, 0.03), sides)   # cassette
		g.color = DARK
		g.box(REAR_AXLE + Vector3(0.065, -0.07, 0.01), Vector3(0.018, 0.075, 0.045))   # dérailleur
		g.tube(BB + Vector3(0.05, 0.1, 0.0), REAR_AXLE + Vector3(0.05, 0.045, 0.0), Vector2(0.004, 0.006), Vector2(0.004, 0.006), 3, false)   # chaîne
		g.tube(BB + Vector3(0.05, -0.1, 0.0), REAR_AXLE + Vector3(0.065, -0.1, 0.01), Vector2(0.004, 0.006), Vector2(0.004, 0.006), 3, false)
	return g.commit()


## Roue d'axe X centrée sur son moyeu : pneu, jante (forme selon `ws.kind`), rayons croisés, moyeu.
static func wheel_mesh(lod: int, ws: Dictionary) -> ArrayMesh:
	var g := Geo.new()
	var segs: int = [28, 10, 6][lod]
	g.color = TYRE_COLOR
	g.ring(Vector3.ZERO, WHEEL_R - 0.013, Vector2(0.0125, 0.013), segs, [6, 3, 3][lod])
	var kind := str(ws["kind"])
	var depth := maxf(float(ws["rim"]), 0.014) if kind != "disc" else 0.02
	var rim_r := WHEEL_R - 0.024 - depth * 0.5
	g.color = ws["color"]
	if lod <= 1:
		g.ring(Vector3.ZERO, rim_r, Vector2(0.01, depth * 0.5), segs, [4, 3][lod])
	if kind == "disc":
		var rings := []
		for s in [[-0.016, 0.03], [-0.011, rim_r], [0.011, rim_r], [0.016, 0.03]]:
			rings.append([Vector3(float(s[0]), 0.0, 0.0), float(s[1]), float(s[1])])
		g.loft(rings, segs, Vector3.UP, Vector3.BACK)
	elif lod == 0:
		g.color = METAL_COLOR
		var n := int(ws["spokes"])
		for k in range(n):
			var a := TAU * float(k) / n
			var side := 1.0 if k % 2 == 0 else -1.0
			var hub := Vector3(side * 0.028, 0.0, 0.0) + Vector3(0.0, cos(a + 0.35), sin(a + 0.35)) * 0.022
			var rim := Vector3(0.0, cos(a), sin(a)) * (rim_r - depth * 0.45)
			g.tube(hub, rim, Vector2(0.0018, 0.0018), Vector2(0.0018, 0.0018), 3, false)
	if lod <= 1:
		g.color = METAL_COLOR
		g.tube(Vector3(-0.05, 0.0, 0.0), Vector3(0.05, 0.0, 0.0), Vector2(0.018, 0.018), Vector2(0.018, 0.018), [8, 5][lod], lod == 0)
	return g.commit()


## Pédalier centré sur le boîtier, manivelle droite vers le bas (angle 0) : plateaux à droite, manivelles, axe.
static func crank_mesh(lod: int) -> ArrayMesh:
	var g := Geo.new()
	var sides: int = [8, 5, 3][lod]
	g.color = METAL_COLOR
	if lod == 0:
		g.ring(Vector3(0.045, 0.0, 0.0), 0.098, Vector2(0.003, 0.012), 20, 3)   # grand plateau
		g.ring(Vector3(0.038, 0.0, 0.0), 0.07, Vector2(0.003, 0.01), 14, 3)     # petit plateau
		g.color = COMPONENT_COLOR
		for k in range(4):   # étoile
			var a := TAU * k / 4.0 + 0.4
			g.tube(Vector3(0.045, 0.0, 0.0), Vector3(0.045, cos(a), sin(a)) * Vector3(1.0, 0.09, 0.09), Vector2(0.004, 0.008), Vector2(0.004, 0.008), 3, false)
	g.color = COMPONENT_COLOR
	g.tube(Vector3(-0.07, 0.0, 0.0), Vector3(0.07, 0.0, 0.0), Vector2(0.02, 0.02), Vector2(0.02, 0.02), sides)   # axe
	for sx in [-1.0, 1.0]:   # droite vers le bas, gauche vers le haut
		g.tube(Vector3(sx * 0.065, 0.0, 0.0), Vector3(sx * PEDAL_HALF_X * 0.95, -sx * CRANK_R, 0.0), Vector2(0.008, 0.016), Vector2(0.007, 0.011), sides)
	return g.commit()


## Maillages d'un niveau de détail : {nom : {"mesh": Mesh, "count": instances}}. `looks` : équipement
## (equipment_meshes.gd equip_looks) ; `colors` : peau, cheveux, couleurs de tenue et de casque
## (DEFAULT_COLORS par défaut), cuites dans les couleurs de sommet. Le tronc et les manches restent blancs :
## leur matériau porte le motif de la tenue.
static func build(lod: int, d: Dictionary, looks := {}, colors := {}) -> Dictionary:
	lod = clampi(lod, 0, 2)
	var col := DEFAULT_COLORS.duplicate()
	col.merge(colors, true)
	var skin: Color = col["skin"]
	var fine := lod == 0
	var radial: int = [10, 5, 4][lod]
	var fs := EquipmentMeshes.frame_spec(str(looks.get("frame", "")))
	var ws := EquipmentMeshes.wheel_spec(str(looks.get("wheels", "")))
	var parts := {}
	var thigh_prof := [[-0.1, 0.55, 0.0, SHORTS_COLOR], [0.0, 1.0, 0.0, SHORTS_COLOR], [0.3, 0.98, 0.008, SHORTS_COLOR],
		[0.64, 0.86, 0.0, SHORTS_COLOR], [0.64, 0.87, 0.0, col["secondary"]], [0.7, 0.86, 0.0, col["secondary"]],
		[0.7, 0.8, 0.0, skin], [0.88, 0.7, 0.0, skin], [1.0, 0.68, 0.0, skin], [1.07, 0.45, 0.0, skin]]
	var upper_prof := [[-0.12, 0.7, 0.0], [0.0, 1.0, 0.0], [0.3, 0.96, 0.0], [0.7, 0.84, 0.0], [1.0, 0.8, 0.0], [1.08, 0.5, 0.0]]
	var fore_prof := [[-0.06, 0.7, 0.0], [0.0, 1.0, 0.0], [0.25, 1.1, 0.0], [0.8, 0.74, 0.0], [1.0, 0.7, 0.0]]
	var sleeve_prof := [[-0.16, 0.75, 0.0], [-0.05, 1.12, 0.0], [0.25, 1.1, 0.0], [0.48, 1.04, 0.0]]
	if lod == 1:
		thigh_prof = [[0.0, 1.0, 0.0, SHORTS_COLOR], [0.68, 0.86, 0.0, SHORTS_COLOR], [0.68, 0.8, 0.0, skin], [1.0, 0.7, 0.0, skin]]
		upper_prof = [[-0.08, 0.8, 0.0], [0.4, 0.95, 0.0], [1.0, 0.8, 0.0]]
		fore_prof = [[0.0, 1.0, 0.0], [0.3, 1.05, 0.0], [1.0, 0.7, 0.0]]
	if lod == 2:
		thigh_prof = [[0.0, 1.0, 0.0, SHORTS_COLOR], [1.0, 0.75, 0.0, SHORTS_COLOR]]
		upper_prof = [[0.0, 1.0, 0.0], [1.0, 0.8, 0.0]]
		fore_prof = [[0.0, 1.0, 0.0], [1.0, 0.75, 0.0]]
	var shin_prof: Array = [SHIN_PROFILE, [[0.0, 0.95, 0.0], [0.3, 1.1, -0.01], [1.0, 0.6, 0.0]], [[0.0, 1.0, 0.0], [1.0, 0.65, 0.0]]][lod]
	parts["torso"] = {"mesh": _torso(d, [16, 8, 4][lod], lod == 2), "count": 1}
	var caps := lod <= 1
	parts["thigh"] = {"mesh": _limb(float(d["thigh"]), float(d["r_thigh"]), thigh_prof, radial, SHORTS_COLOR, caps), "count": 2}
	parts["shin"] = {"mesh": _limb(float(d["shin"]), float(d["r_shin"]), shin_prof, radial, skin, caps), "count": 2}
	parts["upper_arm"] = {"mesh": _limb(float(d["upper_arm"]), float(d["r_arm"]), upper_prof, maxi(radial - 2, 4), skin, caps), "count": 2}
	parts["forearm"] = {"mesh": _limb(float(d["forearm"]), float(d["r_forearm"]), fore_prof, maxi(radial - 2, 4), skin, caps), "count": 2}
	parts["head"] = {"mesh": _head(d, [12, 7, 4][lod], [7, 4, 2][lod], skin, fine), "count": 1}
	parts["shoe"] = {"mesh": _shoe([8, 4, 3][lod], lod), "count": 2}
	parts["bike"] = {"mesh": _bike(lod, d, fs, col["primary"]), "count": 1}
	parts["wheel"] = {"mesh": wheel_mesh(lod, ws), "count": 2}
	if lod == 0:
		var g := Geo.new()
		g.loft(_segment_rings(float(d["upper_arm"]), float(d["r_arm"]), sleeve_prof, Color.WHITE), maxi(radial - 2, 4))
		parts["sleeve"] = {"mesh": g.commit(), "count": 2}
	if lod <= 1:
		parts["pelvis"] = {"mesh": _shorts(d, [14, 8][lod]), "count": 1}
		parts["neck"] = {"mesh": _limb(float(d["neck"]), 0.05 * float(d["bs"]), [[0.0, 1.0, 0.0], [1.0, 0.9, 0.0]], radial, skin), "count": 1}
		parts["hand"] = {"mesh": _hand([8, 4][lod], fine), "count": 2}
		parts["crank"] = {"mesh": crank_mesh(lod), "count": 1}
		var hs := EquipmentMeshes.helmet_spec(str(looks.get("helmet", "")))
		parts["helmet"] = {"mesh": _helmet(d, [18, 8][lod], [7, 3][lod], col["helmet"], bool(hs["visor"]), fine), "count": 1}
		var hair := Geo.new()
		hair.color = col["hair"]
		hair.ellipsoid(Vector3(0.0, 0.0, 0.006) * float(d["hs"]), Vector3(0.083, 0.102, 0.097) * float(d["hs"]), [10, 6][lod], [5, 2][lod], -40.0, 90.0, Callable(), 230.0)   # nuque et côtés, pas le visage
		parts["hair"] = {"mesh": hair.commit(), "count": 1}
		var ss := EquipmentMeshes.socks_spec(str(looks.get("socks", "")))
		parts["sock"] = {"mesh": _sock(d, float(ss["length"]), maxi(radial, 6), ss, col["secondary"]), "count": 2}
		parts["glasses"] = {"mesh": _glasses(d, [10, 6][lod]), "count": 1}
	return parts


## Chaussette : du pied vers le genou sur `length` de la jambe, au profil du mollet un peu élargi ; repère du
## segment cheville → haut de la chaussette (Y local), comme la vue la place. Rayée : deux bandes `accent` en haut.
static func _sock(d: Dictionary, length: float, sides: int, ss: Dictionary, accent: Color) -> ArrayMesh:
	var L := float(d["shin"]) * length
	var base: Color = ss["color"]
	var stops := [[0.0, base], [0.25, base], [0.5, base], [0.75, base], [1.0, base]]
	if ss.get("striped", false):
		stops = [[0.0, base], [0.5, base], [0.62, base], [0.62, accent], [0.74, accent], [0.74, base],
			[0.82, base], [0.82, accent], [0.92, accent], [0.92, base], [1.0, base]]
	var rings := []
	for s in stops:
		var f := float(s[0])
		var r := float(d["r_shin"]) * _shin_radius(1.0 - f * length) * 1.08
		rings.append([Vector3(0.0, (f - 0.5) * L, 0.0), r, r, s[1]])
	var g := Geo.new()
	g.loft(rings, sides, Vector3.RIGHT, Vector3.BACK, false)
	return g.commit()


static func triangles_of(mesh: Mesh) -> int:
	var total := 0
	for i in range(mesh.get_surface_count()):
		var arrays := mesh.surface_get_arrays(i)
		var idx = arrays[Mesh.ARRAY_INDEX]
		total += (idx.size() if idx != null else arrays[Mesh.ARRAY_VERTEX].size()) / 3
	return total


## Triangles de tout l'avatar à ce niveau de détail (chaque instance compte).
static func triangle_count(lod: int, d: Dictionary, looks := {}) -> int:
	var total := 0
	var parts := build(lod, d, looks)
	for name in parts:
		total += triangles_of(parts[name]["mesh"]) * int(parts[name]["count"])
	return total
