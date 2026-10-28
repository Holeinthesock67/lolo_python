extends RefCounted

## Circulation décorative sur la route du parcours (Lot P13), sans aucun nœud ni effet sur la physique.
## Pas de class_name : charger par preload("res://scripts/traffic_model.gd").
##
## Le parcours est découpé en cases de SLOT_M ; chaque case tire, d'après la graine et son indice,
## s'il porte un véhicule (probabilité BASE_RATE, plus VILLAGE_RATE à moins de VILLAGE_NEAR_M d'un point
## `village`), sa sorte, sa couleur, sa vitesse et son sens :
## - en face (`dir = -1`) : il apparaît de SPAWN_AHEAD_M.x à SPAWN_AHEAD_M.y devant le cycliste quand
##   celui-ci atteint la case, et roule vers lui sur la voie de gauche ;
## - dépassement (`dir = +1`) : il apparaît SPAWN_BEHIND_M derrière le cycliste et le double à
##   PASS_SPEED_KMH (ou 10 km/h de plus que lui), écart latéral d'au moins LATERAL_CLEARANCE_M entre sa
##   carrosserie et le cycliste ; s'il peut croiser un véhicule venant en face avant d'avoir fini, il
##   attend FOLLOW_GAP_M derrière, à la vitesse du cycliste, sur la voie de droite. Pas de nouveau
##   véhicule en face pendant un dépassement.
## Aucune case au-dessus de `terrain.snow_line_m` du thème ni sur une pente de plus de MAX_GRADE_PCT.
## Au plus `budget` véhicules à la fois (`living(preset).vehicles`) ; supprimés à plus de
## REMOVE_BEHIND_M derrière le cycliste ou REMOVE_AHEAD_M devant. Un véhicule en face qui en rattrape
## un autre se cale à sa vitesse. En pause, tout est figé.
## Le cycliste roule sur l'axe ; `lateral` est l'écart à l'axe, positif à droite du sens du parcours.
##
## Lot P25 : sept sortes (KINDS de vehicle_mesh.gd), tirées par case dans KIND_SHARES ; le bus seulement
## près d'un village et le tracteur seulement loin des villages (sinon une voiture), même densité qu'en P13.
## Un véhicule trop large pour doubler sur une route de `road_width_m` (`can_pass`) suit le cycliste à
## FOLLOW_GAP_M ; la largeur de la route étant la même sur tout le parcours, il tourne (disparaît, derrière
## le cycliste, hors du champ de la caméra) quand le cycliste a parcouru REMOVE_AHEAD_M depuis qu'il le suit.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")

const SLOT_M := 250.0
const BASE_RATE := 0.03
const VILLAGE_RATE := 0.25
const VILLAGE_NEAR_M := 1000.0
const OVERTAKE_SHARE := 0.4
## Parts des sortes (lot P25) ; `bus` loin d'un village et `tractor` près d'un village deviennent une voiture.
const KIND_SHARES := [["car_a", 0.275], ["car_b", 0.275], ["van", 0.15], ["truck", 0.08], ["moto", 0.07],
	["tractor", 0.10], ["bus", 0.05]]
## Vitesses de croisière (km/h) de chaque sorte.
const SPEED_KMH := {
	"car_a": Vector2(50.0, 70.0), "car_b": Vector2(50.0, 70.0), "van": Vector2(50.0, 70.0),
	"truck": Vector2(45.0, 65.0), "bus": Vector2(45.0, 65.0), "moto": Vector2(60.0, 85.0),
	"tractor": Vector2(20.0, 30.0),
}
const SPAWN_AHEAD_M := Vector2(600.0, 1200.0)
const SPAWN_BEHIND_M := 250.0
const REMOVE_BEHIND_M := 300.0
const REMOVE_AHEAD_M := 1300.0
const PASS_SPEED_KMH := 30.0
const PASS_MARGIN_KMH := 10.0
const PASS_ZONE_M := Vector2(-60.0, 30.0)   # de 60 m derrière à 30 m devant le cycliste : voie de gauche
const FOLLOW_GAP_M := 25.0
const MIN_SPACING_M := 60.0
const MAX_GRADE_PCT := 8.0
const DEFAULT_SNOW_LINE_M := 2200.0
const RIDER_HALF_WIDTH_M := 0.3
const LATERAL_CLEARANCE_M := 1.5
const RIGHT_LANE_M := 1.5
const EDGE_M := 0.4                # marge à chaque bord de la route pour doubler (`can_pass`)
const KINDS := VehicleMesh.KINDS
const COLORS := 6

