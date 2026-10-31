extends RefCounted

## Circulation décorative sur la route du parcours (Lot P13), sans aucun nœud ni effet sur la physique.
## Lot P25 : sept sortes (berline, citadine, utilitaire, camion, autocar, moto, tracteur) tirées d'après leur
## part (KINDS), huit couleurs ; `headlights` dit quand les phares s'allument.
## Pas de class_name : charger par preload("res://scripts/traffic_model.gd").
##
## Le parcours est découpé en cases de SLOT_M ; chaque case tire, d'après la graine et son indice,
## s'il porte un véhicule (probabilité BASE_RATE, plus VILLAGE_RATE à moins de VILLAGE_NEAR_M d'un point
## `village`), sa sorte, sa couleur, sa vitesse (plage de sa sorte) et son sens :
## - en face (`dir = -1`) : il apparaît de SPAWN_AHEAD_M.x à SPAWN_AHEAD_M.y devant le cycliste quand
##   celui-ci atteint la case, et roule vers lui sur la voie d'en face, sa droite (`oncoming_lateral`) ;
## - dépassement (`dir = +1`) : il apparaît SPAWN_BEHIND_M derrière le cycliste et le double à
##   PASS_SPEED_KMH (ou 10 km/h de plus que lui), écart latéral d'au moins LATERAL_CLEARANCE_M entre sa
##   carrosserie et le cycliste ; s'il peut croiser un véhicule venant en face avant d'avoir fini, il
##   attend FOLLOW_GAP_M derrière, à la vitesse du cycliste, sur la voie de droite. Pas de nouveau
##   véhicule en face pendant un dépassement.
## Aucune case au-dessus de `terrain.snow_line_m` du thème ni sur une pente de plus de MAX_GRADE_PCT.
## Au plus `budget` véhicules à la fois (`living(preset).vehicles`) ; supprimés à plus de
## REMOVE_BEHIND_M derrière le cycliste ou REMOVE_AHEAD_M devant. Un véhicule en face qui en rattrape
## un autre se cale à sa vitesse. En pause, tout est figé.
## Le cycliste roule dans la voie de droite, à RoadBuilder.RIDER_LATERAL_M de l'axe (lot P32) ; `lateral` est
## l'écart à l'axe, positif à droite du sens du parcours ; les écarts au cycliste se comptent depuis sa place.
## Lot P32, aucune collision : les cyclistes du décor et les bots (`others` d'update) sont évités. Un véhicule
## s'écarte (LATERAL_MPS) pour laisser LATERAL_CLEARANCE_M à ceux qu'il double, CYCLIST_GAP_M à ceux qu'il
## croise, dès CYCLIST_LOOK_M avant eux ; il ne commence pas un dépassement face à un cycliste qui arrive.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

const SLOT_M := 250.0
const BASE_RATE := 0.03
const VILLAGE_RATE := 0.25
const VILLAGE_NEAR_M := 1000.0
const OVERTAKE_SHARE := 0.4
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
const RIGHT_LANE_M := RoadBuilder.LANE_CENTER_M
const LATERAL_MPS := 1.5
const CYCLIST_GAP_M := 0.5
const CYCLIST_LOOK_M := 40.0
const CYCLIST_HALF_LENGTH_M := 0.9
const LANE_FREE_M := 150.0
## Au-delà de l'accotement, les roues d'un véhicule mordent l'herbe de VERGE_M au plus.
const VERGE_M := 0.25
const HOLD_GAP_M := 5.0
## Sortes (Lot P25) : demi-largeur et longueur hors tout de vehicle_mesh.gd (rétroviseurs compris), part des
## tirages et plage de vitesse.
const KINDS := {
	"car_a": {"half_width": 1.03, "length": 4.6, "share": 0.3, "kmh": Vector2(50.0, 70.0)},
	"car_b": {"half_width": 1.0, "length": 4.1, "share": 0.25, "kmh": Vector2(50.0, 70.0)},
	"van": {"half_width": 1.12, "length": 5.2, "share": 0.13, "kmh": Vector2(50.0, 65.0)},
	"truck": {"half_width": 1.42, "length": 9.2, "share": 0.06, "kmh": Vector2(45.0, 60.0)},
	"bus": {"half_width": 1.44, "length": 12.2, "share": 0.04, "kmh": Vector2(45.0, 60.0)},
	"moto": {"half_width": 0.41, "length": 2.1, "share": 0.07, "kmh": Vector2(55.0, 80.0)},
	"tractor": {"half_width": 1.07, "length": 3.8, "share": 0.15, "kmh": Vector2(20.0, 30.0)},
}
const COLORS := 8
const HEADLIGHT_FOG := 0.3
const HEADLIGHT_RAIN := 0.2
const HEADLIGHT_SUN_DEG := 8.0

