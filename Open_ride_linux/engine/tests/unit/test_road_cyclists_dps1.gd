extends SceneTree

## Lot DPS1 (démonstrations de 42 km du lot DPB1) : jumeau des tests unitaires de core/tests/test_road_cyclists_dps1.py,
## mêmes valeurs. Le cycliste compte comme une ligne à éviter quand un groupe en double un autre s'il sera à hauteur
## pendant le dépassement (`_rider_lane_group`) ; un `overtake` ne se rabat pas devant lui derrière un groupe plus lent
## qu'il rattraperait aussitôt (`_lane_closing`).
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_cyclists_dps1.gd

const Model := preload("res://scripts/road_cyclists_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _group(s: float, size: int, lateral: float) -> Dictionary:
	var members := []
	for i in range(size):
		members.append({"lateral": lateral, "dl": float(i) * Model.FILE_GAP_M})
	return {"dir": 1, "s": s, "members": members}


func _init() -> void:
	var m = Model.new()
	m.rider_lane = Model.RIDER_LATERAL_M
	var slow := _group(40.0, 2, 2.5)
	slow["speed_mps"] = 8.0
	var fast := _group(37.0, 1, 2.5)
	fast["speed_mps"] = 8.5
	var s := float(fast["s"])
	var lane: Dictionary = m._rider_lane_group(fast, [slow], s - 10.0, 8.0, 8.5)
	_check(not lane.is_empty() and is_equal_approx(float(lane["members"][0]["lateral"]), Model.RIDER_LATERAL_M),
		"cycliste à 10 m : une ligne à éviter, la sienne")
	_check(not m._rider_lane_group(fast, [slow], s - 40.0, 13.0, 8.5).is_empty(),
		"cycliste à 40 m, 5 m/s plus vite : à hauteur avant la fin du dépassement")
	_check(m._rider_lane_group(fast, [slow], s - 400.0, 13.0, 8.5).is_empty(), "cycliste à 400 m : non")
	_check(m._rider_lane_group(fast, [slow], s - 40.0, 8.0, 8.5).is_empty(), "cycliste plus lent : non")
	_check(m._rider_lane_group(fast, [slow], s + 80.0, 13.0, 8.5).is_empty(), "cycliste loin devant : non")
	var g := _group(5.0, 1, -0.1)
	g["case"] = "overtake"
	g["half"] = 3.0
	g["speed_mps"] = 13.0
	var back := float(Model._edge_lateral(3.0))
	var ahead := _group(20.0, 2, back)
	ahead["speed_mps"] = 4.0
	m.groups = [g, ahead]
	_check(m._lane_closing(g, 13.0), "groupe à 4 m/s 15 m devant sur sa place de retour : il ne se rabat pas")
	ahead["s"] = 205.0
	_check(not m._lane_closing(g, 13.0), "groupe lent à 200 m : il se rabat")
	ahead["s"] = 20.0
	ahead["speed_mps"] = 13.5
	_check(not m._lane_closing(g, 13.0), "groupe aussi rapide : il se rabat")
	# Garde finale : recul derrière le groupe touché, à sa vitesse ; écart hors de la ligne du cycliste qui rattrape
	var gm = Model.new()
	gm.rider_lane = Model.RIDER_LATERAL_M
	var lead := _group(40.0, 1, 2.5)
	lead["step_mps"] = 5.0
	lead["speed_mps"] = 5.0
	var back_g := _group(39.0, 1, 2.5)
	back_g["step_mps"] = 8.0
	back_g["speed_mps"] = 8.0
	gm.groups = [lead, back_g]
	gm._guard(-500.0, 8.0)
	_check(float(lead["s"]) - float(back_g["s"]) >= Model.GUARD_LEN_M and is_equal_approx(float(back_g["step_mps"]), 5.0),
		"garde : le groupe qui touche recule derrière l'autre, à sa vitesse")
	var caught := _group(1.0, 1, Model.RIDER_LATERAL_M + 0.3)
	caught["speed_mps"] = 5.5
	gm.groups = [caught]
	gm._guard(0.0, 11.0)
	var lat := float(caught["members"][0]["lateral"])
	_check(absf(lat - Model.RIDER_LATERAL_M) >= Model.GUARD_RIDER_WIDTH_M and lat > Model.RIDER_LATERAL_M,
		"garde : rattrapé sur la ligne du cycliste, il s'écarte du côté le plus proche")
	print("test_road_cyclists_dps1 : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