var route = null
var budget: int = 3
var seed: int = 0
var vehicles: Array = []           # {id, kind, color, s, dir, speed_mps, cruise_mps, lateral, wheel}
var spawned_total: int = 0
var overtakes_total: int = 0
var turned_total: int = 0          # véhicules trop larges qui ont tourné sans doubler
var road_width_m: float = 6.0
var _villages: Array = []          # Vector2 (x, z)
var _snow_line_m: float = DEFAULT_SNOW_LINE_M
var _next_slot: int = 0
var _last_rider_s: float = NAN


## `theme` fusionné (theme_loader.gd), `pois` les points d'intérêt (seuls les `village` comptent).
func configure(route_data, theme: Dictionary, pois: Array, vehicle_budget: int, rng_seed: int = 0,
		p_road_width_m: float = 6.0) -> void:
	route = route_data
	road_width_m = p_road_width_m
	budget = maxi(0, vehicle_budget)
	seed = rng_seed
	_villages.clear()
	for p in pois:
		if typeof(p) == TYPE_DICTIONARY and str(p.get("kind", "")) == "village":
			_villages.append(Vector2(float(p.get("x", 0.0)), float(p.get("z", 0.0))))
	var terrain = theme.get("terrain", {})
	_snow_line_m = DEFAULT_SNOW_LINE_M
	if typeof(terrain) == TYPE_DICTIONARY and (typeof(terrain.get("snow_line_m")) == TYPE_INT or typeof(terrain.get("snow_line_m")) == TYPE_FLOAT):
		_snow_line_m = float(terrain["snow_line_m"])
	reset()


func reset() -> void:
	vehicles.clear()
	spawned_total = 0
	overtakes_total = 0
	turned_total = 0
	_next_slot = 0
	_last_rider_s = NAN


func set_budget(vehicle_budget: int) -> void:
	budget = maxi(0, vehicle_budget)
	while vehicles.size() > budget:
		vehicles.pop_back()


static func _u(h: int) -> float:
	return float(h & 0xFFFFFF) / 16777216.0


## Lancer d'une case : {} si elle ne porte rien, sinon le véhicule tiré.
func slot_event(k: int) -> Dictionary:
	if route == null:
		return {}
	var s := (k + 0.5) * SLOT_M
	if s > route.length_m:
		return {}
	var smp: Dictionary = route.sample(s)
	if float(smp["alt_m"]) > _snow_line_m or absf(float(smp["grade_pct"])) > MAX_GRADE_PCT:
		return {}
	var rate := BASE_RATE
	var p2 := Vector2(float(smp["x"]), float(smp["z"]))
	var near_village := false
	for v in _villages:
		if p2.distance_to(v) <= VILLAGE_NEAR_M:
			rate += VILLAGE_RATE
			near_village = true
			break
	var h := VegetationPlacer.hash3(seed, k, 0x7AFF1C)
	if _u(h) >= rate:
		return {}
	var kind := pick_kind(_u(VegetationPlacer._mix(h + 1)), near_village, (h >> 7) & 1)
	var range_kmh: Vector2 = SPEED_KMH[kind]
	return {
		"slot": k,
		"kind": kind,
		"color": int(VegetationPlacer._mix(h + 2) % COLORS),
		"cruise_mps": lerpf(range_kmh.x, range_kmh.y, _u(VegetationPlacer._mix(h + 3))) / 3.6,
		"dir": 1 if _u(VegetationPlacer._mix(h + 4)) < OVERTAKE_SHARE else -1,
		"ahead_m": lerpf(SPAWN_AHEAD_M.x, SPAWN_AHEAD_M.y, _u(VegetationPlacer._mix(h + 5))),
	}


