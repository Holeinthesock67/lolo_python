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
## Lot AS7 : le core fait rouler les mêmes cyclistes (core/src/openride_core/road_cyclists.py, même tirage, test
## de parité unit/test_road_cyclists_parity.gd) et en est l'autorité à moins de NEAR_M du cycliste : `sync_core`
## reprend sa liste `riders`, ceux qui roulent dans son sens l'abritent (`draft_bot` = `rider:<id>`) ;
## l'engine ne garde que le décor lointain, réglé par le préréglage.
## Correctif du 7 novembre (recette vélo sur le gravel) : bord droit et bord gauche pris sur la demi-largeur roulable
## `half_width_at(s)` (option gravel : chemin de 3 à 4 m, world_streamer.rideable_half) ; sur un chemin trop étroit
## pour rouler à MIN_GAP_M du cycliste (`_narrow`), tous les groupes passent en file et restent sur le chemin ;
## FILE_GAP_M de 2,1 m (vélo de 1,7 m) ; écarts latéraux à accélération bornée (SIDE_ACCEL_MPS2) et vélo tourné
## dans le sens où il va (`side_yaw`) ; écart des cyclistes du core rejoint en CORE_LANE_TAU_S, extrapolé entre deux
## listes, sans saut à la reprise.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const RouteMirror := preload("res://scripts/route_mirror.gd")
const RoadRules := preload("res://scripts/road_rules.gd")

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
const MERGE_LOOK_S := 6.0             # lot DPS1 : un `overtake` ne se rabat pas derrière un groupe plus lent rattrapé avant
const PASS_HORIZON_S := 60.0          # lot DPS1 : durée de dépassement au plus, pour savoir si le cycliste sera à hauteur
const MERGE_AHEAD_M := 20.0
const GIVE_UP_S := 60.0
const YIELD_S := 3.0                  # lot AS8 : un groupe de l'engine s'écarte d'un groupe du core à 3 s de sa queue
const NEAR_M := 60.0                  # lot AS7 : cyclistes calculés par le core (liste `riders`)
const CORE_MARGIN_M := 5.0            # ... un cycliste absent de la liste à moins de 55 m n'est plus sur la route
const CORE_LIST_MAX := 10             # ... liste pleine (lot AS10 : 10, au lieu de 6) : ceux qu'elle ne donne pas peuvent encore rouler
const CORE_SHIFT_MAX_M := 50.0        # lot AS9 : écart cycliste affiché / du core au-delà duquel on ne recale pas
const ABREAST_M := 0.6
const FILE_GAP_M := 2.1               # d'axe à axe en file : vélo de 1,7 m et 0,4 m de roue à roue
const RIDER_HALF_WIDTH_M := 0.3
const GUARD_LEN_M := RoadRules.BIKE_LENGTH_M + 0.35  # lot DPS1 : garde finale, en long : contact à 1,7 m, plus une marge (2,05 m, sous FILE_GAP_M)
const GUARD_WIDTH_M := 2.0 * RIDER_HALF_WIDTH_M + 0.05   # ... et en travers (contact à 0,6 m)
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
const GUARD_RIDER_WIDTH_M := MIN_CENTRE_M - 1.5e-3   # lot DPS1 : garde finale, en travers du cycliste
const GUARD_STEPS := 8                # lot DPS1 : corrections au plus par groupe et par pas
const GUARD_REACH_M := GUARD_LEN_M + GUARD_STEPS * (2.0 * GUARD_LEN_M + 0.01)   # portée de la garde autour d'une file
const GROUP_CLEAR_M := 30.0
const VEHICLE_CLEAR_M := 60.0         # pas d'apparition à moins de 60 m d'un véhicule de traffic_model.gd (lot P32)
## Lot DB3 (banc rDB3) : un groupe ne double jamais un véhicule du même sens ; il se cale sur sa vitesse de
## VEHICLE_FOLLOW_M derrière jusqu'à VEHICLE_ALONGSIDE_M à sa hauteur (comme road_cyclists.py du core).
const VEHICLE_FOLLOW_M := 25.0
const VEHICLE_ALONGSIDE_M := 8.0
const VEHICLE_FILE_M := 80.0          # lot AS11 : véhicule de son sens à moins de 80 m derrière, plus vite : en file
const SIDE_SPEED_MPS := 1.5           # écart latéral : vitesse au plus, ...
const SIDE_ACCEL_MPS2 := 2.0          # ... accélération au plus (on s'écarte et on se rabat sans à-coup, essai du 7/11)
const SIDE_TAU_S := 0.5               # ... approche de la place visée,
const SIDE_ARRIVE_MPS := 0.1          # ... à au moins 0,1 m/s jusqu'à y être
const DL_SPEED_MPS := 1.0             # passage de deux de front à la file (et retour) : recul ou retour d'un membre
const CORE_LANE_TAU_S := 0.15         # cyclistes du core : écart affiché qui rejoint celui de la liste, extrapolé
const CORE_LANE_RATE_MAX := 2.0       # ... à sa vitesse latérale estimée (au plus 2 m/s)
const SIDE_LOOK_M := 2.5              # lot P32 : longueur d'un vélo et un peu plus, devant et derrière
const SIDE_CLEAR_M := 0.8             # lot P32 : on ne se décale pas à moins de 0,8 m d'axe à axe d'un autre
const SIDE_CROSS_S := MIN_CENTRE_M / SIDE_SPEED_MPS   # lot AS9 : temps d'un écart d'une place à la voisine
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
## Demi-largeur roulable en s (option gravel : world_streamer.rideable_half), sinon celle du bitume.
var half_width_at: Callable = Callable()
var groups: Array = []             # {id, case, s, speed_mps, power_w, members: [{dl, lateral, outfit, jersey, phase}], …}
var spawned_total: int = 0
var passed_total: int = 0          # groupes `ahead` doublés par le cycliste
var overtook_total: int = 0        # groupes `overtake` qui ont doublé le cycliste
var guard_total: int = 0           # lot DPS1 : corrections de la garde finale (doivent rester rares)
var last_event: Dictionary = {}    # {kind, pos} d'une voix à jouer, vidé à chaque image
var _villages: Array = []
var _climbs: Array = []            # Vector2(start_s, summit_s)
var _next_slot: int = 0
var _started := false
var _clock := 0.0
var _bot_groups: Array = []        # bots de l'image, comme des groupes (lot P32)
var _last_bots_s: Array = []      # abscisses des bots à l'image précédente (vitesse estimée)
var _core_seq := -1                 # trame de la dernière liste `riders` reprise (lot AS7)
## Lot AS11 (révision 1.20) : le core envoie tous ses cyclistes du décor par parties (`road_part`, un groupe jamais
## coupé) ; l'engine n'en tire plus aucun et ne fait plus que les afficher. Faux tant qu'aucune partie n'est reçue.
var core_full := false
var _cycle_prev := {}             # ... et pendant le tour d'avant : une partie perdue (images lentes) ne retire rien
var _cycle_seen := {}               # groupes reçus depuis la dernière partie d'un tour (lot AS11)
var rider_lane := RIDER_LATERAL_M   # lot AS10 : vraie place du cycliste en travers (`lane_m` de la trame)
var direction: int = 1             # sens de marche du cycliste (lot N23) : -1 à rebours, `route` est alors retourné
var base_route = null              # parcours dans son sens, quel que soit le sens de marche
var _base_climbs: Array = []       # montées du parcours dans son sens
var _back_climbs: Array = []       # montées du retour dans le repère retourné (lot N24, set_back_climbs)


## `climbs` : montées de living_decor.gd (`start_s`, `summit_s`) ; `pois` : seuls les `village` comptent.
func configure(route_data, climbs: Array, pois: Array, cyclist_budget: int, rng_seed: int = 0,
		p_road_width_m: float = 6.0, traffic_model = null, p_half_width_at: Callable = Callable()) -> void:
	route = route_data
	base_route = route_data
	direction = 1
	budget = maxi(0, cyclist_budget)
	seed = rng_seed
	road_width_m = p_road_width_m
	half_width_at = p_half_width_at
	traffic = traffic_model
	extend_route(route_data, climbs, pois)
	reset()


