extends RefCounted

## Passants des villages et de la campagne (Lot P21), sans aucun nœud ; affichés par crowd_renderer.gd
## en mode « passants ». Pas de class_name : charger par preload("res://scripts/passersby_model.gd").
##
## Placement déterministe (graine du parcours), par cases de CELL_M le long de la route :
## - village (un bâtiment à moins de VILLAGE_M de la route au milieu de la case) : VILLAGE_PER_CELL.x à
##   VILLAGE_PER_CELL.y personnes par case ;
## - campagne : une personne tous les COUNTRY_GAP_M.x à COUNTRY_GAP_M.y mètres (écart tiré à chaque fois) ;
## - rien dans les zones de spectateurs de P15 (dernier kilomètre des grandes montées), ni dans l'eau ;
##   écart au bord de la chaussée de EDGE_M.x à EDGE_M.y, de l'autre côté si le premier est dans l'eau.
## Rôles (ROLES_VILLAGE, ROLES_COUNTRY) : `walker` et `dog_walker` font des allers-retours sur un segment
## de WALK_LEN_M le long de la route ; `jogger` aussi, plus vite et plus loin, d'abord en sens inverse du
## cycliste (JOGGER_ONCOMING) ; `sitter`, `gardener`, `farmer` et `kid` restent sur place.
## `people` : `[{s, side, role, village, pos, yaw, color, phase, waves, delay, path, len, speed, dir, u0, du}]`,
## trié par `s`.
##
## `update(rider_pos, rider_s, now_s, beep_active)` une fois par image, seulement pour les personnes dont
## le segment est à moins de RESET_M de `rider_s` (dichotomie) : une partie (`waves`) salue une fois par
## passage quand le cycliste est à moins de WAVE_M (après un délai propre), pendant WAVE_S ; le passage se
## termine au-delà de RESET_M. Un salut peut lancer un son (`sound` dans le résultat) : au plus un toutes les
## SOUND_GAP_S, jamais pendant un bip du Click (`beep_active`), choisi selon le rôle (SOUND_OF).
## `visible(cam_pos, cam_s, now_s, budget)` : les personnes les plus proches de la caméra, au plus
## `budget`, avec leur position animée (et celle du chien), l'animation (ANIM) et l'état « salue ».
## `crowd_zones(climbs)` : zones de P15 à passer à `configure` (`exclude`).

const CrowdModel := preload("res://scripts/crowd_model.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")

const CELL_M := 100.0
const VILLAGE_M := 60.0
const VILLAGE_PER_CELL := Vector2i(2, 6)
const COUNTRY_GAP_M := Vector2(300.0, 800.0)
const EDGE_M := Vector2(1.0, 6.0)
const DEFAULT_ROAD_WIDTH_M := 6.0
const WALK_LEN_M := Vector2(20.0, 60.0)
const JOG_LEN_M := Vector2(60.0, 120.0)
const PATH_STEP_M := 10.0
const SPEED_MPS := {"walker": 1.2, "dog_walker": 1.0, "jogger": 2.8}
const JOGGER_ONCOMING := 0.8
const DOG_BEHIND_M := 1.4
const WAVE_M := 15.0
const RESET_M := 30.0
const WAVE_SHARE := 0.6
const WAVE_S := 2.5
const MAX_DELAY_S := 0.5
const VIEW_M := 250.0
const RESELECT_M := 20.0
const RESELECT_S := 1.0
const FAR_M := 40.0
const FAR_EVERY := 3
const SOUND_GAP_S := 20.0
const SOUND_CHANCE := 0.5
const SOUND_M := 30.0
const COLORS := 8

## Rôles et poids : au village, en campagne.
const ROLES_VILLAGE := [["walker", 0.3], ["dog_walker", 0.12], ["sitter", 0.15], ["gardener", 0.15], ["kid", 0.2], ["jogger", 0.08]]
const ROLES_COUNTRY := [["walker", 0.25], ["dog_walker", 0.3], ["jogger", 0.3], ["farmer", 0.15]]
## Animation de crowd.gdshader (INSTANCE_CUSTOM.z), voir anim_of.
const ANIM := {"stand": 0, "walk": 1, "run": 2, "sit": 3, "garden": 4, "hop": 5, "dog": 6}
const SOUND_OF := {"kid": "kid_laugh", "dog_walker": "dog_bark", "jogger": "voice_allez", "farmer": "voice_allez",
	"walker": "voice_allez", "sitter": "voice_bonjour", "gardener": "voice_bonjour"}