var route = null
var budget: int = 3
var seed: int = 0
var vehicles: Array = []           # {id, kind, color, s, dir, speed_mps, cruise_mps, lateral, wheel}
var spawned_total: int = 0
var overtakes_total: int = 0
var _villages: Array = []          # Vector2 (x, z)
var _snow_line_m: float = DEFAULT_SNOW_LINE_M
var _next_slot: int = 0
var _last_rider_s: float = NAN
var _others: Array = []            # cyclistes du décor et bots de la dernière image : {s, lateral, dir}


## `theme` fusionné (theme_loader.gd), `pois` les points d'intérêt (seuls les `village` comptent).
func configure(route_data, theme: Dictionary, pois: Array, vehicle_budget: int, rng_seed: int = 0) -> void:
	route = route_data
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
	for v in _villages:
		if p2.distance_to(v) <= VILLAGE_NEAR_M:
			rate += VILLAGE_RATE
			break
	var h := VegetationPlacer.hash3(seed, k, 0x7AFF1C)
	if _u(h) >= rate:
		return {}
	var kind := pick_kind(_u(VegetationPlacer._mix(h + 1)))
	var range_kmh: Vector2 = KINDS[kind]["kmh"]
	return {
		"slot": k,
		"kind": kind,
		"color": int(VegetationPlacer._mix(h + 2) % COLORS),
		"cruise_mps": lerpf(range_kmh.x, range_kmh.y, _u(VegetationPlacer._mix(h + 3))) / 3.6,
		"dir": 1 if _u(VegetationPlacer._mix(h + 4)) < OVERTAKE_SHARE else -1,
		"ahead_m": lerpf(SPAWN_AHEAD_M.x, SPAWN_AHEAD_M.y, _u(VegetationPlacer._mix(h + 5))),
	}


## Sorte tirée d'après `u` (0 à 1) et les parts de KINDS, dans l'ordre de la table.
static func pick_kind(u: float) -> String:
	var acc := 0.0
	for k in KINDS:
		acc += float(KINDS[k]["share"])
		if u < acc:
			return k
	return KINDS.keys()[KINDS.size() - 1]


## Phares allumés (Lot P25) : brume (`fog_boost`) ou pluie de weather_model.gd, ou soleil bas du thème.
static func headlights(weather_eval: Dictionary, sun_elevation_deg: float) -> bool:
	return float(weather_eval.get("fog_boost", 0.0)) >= HEADLIGHT_FOG or float(weather_eval.get("rain", 0.0)) >= HEADLIGHT_RAIN \
		or sun_elevation_deg <= HEADLIGHT_SUN_DEG


## Écart du dépassant à la hauteur du cycliste : LATERAL_CLEARANCE_M entre sa carrosserie et le cycliste.
static func lane_lateral(kind: String) -> float:
	return RoadBuilder.RIDER_LATERAL_M - (RIDER_HALF_WIDTH_M + LATERAL_CLEARANCE_M + float(KINDS[kind]["half_width"]))


## Écart d'un véhicule en face : milieu de sa voie (sa droite), plus loin si le cycliste le demande.
static func oncoming_lateral(kind: String) -> float:
	return minf(-RIGHT_LANE_M, lane_lateral(kind))


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


## Une image : `rider_s` position du cycliste (m), `rider_v` sa vitesse (m/s) ; `others` : cyclistes du décor et
## bots à éviter, {s, lateral, dir}.
func update(rider_s: float, rider_v: float, dt_s: float, paused: bool = false, others: Array = []) -> void:
	if route == null or paused:
		return
	_others = others
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
			if _overtaking() or not _segment_ok(s0) or not _free_at(s0, -1) or not _others_clear_at(s0):
				continue
			_spawn(ev, s0, -1)
		else:
			var s1 := rider_s - SPAWN_BEHIND_M
			if _overtaking() or not _segment_ok(maxf(s1, 0.0)) or float(ev["cruise_mps"]) <= rider_v or not _others_clear_at(s1):
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
			v["lateral"] = move_toward(float(v["lateral"]), _clear_of_others(v, oncoming_lateral(v["kind"])), LATERAL_MPS * dt_s)
		else:
			_move_overtaker(v, rel, rider_v, dt_s)
		_hold(v)
		v["wheel"] = fposmod(float(v["wheel"]) + float(v["speed_mps"]) * dt_s / 0.33, TAU)
	# Suppressions
	var kept := []
	for v in vehicles:
		var rel2 := float(v["s"]) - rider_s
		if rel2 >= -REMOVE_BEHIND_M and rel2 <= REMOVE_AHEAD_M and float(v["s"]) >= 0.0 and float(v["s"]) <= route.length_m:
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
	if not committed and rel >= PASS_ZONE_M.x - 40.0 and rel < 0.0 and _clear_to_pass(v, rel, rider_v, pass_mps):
		committed = true
		v["committed"] = true
	var spd := cruise
	var target_lat := RIGHT_LANE_M
	var goal := NAN
	if committed and rel < PASS_ZONE_M.y:
		spd = pass_mps
		target_lat = left if rel >= PASS_ZONE_M.x else RIGHT_LANE_M
		# Pas sur la voie de gauche à temps (ou plus à gauche, pour laisser la place aux bots et aux cyclistes du
		# décor) : il ne s'approche pas plus du cycliste
		goal = _clear_of_others(v, left)
		if absf(float(v["lateral"]) - minf(left, goal)) > 0.05 and rel > -FOLLOW_GAP_M:
			spd = minf(spd, rider_v)
	elif not committed:
		if rel >= PASS_ZONE_M.x - 40.0:
			spd = pass_mps
		if rel + (spd - rider_v) * dt_s >= -FOLLOW_GAP_M:
			spd = rider_v
	v["speed_mps"] = spd
	v["s"] = float(v["s"]) + spd * dt_s
	v["lateral"] = move_toward(float(v["lateral"]), _clear_of_others(v, target_lat), LATERAL_MPS * dt_s)
	if not v.get("passed", false) and rel > 0.0:
		v["passed"] = true
		overtakes_total += 1