## Route prolongée du monde ouvert (même début, abscisses gardées) : nouvelle route, montées et villages, sans
## retirer les groupes en cours. À rebours (lot N23), le parcours retourné s'allonge par son début : les groupes
## gardent leur place sur la route (u = L - s décalé de l'allongement).
func extend_route(route_data, climbs: Array, pois: Array) -> void:
	var grown := 0.0 if base_route == null or route_data == null else float(route_data.length_m) - float(base_route.length_m)
	base_route = route_data
	route = route_data if direction > 0 or route_data == null else RouteMirror.new(route_data)
	if direction < 0:
		for g in groups:
			g["s"] = float(g["s"]) + grown
	_villages.clear()
	for p in pois:
		if typeof(p) == TYPE_DICTIONARY and str(p.get("kind", "")) == "village":
			_villages.append(Vector2(float(p.get("x", 0.0)), float(p.get("z", 0.0))))
	_base_climbs.clear()
	for c in climbs:
		if typeof(c) == TYPE_DICTIONARY:
			_base_climbs.append(Vector2(float(c.get("start_s", 0.0)), float(c.get("summit_s", c.get("end_s", 0.0)))))
	_climbs = _base_climbs.duplicate() if direction > 0 else _back_climbs.duplicate()   # retour : set_back_climbs


## Lot N24 : montées du retour (climb_detector.gd `detect_back`, repère du parcours, pied au-dessus du sommet), gardées
## dans le repère retourné pour le demi-tour. Après `configure`.
func set_back_climbs(back: Array) -> void:
	_back_climbs.clear()
	if base_route == null:
		return
	var length := float(base_route.length_m)
	for c in back:
		if typeof(c) == TYPE_DICTIONARY:
			_back_climbs.append(Vector2(RouteMirror.flip_s(length, float(c.get("start_s", 0.0))),
				RouteMirror.flip_s(length, float(c.get("summit_s", 0.0)))))
	if direction < 0:
		_climbs = _back_climbs.duplicate()


## Abscisse du parcours `s` dans le repère du modèle (u = L - s à rebours, lot N23) ; réciproque.
func model_s(s: float) -> float:
	return s if direction > 0 or route == null else RouteMirror.flip_s(float(route.length_m), s)


## Lot N23 (jumeau de road_cyclists.py `set_direction`) : le cycliste a fait demi-tour (`rider_s` : sa place sur le
## parcours). Le modèle roule ensuite sur le parcours retourné ; les groupes déjà là restent à leur place : ceux qui
## allaient dans son sens viennent en face, ceux d'en face qui l'avaient croisé roulent devant lui (`ahead`), ceux
## d'en face pas encore croisés, désormais dans son dos, quittent la route ; ceux du core (`core`) restent au core.
## À rebours, les montées sont celles du retour (lot N24). Vrai si le sens a changé.
func set_direction(dir: int, rider_s: float = NAN) -> bool:
	var d := -1 if dir < 0 else 1
	if d == direction or base_route == null:
		return false
	direction = d
	route = base_route if d > 0 else RouteMirror.new(base_route)
	_climbs = _base_climbs.duplicate() if d > 0 else _back_climbs.duplicate()
	var rider := NAN if is_nan(rider_s) else model_s(rider_s)
	var length := float(base_route.length_m)
	var kept := []
	for g in groups:
		g["s"] = RouteMirror.flip_s(length, float(g["s"]))
		g["dir"] = -int(g["dir"])
		for m in g["members"]:
			m["lateral"] = -float(m["lateral"])
			m["lat_v"] = -float(m.get("lat_v", 0.0))
			for key in ["lane_core", "lane_seen", "lane_rate"]:
				if m.has(key):
					m[key] = -float(m[key])
		g.erase("pass_lat")
		g.erase("last_rel")
		g["behind_t"] = 0.0
		if str(g["case"]) != "core":
			if int(g["dir"]) < 0:
				g["case"] = "oncoming"
				g["side"] = "left"
			elif not is_nan(rider) and float(g["s"]) < rider:
				continue                      # désormais dans son dos, dans son sens : il quitte la route
			else:
				g["case"] = "ahead"
				g["side"] = "right"
				g["passed"] = false
		kept.append(g)
	groups = kept
	_started = false   # cases suivantes tirées depuis la place du cycliste dans le nouveau repère
	_last_bots_s = []
	return true


func reset() -> void:
	groups.clear()
	spawned_total = 0
	passed_total = 0
	overtook_total = 0
	guard_total = 0
	last_event = {}
	_next_slot = 0
	_started = false
	_clock = 0.0
	_core_seq = -1


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


func _half_at(s: float) -> float:
	var half := road_width_m * 0.5
	if half_width_at.is_valid():
		half = minf(half, float(half_width_at.call(model_s(s))))
	return maxf(half, EDGE_IN_M)


## Écart à l'axe de la place la plus proche du bord droit, roues à EDGE_IN_M du bord.
static func _edge_lateral(half: float) -> float:
	return half - EDGE_IN_M


## Chemin trop étroit pour rouler à MIN_GAP_M du cycliste en restant dessus : on y roule en file.
static func _narrow(half: float) -> bool:
	return half - EDGE_IN_M < RIDER_LATERAL_M + MIN_CENTRE_M - 1e-6


func _grade_at(s: float, dir: int) -> float:
	var smp: Dictionary = route.sample(clampf(s, 0.0, route.length_m))
	return float(smp["grade_pct"]) * float(dir)


## Une image : `rider_s`, `rider_v` (m/s) du cycliste ; `bots` : places des bots [{s, lateral}]
## (bots_view_model.places()).
## Lot AS10 : `lane` : écart à l'axe du cycliste (`lane_m` de la trame, lot AS2) ; les groupes l'évitent là où il
## est (NAN : sa dernière place connue, RIDER_LATERAL_M au départ).
func update(rider_s: float, rider_v: float, dt_s: float, paused: bool = false, bots: Array = [], lane: float = NAN) -> void:
	if not is_nan(lane):
		rider_lane = lane
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
		if not ev.is_empty() and rider_count() + int(ev["size"]) <= budget and not core_full:
			_spawn(ev, rider_s, rider_v, bots)
	# Bots vus comme des groupes d'un cycliste (lot P32) : vitesse estimée d'une image à l'autre
	_bot_groups = []
	var bots_s := []
	var bot_dir := direction   # les bots gardent le sens du parcours : en face à rebours (lot N23)
	for i in range(bots.size()):
		var b := float(bots[i]["s"])
		var v_b := rider_v
		if i < _last_bots_s.size() and dt_s > 0.0:
			v_b = maxf(0.0, bot_dir * (b - float(_last_bots_s[i])) / dt_s)
		_bot_groups.append({"bot": true, "dir": bot_dir, "s": b, "speed_mps": v_b, "members": [{"lateral": float(bots[i]["lateral"])}]})
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
	_guard(rider_s, rider_v)


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
			"id": "c%d-%d" % [int(ev["slot"]), i],
		})
	var g := {
		"id": "c%d" % int(ev["slot"]), "case": case_name, "dir": dir, "s": s0,
		"flat_mps": flat, "delta_mps": float(ev["kmh"]) / 3.6, "power_w": power_for(flat),
		"speed_mps": flat, "speed_at": -INF, "members": members, "salut": ev["salut"],
		"behind_t": 0.0, "passed": false, "best_rel": -INF, "side": "left" if dir < 0 else "right",
	}
	g["bot_near"] = _bot_near(g, bots)
	g["half"] = _half_at(s0)
	if _narrow(float(g["half"])):
		for i in range(members.size()):
			var m: Dictionary = members[i]
			m["col0"] = m["col"]
			m["dl0"] = m["dl"]
			m["col"] = 0
			m["dl"] = float(i) * FILE_GAP_M
	for m in members:
		m["lateral"] = _target_lateral(g, m)
		m["lat_v"] = 0.0
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
## Sur un chemin étroit, jamais hors de la bande roulable.
func _target_lateral(g: Dictionary, m: Dictionary) -> float:
	var own := _base_lateral(g, m)
	if g.has("pass_lat"):
		own = minf(own, float(g["pass_lat"])) if int(g["dir"]) == 1 else maxf(own, float(g["pass_lat"]))
	var half := float(g.get("half", road_width_m * 0.5))
	if _narrow(half):
		var edge := _edge_lateral(half)
		own = clampf(own, -edge, edge)
	return own


