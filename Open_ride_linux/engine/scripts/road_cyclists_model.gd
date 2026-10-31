extends RefCounted

## Cyclistes du décor sur la route du parcours (Lot P28, demande du propriétaire du 28 octobre : « plutôt
## plus de vélos »), sans aucun nœud ni effet sur la physique : ce ne sont pas des bots (ni aspiration, ni
## écart au HUD, ni classement). Pas de class_name : charger par preload("res://scripts/road_cyclists_model.gd").
##
## Le parcours est découpé en cases de SLOT_M ; quand le cycliste atteint une case, elle tire d'après la graine
## et son indice un groupe avec la probabilité RATE_FLAT, RATE_CLIMB (dans une montée de `climbs`) ou
## RATE_VILLAGE (à moins de VILLAGE_NEAR_M d'un point `village`). Taille : 1, 2 ou 3 à 6 (SIZE_SHARES), en
## file ou à deux de front (ABREAST_M d'écart, FILE_GAP_M l'un derrière l'autre). Trois cas (CASE_SHARES) :
## - `oncoming` : en face, sur le bord gauche, apparaît de SPAWN_AHEAD_M devant ; pas de groupe en face
##   tant qu'un véhicule de traffic_model.gd est sur la route ;
## - `ahead` : devant et plus lent, sur le bord droit, apparaît de SPAWN_SLOW_M devant ; le cycliste le double ;
##   il reste à MIN_GAP_M au moins de sa droite (il se serre sur le bord) ;
## - `overtake` : arrive SPAWN_BEHIND_M derrière, OVERTAKE_KMH plus vite que le cycliste (au moins la vitesse
##   d'OVERTAKE_MIN_KMH sur le plat), passe en file à MIN_GAP_M au moins sur sa gauche dès PASS_START_M
##   derrière, se rabat à MERGE_AHEAD_M devant ; s'il ne gagne plus de terrain, il disparaît après GIVE_UP_S.
## Vitesse : vitesse de plat tirée du cas, convertie en puissance constante (frottement, pente, air), puis
## vitesse sur la pente sous le groupe (dans son sens), recalculée toutes les SPEED_PERIOD_S, au plus MAX_KMH.
## Écart latéral : centre à centre, au moins MIN_GAP_M + 2 × RIDER_HALF_WIDTH_M du cycliste (dans la voie de
## droite, à RIDER_LATERAL_M de l'axe, lot P32) et, à moins de BOT_LOOK_M d'un bot (à sa place en travers,
## BOT_LATERAL_M d'habitude, côte à côte en peloton : bots_view_model.gd), de ce bot : le groupe `ahead` se met en file sur l'accotement. Chacun roule à droite dans
## son sens : `ahead` sur le bord droit, `oncoming` sur le bord gauche (sa droite), `overtake` passe à gauche
## du cycliste puis se rabat sur le bord droit. Au plus `budget` cyclistes à la fois (`living(preset).cyclists`), supprimés à plus
## de REMOVE_BEHIND_M derrière ou REMOVE_AHEAD_M devant. En pause, tout est figé.
## Un groupe qui double dit « Salut ! » une fois sur SALUT_EVERY en passant (`last_event`, voix des passants).
## `lateral` : écart à l'axe, positif à droite du sens du parcours.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