var people: Array = []
var states: Dictionary = {}       # indice -> {"near", "since", "done", "wave_at"}
var last_sound_s: float = -INF
var _seed := 0
var _sound_count := 0
var _entries: Array = []         # entrées de la dernière sélection (visible)
var selection_serial := 0        # change à chaque nouvelle sélection
var dog_count := 0
var bench_count := 0
var _active: Array = []          # entrées qui peuvent changer : marcheurs et personnes qui saluent
var _frame := 0
var _sel_cam := Vector3(INF, INF, INF)
var _sel_t := -INF
var _sel_budget := -1


static func _u(h: int) -> float:
	return float(h & 0xFFFFFF) / 16777216.0


static func _pick(table: Array, u: float) -> String:
	var acc := 0.0
	for e in table:
		acc += float(e[1])
		if u < acc:
			return str(e[0])
	return str(table[-1][0])


## Centres des bâtiments (x, z) rangés dans une grille de CELL_M de côté.
static func _building_grid(buildings: Array) -> Dictionary:
	var grid := {}
	for b in buildings:
		if typeof(b) != TYPE_DICTIONARY or typeof(b.get("outer")) != TYPE_ARRAY or b["outer"].is_empty():
			continue
		var c := Vector2.ZERO
		for p in b["outer"]:
			c += Vector2(float(p[0]), float(p[1]))
		c /= float(b["outer"].size())
		var key := Vector2i(int(floor(c.x / CELL_M)), int(floor(c.y / CELL_M)))
		if not grid.has(key):
			grid[key] = []
		grid[key].append(c)
	return grid


static func _near_building(grid: Dictionary, p: Vector3) -> bool:
	var q := Vector2(p.x, p.z)
	var k := Vector2i(int(floor(q.x / CELL_M)), int(floor(q.y / CELL_M)))
	for dx in range(-1, 2):
		for dz in range(-1, 2):
			for c in grid.get(k + Vector2i(dx, dz), []):
				if (c as Vector2).distance_to(q) < VILLAGE_M:
					return true
	return false


## Zones de spectateurs de P15 (`[[s0, s1]]`) pour les montées de climb_detector.gd.
static func crowd_zones(climbs: Array, crowd_all_climbs: bool = false) -> Array:
	var out := []
	for c in climbs:
		if float(c["length_m"]) < CrowdModel.MIN_CLIMB_M and not crowd_all_climbs:
			continue
		var summit := float(c["summit_s"])
		out.append([maxf(float(c["start_s"]), summit - CrowdModel.ZONE_M), summit])
	return out


func configure(route, buildings: Array = [], water: Dictionary = {}, seed: int = 0,
		road_width_m: float = DEFAULT_ROAD_WIDTH_M, exclude: Array = []) -> void:
	people.clear()
	states.clear()
	_entries = []
	_active = []
	_sel_budget = -1
	last_sound_s = -INF
	_sound_count = 0
	_seed = seed
	if route == null:
		return
	var grid := _building_grid(buildings)
	var half := road_width_m * 0.5
	var n_cells := int(ceil(route.length_m / CELL_M))
	var next_country := COUNTRY_GAP_M.x * 0.5 + (COUNTRY_GAP_M.y - COUNTRY_GAP_M.x) * 0.5 * _u(VegetationPlacer.hash3(seed, 911, 3))
	var serial := 0
	for k in range(n_cells):
		var c0 := k * CELL_M
		var c1 := minf((k + 1) * CELL_M, route.length_m)
		var mid: Dictionary = route.sample((c0 + c1) * 0.5)
		var village := _near_building(grid, Vector3(mid["x"], 0.0, mid["z"]))
		var spots: Array = []
		if village:
			var hc := VegetationPlacer.hash3(seed ^ 0x7A55, k, 1)
			var n := VILLAGE_PER_CELL.x + int(_u(hc) * float(VILLAGE_PER_CELL.y - VILLAGE_PER_CELL.x + 1))
			for j in range(mini(n, VILLAGE_PER_CELL.y)):
				spots.append(c0 + (j + _u(VegetationPlacer._mix(hc + 31 * (j + 1)))) * (c1 - c0) / float(n))
			next_country = c1 + COUNTRY_GAP_M.x
		else:
			while next_country < c1:
				spots.append(next_country)
				next_country += lerpf(COUNTRY_GAP_M.x, COUNTRY_GAP_M.y, _u(VegetationPlacer.hash3(seed ^ 0x0C7, serial, 5)))
				serial += 1
		for s in spots:
			if _excluded(float(s), exclude):
				continue
			var p := _make_person(route, float(s), village, half, water)
			if not p.is_empty():
				people.append(p)
	people.sort_custom(func(a, b): return a["s"] < b["s"])