func _base_lateral(g: Dictionary, m: Dictionary) -> float:
	var half := float(g.get("half", road_width_m * 0.5))
	var edge := _edge_lateral(half)
	var col := float(m["col"]) * ABREAST_M
	if _narrow(half):
		# Chemin étroit : le plus à l'extérieur de front sur le bord, les autres à l'intérieur, le temps de reculer
		# dans la file (dans le même ordre en travers)
		var max_col := 0
		for o in g["members"]:
			max_col = maxi(max_col, int(o.get("col", 0)))
		col -= float(max_col) * ABREAST_M
	match str(g["case"]):
		"oncoming":
			return -(edge + col)
		"overtake":
			if str(g["side"]) == "left":
				return rider_lane - MIN_CENTRE_M
	if bool(g.get("bot_near", false)) and not _narrow(half):
		return maxf(edge, BOT_LATERAL_M + MIN_CENTRE_M)
	return edge + col


## De deux de front à la file (`file`) et retour, sans se chevaucher : en file, un membre recule à DL_SPEED_MPS
## jusqu'à sa place puis se range dans la ligne ; de retour de front, il reprend sa colonne et ne remonte qu'une
## fois à côté de celui qu'il suit.
## Lot AS11 (code de la route, 17/11) : un véhicule de son sens arrive derrière (à moins de VEHICLE_FILE_M, plus
## vite) : le groupe se met en file pour le laisser doubler (road_cyclists._vehicle_coming du core).
func _vehicle_coming(g: Dictionary) -> bool:
	if traffic == null:
		return false
	var own := _step_mps(g)
	for v in traffic.vehicles:
		if int(v.get("dir", 1)) != int(g["dir"]):
			continue
		if not v.has("s"):
			continue
		var behind := (float(g["s"]) - float(v["s"])) * int(g["dir"])
		if behind > 0.0 and behind < VEHICLE_FILE_M and float(v.get("speed_mps", 0.0)) > own:
			return true
	return false


func _formation(g: Dictionary, file: bool, dt_s: float) -> void:
	var members: Array = g["members"]
	for i in range(members.size()):
		var m: Dictionary = members[i]
		if not m.has("col0"):
			m["col0"] = m["col"]
			m["dl0"] = m["dl"]
		if file:
			var dl_t := float(i) * FILE_GAP_M
			m["dl"] = move_toward(float(m["dl"]), dl_t, DL_SPEED_MPS * dt_s)
			if absf(float(m["dl"]) - dl_t) < 1e-6:
				m["col"] = 0
		else:
			m["col"] = m["col0"]
			if absf(float(m["lateral"]) - _target_lateral(g, m)) < 0.05:
				m["dl"] = move_toward(float(m["dl"]), float(m["dl0"]), DL_SPEED_MPS * dt_s)


## Écart latéral vers sa place sans à-coup : vitesse au plus SIDE_SPEED_MPS, approche en SIDE_TAU_S, accélération
## et freinage au plus SIDE_ACCEL_MPS2 (arrêt sur la place, sans la dépasser).
func _side_step(g: Dictionary, m: Dictionary, dt_s: float, rider_s: float, bots: Array, rider_v: float = 0.0) -> void:
	var lat0 := float(m["lateral"])
	var target := _target_lateral(g, m)
	var d := target - lat0
	var want := signf(d) * minf(SIDE_SPEED_MPS, minf(sqrt(2.0 * SIDE_ACCEL_MPS2 * absf(d)),
			maxf(absf(d) / SIDE_TAU_S, SIDE_ARRIVE_MPS)))
	var v1 := move_toward(float(m.get("lat_v", 0.0)), want, SIDE_ACCEL_MPS2 * dt_s)
	var lat1 := lat0 + v1 * dt_s
	if (target - lat1) * d <= 0.0:
		lat1 = target
		v1 = 0.0
	if _side_blocked(g, float(g["s"]) - float(g["dir"]) * float(m["dl"]), lat0, lat1, rider_s, bots, rider_v):
		lat1 = lat0
		v1 = 0.0
	m["lateral"] = lat1
	m["lat_v"] = v1