const SLOT_M := 250.0
## Distance parcourue par tour de pédalier : braquet de 50 × 17, roue de 2,1 m (cyclistes du décor et bots).
const DEVELOPMENT_M := 2.1 * 50.0 / 17.0
const RATE_FLAT := 0.25
const RATE_CLIMB := 0.75
const RATE_VILLAGE := 0.4
const VILLAGE_NEAR_M := 1000.0
const SIZE_SHARES := [0.55, 0.25, 0.20]   # 1, 2, de 3 à 6
const CASE_SHARES := [["oncoming", 0.40], ["ahead", 0.35], ["overtake", 0.25]]
const ONCOMING_KMH := Vector2(22.0, 35.0)
const AHEAD_KMH := Vector2(18.0, 28.0)
const OVERTAKE_KMH := Vector2(4.0, 8.0)
const OVERTAKE_MIN_KMH := 25.0
const MAX_KMH := 70.0
const MIN_KMH := 9.0
const SPAWN_AHEAD_M := Vector2(600.0, 1100.0)
const SPAWN_SLOW_M := Vector2(250.0, 600.0)
const SPAWN_BEHIND_M := 150.0
const REMOVE_BEHIND_M := 300.0
const REMOVE_AHEAD_M := 1200.0
const PASS_START_M := 30.0
const MERGE_AHEAD_M := 20.0
const GIVE_UP_S := 60.0
const ABREAST_M := 0.6
const FILE_GAP_M := 1.5
const RIDER_HALF_WIDTH_M := 0.3
const MIN_GAP_M := 0.7                # d'épaule à épaule, comme un cycliste qui en double un autre
const EDGE_IN_M := 0.5                # roues à 0,5 m du bord de la chaussée
const SHOULDER_M := 0.5
const RIDER_LATERAL_M := RoadBuilder.RIDER_LATERAL_M
const BOT_LATERAL_M := RoadBuilder.BOT_LATERAL_M
const BOT_LOOK_M := 30.0
const FALL_BACK_MPS := 0.5
const CATCH_M := 4.0                  # un groupe en rattrape un autre à 4 m de sa queue (lot P32)
const LANE_FREE_M := 100.0
const MIN_CENTRE_M := MIN_GAP_M + 2.0 * RIDER_HALF_WIDTH_M
const GROUP_CLEAR_M := 30.0
const VEHICLE_CLEAR_M := 60.0         # pas d'apparition à moins de 60 m d'un véhicule de traffic_model.gd (lot P32)
const SIDE_SPEED_MPS := 1.5
const SIDE_LOOK_M := 2.5              # lot P32 : longueur d'un vélo et un peu plus, devant et derrière
const SIDE_CLEAR_M := 0.8             # lot P32 : on ne se décale pas à moins de 0,8 m d'axe à axe d'un autre
const SPEED_PERIOD_S := 1.0
const SALUT_EVERY := 3
## Puissance constante : frottement (Crr × m × g), poids (m × g), air (½ × CdA × ρ)
const ROLL_N := 3.9
const WEIGHT_N := 785.0
const AIR_K := 0.21

var route = null
var traffic = null                 # traffic_model.gd (pas de groupe en face pendant qu'un véhicule passe)
var budget: int = 8
var seed: int = 0
var road_width_m: float = 6.0
var groups: Array = []             # {id, case, s, speed_mps, power_w, members: [{dl, lateral, outfit, jersey, phase}], …}
var spawned_total: int = 0
var passed_total: int = 0          # groupes `ahead` doublés par le cycliste
var overtook_total: int = 0        # groupes `overtake` qui ont doublé le cycliste
var last_event: Dictionary = {}    # {kind, pos} d'une voix à jouer, vidé à chaque image
var _villages: Array = []
var _climbs: Array = []            # Vector2(start_s, summit_s)
var _next_slot: int = 0
var _started := false
var _clock := 0.0
var _bot_groups: Array = []        # bots de l'image, comme des groupes (lot P32)
var _last_bots_s: Array = []      # abscisses des bots à l'image précédente (vitesse estimée)


## `climbs` : montées de living_decor.gd (`start_s`, `summit_s`) ; `pois` : seuls les `village` comptent.
func configure(route_data, climbs: Array, pois: Array, cyclist_budget: int, rng_seed: int = 0,
		p_road_width_m: float = 6.0, traffic_model = null) -> void:
	route = route_data
	budget = maxi(0, cyclist_budget)
	seed = rng_seed
	road_width_m = p_road_width_m
	traffic = traffic_model
	_villages.clear()
	for p in pois:
		if typeof(p) == TYPE_DICTIONARY and str(p.get("kind", "")) == "village":
			_villages.append(Vector2(float(p.get("x", 0.0)), float(p.get("z", 0.0))))
	_climbs.clear()
	for c in climbs:
		if typeof(c) == TYPE_DICTIONARY:
			_climbs.append(Vector2(float(c.get("start_s", 0.0)), float(c.get("summit_s", c.get("end_s", 0.0)))))
	reset()


func reset() -> void:
	groups.clear()
	spawned_total = 0
	passed_total = 0
	overtook_total = 0
	last_event = {}
	_next_slot = 0
	_started = false
	_clock = 0.0


func set_budget(cyclist_budget: int) -> void:
	budget = maxi(0, cyclist_budget)
	while rider_count() > budget and not groups.is_empty():
		groups.pop_back()


func rider_count() -> int:
	var n := 0
	for g in groups:
		n += (g["members"] as Array).size()
	return n


static func _u(h: int) -> float:
	return float(h & 0xFFFFFF) / 16777216.0


