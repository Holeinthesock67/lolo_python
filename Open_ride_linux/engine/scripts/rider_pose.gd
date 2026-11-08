extends RefCounted

## Pose d'un cycliste posé sur la route (lot CY1) : position, cap et roulis du vélo du joueur et des bots.
##
## Avant ce lot, le vélo prenait le cap de la colonne `heading_deg` (moyenne sur environ 30 m, format §4.5) alors
## que sa position suivait la courbe de Catmull-Rom tracée par les points tous les 10 m : dans un virage serré,
## le vélo tournait 20 m avant le virage et roulait en crabe (jusqu'à 29° entre le cap affiché et la direction
## suivie sur un carré à angles droits), sans jamais se pencher.
##
## - Trajectoire lissée : moyenne des points de la voie (`sample_point + bank_right × lateral`, comme
##   road_builder.gd) sur ± SMOOTH_HALF_M autour de `s`, un point tous les STEP_M. Le cycliste coupe un peu le
##   virage (au plus 0,7 m sur un angle droit de 3 points, rien en ligne droite) et ne fait plus d'écart.
## - Cap : direction de cette trajectoire lissée (corde sur ± STEP_M) : le vélo regarde où il va.
## - Roulis : inclinaison d'équilibre atan(v² κ / g), κ courbure de la trajectoire lissée (écart de cap sur
##   ± CURVE_HALF_M), penché vers l'intérieur. Sur une piste relevée (lot VD4), l'écart au relèvement est borné à
##   ± LEAN_MAX_DEG : à la vitesse de course dans un virage relevé, le vélo reste à peu près perpendiculaire à la
##   piste ; arrêté ou en ligne droite, il est droit.
## - Sans état : la pose ne dépend que de la route, de `s`, de l'écart à l'axe et de la vitesse. Continue quand `s`
##   avance (fenêtre glissante), donc sans saut d'une image à l'autre, et la même pour le joueur et les bots.
## Convention de roulis : celle de `rotation.z` de l'avatar (positif : la droite monte, penché à gauche).
## `route` : route_data.gd (`sample_xyzh` sinon `sample`, `wrap_s`, `is_loop`, et `bank_at` / `bank_right` s'ils existent).
## Pas de class_name : charger par preload("res://scripts/rider_pose.gd").

const STEP_M := 2.0
const SMOOTH_HALF_M := 4.0
const CURVE_HALF_M := 2.0
const LEAN_MAX_DEG := 30.0
const GRAVITY := 9.81

const _W := int(SMOOTH_HALF_M / STEP_M)
const _C := int(CURVE_HALF_M / STEP_M)
const _HALF := _W + _C + 1


## Point de la voie à `lateral` mètres de l'axe en `s` (même coupe que road_builder.gd et main.gd). Parcours
## ouvert : avant le départ ou après l'arrivée, prolongé tout droit dans l'axe du bout (grille de départ des bots,
## lot AS2), donc la moyenne glissante ne se tasse pas aux extrémités.
static func lane_point(route, s: float, lateral: float) -> Vector3:
	var p: float = route.wrap_s(s)
	var smp: Vector4
	if route.has_method("sample_xyzh"):
		smp = route.sample_xyzh(p)
	else:   # routes simplifiées des tests : sample() seul
		var d: Dictionary = route.sample(p)
		smp = Vector4(d["x"], d["y"], d["z"], deg_to_rad(float(d["heading_deg"])))
	var h := smp.w
	var right := Vector3(cos(h), 0.0, sin(h))
	if route.has_method("bank_right"):
		right = route.bank_right(p, h)
	var out := Vector3(smp.x, smp.y, smp.z) + right * lateral
	if s != p and not (route.has_method("is_loop") and route.is_loop()):
		out += Vector3(sin(h), 0.0, -cos(h)) * (s - p)
	return out


## Cap (radians, sens horaire depuis le nord, comme `heading_deg`) de la corde de `a` à `b` ; `fallback` si
## la corde est nulle (bout d'un parcours ouvert).
static func chord_heading(a: Vector3, b: Vector3, fallback: float) -> float:
	var dx := b.x - a.x
	var dz := b.z - a.z
	if dx * dx + dz * dz < 1e-8:
		return fallback
	return atan2(dx, -dz)


## Roulis d'équilibre pour la vitesse `v` (m/s) et la courbure `kappa` (1/m, > 0 en virage à droite), borné à
## ± LEAN_MAX_DEG du relèvement `bank_rad` de la piste.
static func lean_roll(v: float, kappa: float, bank_rad: float = 0.0) -> float:
	var phys := -atan(v * v * kappa / GRAVITY)
	var lim := deg_to_rad(LEAN_MAX_DEG)
	return bank_rad + clampf(phys - bank_rad, -lim, lim)


static func _wrap_angle(a: float) -> float:
	return fposmod(a + PI, TAU) - PI


## Pose en `s` : {pos: Vector3, yaw: float (cap en radians, sens horaire), roll: float (rotation.z),
## kappa: float}. À poser comme `rotation = Vector3(tangage, -yaw, roll)`.
static func pose(route, s: float, lateral: float, v: float) -> Dictionary:
	var q: Array[Vector3] = []
	q.resize(2 * _HALF + 1)
	for k in range(-_HALF, _HALF + 1):
		q[k + _HALF] = lane_point(route, s + k * STEP_M, lateral)
	# Moyennes glissantes sur 2W+1 points, pour les décalages -(C+1) … C+1.
	var n := 2 * _W + 1
	var sm: Array[Vector3] = []
	sm.resize(2 * (_C + 1) + 1)
	var acc := Vector3.ZERO
	for i in n:
		acc += q[i]
	sm[0] = acc / n
	for j in range(1, sm.size()):
		acc += q[j + n - 1] - q[j - 1]
		sm[j] = acc / n
	var mid := _C + 1
	var p: float = route.wrap_s(s)
	var fallback := deg_to_rad(float(route.sample(p)["heading_deg"]))
	var yaw := chord_heading(sm[mid - 1], sm[mid + 1], fallback)
	var yaw_a := chord_heading(sm[mid - _C - 1], sm[mid - _C + 1], yaw)
	var yaw_b := chord_heading(sm[mid + _C - 1], sm[mid + _C + 1], yaw)
	var kappa := _wrap_angle(yaw_b - yaw_a) / (2.0 * _C * STEP_M)
	var bank := deg_to_rad(float(route.bank_at(p))) if route.has_method("bank_at") else 0.0
	return {"pos": sm[mid], "yaw": yaw, "roll": lean_roll(maxf(v, 0.0), kappa, bank), "kappa": kappa}