func _move(g: Dictionary, rider_s: float, rider_v: float, dt_s: float, bots: Array) -> void:
	var dir: int = g["dir"]
	var members: Array = g["members"]
	if str(g["case"]) == "core":
		# Lot AS7 : calculé par le core, extrapolé jusqu'à sa prochaine liste (puis à sa dernière vitesse) ; pas à
		# l'image de sa reprise, déjà à sa place (lot AS9)
		var fresh: bool = g.get("fresh", false)
		g.erase("fresh")
		if not fresh:
			g["s"] = float(g["s"]) + float(dir) * float(g["speed_mps"]) * dt_s
		var k := 1.0 - exp(-dt_s / CORE_LANE_TAU_S)
		for m in members:
			var lat0 := float(m["lateral"])
			if m.has("lane_core"):
				if not fresh:
					m["lane_core"] = float(m["lane_core"]) + float(m.get("lane_rate", 0.0)) * dt_s
				m["lateral"] = lat0 + (float(m["lane_core"]) - lat0) * k
			m["lat_v"] = (float(m["lateral"]) - lat0) / dt_s if dt_s > 0.0 else 0.0
		return
	if _clock - float(g["speed_at"]) >= SPEED_PERIOD_S:
		g["speed_at"] = _clock
		var spd := speed_on_grade(float(g["power_w"]), _grade_at(float(g["s"]), dir))
		if str(g["case"]) == "overtake":
			spd = maxf(rider_v + float(g["delta_mps"]), speed_on_grade(power_for(OVERTAKE_MIN_KMH / 3.6), _grade_at(float(g["s"]), dir)))
			spd = minf(spd, MAX_KMH / 3.6)
		g["speed_mps"] = spd
	var near := _bot_near(g, bots)
	g["bot_near"] = near
	g["half"] = _half_at(float(g["s"]))
	var case_name := str(g["case"])
	var spd_now := float(g["speed_mps"])
	var rel_now := float(g["s"]) - rider_s
	if case_name == "overtake":
		var tail_now := rel_now - float(members.size() - 1) * FILE_GAP_M
		# Lot AS9 : il ne sort pour doubler que derrière le cycliste, à plus de SIDE_LOOK_M de sa roue (ralenti devant
		# lui par un groupe lent, c'est le cycliste qui le double : il reste sur sa droite au lieu de traverser sa ligne)
		# Lot AS11 (« rabattre plus tôt », 17/11) : fenêtre de la règle commune (draft.pass_window du core)
		var win := overtake_window(spd_now - rider_v, absf(_group_lateral(g) - (rider_lane - MIN_CENTRE_M)))
		if str(g["side"]) == "right" and rel_now >= win.x and rel_now < -SIDE_LOOK_M and tail_now < win.y:
			# lot DPS1 : ni bot à côté, ni autre groupe déjà sur la ligne de dépassement à sa hauteur (il attend derrière,
			# sur la droite, au lieu de s'y glisser entre ses membres)
			if near or not _line_free(g, rider_lane - MIN_CENTRE_M):
				spd_now = minf(spd_now, rider_v)       # un bot à côté : attend derrière, sur la droite
			else:
				g["side"] = "left"
		elif str(g["side"]) == "left" and tail_now > win.y and not near and not _lane_closing(g, spd_now):
			g["side"] = "right"
		# Lot AS9 : sorti tout près derrière le cycliste, il ne s'approche pas à moins de SIDE_LOOK_M de sa roue tant
		# qu'il n'est pas hors de sa ligne
		if str(g["side"]) == "left" and rel_now < 0.0 and dt_s > 0.0 \
				and absf(_group_lateral(g) - rider_lane) < MIN_CENTRE_M - 1e-3:
			spd_now = minf(spd_now, maxf(0.0, -SIDE_LOOK_M - rel_now) / dt_s)
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
		# Bots à moins de BOT_LOOK_M : on ne double pas sur leur ligne, ni en la traversant (file longue)
		var lanes: Array = alongside.duplicate()
		for b in _bot_groups:
			if not alongside.has(b) and absf(float(b["s"]) - float(g["s"])) < BOT_LOOK_M + float(members.size()) * FILE_GAP_M:
				lanes.append(b)
		# Lot DPS1 : le cycliste est un usager comme un bot : on ne double pas sur sa ligne, ni en la traversant, s'il
		# sera à hauteur pendant le dépassement (fenêtre en temps, `_rider_lane_group`)
		if dir == 1:
			var rider_g := _rider_lane_group(g, near_groups, rider_s, rider_v, spd_now)
			if not rider_g.is_empty():
				lanes.append(rider_g)
		var pass_lat := own
		for _i in range(3):
			for h in lanes:
				var h_lat := _group_lateral(h)
				if absf(pass_lat - h_lat) < MIN_CENTRE_M:
					pass_lat = h_lat - signf(h_lat) * MIN_CENTRE_M
		var slowest := INF
		var blocking := false     # encore sur la trajectoire d'un groupe qu'il n'a pas dépassé
		for h in near_groups:
			slowest = minf(slowest, _speed_of(g, h))   # lot AS10 : devant lui, à la vitesse où il roule
			# encore derrière lui, un de ses membres sur sa ligne (la queue se décale après la tête)
			if (float(g["s"]) - float(h["s"])) * dir < 0.0 and _closest_lateral(g, _group_lateral(h)) < MIN_CENTRE_M - 0.05:
				blocking = true
		# Pour passer, il faudrait traverser la place d'un autre (un bot entre lui et l'axe) : il ne se décale pas
		# et, derrière, il attend
		var crossing := false
		for h in lanes:
			var h_lat := _group_lateral(h)
			var through := h_lat > minf(cur, pass_lat) and h_lat < maxf(cur, pass_lat)
			if through or (absf(pass_lat - h_lat) < MIN_CENTRE_M - 0.05 and absf(pass_lat - h_lat) < absf(cur - h_lat)):
				crossing = true
				slowest = minf(slowest, _speed_of(g, h))   # lot AS10 : devant lui, à la vitesse où il roule
				if (float(g["s"]) - float(h["s"])) * dir < 0.0:
					blocking = true
		var faster := spd_now > slowest
		var out := not blocking     # déjà écarté de ceux qu'il double : il finit
		if crossing:
			if blocking:
				spd_now = minf(spd_now, slowest - FALL_BACK_MPS)
		elif faster and (out or _lane_free_for(g, rider_s) and (dir == -1 or absf(pass_lat - rider_lane) >= MIN_CENTRE_M
				or absf(float(g["s"]) - rider_s) > PASS_START_M)):
			if absf(pass_lat - own) > 1e-3:
				g["pass_lat"] = pass_lat
			if blocking:
				spd_now = minf(spd_now, slowest)
		elif blocking or not faster:
			spd_now = minf(spd_now, slowest - FALL_BACK_MPS)
	spd_now = _yield_to_core(g, spd_now, rider_s, bots)
	# jamais à reculons derrière un usager arrêté (revue C5-06, comme road_cyclists.py)
	spd_now = maxf(0.0, _behind_vehicles(g, spd_now))
	g["s"] = float(g["s"]) + float(dir) * spd_now * dt_s
	g["step_mps"] = spd_now
	var rel := float(g["s"]) - rider_s
	var rel0 := float(g.get("last_rel", rel))
	g["last_rel"] = rel
	# En file près d'un bot (`ahead`, sur l'accotement) et sur un chemin étroit (tous les cas)
	_formation(g, _narrow(float(g["half"])) or (case_name == "ahead" and near) or _vehicle_coming(g), dt_s)
	for m in members:
		_side_step(g, m, dt_s, rider_s, bots, rider_v)
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
			if not g["passed"] and last_rel > overtake_window(float(g["speed_mps"]) - rider_v).y:
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


## Lot AS8 (recette rPK1 du 13/11 : contacts « ahead / core » et « oncoming / core » vers 60 m sur les cols) :
## un groupe du core ne voit pas ceux de l'engine, c'est donc toujours celui qui voit l'autre qui l'évite. Un groupe
## de l'engine rattrapé par un groupe du core plus rapide de son sens, sur sa ligne, s'écarte vers sa gauche (vers
## l'axe, comme pour doubler) de MIN_CENTRE_M dès que le groupe du core est à moins de YIELD_S secondes de sa queue,
## et le laisse passer sur sa place ; s'il ne peut pas s'écarter (cycliste à côté, bot, autre groupe sur la place
## visée) ou qu'il n'est pas encore sorti de la ligne, il roule à la vitesse du groupe du core quand celui-ci est
## à moins de CATCH_M. Il se rabat ensuite sans se poser sur lui (`_side_blocked`). Les groupes d'en face gardent
## leurs écarts. Rend la vitesse du pas.
## Vitesse bornée par celle d'un véhicule du même sens juste devant ou à sa hauteur (lot DB3) : un groupe ne double
## jamais la circulation (traffic_model.gd), ni à droite ni à gauche.
## Garde finale du registre commun (lot DPS1, comme `_guard` de road_cyclists.py) : après que chaque groupe a avancé
## selon sa règle, personne ne chevauche personne. Le cycliste et les bots d'abord, immobiles ; puis les groupes, du plus
## avancé au plus en retrait dans leur sens : un membre qui touche un usager posé devant lui fait reculer son groupe,
## à sa vitesse au plus ; touché par derrière ou par un usager d'en face, il s'écarte à la place libre la plus proche,
## sinon son groupe est avancé devant, à la vitesse de l'autre. Corrections comptées dans `guard_total`.
func _guard(rider_s: float, rider_v: float) -> void:
	if not _guard_needed(rider_s):
		return
	var placed: Array = [[rider_s, rider_lane, rider_v, 1, GUARD_RIDER_WIDTH_M]]   # le cycliste : à MIN_CENTRE_M au moins en travers
	for b in _bot_groups:
		placed.append([float(b["s"]), float(b["members"][0]["lateral"]), float(b["speed_mps"]), int(b["dir"]), GUARD_WIDTH_M])
	var order: Array = groups.duplicate()
	order.sort_custom(func(a, b): return -float(a["dir"]) * float(a["s"]) < -float(b["dir"]) * float(b["s"]))
	for g in order:
		_guard_group(g, placed)
		for m in g["members"]:
			placed.append([float(g["s"]) - float(g["dir"]) * float(m["dl"]), float(m["lateral"]), _step_mps(g), int(g["dir"]), GUARD_WIDTH_M])