func in_climb(s: float) -> bool:
	for c in _climbs:
		if s >= c.x and s <= c.y:
			return true
	return false


## Lancer d'une case : {} si elle ne porte rien, sinon le groupe tiré.
func slot_event(k: int) -> Dictionary:
	if route == null:
		return {}
	var s := (k + 0.5) * SLOT_M
	if s > route.length_m:
		return {}
	var rate := RATE_FLAT
	if in_climb(s):
		rate = RATE_CLIMB
	else:
		var smp: Dictionary = route.sample(s)
		var p2 := Vector2(float(smp["x"]), float(smp["z"]))
		for v in _villages:
			if p2.distance_to(v) <= VILLAGE_NEAR_M:
				rate = RATE_VILLAGE
				break
	var h := VegetationPlacer.hash3(seed, k, 0xC1C1E5)
	if _u(h) >= rate:
		return {}
	var us := _u(VegetationPlacer._mix(h + 1))
	var size := 1
	if us >= SIZE_SHARES[0] + SIZE_SHARES[1]:
		size = 3 + int(_u(VegetationPlacer._mix(h + 2)) * 4.0)
	elif us >= SIZE_SHARES[0]:
		size = 2
	var uc := _u(VegetationPlacer._mix(h + 3))
	var case_name: String = CASE_SHARES[CASE_SHARES.size() - 1][0]
	var acc := 0.0
	for e in CASE_SHARES:
		acc += float(e[1])
		if uc < acc:
			case_name = e[0]
			break
	var range_kmh: Vector2 = ONCOMING_KMH if case_name == "oncoming" else (AHEAD_KMH if case_name == "ahead" else OVERTAKE_KMH)
	return {
		"slot": k, "case": case_name, "size": size,
		"abreast": size >= 2 and (h >> 9) & 1 == 0,
		"kmh": lerpf(range_kmh.x, range_kmh.y, _u(VegetationPlacer._mix(h + 4))),
		"dist_m": _u(VegetationPlacer._mix(h + 5)),
		"salut": int(VegetationPlacer._mix(h + 6) % SALUT_EVERY) == 0,
		"hash": h,
	}


## Puissance qui donne `v` sur le plat.
static func power_for(v_mps: float) -> float:
	return ROLL_N * v_mps + AIR_K * v_mps * v_mps * v_mps


## Vitesse à puissance `p` sur une pente `grade_pct` (dans le sens du cycliste du décor), de MIN_KMH à MAX_KMH.
static func speed_on_grade(p: float, grade_pct: float) -> float:
	var c := ROLL_N + WEIGHT_N * grade_pct / 100.0
	var lo := 0.0
	var hi := MAX_KMH / 3.6
	for i in range(18):
		var mid := (lo + hi) * 0.5
		if c * mid + AIR_K * mid * mid * mid < p:
			lo = mid
		else:
			hi = mid
	return clampf(lo, MIN_KMH / 3.6, MAX_KMH / 3.6)


## Écart à l'axe de la place la plus proche de l'axe d'un groupe rangé sur le bord droit, à MIN_GAP_M au
## moins du cycliste.
func _edge_lateral() -> float:
	return maxf(road_width_m * 0.5 - EDGE_IN_M, RIDER_LATERAL_M + MIN_CENTRE_M)


func _grade_at(s: float, dir: int) -> float:
	var smp: Dictionary = route.sample(clampf(s, 0.0, route.length_m))
	return float(smp["grade_pct"]) * float(dir)


## Une image : `rider_s`, `rider_v` (m/s) du cycliste ; `bots` : places des bots [{s, lateral}]
## (bots_view_model.places()).
func update(rider_s: float, rider_v: float, dt_s: float, paused: bool = false, bots: Array = []) -> void:
	last_event = {}
	if route == null or paused:
		return
	_clock += dt_s
	if not _started:
		_started = true
		_next_slot = maxi(0, int(floor(rider_s / SLOT_M)) + 1)
	while _next_slot * SLOT_M <= rider_s:
		var ev := slot_event(_next_slot)
		_next_slot += 1
		if not ev.is_empty() and rider_count() + int(ev["size"]) <= budget:
			_spawn(ev, rider_s, rider_v, bots)
	# Bots vus comme des groupes d'un cycliste (lot P32) : vitesse estimée d'une image à l'autre
	_bot_groups = []
	var bots_s := []
	for i in range(bots.size()):
		var b := float(bots[i]["s"])
		var v_b := rider_v
		if i < _last_bots_s.size() and dt_s > 0.0:
			v_b = maxf(0.0, (b - float(_last_bots_s[i])) / dt_s)
		_bot_groups.append({"bot": true, "dir": 1, "s": b, "speed_mps": v_b, "members": [{"lateral": float(bots[i]["lateral"])}]})
		bots_s.append(b)
	_last_bots_s = bots_s
	var kept := []
	for g in groups:
		_move(g, rider_s, rider_v, dt_s, bots)
		var rel := float(g["s"]) - rider_s
		var gone: bool = g.get("gone", false)
		if not gone and rel >= -REMOVE_BEHIND_M and rel <= REMOVE_AHEAD_M and float(g["s"]) >= 0.0 and float(g["s"]) <= route.length_m:
			kept.append(g)
	groups = kept