static func _excluded(s: float, exclude: Array) -> bool:
	for z in exclude:
		if s >= float(z[0]) and s <= float(z[1]):
			return true
	return false


func _make_person(route, s: float, village: bool, half: float, water: Dictionary) -> Dictionary:
	var h := VegetationPlacer.hash3(_seed ^ 0x9A55, int(round(s * 10.0)), 2)
	var role := _pick(ROLES_VILLAGE if village else ROLES_COUNTRY, _u(h))
	var edge := lerpf(EDGE_M.x, EDGE_M.y, _u(VegetationPlacer._mix(h + 1)))
	if role == "farmer" or role == "gardener":
		edge = lerpf(3.5, EDGE_M.y, _u(VegetationPlacer._mix(h + 1)))
	var first_side := -1 if _u(VegetationPlacer._mix(h + 2)) < 0.5 else 1
	var moving := SPEED_MPS.has(role)
	var length := 0.0
	if moving:
		var range_m: Vector2 = JOG_LEN_M if role == "jogger" else WALK_LEN_M
		length = minf(lerpf(range_m.x, range_m.y, _u(VegetationPlacer._mix(h + 3))), maxf(route.length_m - s, 0.0))
		if length < PATH_STEP_M:
			moving = false
			role = "sitter" if village else "farmer"
	for side in [first_side, -first_side]:
		var lateral := float(side) * (half + edge)
		var path := PackedVector3Array()
		var steps := int(ceil(length / PATH_STEP_M)) if moving else 0
		var dry := true
		for i in range(steps + 1):
			var si := s + (length * float(i) / float(steps) if steps > 0 else 0.0)
			var smp: Dictionary = route.sample(si)
			var hd := deg_to_rad(float(smp["heading_deg"]))
			var pt := Vector3(smp["x"], smp["y"], smp["z"]) + Vector3(cos(hd), 0.0, sin(hd)) * lateral
			if CrowdModel._in_water(pt, water):
				dry = false
				break
			path.append(pt)
		if not dry:
			continue
		var to_road := Vector3(path[0].x, 0.0, path[0].z)
		var c: Vector3 = route.sample_point(s)
		to_road = Vector3(c.x - to_road.x, 0.0, c.z - to_road.z).normalized()
		var dir := 1.0
		if role == "jogger":
			dir = -1.0 if _u(VegetationPlacer._mix(h + 4)) < JOGGER_ONCOMING else 1.0
		elif moving:
			dir = -1.0 if _u(VegetationPlacer._mix(h + 4)) < 0.5 else 1.0
		return {
			"s": s, "side": side, "role": role, "village": village, "edge_m": edge,
			"pos": path[0], "yaw": atan2(to_road.x, to_road.z) + (_u(VegetationPlacer._mix(h + 5)) - 0.5) * 0.8,
			"color": int(VegetationPlacer._mix(h + 6) % COLORS),
			"phase": _u(VegetationPlacer._mix(h + 7)),
			"waves": _u(VegetationPlacer._mix(h + 8)) < WAVE_SHARE,
			"delay": MAX_DELAY_S * _u(VegetationPlacer._mix(h + 9)),
			"path": path, "len": length if moving else 0.0,
			"speed": float(SPEED_MPS.get(role, 0.0)) if moving else 0.0, "dir": dir,
			"u0": _start_offset(length if moving else 0.0, _u(VegetationPlacer._mix(h + 7)), dir),
			"du": dir * float(SPEED_MPS.get(role, 0.0)) if moving else 0.0,
		}
	return {}


static func _start_offset(length: float, phase: float, dir: float) -> float:
	return length - phase * length if dir < 0.0 else phase * length


## Abscisse brute de la personne sur son segment (avant les allers-retours) : `u0 + du × t`.
static func _raw_offset(p: Dictionary, now_s: float) -> float:
	return float(p["u0"]) + float(p["du"]) * now_s


## Abscisse de la personne sur son segment (0 à `len`) : allers-retours.
static func path_offset(p: Dictionary, now_s: float) -> float:
	var length := float(p["len"])
	if length <= 0.0:
		return 0.0
	return pingpong(_raw_offset(p, now_s), length)