## Lot DPS1 : vrai si deux occupants se touchent (au sens de `_touch`) ; sinon la garde ne changerait rien et elle est
## sautée. Comparaisons directes, sans tableau ni tri : quelques groupes près du cycliste, à chaque pas.
func _guard_needed(rider_s: float) -> bool:
	var n := groups.size()
	var lo := PackedFloat64Array()
	var hi := PackedFloat64Array()
	lo.resize(n)
	hi.resize(n)
	for gi in range(n):   # étendue de chaque file le long de la route : les files éloignées ne se comparent pas
		var g: Dictionary = groups[gi]
		var d_lo := INF
		var d_hi := -INF
		for m in g["members"]:
			var ms := float(g["s"]) - float(g["dir"]) * float(m["dl"])
			d_lo = minf(d_lo, ms)
			d_hi = maxf(d_hi, ms)
		lo[gi] = d_lo - GUARD_LEN_M
		hi[gi] = d_hi + GUARD_LEN_M
	for gi in range(n):
		var near_rider := rider_s > lo[gi] and rider_s < hi[gi]
		var near_bot := false
		for b in _bot_groups:
			if float(b["s"]) > lo[gi] and float(b["s"]) < hi[gi]:
				near_bot = true
		var near_h: Array = []
		for hi_ in range(gi + 1, n):
			if lo[hi_] < hi[gi] and hi[hi_] > lo[gi]:
				near_h.append(groups[hi_])
		if not near_rider and not near_bot and near_h.is_empty():
			continue
		var g: Dictionary = groups[gi]
		var g_s := float(g["s"])
		var g_dir := float(g["dir"])
		for m in g["members"]:
			var s := g_s - g_dir * float(m["dl"])
			var lat := float(m["lateral"])
			if near_rider and absf(rider_s - s) < GUARD_LEN_M and absf(rider_lane - lat) < GUARD_RIDER_WIDTH_M:
				return true
			if near_bot:
				for b in _bot_groups:
					if absf(float(b["s"]) - s) < GUARD_LEN_M and absf(float(b["members"][0]["lateral"]) - lat) < GUARD_WIDTH_M:
						return true
			for h in near_h:
				var h_s := float(h["s"])
				var h_dir := float(h["dir"])
				for o in h["members"]:
					if absf(h_s - h_dir * float(o["dl"]) - s) < GUARD_LEN_M and absf(float(o["lateral"]) - lat) < GUARD_WIDTH_M:
						return true
	return false

## Lot DPS1 : vrai si aucun membre d'un autre groupe de son sens n'est sur la ligne `lat` (à moins de MIN_CENTRE_M) à
## hauteur de `g`, de sa queue à sa tête, à SIDE_LOOK_M près.
func _line_free(g: Dictionary, lat: float) -> bool:
	var dir := int(g["dir"])
	var head := float(g["s"]) * float(dir)
	var tail := head - float((g["members"] as Array).size() - 1) * FILE_GAP_M
	for h in groups:
		if is_same(h, g) or int(h["dir"]) != dir:
			continue
		for m in h["members"]:
			var ms := (float(h["s"]) - float(h["dir"]) * float(m["dl"])) * float(h["dir"])
			if ms > tail - SIDE_LOOK_M and ms < head + SIDE_LOOK_M and absf(float(m["lateral"]) - lat) < MIN_CENTRE_M:
				return false
	return true


static func _touch(s: float, lat: float, placed: Array) -> int:
	for i in range(placed.size()):
		var o: Array = placed[i]
		if absf(float(o[0]) - s) < GUARD_LEN_M and absf(float(o[1]) - lat) < float(o[4]):
			return i
	return -1


func _guard_group(g: Dictionary, all_placed: Array) -> void:
	var dir := int(g["dir"])
	var edge := _edge_lateral(_half_at(float(g["s"])))
	# Seuls comptent les occupants à portée : un pas de la garde déplace le groupe de moins de 2 × GUARD_LEN_M, d'où
	# GUARD_REACH_M autour de sa file (même résultat qu'avec tous les occupants, beaucoup moins de calcul).
	var lo := INF
	var hi := -INF
	for m in g["members"]:
		var m_s0 := float(g["s"]) - float(dir) * float(m["dl"])
		lo = minf(lo, m_s0)
		hi = maxf(hi, m_s0)
	lo -= GUARD_REACH_M
	hi += GUARD_REACH_M
	var placed: Array = []
	for o in all_placed:
		if float(o[0]) > lo and float(o[0]) < hi:
			placed.append(o)
	if placed.is_empty():
		return
	for _k in range(GUARD_STEPS):
		var hit_m: Dictionary = {}
		var hit_o: Array = []
		for m in g["members"]:
			var i := _touch(float(g["s"]) - float(dir) * float(m["dl"]), float(m["lateral"]), placed)
			if i >= 0:
				hit_m = m
				hit_o = placed[i]
				break
		if hit_o.is_empty():
			return
		var o_s := float(hit_o[0])
		var o_lat := float(hit_o[1])
		var o_v := float(hit_o[2])
		var o_dir := int(hit_o[3])
		var o_w := float(hit_o[4])
		var m_s := float(g["s"]) - float(dir) * float(hit_m["dl"])
		var ahead := (o_s - m_s) * float(dir)
		guard_total += 1
		var rider_o := o_w == GUARD_RIDER_WIDTH_M
		if o_dir == dir and ahead >= 0.0 and not rider_o:
			g["s"] = float(g["s"]) - float(dir) * (GUARD_LEN_M - ahead + 1e-3)
			g["step_mps"] = minf(_step_mps(g), maxf(0.0, o_v))
			continue
		var best := NAN
		for lat in [o_lat - o_w - 1e-3, o_lat + o_w + 1e-3]:
			if lat >= -edge and lat <= edge and _touch(m_s, lat, placed) < 0 and (
					is_nan(best) or absf(lat - float(hit_m["lateral"])) < absf(best - float(hit_m["lateral"]))):
				best = lat
		if not is_nan(best):
			hit_m["lateral"] = best
			hit_m["lat_v"] = 0.0
		elif o_dir == dir and rider_o and ahead >= 0.0:
			# à côté du cycliste ou juste derrière lui, sans place libre en travers : retenu derrière lui
			g["s"] = float(g["s"]) - float(dir) * (GUARD_LEN_M - ahead + 1e-3)
			g["step_mps"] = minf(_step_mps(g), maxf(0.0, o_v))
		elif o_dir == dir and rider_o:
			g["s"] = float(g["s"]) + float(dir) * (GUARD_LEN_M + ahead + 1e-3)
			g["step_mps"] = maxf(_step_mps(g), o_v)
		elif o_dir == dir:
			# un membre d'un groupe plus avancé, à côté ou derrière lui (files mêlées) : il passe derrière ce membre
			g["s"] = float(g["s"]) - float(dir) * (GUARD_LEN_M - ahead + 1e-3)
			g["step_mps"] = minf(_step_mps(g), maxf(0.0, o_v))
		else:
			return


## Lot DPS1 (hauts plateaux, toundra, forêt boréale) : vrai si un groupe `overtake` qui vient de doubler le cycliste
## se rabattrait derrière un groupe plus lent de son sens, sur la place où il revient, qu'il rattraperait en moins de
## MERGE_LOOK_S : il freinerait net juste devant le cycliste, à moitié rabattu. Il reste sur sa ligne de dépassement.
func _lane_closing(g: Dictionary, spd_now: float) -> bool:
	var back := _edge_lateral(float(g["half"]))
	var dir := int(g["dir"])
	var head := float(g["s"]) * float(dir)
	for h in groups + _bot_groups:
		if is_same(h, g) or int(h["dir"]) != dir:
			continue
		var v_h := _step_mps(h)
		if v_h >= spd_now:
			continue
		var on_back := false
		for m in h["members"]:
			if absf(float(m["lateral"]) - back) < MIN_CENTRE_M:
				on_back = true
				break
		if not on_back:
			continue
		var gap := float(h["s"]) * float(dir) - float((h["members"] as Array).size() - 1) * FILE_GAP_M - head
		if gap > -CATCH_M and gap < CATCH_M + (spd_now - v_h) * MERGE_LOOK_S:
			return true
	return false