## Vrai si aucun cycliste du décor ni aucun bot n'est à moins de MIN_SPACING_M de `s` (apparition d'un véhicule).
func _others_clear_at(s: float) -> bool:
	for o in _others:
		if absf(float(o["s"]) - s) < MIN_SPACING_M:
			return false
	return true


## Écart à l'axe visé `target`, décalé pour ne toucher aucun cycliste du décor ni aucun bot sur sa longueur et
## CYCLIST_LOOK_M devant lui. Ceux du même sens sont doublés à LATERAL_CLEARANCE_M de carrosserie, seulement si
## la voie d'en face est libre (`_lane_free`) et une fois écarté ; sinon le véhicule attend derrière (`hold_s`,
## appliqué par `_hold`). Ceux d'en face sont croisés à CYCLIST_GAP_M. Le véhicule reste sur la chaussée et ses
## accotements (RoadBuilder.ROAD_WIDTH_M, SHOULDER_WIDTH_M, VERGE_M) : sans la place, il attend (les bots serrent
## à droite à l'approche d'un véhicule, bots_view_model.gd).
func _clear_of_others(v: Dictionary, target: float) -> float:
	var k: Dictionary = KINDS[v["kind"]]
	var hw := float(k["half_width"])
	var half_len := float(k["length"]) * 0.5 + CYCLIST_HALF_LENGTH_M
	var dir := int(v["dir"])
	var out := target
	v.erase("hold_s")
	for same in [true, false]:
		for o in _others:
			if (int(o["dir"]) == dir) != same:
				continue
			var ahead := (float(o["s"]) - float(v["s"])) * dir
			if ahead < -half_len or ahead > half_len + CYCLIST_LOOK_M:
				continue
			var room := RIDER_HALF_WIDTH_M + (LATERAL_CLEARANCE_M if same else CYCLIST_GAP_M) + hw
			var lat := float(o["lateral"])
			# Pas encore écarté : il attend derrière d'avoir pris sa place pour doubler
			if same and ahead > half_len and absf(float(v["lateral"]) - lat) < room - 0.05:
				_hold_behind(v, float(o["s"]))
			if absf(out - lat) >= room:
				continue
			if same and ahead > half_len and not _lane_free(v):
				_hold_behind(v, float(o["s"]))
				continue
			out = lat - room if out < lat else lat + room
	# Jamais hors de la route : sans la place de passer sur la chaussée, il attend derrière (ou, en face, devant) le
	# premier qu'il toucherait ; seul un dépassement déjà engagé à côté d'un cycliste qui s'écarte mord l'herbe
	var edge := RoadBuilder.ROAD_WIDTH_M * 0.5 + RoadBuilder.SHOULDER_WIDTH_M + VERGE_M - hw
	if absf(out) > edge:
		var clamped := clampf(out, -edge, edge)
		var blocked: Array = []
		for o in _others:
			var ahead := (float(o["s"]) - float(v["s"])) * dir
			var gap_m := LATERAL_CLEARANCE_M if int(o["dir"]) == dir else CYCLIST_GAP_M
			if ahead < -half_len or ahead > half_len + CYCLIST_LOOK_M \
					or absf(clamped - float(o["lateral"])) >= RIDER_HALF_WIDTH_M + gap_m + hw:
				continue
			if ahead <= half_len and dir == 1:
				return out
			blocked.append(float(o["s"]))
		for s_o in blocked:
			_hold_behind(v, s_o)
		out = clamped
	return out