## Sorte tirée dans KIND_SHARES pour `u` de 0 à 1 ; `car_bit` choisit la voiture qui remplace un bus loin
## d'un village ou un tracteur près d'un village.
static func pick_kind(u: float, near_village: bool, car_bit: int) -> String:
	var kind: String = KIND_SHARES[KIND_SHARES.size() - 1][0]
	var acc := 0.0
	for e in KIND_SHARES:
		acc += float(e[1])
		if u < acc:
			kind = e[0]
			break
	if (kind == "bus" and not near_village) or (kind == "tractor" and near_village):
		kind = "car_a" if car_bit == 0 else "car_b"
	return kind


## Vrai si une sorte peut doubler le cycliste sur une route de `width_m` : sa largeur, l'écart latéral,
## le cycliste et une marge EDGE_M de chaque côté.
static func can_pass(kind: String, width_m: float) -> bool:
	return width_m >= 2.0 * float(KINDS[kind]["half_width"]) + LATERAL_CLEARANCE_M + 2.0 * RIDER_HALF_WIDTH_M + 2.0 * EDGE_M


static func lane_lateral(kind: String) -> float:
	return -(RIDER_HALF_WIDTH_M + LATERAL_CLEARANCE_M + float(KINDS[kind]["half_width"]))


func _segment_ok(s: float) -> bool:
	if route == null or s < 0.0 or s > route.length_m:
		return false
	var smp: Dictionary = route.sample(s)
	return float(smp["alt_m"]) <= _snow_line_m and absf(float(smp["grade_pct"])) <= MAX_GRADE_PCT


func _free_at(s: float, dir: int) -> bool:
	for v in vehicles:
		if int(v["dir"]) == dir and absf(float(v["s"]) - s) < MIN_SPACING_M:
			return false
	return true


func _overtaking() -> bool:
	for v in vehicles:
		if int(v["dir"]) == 1:
			return true
	return false


## Une image : `rider_s` position du cycliste (m), `rider_v` sa vitesse (m/s).
func update(rider_s: float, rider_v: float, dt_s: float, paused: bool = false) -> void:
	if route == null or paused:
		return
	if is_nan(_last_rider_s):
		_next_slot = maxi(0, int(floor(rider_s / SLOT_M)) + 1)
	_last_rider_s = rider_s
	# Nouvelles cases atteintes par le cycliste
	while (_next_slot) * SLOT_M <= rider_s:
		var ev := slot_event(_next_slot)
		_next_slot += 1
		if ev.is_empty() or vehicles.size() >= budget:
			continue
		if int(ev["dir"]) == -1:
			var s0 := rider_s + float(ev["ahead_m"])
			if _overtaking() or not _segment_ok(s0) or not _free_at(s0, -1):
				continue
			_spawn(ev, s0, -1)
		else:
			var s1 := rider_s - SPAWN_BEHIND_M
			if _overtaking() or not _segment_ok(maxf(s1, 0.0)) or float(ev["cruise_mps"]) <= rider_v:
				continue
			_spawn(ev, s1, 1)
	# Déplacement
	for v in vehicles:
		var rel := float(v["s"]) - rider_s
		if int(v["dir"]) == -1:
			# Un véhicule en face plus rapide reste derrière le précédent, à MIN_SPACING_M au moins
			var spd := float(v["cruise_mps"])
			for o in vehicles:
				if o != v and int(o["dir"]) == -1 and float(o["s"]) < float(v["s"]) \
						and float(v["s"]) - float(o["s"]) < MIN_SPACING_M + 20.0:
					spd = minf(spd, float(o["speed_mps"]))
			v["speed_mps"] = spd
			v["s"] = float(v["s"]) - spd * dt_s
			v["lateral"] = lane_lateral(v["kind"])
		else:
			_move_overtaker(v, rel, rider_v, dt_s)
		v["wheel"] = fposmod(float(v["wheel"]) + float(v["speed_mps"]) * dt_s / 0.33, TAU)
	# Suppressions
	var kept := []
	for v in vehicles:
		var rel2 := float(v["s"]) - rider_s
		if v.get("turned", false):
			turned_total += 1
		elif rel2 >= -REMOVE_BEHIND_M and rel2 <= REMOVE_AHEAD_M and float(v["s"]) >= 0.0 and float(v["s"]) <= route.length_m:
			kept.append(v)
	vehicles = kept


