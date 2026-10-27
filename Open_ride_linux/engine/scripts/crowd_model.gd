extends RefCounted

## Spectateurs du dernier kilomètre des montées (Lot P15), sans aucun nœud. Montées de climb_detector.gd
## (P14). Pas de class_name : charger par preload("res://scripts/crowd_model.gd").
##
## Placement déterministe (graine + indice de la case) : cases de SLOT_M de chaque côté de la route sur
## le dernier ZONE_M de chaque montée d'au moins MIN_CLIMB_M (toutes avec `crowd_all_climbs`).
## Probabilité d'une case de DENSITY.x au début de la zone à DENSITY.y au sommet, modulée par des groupes
## de GROUP_M (un groupe sur trois est clairsemé) ; jusqu'à 2 spectateurs par case. Écart au bord de la
## chaussée de EDGE_M.x à EDGE_M.y ; aucun dans l'eau (surfaces et cours d'eau).
## `spectators` : `[{s, side, pos, yaw, color, flag, phase, delay, group}]`, trié par `s`.
##
## `update(rider_pos, rider_s, now_s)` : état « calme » ou « encourage » (cycliste à moins de
## CHEER_RADIUS_M), qui bascule après le délai propre au spectateur (0 à MAX_DELAY_S) ; seuls les
## spectateurs à moins de WINDOW_M de `rider_s` sont examinés (recherche par dichotomie).
## `cheer(rider_s, now_s, power_w, ftp_w)` : intensité de la clameur de 0 à 1 : distance au groupe le plus
## proche (nulle au-delà de HEAR_M), taille du groupe, puissance relative à la FTP si fournie, et bonus
## d'un dépassement de bot récent (`observe_bots`, PASS_BOOST pendant PASS_BOOST_S).

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")

const ZONE_M := 1000.0
const MIN_CLIMB_M := 3000.0
const SLOT_M := 2.0
const DENSITY := Vector2(0.12, 0.85)
const GROUP_M := 25.0
const EDGE_M := Vector2(0.3, 3.0)
const WATER_MARGIN_M := 1.0
const DEFAULT_ROAD_WIDTH_M := 6.0
const CHEER_RADIUS_M := 25.0
const MAX_DELAY_S := 0.6
const WINDOW_M := 60.0
const HEAR_M := 150.0
const PASS_BOOST := 0.35
const PASS_BOOST_S := 5.0
const COLORS := 8

var spectators: Array = []
var groups: Array = []          # {s, count, center: Vector3}
var states: Dictionary = {}     # indice -> {"cheer": bool, "since": float}
var _last_pass_s: float = -INF
var _bot_rel: Dictionary = {}   # id -> signe (bot devant : +1, derrière : -1)


static func _u(h: int) -> float:
	return float(h & 0xFFFFFF) / 16777216.0


static func _in_water(p: Vector3, water: Dictionary) -> bool:
	for a in water.get("areas", []):
		if typeof(a) == TYPE_DICTIONARY and typeof(a.get("outer")) == TYPE_ARRAY and a["outer"].size() >= 3:
			if VegetationPlacer.point_in_ring(p.x, p.z, a["outer"]):
				return true
	var q := Vector2(p.x, p.z)
	for l in water.get("lines", []):
		if typeof(l) != TYPE_DICTIONARY or typeof(l.get("points")) != TYPE_ARRAY:
			continue
		var pts: Array = l["points"]
		var half := float(l.get("width_m", 2.0)) * 0.5 + WATER_MARGIN_M
		for i in range(pts.size() - 1):
			var a2 := Vector2(float(pts[i][0]), float(pts[i][1]))
			var ab := Vector2(float(pts[i + 1][0]), float(pts[i + 1][1])) - a2
			var len2 := ab.length_squared()
			var t := 0.0 if len2 <= 0.0 else clampf((q - a2).dot(ab) / len2, 0.0, 1.0)
			if (a2 + ab * t).distance_to(q) < half:
				return true
	return false