## Garde dans `hold_s` le plus proche devant de ceux derrière qui le véhicule `v` doit attendre.
func _hold_behind(v: Dictionary, s: float) -> void:
	if not v.has("hold_s") or (s - float(v["hold_s"])) * int(v["dir"]) < 0.0:
		v["hold_s"] = s


## Vrai si rien ne vient en face du véhicule `v` à moins de LANE_FREE_M : ni véhicule, ni cycliste du décor, ni
## bot, ni (pour un véhicule en face) le cycliste.
func _lane_free(v: Dictionary) -> bool:
	var dir := int(v["dir"])
	var s := float(v["s"])
	for o in _others:
		var ahead := (float(o["s"]) - s) * dir
		if int(o["dir"]) != dir and ahead > -5.0 and ahead < LANE_FREE_M:
			return false
	for o in vehicles:
		var ahead2 := (float(o["s"]) - s) * dir
		if int(o["dir"]) != dir and ahead2 > -5.0 and ahead2 < LANE_FREE_M:
			return false
	if dir == -1:
		var ahead3 := s - _last_rider_s
		if ahead3 > -5.0 and ahead3 < LANE_FREE_M:
			return false
	return true


## Véhicule qui attend derrière un cycliste du décor ou un bot (`hold_s`) : il ne s'en approche pas à moins de
## HOLD_GAP_M de sa carrosserie, à la vitesse de celui-ci.
func _hold(v: Dictionary) -> void:
	if not v.has("hold_s"):
		return
	var dir := int(v["dir"])
	var limit := float(v["hold_s"]) - dir * (float(KINDS[v["kind"]]["length"]) * 0.5 + CYCLIST_HALF_LENGTH_M + HOLD_GAP_M)
	if (float(v["s"]) - limit) * dir > 0.0:
		v["s"] = limit


## Vrai si aucun véhicule ni cycliste du décor en face ne peut croiser le dépassant avant qu'il ait fini de doubler.
func _clear_to_pass(v: Dictionary, rel: float, rider_v: float, pass_mps: float) -> bool:
	var t_pass := (PASS_ZONE_M.y - rel) / maxf(pass_mps - rider_v, 0.5)
	for o in _others:
		var gap_o := float(o["s"]) - float(v["s"])
		if int(o["dir"]) == -1 and gap_o > 0.0 and gap_o < t_pass * (10.0 + pass_mps) + 100.0:
			return false
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
		"lateral": oncoming_lateral(ev["kind"]) if dir == -1 else RIGHT_LANE_M,
		"wheel": 0.0,
		"passed": false,
	})


## Véhicule posé par un test (lot P32 : captures et contrôle des voies) : sorte `kind`, sens `dir`, à `rel_m` du
## cycliste (négatif : derrière), à `kmh` ; dans le même sens et dans PASS_ZONE_M, il est posé en train de
## doubler (voie de gauche) si la voie d'en face le permet (`_clear_to_pass`), sinon FOLLOW_GAP_M derrière le
## cycliste, où il attend. Il suit ensuite les mêmes règles que les autres.
func place_for_test(rider_s: float, rider_v: float, kind: String, dir: int, rel_m: float, kmh: float) -> void:
	if route == null or not KINDS.has(kind):
		return
	var d := 1 if dir >= 0 else -1
	_spawn({"slot": 1000000 + spawned_total, "kind": kind, "color": spawned_total % COLORS, "cruise_mps": kmh / 3.6},
		rider_s + rel_m, d)
	if d == 1 and rel_m >= PASS_ZONE_M.x and rel_m < PASS_ZONE_M.y:
		var v: Dictionary = vehicles[vehicles.size() - 1]
		var pass_mps := minf(kmh / 3.6, maxf(PASS_SPEED_KMH / 3.6, rider_v + PASS_MARGIN_KMH / 3.6))
		if _clear_to_pass(v, rel_m, rider_v, pass_mps):
			v["committed"] = true
			v["lateral"] = lane_lateral(kind)
		else:
			# Attend derrière, à FOLLOW_GAP_M ou plus loin, derrière le dernier cycliste du décor ou bot qui y roule
			var room := float(KINDS[kind]["length"]) * 0.5 + CYCLIST_HALF_LENGTH_M + HOLD_GAP_M
			var hold_s := rider_s - FOLLOW_GAP_M
			for _i in range(2 * _others.size() + 1):
				var free := true
				for o in _others:
					if absf(float(o["s"]) - hold_s) < room:
						hold_s = float(o["s"]) - room
						free = false
				if free:
					break
			v["s"] = hold_s


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