## Le cycliste vu comme un groupe d'un cycliste sur sa ligne (`rider_lane`), comme un bot (lot P32), s'il sera à
## hauteur du groupe `g` pendant le dépassement de `ahead` (lot DPS1) : à moins de PASS_START_M de lui maintenant, ou
## rattrapé (ou rattrapant) avant la fin du dépassement, au plus PASS_HORIZON_S, plus SIDE_CROSS_S ; sinon {}.
func _rider_lane_group(g: Dictionary, ahead: Array, rider_s: float, rider_v: float, spd_now: float) -> Dictionary:
	var size := float((g["members"] as Array).size())
	var rel := rider_s - float(g["s"])
	var lo := -(size - 1.0) * FILE_GAP_M - SIDE_LOOK_M - RoadRules.BIKE_LENGTH_M
	var hi := SIDE_LOOK_M + RoadRules.BIKE_LENGTH_M
	var hit := rel >= lo - PASS_START_M and rel <= hi + PASS_START_M
	if not hit:
		var slowest := spd_now
		var span := 0.0
		var first := true
		for h in ahead:
			var v_h := _step_mps(h)
			var d := float(h["s"]) - float(g["s"]) + (float((h["members"] as Array).size()) + size) * FILE_GAP_M
			slowest = v_h if first else minf(slowest, v_h)
			span = d if first else maxf(span, d)
			first = false
		var t_pass := minf(maxf(span, 0.0) / maxf(spd_now - slowest, 0.1), PASS_HORIZON_S) + SIDE_CROSS_S
		var rel_t := rel + (rider_v - spd_now) * t_pass
		hit = minf(rel, rel_t) <= hi and maxf(rel, rel_t) >= lo
	if not hit:
		return {}
	return {"id": "rider", "case": "ahead", "dir": 1, "s": rider_s, "speed_mps": rider_v, "step_mps": rider_v,
		"members": [{"lateral": rider_lane}]}


func _behind_vehicles(g: Dictionary, spd_now: float) -> float:
	if traffic == null:
		return spd_now
	var dir := int(g["dir"])
	for v in traffic.vehicles:
		if (1 if int(v.get("dir", dir)) >= 0 else -1) != dir:
			continue
		var gap := (float(v.get("s", INF)) - float(g["s"])) * float(dir)
		if gap > -VEHICLE_ALONGSIDE_M and gap < VEHICLE_FOLLOW_M:
			spd_now = minf(spd_now, maxf(float(v.get("speed_mps", spd_now)), 0.0))
	return spd_now


func _yield_to_core(g: Dictionary, spd_now: float, rider_s: float, bots: Array) -> float:
	# Lot AS10 : un groupe que le core a donné (sorti de la liste, `_to_decor`) roule aussi chez le core, qui le voit
	# et le fait doubler à sa vraie place : il garde sa vitesse au lieu de rouler à celle du groupe du core qui le double
	# (contacts « core / ahead » vers −60 m à 65 km/h : il restait à côté de lui pendant que le core le rabattait)
	if g.get("core_known", false):
		return spd_now
	var dir := int(g["dir"])
	var members: Array = g["members"]
	var g_head := float(g["s"]) * dir
	var g_tail := g_head - float(members.size() - 1) * FILE_GAP_M
	var chasers := []
	for h in groups:
		if str(h["case"]) != "core" or int(h["dir"]) != dir:
			continue
		var v_h := float(h["speed_mps"])
		var h_head := float(h["s"]) * dir
		var h_tail := h_head - float((h["members"] as Array).size() - 1) * FILE_GAP_M
		if v_h <= spd_now or h_tail > g_head:
			continue                        # pas plus rapide, ou déjà passé devant lui
		if h_head < g_tail - CATCH_M - maxf(0.0, v_h - spd_now) * YIELD_S:
			continue                        # encore loin
		chasers.append(h)
	if chasers.is_empty():
		return spd_now
	# Place visée : à MIN_CENTRE_M à gauche (dans son sens) du plus à gauche des groupes du core qui arrivent
	var yield_lat := _left_most(chasers, dir) - float(dir) * MIN_CENTRE_M
	var cur := _group_lateral(g)
	var lanes := []
	for h in groups:
		if is_same(h, g) or chasers.has(h):
			continue
		if absf(float(h["s"]) - float(g["s"])) < BOT_LOOK_M + float(members.size() + (h["members"] as Array).size()) * FILE_GAP_M:
			for m in h["members"]:
				lanes.append(float(m["lateral"]))
	for b in bots:
		if absf(float(b["s"]) - float(g["s"])) < BOT_LOOK_M + float(members.size()) * FILE_GAP_M:
			lanes.append(float(b["lateral"]))
	if absf(float(g["s"]) - rider_s) < PASS_START_M + float(members.size()) * FILE_GAP_M:
		lanes.append(rider_lane)
	var free := true
	for lat in lanes:
		if absf(yield_lat - float(lat)) < MIN_CENTRE_M - 0.05 or (float(lat) > minf(cur, yield_lat) and float(lat) < maxf(cur, yield_lat)):
			free = false
			break
	if free:
		g["pass_lat"] = minf(yield_lat, float(g.get("pass_lat", yield_lat))) if dir == 1 else maxf(yield_lat, float(g.get("pass_lat", yield_lat)))
	# Tant qu'il est sur la ligne d'un groupe du core tout proche, il roule à sa vitesse
	for h in chasers:
		var h_head := float(h["s"]) * dir
		if h_head >= g_tail - CATCH_M and _lateral_gap(g, h) < MIN_CENTRE_M - 0.05:
			spd_now = maxf(spd_now, float(h["speed_mps"]))
	return spd_now


## Écart à l'axe du membre le plus à gauche (dans le sens `dir`) des groupes `gs`.
static func _left_most(gs: Array, dir: int) -> float:
	var best := INF if dir == 1 else -INF
	for h in gs:
		for m in h["members"]:
			best = minf(best, float(m["lateral"])) if dir == 1 else maxf(best, float(m["lateral"]))
	return best


## Plus petit écart en travers entre un membre de `g` et un membre de `h`.
func _lateral_gap(g: Dictionary, h: Dictionary) -> float:
	var best := INF
	for m in h["members"]:
		best = minf(best, _closest_lateral(g, float(m["lateral"])))
	return best


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
func _side_blocked(g: Dictionary, s: float, lat0: float, lat1: float, rider_s: float, bots: Array, rider_v: float = 0.0) -> bool:
	if absf(lat1 - lat0) < 1e-6:
		return false
	var g_vel := float(g["dir"]) * _step_mps(g)
	var near := []
	if _closing_near(s, g_vel, rider_s, rider_v):
		near.append(rider_lane)
	for i in range(bots.size()):
		var b_v := float(_bot_groups[i]["speed_mps"]) if i < _bot_groups.size() else rider_v
		if _closing_near(s, g_vel, float(bots[i]["s"]), b_v):
			near.append(float(bots[i]["lateral"]))
	for h in groups:
		var h_vel := float(h["dir"]) * _step_mps(h)
		if is_same(h, g) or absf(float(h["s"]) - s) > SIDE_LOOK_M + absf(g_vel - h_vel) * SIDE_CROSS_S + float((h["members"] as Array).size()) * FILE_GAP_M:
			continue
		for m in h["members"]:
			if _closing_near(s, g_vel, float(h["s"]) - float(h["dir"]) * float(m["dl"]), h_vel):
				near.append(float(m["lateral"]))
	for o_lat in near:
		var d1 := absf(lat1 - float(o_lat))
		if d1 < SIDE_CLEAR_M and d1 < absf(lat0 - float(o_lat)):
			return true
	return false