func _spawn(ev: Dictionary, rider_s: float, rider_v: float, bots: Array = [], at_s: float = NAN) -> void:
	var case_name: String = ev["case"]
	var dir := -1 if case_name == "oncoming" else 1
	var s0 := rider_s
	if not is_nan(at_s):
		s0 = at_s
	else:
		match case_name:
			"oncoming":
				if traffic != null and not (traffic.vehicles as Array).is_empty():
					return
				s0 = rider_s + lerpf(SPAWN_AHEAD_M.x, SPAWN_AHEAD_M.y, float(ev["dist_m"]))
			"ahead":
				s0 = rider_s + lerpf(SPAWN_SLOW_M.x, SPAWN_SLOW_M.y, float(ev["dist_m"]))
			_:
				s0 = rider_s - SPAWN_BEHIND_M
				if s0 < 0.0:
					return
	if s0 < 0.0 or s0 > route.length_m:
		return
	# Lot P32 : jamais d'apparition sur un véhicule de la route ni sur un autre groupe
	if is_nan(at_s):
		if traffic != null:
			for v in traffic.vehicles:
				if absf(float(v.get("s", INF)) - s0) < VEHICLE_CLEAR_M:
					return
		for h in groups:
			if absf(float(h["s"]) - s0) < GROUP_CLEAR_M:
				return
	var flat := float(ev["kmh"]) / 3.6
	if case_name == "overtake":
		flat = maxf(rider_v + flat, OVERTAKE_MIN_KMH / 3.6)
	var h: int = ev["hash"]
	var members := []
	var abreast: bool = ev["abreast"] and case_name != "overtake"
	for i in range(int(ev["size"])):
		var hi := VegetationPlacer._mix(h + 100 + i)
		members.append({
			"dl": float(i / 2 if abreast else i) * FILE_GAP_M,
			"col": i % 2 if abreast else 0,
			"lateral": 0.0,
			"jersey": int(hi % 8),
			"look": int((hi >> 4) & 0xFFFF),
			"phase": _u(VegetationPlacer._mix(hi + 1)),
		})
	var g := {
		"id": "c%d" % int(ev["slot"]), "case": case_name, "dir": dir, "s": s0,
		"flat_mps": flat, "delta_mps": float(ev["kmh"]) / 3.6, "power_w": power_for(flat),
		"speed_mps": flat, "speed_at": -INF, "members": members, "salut": ev["salut"],
		"behind_t": 0.0, "passed": false, "best_rel": -INF, "side": "left" if dir < 0 else "right",
	}
	g["bot_near"] = _bot_near(g, bots)
	for m in members:
		m["lateral"] = _target_lateral(g, m)
	groups.append(g)
	spawned_total += 1


## Groupe posé par un test (lot P32 : captures et contrôle des voies) : cas `case_name`, `size` cyclistes, de
## front si `abreast`, tête à `rel_m` du cycliste ; il suit ensuite les mêmes règles que les autres.
func place_for_test(rider_s: float, rider_v: float, case_name: String, rel_m: float, size: int = 1, abreast: bool = false) -> void:
	if route == null or not case_name in ["oncoming", "ahead", "overtake"]:
		return
	var kmh: float = {"oncoming": ONCOMING_KMH.x, "ahead": AHEAD_KMH.x, "overtake": OVERTAKE_KMH.y}[case_name]
	_spawn({"case": case_name, "slot": 1000000 + spawned_total, "kmh": kmh, "dist_m": 0.0, "size": maxi(1, size),
		"abreast": abreast, "hash": 7919 * (spawned_total + 1), "salut": false}, rider_s, rider_v, [], rider_s + rel_m)