## Sens de marche courant (+1 vers les `s` croissants, -1 sinon, 0 à l'arrêt).
static func heading_sign(p: Dictionary, now_s: float) -> float:
	var length := float(p["len"])
	if length <= 0.0:
		return 0.0
	var u := _raw_offset(p, now_s)
	# Allers (tranches paires de `u`) et retours (impaires) ; `u` varie dans le sens de `dir`
	return (1.0 if int(floor(u / length)) % 2 == 0 else -1.0) * float(p["dir"])


## Point du segment à l'abscisse `off` (interpolé entre les points du chemin).
static func path_point(p: Dictionary, off: float) -> Vector3:
	var path: PackedVector3Array = p["path"]
	if path.size() < 2:
		return path[0]
	var f := clampf(off / float(p["len"]), 0.0, 1.0) * float(path.size() - 1)
	var i := mini(int(f), path.size() - 2)
	return path[i].lerp(path[i + 1], f - float(i))


static func position_at(p: Dictionary, now_s: float) -> Vector3:
	if float(p["len"]) <= 0.0:
		return p["pos"]
	return path_point(p, path_offset(p, now_s))


## Premier indice de `people` dont `s` est au moins `s_min`.
func _lower_bound(s_min: float) -> int:
	var lo := 0
	var hi := people.size()
	while lo < hi:
		var mid := (lo + hi) >> 1
		if float(people[mid]["s"]) < s_min:
			lo = mid + 1
		else:
			hi = mid
	return lo


## Une fois par image. Rend `{"sound": sorte ou "", "pos": Vector3}`.
func update(rider_pos: Vector3, rider_s: float, now_s: float, beep_active: bool = false) -> Dictionary:
	var out := {"sound": "", "pos": Vector3.ZERO}
	# Hors de portée (en abscisse) : passage terminé, l'état est oublié
	for idx in states.keys():
		var q: Dictionary = people[idx]
		var dq := rider_s - float(q["s"])
		if dq < -RESET_M or dq > float(q["len"]) + RESET_M:
			states.erase(idx)
	var i := _lower_bound(rider_s - RESET_M - JOG_LEN_M.y)
	while i < people.size() and float(people[i]["s"]) <= rider_s + RESET_M:
		var p: Dictionary = people[i]
		var ds := rider_s - float(p["s"])
		if not bool(p["waves"]) or ds < -RESET_M or ds > float(p["len"]) + RESET_M:
			i += 1
			continue
		var pos := position_at(p, now_s)
		var d := Vector2(pos.x - rider_pos.x, pos.z - rider_pos.z).length()   # à l'horizontale
		var st: Dictionary = states.get(i, {})
		if st.is_empty():
			st = {"near": false, "since": now_s, "done": false, "wave_at": NAN}
			states[i] = st
		var near := d < WAVE_M
		if near != bool(st["near"]):
			st["near"] = near
			st["since"] = now_s
		if d > RESET_M:
			st["done"] = false    # passage terminé : la personne pourra saluer au prochain
		if near and not bool(st["done"]) and now_s - float(st["since"]) >= float(p["delay"]):
			st["done"] = true
			st["wave_at"] = now_s
			if out["sound"] == "" and not beep_active and now_s - last_sound_s >= SOUND_GAP_S and d < SOUND_M:
				var hs := VegetationPlacer.hash3(_seed ^ 0x50D, i, _sound_count + int(now_s))
				if _u(hs) < SOUND_CHANCE:
					out["sound"] = SOUND_OF.get(str(p["role"]), "voice_allez")
					out["pos"] = pos
					last_sound_s = now_s
					_sound_count += 1
		i += 1
	return out


## Vrai si la personne `i` salue à l'instant `now_s`.
func is_waving(i: int, now_s: float) -> bool:
	var st: Dictionary = states.get(i, {})
	if st.is_empty() or is_nan(float(st["wave_at"])):
		return false
	return now_s - float(st["wave_at"]) < WAVE_S


## Animation de la personne `p` (clé de ANIM).
static func anim_of(p: Dictionary) -> String:
	match str(p["role"]):
		"walker", "dog_walker":
			return "walk"
		"jogger":
			return "run"
		"sitter":
			return "sit"
		"gardener", "farmer":
			return "garden"
		"kid":
			return "hop"
	return "stand"