## Lot AS9 : vrai si un autre, à `o_s` et à la vitesse `o_vel` (signée dans le sens du parcours), est à moins de
## SIDE_LOOK_M plus le chemin que lui et le groupe (à `s`, `g_vel`) se rapprochent en SIDE_CROSS_S (à 65 km/h, un
## groupe ralenti à 25 km/h voit le cycliste arriver de 10 m).
static func _closing_near(s: float, g_vel: float, o_s: float, o_vel: float) -> bool:
	var ds := o_s - s
	var closing := (g_vel - o_vel) * (1.0 if ds >= 0.0 else -1.0)
	return absf(ds) < SIDE_LOOK_M + maxf(0.0, closing) * SIDE_CROSS_S


## Lot AS9 : vitesse du dernier pas d'un groupe, sa vitesse tant qu'il n'a pas roulé.
static func _step_mps(g: Dictionary) -> float:
	return float(g.get("step_mps", g["speed_mps"]))

## Lot AS10 (banc rAS10 du volcan) : vitesse d'un groupe `h` pour celui qui le rattrape (`g`) : devant lui, celle où il
## roule (retenu derrière un autre, 4 m/s de moins que sa vitesse voulue) ; derrière, sa vitesse voulue (pas de
## ralentissement en cascade de deux groupes qui se règlent l'un sur l'autre). Comme `speed_of` du core.
static func _speed_of(g: Dictionary, h: Dictionary) -> float:
	return _step_mps(h) if (float(h["s"]) - float(g["s"])) * int(g["dir"]) > 0.0 else float(h["speed_mps"])

## Plus petit écart latéral d'un membre du groupe `g` à `lat`.
func _closest_lateral(g: Dictionary, lat: float) -> float:
	var best := INF
	for m in g["members"]:
		best = minf(best, absf(float(m["lateral"]) - lat))
	return best


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


## Lot AS11 : fenêtre où un groupe `overtake` double le cycliste hors de sa ligne (road_cyclists.overtake_window).
static func overtake_window(closing_mps: float, lateral_m: float = MIN_CENTRE_M) -> Vector2:
	return RoadRules.pass_window(RoadRules.BIKE_LENGTH_M, RoadRules.BIKE_LENGTH_M, closing_mps, maxf(lateral_m, MIN_CENTRE_M),
		SIDE_SPEED_MPS)


## Abscisse et écart latéral de chaque cycliste : [{group, member, s, lateral, dir}].
func riders() -> Array:
	var out := []
	for g in groups:
		for m in g["members"]:
			out.append({"group": g, "member": m, "id": str(m["id"]), "s": float(g["s"]) - float(g["dir"]) * float(m["dl"]),
				"lateral": float(m["lateral"]), "dir": int(g["dir"]), "yaw": side_yaw(g, m)})
	return out


## Lot AS7 : liste `riders` du core (une trame sur trois, `seq` de la trame), reprise une seule fois par trame.
## Les cyclistes reçus d'un même groupe (`c<case>-<rang>`) forment un groupe `core` de même `id` que celui de
## l'engine, extrapolé jusqu'à la liste suivante ; le membre de l'engine de même `id` lui laisse sa place (et sa
## tenue, son pédalier). Un cycliste, de l'engine ou du core, absent d'une liste qui n'est pas pleine à moins de
## NEAR_M − CORE_MARGIN_M n'est plus sur la route ; plus loin, un groupe que le core ne suit plus reste au décor
## (`_to_decor` : groupe de l'engine, à sa dernière vitesse) jusqu'à sortir de la fenêtre.
## Lot AS9 (banc r879b du 14/11 sur le volcan, roulé à 50–65 km/h : contacts « overtake / core » à −61 m et
## « core / cycliste » à −1 m) :
## - un groupe dont la liste ne donne qu'une partie (à cheval sur NEAR_M) appartient tout entier au core : ses
##   membres hors liste, ceux de la copie de l'engine comme ceux que le core donnait avant, gardent leur place
##   dans le groupe par rapport à un membre reçu (`_anchor`), au lieu de rester là où l'engine les faisait
##   rouler (pas au même endroit que le core : la tête du core se posait sur le 2e de l'engine) ;
## - `core_s` : abscisse du cycliste dans la trame ; le cycliste affiché (`rider_s`, interpolé par
##   camera_follow.gd) n'est pas au même endroit, chaque cycliste du core garde donc son écart du core au
##   cycliste, pas sa position absolue (comme les véhicules, traffic_model.sync_core), et n'est pas extrapolé
##   une fois de plus à l'image de sa reprise (`fresh`).
## Lot AS11 (révision 1.20) : `part` et `parts` (`road_part` de la trame) : la liste donne des groupes entiers ;
## les groupes qu'elle ne donne pas attendent la fin du tour, où ceux qu'aucune partie n'a donnés partent.
func sync_core(list: Array, seq: int, rider_s: float, core_s: float = NAN, part: int = -1, parts: int = 0) -> void:
	if seq == _core_seq:
		return
	_core_seq = seq
	if parts > 0 and not core_full:
		core_full = true
		groups = groups.filter(func(g): return str(g["case"]) == "core")   # plus de groupe tiré par l'engine
	var shift := 0.0
	if not is_nan(core_s) and absf(rider_s - core_s) < CORE_SHIFT_MAX_M:
		shift = rider_s - core_s
	var full := list.size() >= CORE_LIST_MAX
	var keep_missing := parts == 0      # lot AS11 : en parties, un groupe arrive entier, un membre absent est parti
	var by_id := {}
	var decor_by_id := {}
	for g in groups:
		if str(g["case"]) == "core":
			by_id[str(g["id"])] = g
		else:
			decor_by_id[str(g["id"])] = g
	var items_of := {}                # groupe -> cyclistes reçus
	for item in list:
		if typeof(item) != TYPE_DICTIONARY or str(item.get("id", "")) == "":
			continue
		var gid := str(item["id"]).get_slice("-", 0)
		if not items_of.has(gid):
			items_of[gid] = []
		items_of[gid].append(item)
	var seen := {}
	var added := []
	for gid in items_of:
		var items: Array = items_of[gid]
		var cg: Dictionary = by_id.get(gid, {})
		if cg.is_empty():
			cg = {"id": gid, "case": "core", "dir": 1, "s": rider_s, "speed_mps": 0.0, "members": [], "salut": false,
				"passed": true, "speed_at": INF, "behind_t": 0.0, "best_rel": -INF, "side": "right"}
			added.append(cg)
		var eg: Dictionary = decor_by_id.get(gid, {})
		var dir := 1 if int(items[0].get("dir", 1)) >= 0 else -1
		var head := -INF
		for item in items:
			head = maxf(head, (float(item.get("s", rider_s)) + shift) * dir)
		var own := {}
		for m in cg["members"]:
			own[str(m["id"])] = m
		# Écart en file (dl) d'un membre reçu avant et après la reprise, dans le groupe du core et dans la copie
		# de l'engine : les membres hors liste en gardent autant (`_anchor`)
		var shift_core := NAN
		var shift_decor := NAN
		var members := []
		for item in items:
			var id := str(item["id"])
			seen[id] = true
			var item_s := float(item.get("s", rider_s)) + shift
			var cm: Dictionary = own.get(id, {})
			var from_decor := false
			if cm.is_empty() and not eg.is_empty():
				cm = _take_member_from(eg, id)
				from_decor = not cm.is_empty()
			if cm.is_empty():
				cm = _take_member(id)
			var lane := float(item.get("lane_m", _edge_lateral(_half_at(item_s))))
			if cm.is_empty():
				var look := int(item.get("look", 0))
				cm = {"jersey": look % 8, "look": (look >> 4) & 0xFFFF, "phase": _u(VegetationPlacer._mix(look)), "id": id,
					"lateral": lane, "lat_v": 0.0}
			# Écart du core repris sans saut : visé, extrapolé à sa vitesse latérale entre deux listes (_move)
			var rate := 0.0
			var since := _clock - float(cg.get("sync_at", -INF))
			if cm.has("lane_seen") and since > 1e-3:
				rate = clampf((lane - float(cm["lane_seen"])) / since, -CORE_LANE_RATE_MAX, CORE_LANE_RATE_MAX)
			cm["lane_seen"] = lane
			cm["lane_core"] = lane
			cm["lane_rate"] = rate
			var dl := head - item_s * dir
			if cm.has("dl"):
				if own.has(id) and is_nan(shift_core):
					shift_core = dl - float(cm["dl"])
				elif from_decor and is_nan(shift_decor):
					shift_decor = dl - float(cm["dl"])
			cm["dl"] = dl
			cm["col"] = 0
			members.append(cm)
		for m in cg["members"]:
			if keep_missing and not seen.has(str(m["id"])) and _still_on_road(cg, m, rider_s, full):
				_anchor(m, shift_core, float(cg["s"]) * dir, head)
				members.append(m)
		if not eg.is_empty():
			for m in eg["members"]:
				if keep_missing and not seen.has(str(m["id"])) and _still_on_road(eg, m, rider_s, full):
					_anchor(m, shift_decor, float(eg["s"]) * int(eg["dir"]), head)
					m["col"] = 0
					m.erase("col0")
					m.erase("dl0")
					members.append(m)
			eg["members"] = []              # tout le groupe est au core
		# Tête du groupe : le premier de la file, reçu ou non ; membres rangés de la tête à la queue (`_formation`)
		var lead := 0.0
		for m in members:
			lead = minf(lead, float(m["dl"]))
		for m in members:
			m["dl"] = float(m["dl"]) - lead
		head -= lead
		members.sort_custom(func(a, b): return float(a["dl"]) < float(b["dl"]))
		cg["members"] = members
		cg["dir"] = dir
		cg["s"] = head * dir
		cg["speed_mps"] = float(items[0].get("v", 0.0))
		cg["core"] = true
		cg["sync_at"] = _clock
		cg["fresh"] = true              # déjà à sa place de cette image : pas extrapolé une fois de plus
	var kept := []
	if parts > 0:
		for gid in items_of:
			_cycle_seen[gid] = true
		var last := part >= parts - 1
		for g in groups:
			var gid := str(g["id"])
			if items_of.has(gid) or (not last or _cycle_seen.has(gid) or _cycle_prev.has(gid)) and str(g["case"]) == "core":
				kept.append(g)
		if last:
			_cycle_prev = _cycle_seen
			_cycle_seen = {}
		groups = kept + added
		return
	for g in groups:
		var is_core := str(g["case"]) == "core"
		if is_core and items_of.has(str(g["id"])):
			kept.append(g)
			continue
		var members := []
		for m in g["members"]:
			if not seen.has(str(m["id"])) and _still_on_road(g, m, rider_s, full):
				members.append(m)
		if members.is_empty():
			continue
		g["members"] = members
		if is_core:
			_to_decor(g)                    # sorti de la liste : décor lointain, aux règles de l'engine
		kept.append(g)
	groups = kept + added