## Dépassement : voie de droite, puis voie de gauche dans PASS_ZONE_M (seulement si aucun véhicule en
## face ne peut arriver avant la fin du dépassement), retour à droite ensuite. Sans feu vert, il suit le
## cycliste à FOLLOW_GAP_M, sur la voie de droite.
func _move_overtaker(v: Dictionary, rel: float, rider_v: float, dt_s: float) -> void:
	var cruise := float(v["cruise_mps"])
	var pass_mps := minf(cruise, maxf(PASS_SPEED_KMH / 3.6, rider_v + PASS_MARGIN_KMH / 3.6))
	var left := lane_lateral(v["kind"])
	var committed: bool = v.get("committed", false)
	if not can_pass(v["kind"], road_width_m) and not committed:
		# Trop large pour doubler : suit le cycliste, puis tourne après REMOVE_AHEAD_M
		if rel >= -FOLLOW_GAP_M - 5.0:
			if not v.has("follow_from"):
				v["follow_from"] = float(v["s"])
			elif float(v["s"]) - float(v["follow_from"]) >= REMOVE_AHEAD_M:
				v["turned"] = true
	elif not committed and rel >= PASS_ZONE_M.x - 40.0 and rel < 0.0 and _clear_to_pass(v, rel, rider_v, pass_mps):
		committed = true
		v["committed"] = true
	var spd := cruise
	var target_lat := RIGHT_LANE_M
	if committed and rel < PASS_ZONE_M.y:
		spd = pass_mps
		target_lat = left if rel >= PASS_ZONE_M.x else RIGHT_LANE_M
		# Pas sur la voie de gauche à temps : il ne s'approche pas plus du cycliste
		if absf(float(v["lateral"]) - left) > 0.05 and rel > -FOLLOW_GAP_M:
			spd = minf(spd, rider_v)
	elif not committed:
		if rel >= PASS_ZONE_M.x - 40.0:
			spd = pass_mps
		if rel + (spd - rider_v) * dt_s >= -FOLLOW_GAP_M:
			spd = rider_v
	v["speed_mps"] = spd
	v["s"] = float(v["s"]) + spd * dt_s
	v["lateral"] = move_toward(float(v["lateral"]), target_lat, 1.5 * dt_s)
	if not v.get("passed", false) and rel > 0.0:
		v["passed"] = true
		overtakes_total += 1


## Vrai si aucun véhicule en face ne peut croiser le dépassant avant qu'il ait fini de doubler.
func _clear_to_pass(v: Dictionary, rel: float, rider_v: float, pass_mps: float) -> bool:
	var t_pass := (PASS_ZONE_M.y - rel) / maxf(pass_mps - rider_v, 0.5)
	for o in vehicles:
		if int(o["dir"]) != -1:
			continue
		var gap := float(o["s"]) - float(v["s"])
		if gap > 0.0 and gap < t_pass * (float(o["speed_mps"]) + pass_mps) + 100.0:
			return false
	return true


func _spawn(ev: Dictionary, s: float, dir: int) -> void:
	spawned_total += 1
	vehicles.append({
		"id": "v%d" % int(ev["slot"]),
		"kind": ev["kind"],
		"color": ev["color"],
		"s": s,
		"dir": dir,
		"cruise_mps": ev["cruise_mps"],
		"speed_mps": ev["cruise_mps"],
		"lateral": lane_lateral(ev["kind"]) if dir == -1 else RIGHT_LANE_M,
		"wheel": 0.0,
		"passed": false,
	})


## Position et cap (rad autour de y) d'un véhicule dans le monde.
func world_transform(v: Dictionary) -> Transform3D:
	var s := clampf(float(v["s"]), 0.0, route.length_m)
	var smp: Dictionary = route.sample(s)
	var h := deg_to_rad(float(smp["heading_deg"]))
	var fwd := Vector3(sin(h), 0.0, -cos(h))
	var right := Vector3(cos(h), 0.0, sin(h))
	var pos := Vector3(float(smp["x"]), float(smp["y"]), float(smp["z"])) + right * float(v["lateral"])
	var facing := fwd * float(v["dir"])
	return Transform3D(Basis(Vector3.UP, atan2(-facing.x, -facing.z)), pos)