## Tri des personnes à moins de VIEW_M en `s` par distance à la caméra ; garde les `budget` premières
## et prépare leurs entrées (places des chiens et des bancs comprises).
func _reselect(cam_pos: Vector3, cam_s: float, now_s: float, budget: int) -> void:
	var cand := []
	var i := _lower_bound(cam_s - VIEW_M - JOG_LEN_M.y)
	while i < people.size() and float(people[i]["s"]) <= cam_s + VIEW_M:
		cand.append([position_at(people[i], now_s).distance_squared_to(cam_pos), i])
		i += 1
	cand.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
	_entries = []
	_active = []
	dog_count = 0
	bench_count = 0
	for j in range(mini(budget, cand.size())):
		var idx: int = cand[j][1]
		var p: Dictionary = people[idx]
		var role := str(p["role"])
		var e := {"i": idx, "p": p, "pos": position_at(p, now_s), "yaw": float(p["yaw"]), "anim": anim_of(p), "wave": false,
			"moving": float(p["len"]) > 0.0, "dirty": false, "fresh": true, "dog": -1, "bench": -1, "turns": role != "sitter"}
		if role == "dog_walker" and bool(e["moving"]):
			e["dog"] = dog_count
			e["dog_pos"] = p["pos"]
			e["dog_yaw"] = float(p["yaw"])
			dog_count += 1
		if role == "sitter":
			e["bench"] = bench_count
			bench_count += 1
		_entries.append(e)
		if bool(e["moving"]) or bool(p["waves"]):
			_active.append(e)
	_sel_cam = cam_pos
	_sel_t = now_s
	_sel_budget = budget
	selection_serial += 1


## Les `budget` personnes les plus proches de `cam_pos` (à moins de VIEW_M en `s` de `cam_s`) :
## `[{i, pos, yaw, anim, wave, moving, dirty, dog, dog_pos, dog_yaw, bench}]` ; `dog` et `bench` : place du
## chien (promeneurs) et du banc (personnes assises) dans leur MultiMesh, -1 sinon. Le tri n'est refait
## que tous les RESELECT_M de caméra ou toutes les RESELECT_S (`selection_serial` change alors) ; entre
## deux, les mêmes entrées sont mises à jour sur place et `dirty` marque celles qui ont changé (marcheurs,
## personnes qui saluent).
func visible(cam_pos: Vector3, cam_s: float, now_s: float, budget: int) -> Array:
	if budget <= 0:
		if not _entries.is_empty() or _sel_budget != 0:
			_entries = []
			_active = []
			dog_count = 0
			bench_count = 0
			_sel_budget = 0
			selection_serial += 1
		return _entries
	if budget != _sel_budget or cam_pos.distance_to(_sel_cam) > RESELECT_M or absf(now_s - _sel_t) > RESELECT_S:
		_reselect(cam_pos, cam_s, now_s, budget)
	var far2 := FAR_M * FAR_M
	_frame += 1
	for e in _active:
		var p: Dictionary = e["p"]
		var moving: bool = e["moving"]
		var wave := false
		if p["waves"] and not states.is_empty():
			wave = is_waving(e["i"], now_s)
		var dirty: bool = wave != e["wave"]
		e["wave"] = wave
		# Au-delà de FAR_M, un marcheur n'avance qu'une image sur FAR_EVERY (à tour de rôle)
		if moving and (e["fresh"] or (e["i"] + _frame) % FAR_EVERY == 0 or (e["pos"] as Vector3).distance_squared_to(cam_pos) < far2):
			var length: float = p["len"]
			var u: float = p["u0"] + p["du"] * now_s
			var m := int(floor(u / length))
			var off := u - m * length
			var sg: float = p["dir"]
			if m % 2 != 0:
				off = length - off
				sg = -sg
			var path: PackedVector3Array = p["path"]
			var f := off / length * float(path.size() - 1)
			var k := mini(int(f), path.size() - 2)
			var a := path[k]
			var b := path[k + 1]
			e["pos"] = a.lerp(b, f - float(k))
			e["yaw"] = atan2((b.x - a.x) * sg, (b.z - a.z) * sg)
			if e["dog"] >= 0:
				# Le chien suit son maître sur le même chemin
				e["dog_pos"] = path_point(p, clampf(off - sg * DOG_BEHIND_M, 0.0, length))
				e["dog_yaw"] = e["yaw"]
			e["fresh"] = false
			dirty = true
		if wave and e["turns"]:
			var to_rider: Vector3 = cam_pos - (e["pos"] as Vector3)
			e["yaw"] = atan2(to_rider.x, to_rider.z)   # tourne la tête (et le corps) vers le cycliste
			dirty = true
		elif dirty and not moving:
			e["yaw"] = p["yaw"]
		e["dirty"] = dirty
	return _entries