## Lot AS9 : écart en file d'un membre hors liste repris dans le groupe du core de tête `head` (dans son sens) :
## décalé de `dl_shift` comme les membres reçus de son ancien groupe, sinon à sa place sur la route (tête de
## l'ancien groupe `old_head`, dans son sens).
static func _anchor(m: Dictionary, dl_shift: float, old_head: float, head: float) -> void:
	if not is_nan(dl_shift):
		m["dl"] = float(m["dl"]) + dl_shift
	else:
		m["dl"] = head - (old_head - float(m["dl"]))


## Groupe du core sorti de la liste : il redevient un groupe de l'engine (`ahead` dans le sens du parcours,
## `oncoming` en face), à sa dernière vitesse tenue à puissance constante, pour qu'il double ou laisse passer
## les autres groupes au lieu de rouler au travers (banc E1 du 5/11 : contacts « core / ahead » à 2,5 m de l'axe).
func _to_decor(g: Dictionary) -> void:
	g.erase("core")
	g["core_known"] = true              # lot AS10 : le core le fait encore rouler (`_yield_to_core`)
	var dir := int(g["dir"])
	var v := float(g["speed_mps"])
	g["case"] = "oncoming" if dir < 0 else "ahead"
	g["flat_mps"] = v
	g["delta_mps"] = 0.0
	g["power_w"] = power_for(v)
	g["speed_at"] = -INF
	g["passed"] = true
	g["side"] = "left" if dir < 0 else "right"
	for m in g["members"]:
		m["col"] = 0
		m.erase("col0")
		m.erase("dl0")
		m.erase("lane_core")
		m.erase("lane_seen")
		m.erase("lane_rate")


## Faux si le core dit que le membre `m` du groupe `g` n'est plus sur la route : liste pas pleine et membre à moins
## de NEAR_M − CORE_MARGIN_M du cycliste.
func _still_on_road(g: Dictionary, m: Dictionary, rider_s: float, full: bool) -> bool:
	var s_m := float(g["s"]) - float(g["dir"]) * float(m["dl"])
	return full or absf(s_m - rider_s) >= NEAR_M - CORE_MARGIN_M


## Membre d'identifiant `id` du groupe `g`, retiré de ce groupe (vide s'il n'y est pas).
static func _take_member_from(g: Dictionary, id: String) -> Dictionary:
	var members: Array = g["members"]
	for i in range(members.size()):
		if str(members[i]["id"]) == id:
			var m: Dictionary = members[i]
			members.remove_at(i)
			return m
	return {}


## Membre de l'engine d'identifiant `id`, retiré de son groupe (vide si l'engine ne l'a pas tiré).
func _take_member(id: String) -> Dictionary:
	for g in groups:
		if str(g["case"]) == "core":
			continue
		var members: Array = g["members"]
		for i in range(members.size()):
			if str(members[i]["id"]) == id:
				var m: Dictionary = members[i]
				members.remove_at(i)
				return m
	return {}


## Lacet (rad, vers sa gauche positif) d'un membre qui s'écarte ou se rabat : sa trajectoire, de sa vitesse latérale
## et de sa vitesse, au plus 0,35 rad (20°).
static func side_yaw(g: Dictionary, m: Dictionary) -> float:
	var v := maxf(float(g.get("speed_mps", 0.0)), 1.0)
	return clampf(-float(m.get("lat_v", 0.0)) * float(g.get("dir", 1)) / v, -0.35, 0.35)


## Position d'un membre dans le monde.
func world_position(g: Dictionary, m: Dictionary) -> Vector3:
	return world_transform(float(g["s"]) - float(g["dir"]) * float(m["dl"]), float(m["lateral"]), int(g["dir"])).origin


## Position, cap et tangage (pente de la route affichée) d'un cycliste (face vers +z local, comme people_mesh.gd) à `s`, `lateral`, dans le sens `dir`.
func world_transform(s: float, lateral: float, dir: int, yaw: float = 0.0) -> Transform3D:
	var smp: Dictionary = route.sample(clampf(s, 0.0, route.length_m))
	var h := deg_to_rad(float(smp["heading_deg"]))
	var fwd := Vector3(sin(h), 0.0, -cos(h))
	var right := Vector3(cos(h), 0.0, sin(h))
	var pos := Vector3(float(smp["x"]), float(smp["y"]), float(smp["z"])) + right * lateral
	var facing := fwd * float(dir)
	# Tangage selon la pente affichée dans le sens de marche (avant vers +z local : rotation −x = nez levé)
	var pitch: float = route.display_pitch(s) * float(dir)
	# Lacet du rabattement (`yaw`, vers la gauche du sens de marche positif) : cap tourné autour de la verticale
	return Transform3D(Basis(Vector3.UP, atan2(facing.x, facing.z) + yaw) * Basis(Vector3.RIGHT, -pitch), pos)


## Cadence (tr/min) à `v` (m/s) avec le développement DEVELOPMENT_M ; roue libre au-delà de 55 km/h.
static func cadence_rpm(v_mps: float) -> float:
	if v_mps > 55.0 / 3.6:
		return 0.0
	return v_mps / DEVELOPMENT_M * 60.0