## Vrai si un bot est à moins de BOT_LOOK_M du groupe (de son dernier à son premier).
func _bot_near(g: Dictionary, bots: Array) -> bool:
	var head := float(g["s"])
	var tail := head - float(g["dir"]) * float((g["members"] as Array).size()) * FILE_GAP_M
	for b in bots:
		if float(b["s"]) > minf(head, tail) - BOT_LOOK_M and float(b["s"]) < maxf(head, tail) + BOT_LOOK_M:
			return true
	return false


## Écart latéral visé pour un membre `m` du groupe `g` (voir l'en-tête) ; `g.side` : bord où roule le groupe.
func _target_lateral(g: Dictionary, m: Dictionary) -> float:
	if g.has("pass_lat"):
		var own := _base_lateral(g, m)
		return minf(own, float(g["pass_lat"])) if int(g["dir"]) == 1 else maxf(own, float(g["pass_lat"]))
	return _base_lateral(g, m)


func _base_lateral(g: Dictionary, m: Dictionary) -> float:
	var edge := _edge_lateral()
	var col := float(m["col"]) * ABREAST_M
	match str(g["case"]):
		"oncoming":
			return -(road_width_m * 0.5 - EDGE_IN_M + col)
		"overtake":
			if str(g["side"]) == "left":
				return RIDER_LATERAL_M - MIN_CENTRE_M
	if bool(g.get("bot_near", false)):
		return maxf(edge, BOT_LATERAL_M + MIN_CENTRE_M)
	return edge + col