func configure(route, climbs: Array, water: Dictionary = {}, crowd_all_climbs: bool = false,
		seed: int = 0, road_width_m: float = DEFAULT_ROAD_WIDTH_M) -> void:
	spectators.clear()
	groups.clear()
	states.clear()
	_bot_rel.clear()
	_last_pass_s = -INF
	if route == null:
		return
	var half := road_width_m * 0.5
	for c in climbs:
		if float(c["length_m"]) < MIN_CLIMB_M and not crowd_all_climbs:
			continue
		var summit := float(c["summit_s"])
		var z0 := maxf(float(c["start_s"]), summit - ZONE_M)
		var n_slots := int((summit - z0) / SLOT_M)
		for side in [-1, 1]:
			for i in range(n_slots):
				var s := z0 + (i + 0.5) * SLOT_M
				var t := (s - z0) / maxf(summit - z0, 1.0)
				var gidx := int(floor(s / GROUP_M))
				var hg := VegetationPlacer.hash3(seed, gidx, side + 7)
				var group_factor := 0.35 if hg % 3 == 0 else 1.0
				var p := lerpf(DENSITY.x, DENSITY.y, t) * group_factor
				var h := VegetationPlacer.hash3(seed ^ 0x0C20D, int(round(s * 10.0)), side)
				var n_here := 0
				if _u(h) < p:
					n_here = 2 if _u(VegetationPlacer._mix(h + 9)) < p * 0.5 else 1
				for k in range(n_here):
					var hk := VegetationPlacer._mix(h + 17 * (k + 1))
					var smp: Dictionary = route.sample(s + (_u(hk) - 0.5) * SLOT_M * 0.8)
					var hd := deg_to_rad(float(smp["heading_deg"]))
					var right := Vector3(cos(hd), 0.0, sin(hd))
					var edge := lerpf(EDGE_M.x, EDGE_M.y, _u(VegetationPlacer._mix(hk + 1)))
					var lateral := float(side) * (half + edge)
					var pos := Vector3(smp["x"], smp["y"], smp["z"]) + right * lateral
					if _in_water(pos, water):
						continue
					var to_road := -right * float(side)
					spectators.append({
						"s": s, "side": side, "pos": pos, "edge_m": edge,
						"yaw": atan2(to_road.x, to_road.z) + (_u(VegetationPlacer._mix(hk + 2)) - 0.5) * 1.2,   # face (+z) vers la route
						"color": int(VegetationPlacer._mix(hk + 3) % COLORS),
						"flag": _u(VegetationPlacer._mix(hk + 4)) < 0.25,
						"phase": _u(VegetationPlacer._mix(hk + 5)),
						"delay": MAX_DELAY_S * _u(VegetationPlacer._mix(hk + 6)),
						"group": gidx,
					})
	spectators.sort_custom(func(a, b): return a["s"] < b["s"] or (a["s"] == b["s"] and a["side"] < b["side"]))
	var by_group := {}
	for sp in spectators:
		var g: int = sp["group"]
		if not by_group.has(g):
			by_group[g] = {"s": 0.0, "count": 0, "center": Vector3.ZERO}
		by_group[g]["s"] += float(sp["s"])
		by_group[g]["center"] += sp["pos"]
		by_group[g]["count"] += 1
	var keys := by_group.keys()
	keys.sort()
	for g in keys:
		var e: Dictionary = by_group[g]
		groups.append({"s": e["s"] / e["count"], "count": e["count"], "center": e["center"] / e["count"]})


## Premier indice de `spectators` dont `s` est au moins `s_min`.
func _lower_bound(s_min: float) -> int:
	var lo := 0
	var hi := spectators.size()
	while lo < hi:
		var mid := (lo + hi) >> 1
		if float(spectators[mid]["s"]) < s_min:
			lo = mid + 1
		else:
			hi = mid
	return lo


func update(rider_pos: Vector3, rider_s: float, now_s: float) -> void:
	# États hors de la fenêtre : retour au calme
	for idx in states.keys():
		if absf(float(spectators[idx]["s"]) - rider_s) > WINDOW_M:
			states.erase(idx)
	var i := _lower_bound(rider_s - WINDOW_M)
	while i < spectators.size() and float(spectators[i]["s"]) <= rider_s + WINDOW_M:
		var sp: Dictionary = spectators[i]
		var near := (sp["pos"] as Vector3).distance_to(rider_pos) < CHEER_RADIUS_M
		var st: Dictionary = states.get(i, {})
		if st.is_empty():
			st = {"near": false, "since": now_s, "cheer": false}
			states[i] = st
		if near != bool(st["near"]):
			st["near"] = near
			st["since"] = now_s
		if bool(st["cheer"]) != near and now_s - float(st["since"]) >= float(sp["delay"]):
			st["cheer"] = near
		i += 1


func state(i: int) -> String:
	var st: Dictionary = states.get(i, {})
	return "encourage" if bool(st.get("cheer", false)) else "calme"


## Suit les bots (`[{id, s}]` de la trame) : un bot qui passe de devant à derrière le cycliste est un
## dépassement.
func observe_bots(rider_s: float, bots: Array, now_s: float) -> void:
	for b in bots:
		if typeof(b) != TYPE_DICTIONARY:
			continue
		var id := str(b.get("id", ""))
		var rel := signf(float(b.get("s", rider_s)) - rider_s)
		if rel == 0.0:
			continue
		if _bot_rel.get(id, 0.0) > 0.0 and rel < 0.0:
			_last_pass_s = now_s
		_bot_rel[id] = rel


## Indice du groupe le plus proche de `rider_s` (-1 sans groupe).
func nearest_group(rider_s: float) -> int:
	if groups.is_empty():
		return -1
	# Groupes triés par s : dichotomie, puis le plus proche des deux voisins
	var lo := 0
	var hi := groups.size()
	while lo < hi:
		var mid := (lo + hi) >> 1
		if float(groups[mid]["s"]) < rider_s:
			lo = mid + 1
		else:
			hi = mid
	if lo >= groups.size():
		return groups.size() - 1
	if lo > 0 and absf(float(groups[lo - 1]["s"]) - rider_s) <= absf(float(groups[lo]["s"]) - rider_s):
		return lo - 1
	return lo


func cheer(rider_s: float, now_s: float, power_w: float = NAN, ftp_w: float = NAN) -> float:
	var gi := nearest_group(rider_s)
	if gi < 0:
		return 0.0
	var g: Dictionary = groups[gi]
	var d := absf(float(g["s"]) - rider_s)
	if d >= HEAR_M:
		return 0.0
	var size := clampf(float(g["count"]) / 20.0, 0.2, 1.0)
	var v := (1.0 - d / HEAR_M) * size
	if is_finite(power_w) and is_finite(ftp_w) and ftp_w > 0.0:
		v *= lerpf(0.8, 1.3, clampf((power_w / ftp_w - 0.6) / 0.8, 0.0, 1.0))
	if now_s - _last_pass_s < PASS_BOOST_S:
		v += PASS_BOOST * (1.0 - (now_s - _last_pass_s) / PASS_BOOST_S) * (1.0 - d / HEAR_M)
	return clampf(v, 0.0, 1.0)
