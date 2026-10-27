extends RefCounted

## Géométrie et cinématique de l'avatar (lot V6) : un cycliste fait de volumes simples assemblés par le
## code (aucun fichier 3D), sur un vélo de base générique dont V7 remplacera les pièces.
##
## Repère : mètres, Y vers le haut, l'avant du vélo vers −Z (comme bots_view.gd), X vers la droite du
## cycliste, origine au sol sous le pédalier. Les segments (cuisse, jambe, bras, avant-bras) gardent une
## longueur fixe : leurs maillages sont construits une fois, seule leur transformation change à chaque image.
##
## - Trois niveaux de détail : 0 = cycliste (≤ 6 000 triangles), 1 = intermédiaire (≤ 1 500), 2 = bots (≤ 300).
## - Jambes et bras : cinématique à deux segments dans le plan vertical (pied sur la pédale, main sur le
##   cintre), le genou vers l'avant et le coude vers l'arrière, sans squelette importé.
## Pas de class_name : charger par preload("res://scripts/avatar_mesh.gd").

const AvatarModel := preload("res://scripts/avatar_model.gd")
const EquipmentMeshes := preload("res://scripts/equipment_meshes.gd")

const LOD_MAX_TRIANGLES := [6000, 1500, 300]
const CRANK_R := 0.1725
const BB := Vector3(0.0, 0.30, 0.0)         # boîtier de pédalier
const PEDAL_HALF_X := 0.085
const SADDLE_Z := 0.22                       # hanche assise : en arrière du pédalier
const BAR := Vector3(0.0, 0.95, -0.45)       # milieu du cintre
const BAR_HALF_X := 0.19
const WHEEL_R := 0.34
const WHEEL_BASE := 1.04
const SEATED_REACH := 0.96                   # hanche assise : part de la longueur de jambe au bas de la course
const STANDING_REACH := 0.99
const SEATED_LEAN := 1.0                     # inclinaison du tronc par rapport à la verticale (rad)
const STANDING_LEAN := 0.75

## Longueurs et rayons selon la taille et la silhouette.
static func dims(settings: Dictionary) -> Dictionary:
	var hs: float = AvatarModel.height_scale(str(settings.get("height", "M")))
	var bs: float = AvatarModel.build_scale(str(settings.get("build", "medium")))
	return {
		"hs": hs, "bs": bs,
		"thigh": 0.42 * hs, "shin": 0.42 * hs, "torso": 0.52 * hs,
		"upper_arm": 0.28 * hs, "forearm": 0.27 * hs,
		"r_thigh": 0.072 * bs, "r_shin": 0.052 * bs, "r_torso": 0.145 * bs,
		"r_arm": 0.044 * bs, "r_forearm": 0.038 * bs, "r_head": 0.105 * hs,
	}


static func pedal_pos(angle: float, side: int) -> Vector3:
	var a := angle + (0.0 if side > 0 else PI)
	return Vector3(side * PEDAL_HALF_X, BB.y - CRANK_R * cos(a), BB.z - CRANK_R * sin(a))


## Hanche : assise en arrière du pédalier, en danseuse au-dessus et plus avant (jambe presque tendue).
static func hip_pos(standing: bool, d: Dictionary) -> Vector3:
	var reach: float = float(d["thigh"]) + float(d["shin"])
	var k := STANDING_REACH if standing else SEATED_REACH
	var z := 0.10 if standing else SADDLE_Z
	return Vector3(0.0, BB.y - CRANK_R + sqrt(maxf((k * reach) * (k * reach) - z * z, 0.01)), z)


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
	var shoulder := hip + Vector3(0.0, cos(lean), -sin(lean)) * float(d["torso"])
	var out := {"hip": hip, "shoulder": shoulder,
		"head": shoulder + Vector3(0.0, 0.10, -0.07) * float(d["hs"]) + Vector3(0.0, float(d["r_head"]), -float(d["r_head"]) * 0.3)}
	for side in [1, -1]:
		var key := "r" if side > 0 else "l"
		var hip_s := hip + Vector3(side * 0.085 * float(d["bs"]), 0.0, 0.0)
		var ankle := pedal_pos(angle, side) + Vector3(0.0, 0.07, 0.03)
		out["hip_" + key] = hip_s
		out["ankle_" + key] = ankle
		out["knee_" + key] = two_bone(hip_s, ankle, float(d["thigh"]), float(d["shin"]), Vector3(0.05 * side, 0.0, -1.0))
		var sh := shoulder + Vector3(side * 0.17 * float(d["bs"]), -0.02, 0.0)
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


static func _capsule(radius: float, length: float, radial: int, rings: int) -> CapsuleMesh:
	var m := CapsuleMesh.new()
	m.radius = radius
	m.height = length + radius
	m.radial_segments = radial
	m.rings = rings
	return m