func _move(g: Dictionary, rider_s: float, rider_v: float, dt_s: float, bots: Array) -> void:
	var dir: int = g["dir"]
	var members: Array = g["members"]
	if _clock - float(g["speed_at"]) >= SPEED_PERIOD_S:
		g["speed_at"] = _clock
		var spd := speed_on_grade(float(g["power_w"]), _grade_at(float(g["s"]), dir))
		if str(g["case"]) == "overtake":
			spd = maxf(rider_v + float(g["delta_mps"]), speed_on_grade(power_for(OVERTAKE_MIN_KMH / 3.6), _grade_at(float(g["s"]), dir)))
			spd = minf(spd, MAX_KMH / 3.6)
		g["speed_mps"] = spd
	var near := _bot_near(g, bots)
	g["bot_near"] = near
	var case_name := str(g["case"])
	var spd_now := float(g["speed_mps"])
	var rel_now := float(g["s"]) - rider_s
	if case_name == "overtake":
		var tail_now := rel_now - float(members.size() - 1) * FILE_GAP_M
		if str(g["side"]) == "right" and rel_now >= -PASS_START_M and tail_now < MERGE_AHEAD_M:
			if near:
				spd_now = minf(spd_now, rider_v)       # un bot à côté : attend derrière, sur la droite
			else:
				g["side"] = "left"
		elif str(g["side"]) == "left" and tail_now > MERGE_AHEAD_M and not near:
			g["side"] = "right"
	# Lot P32 : un groupe qui en rattrape un autre du même sens le double vers l'axe si la voie d'en face est
	# libre et que le cycliste n'est pas à côté ; il reste à la vitesse de l'autre tant qu'il ne s'est pas écarté,
	# ou derrière lui si la voie n'est pas libre ; un groupe qui n'est pas plus rapide se laisse distancer.
	g.erase("pass_lat")
	var alongside := _caught_groups(g)     # tous ceux du même sens à sa hauteur, quel que soit leur écart
	var own := _base_lateral(g, members[0])
	var cur := _group_lateral(g)
	var near_groups := []                   # ceux qui le gênent : sur sa place ou sur sa position en travers
	for h in alongside:
		var h_lat := _group_lateral(h)
		if absf(h_lat - own) < MIN_CENTRE_M or absf(h_lat - cur) < MIN_CENTRE_M:
			near_groups.append(h)
	if not near_groups.is_empty():
		var pass_lat := own
		for _i in range(3):
			for h in alongside:
				var h_lat := _group_lateral(h)
				if absf(pass_lat - h_lat) < MIN_CENTRE_M:
					pass_lat = h_lat - signf(h_lat) * MIN_CENTRE_M
		var slowest := INF
		var blocking := false     # encore sur la trajectoire d'un groupe qu'il n'a pas dépassé
		for h in near_groups:
			slowest = minf(slowest, float(h["speed_mps"]))
			if (float(g["s"]) - float(h["s"])) * dir < 0.0 and absf(cur - _group_lateral(h)) < MIN_CENTRE_M - 0.05:
				blocking = true
		# Pour passer, il faudrait traverser la place d'un autre (un bot entre lui et l'axe) : il ne se décale pas
		# et, derrière, il attend
		var crossing := false
		for h in alongside:
			var h_lat := _group_lateral(h)
			var through := h_lat > minf(cur, pass_lat) and h_lat < maxf(cur, pass_lat)
			if through or (absf(pass_lat - h_lat) < MIN_CENTRE_M - 0.05 and absf(pass_lat - h_lat) < absf(cur - h_lat)):
				crossing = true
				slowest = minf(slowest, float(h["speed_mps"]))
				if (float(g["s"]) - float(h["s"])) * dir < 0.0:
					blocking = true
		var faster := spd_now > slowest
		var out := not blocking     # déjà écarté de ceux qu'il double : il finit
		if crossing:
			if blocking:
				spd_now = minf(spd_now, slowest - FALL_BACK_MPS)
		elif faster and (out or _lane_free_for(g, rider_s) and (dir == -1 or absf(pass_lat - RIDER_LATERAL_M) >= MIN_CENTRE_M
				or absf(float(g["s"]) - rider_s) > PASS_START_M)):
			if absf(pass_lat - own) > 1e-3:
				g["pass_lat"] = pass_lat
			if blocking:
				spd_now = minf(spd_now, slowest)
		elif blocking or not faster:
			spd_now = minf(spd_now, slowest - FALL_BACK_MPS)
	g["s"] = float(g["s"]) + float(dir) * spd_now * dt_s
	var rel := float(g["s"]) - rider_s
	var rel0 := float(g.get("last_rel", rel))
	g["last_rel"] = rel
	# Près d'un bot, le groupe `ahead` se met en file sur l'accotement
	if case_name == "ahead":
		for i in range(members.size()):
			var m: Dictionary = members[i]
			if not m.has("col0"):
				m["col0"] = m["col"]
				m["dl0"] = m["dl"]
			m["col"] = 0 if near else m["col0"]
			m["dl"] = float(i) * FILE_GAP_M if near else m["dl0"]
	for m in members:
		var lat0 := float(m["lateral"])
		var lat1 := move_toward(lat0, _target_lateral(g, m), SIDE_SPEED_MPS * dt_s)
		if _side_blocked(g, float(g["s"]) - float(dir) * float(m["dl"]), lat0, lat1, rider_s, bots):
			lat1 = lat0
		m["lateral"] = lat1
	match case_name:
		"ahead":
			var tail := float(members.size()) * FILE_GAP_M
			if not g["passed"] and rel - tail < 0.0 and rel0 - tail >= 0.0:
				g["passed"] = true
				passed_total += 1
		"overtake":
			var last_rel := rel - float(members.size() - 1) * FILE_GAP_M
			if rel >= 0.0 and rel0 < 0.0 and g["salut"] and not g.get("said", false):
				g["said"] = true
				last_event = {"kind": "voice_salut", "pos": world_position(g, members[0])}
			if not g["passed"] and last_rel > MERGE_AHEAD_M:
				g["passed"] = true
				overtook_total += 1
			# Ne gagne plus de terrain : disparaît après GIVE_UP_S
			if rel <= float(g["best_rel"]) + 0.01 and rel < 0.0:
				g["behind_t"] = float(g["behind_t"]) + dt_s
				if float(g["behind_t"]) >= GIVE_UP_S:
					g["gone"] = true
			else:
				g["behind_t"] = 0.0
			g["best_rel"] = maxf(float(g["best_rel"]), rel)


## Groupes du même sens que `g` (et bots) qui le chevauchent, dont la queue est à moins de CATCH_M devant sa tête
## ou la tête à moins de CATCH_M derrière sa queue, quel que soit leur écart à l'axe.
func _caught_groups(g: Dictionary) -> Array:
	var dir := int(g["dir"])
	var g_head := float(g["s"]) * dir
	var g_tail := g_head - float((g["members"] as Array).size() - 1) * FILE_GAP_M
	var out := []
	for h in groups + _bot_groups:
		if is_same(h, g) or int(h["dir"]) != dir:
			continue
		var h_head := float(h["s"]) * dir
		var h_tail := h_head - float((h["members"] as Array).size() - 1) * FILE_GAP_M
		if h_tail > g_head + CATCH_M or h_head < g_tail - CATCH_M:
			continue
		out.append(h)
	return out