static func _sphere(radius: float, radial: int, rings: int, squash := 1.0) -> SphereMesh:
	var m := SphereMesh.new()
	m.radius = radius
	m.height = 2.0 * radius * squash
	m.radial_segments = radial
	m.rings = rings
	return m


static func _box(size: Vector3) -> BoxMesh:
	var m := BoxMesh.new()
	m.size = size
	return m


static func _cylinder(radius: float, height: float, radial: int) -> CylinderMesh:
	var m := CylinderMesh.new()
	m.top_radius = radius
	m.bottom_radius = radius
	m.height = height
	m.radial_segments = radial
	m.rings = 1
	return m


## Maillages d'un niveau de détail : {nom : {"mesh": Mesh, "count": instances}}. Le vélo de base
## (cadre, fourche, cintre, selle, pédales, deux roues) est inclus ; V7 remplace ses pièces.
static func build(lod: int, d: Dictionary, looks := {}) -> Dictionary:
	lod = clampi(lod, 0, 2)
	var radial: int = [12, 7, 4][lod]
	var rings: int = [4, 1, 1][lod]
	var wheel: int = [36, 16, 6][lod]
	var parts := {
		"torso": {"mesh": _limb(float(d["r_torso"]), float(d["torso"]), radial + (1 if lod == 1 else 0), rings + (1 if lod == 1 else 0), lod), "count": 1},
		"thigh": {"mesh": _limb(float(d["r_thigh"]), float(d["thigh"]), radial, rings, lod), "count": 2},
		"shin": {"mesh": _limb(float(d["r_shin"]), float(d["shin"]), radial, rings, lod), "count": 2},
		"upper_arm": {"mesh": _limb(float(d["r_arm"]), float(d["upper_arm"]), maxi(radial - 2, 4), maxi(rings - 1, 1), lod), "count": 2},
		"forearm": {"mesh": _limb(float(d["r_forearm"]), float(d["forearm"]), maxi(radial - 2, 4), maxi(rings - 1, 1), lod), "count": 2},
		"head": {"mesh": _sphere(float(d["r_head"]), [20, 10, 6][lod], [10, 5, 2][lod]), "count": 1},
		"shoe": {"mesh": _box(Vector3(0.09, 0.07, 0.26)), "count": 2},
		"frame": {"mesh": _box(Vector3(0.05, 1.0, 0.05)), "count": 3},
		"tyre": {"mesh": _cylinder(WHEEL_R, 0.05, wheel), "count": 2},
	}
	if lod <= 1:
		parts["saddle"] = {"mesh": _box(Vector3(0.12, 0.05, 0.26)), "count": 1}
		parts["bar"] = {"mesh": _box(Vector3(0.42, 0.03, 0.05)), "count": 1}
		parts["helmet"] = {"mesh": _sphere(float(d["r_head"]) * 1.12, [20, 10][lod], [8, 4][lod], 0.8), "count": 1}
		parts["hair"] = {"mesh": _sphere(float(d["r_head"]) * 1.06, [14, 8][lod], [6, 3][lod]), "count": 1}
		parts["pelvis"] = {"mesh": _box(Vector3(0.28 * float(d["bs"]), 0.16, 0.2)), "count": 1}
	if lod == 0:
		parts["crank"] = {"mesh": _box(Vector3(0.025, CRANK_R, 0.025)), "count": 2}
	if lod <= 1:   # niveaux détaillés : cadre, roues, casque, chaussettes et lunettes de l'équipement (lot V7)
		for k in ["frame", "tyre", "helmet"]:
			parts.erase(k)
		parts.merge(EquipmentMeshes.build(lod, looks, d), true)
	return parts


## Segment d'un membre ou du tronc : capsule, ou parallélépipède au niveau le plus léger (bots).
static func _limb(radius: float, length: float, radial: int, rings: int, lod: int) -> Mesh:
	if lod >= 2:
		return _box(Vector3(radius * 2.0, length + radius, radius * 2.0))
	return _capsule(radius, length, radial, rings)


static func triangles_of(mesh: Mesh) -> int:
	var total := 0
	for i in range(mesh.get_surface_count()):
		var arrays := mesh.surface_get_arrays(i)
		var idx = arrays[Mesh.ARRAY_INDEX]
		total += (idx.size() if idx != null else arrays[Mesh.ARRAY_VERTEX].size()) / 3
	return total


## Triangles de tout l'avatar à ce niveau de détail (chaque instance compte).
static func triangle_count(lod: int, d: Dictionary) -> int:
	var total := 0
	var parts := build(lod, d)
	for name in parts:
		total += triangles_of(parts[name]["mesh"]) * int(parts[name]["count"])
	return total