## Vrai si passer de `lat0` à `lat1` à l'abscisse `s` rapprocherait un membre du groupe `g` à moins de SIDE_CLEAR_M
## d'un cycliste d'un autre groupe, d'un bot ou du cycliste qui roule à côté de lui (lot P32 : on ne se rabat pas
## sur quelqu'un, on attend qu'il soit passé).
func _side_blocked(g: Dictionary, s: float, lat0: float, lat1: float, rider_s: float, bots: Array) -> bool:
	if absf(lat1 - lat0) < 1e-6:
		return false
	var near := []
	if absf(rider_s - s) < SIDE_LOOK_M:
		near.append(RIDER_LATERAL_M)
	for b in bots:
		if absf(float(b["s"]) - s) < SIDE_LOOK_M:
			near.append(float(b["lateral"]))
	for h in groups:
		if is_same(h, g) or absf(float(h["s"]) - s) > SIDE_LOOK_M + float((h["members"] as Array).size()) * FILE_GAP_M:
			continue
		for m in h["members"]:
			if absf(float(h["s"]) - float(h["dir"]) * float(m["dl"]) - s) < SIDE_LOOK_M:
				near.append(float(m["lateral"]))
	for o_lat in near:
		var d1 := absf(lat1 - float(o_lat))
		if d1 < SIDE_CLEAR_M and d1 < absf(lat0 - float(o_lat)):
			return true
	return false


## Écart à l'axe d'un groupe : celui de son premier membre.
func _group_lateral(g: Dictionary) -> float:
	return float((g["members"] as Array)[0]["lateral"])


## Vrai si rien ne vient en face du groupe `g` à moins de LANE_FREE_M : ni groupe, ni véhicule de traffic_model.gd,
## ni (pour un groupe en face) le cycliste.
func _lane_free_for(g: Dictionary, rider_s: float) -> bool:
	var dir := int(g["dir"])
	var s := float(g["s"])
	for h in groups:
		var ahead := (float(h["s"]) - s) * dir
		if int(h["dir"]) != dir and ahead > -5.0 and ahead < LANE_FREE_M:
			return false
	if traffic != null:
		for v in traffic.vehicles:
			var ahead2 := (float(v.get("s", INF)) - s) * dir
			if int(v.get("dir", dir)) != dir and ahead2 > -5.0 and ahead2 < LANE_FREE_M:
				return false
	if dir == -1 and (s - rider_s) > -5.0 and (s - rider_s) < LANE_FREE_M:
		return false
	return true


## Abscisse et écart latéral de chaque cycliste : [{group, member, s, lateral, dir}].
func riders() -> Array:
	var out := []
	for g in groups:
		for m in g["members"]:
			out.append({"group": g, "member": m, "s": float(g["s"]) - float(g["dir"]) * float(m["dl"]),
				"lateral": float(m["lateral"]), "dir": int(g["dir"])})
	return out


## Position d'un membre dans le monde.
func world_position(g: Dictionary, m: Dictionary) -> Vector3:
	return world_transform(float(g["s"]) - float(g["dir"]) * float(m["dl"]), float(m["lateral"]), int(g["dir"])).origin


## Position et cap d'un cycliste (face vers +z local, comme people_mesh.gd) à `s`, `lateral`, dans le sens `dir`.
func world_transform(s: float, lateral: float, dir: int) -> Transform3D:
	var smp: Dictionary = route.sample(clampf(s, 0.0, route.length_m))
	var h := deg_to_rad(float(smp["heading_deg"]))
	var fwd := Vector3(sin(h), 0.0, -cos(h))
	var right := Vector3(cos(h), 0.0, sin(h))
	var pos := Vector3(float(smp["x"]), float(smp["y"]), float(smp["z"])) + right * lateral
	var facing := fwd * float(dir)
	return Transform3D(Basis(Vector3.UP, atan2(facing.x, facing.z)), pos)


## Cadence (tr/min) à `v` (m/s) avec le développement DEVELOPMENT_M ; roue libre au-delà de 55 km/h.
static func cadence_rpm(v_mps: float) -> float:
	if v_mps > 55.0 / 3.6:
		return 0.0
	return v_mps / DEVELOPMENT_M * 60.0
