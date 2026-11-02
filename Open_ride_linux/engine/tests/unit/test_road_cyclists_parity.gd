extends SceneTree

## Parité des cyclistes du décor (lot AS7) : le modèle de l'engine `road_cyclists_model.gd` rejoue la séance
## de `tests/make_road_cyclists_parity.py` (20 km de plaine puis 10 km de montée, un bot, budget 16, graine 7)
## et doit tirer les mêmes groupes que le portage du core `core/src/openride_core/road_cyclists.py`, aux mêmes
## places (relevé `tests/data/road_cyclists_parity.json`, écart toléré TOL_M).
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_cyclists_parity.gd

const Model := preload("res://scripts/road_cyclists_model.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

const TRACE := "res://tests/data/road_cyclists_parity.json"
const TOL_M := 0.05

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Même route que le relevé (et que test_road_cyclists_model.gd).
func _route(spec: Dictionary):
	var flat := float(spec["flat_m"])
	var length := float(spec["length_m"])
	var pct := float(spec["climb_pct"])
	var ds := float(spec["ds_m"])
	var n := int(length / ds) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var s := i * ds
		var climbing := s >= flat and s < flat + 10000.0
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(200.0 + clampf(s - flat, 0.0, 10000.0) * pct / 100.0)
		cols["x"].append(s)
		cols["z"].append(0.0)
		cols["grade_pct"].append(pct if climbing else 0.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var ref = JSON.parse_string(FileAccess.get_file_as_string(TRACE))
	_check(ref is Dictionary, "relevé du core lu (%s)" % TRACE)
	if not ref is Dictionary:
		quit(1)
		return
	var spec: Dictionary = ref["route"]
	var flat := float(spec["flat_m"])
	var m = Model.new()
	m.configure(_route(spec), [{"start_s": flat, "summit_s": flat + 10000.0}], [], int(ref["budget"]), int(ref["seed"]))
	var fps := int(ref["fps"])
	var every := fps * int(ref["every_s"])
	var dt := 1.0 / float(fps)
	var s := 300.0
	var bot := 100.0
	var seen := {}
	var log := []
	var frames: Array = ref["frames"]
	var fi := 0
	var frame := 0
	var worst := 0.0
	var mismatch := ""
	while s < flat + 10000.0:
		var v := 30.0 / 3.6 if s < flat else 14.0 / 3.6
		bot += (32.0 if bot < flat else 15.0) / 3.6 * dt
		m.update(s, v, dt, false, [{"s": bot, "lateral": Model.BOT_LATERAL_M}])   # places des bots (P32, bots_view_model)
		for g in m.groups:
			if not seen.has(g["id"]):
				seen[g["id"]] = true
				log.append([g["id"], g["case"], (g["members"] as Array).size()])
		if frame % every == 0 and fi < frames.size() and mismatch == "":
			var want: Array = frames[fi]["riders"]
			var got := []
			for g in m.groups:
				var members: Array = g["members"]
				for i in range(members.size()):
					got.append(["%s-%d" % [g["id"], i], float(g["s"]) - float(g["dir"]) * float(members[i]["dl"]), float(members[i]["lateral"])])
			if got.size() != want.size():
				mismatch = "image %d : %d cyclistes au lieu de %d" % [frame, got.size(), want.size()]
			else:
				for j in range(got.size()):
					var w: Array = want[j]
					var e := maxf(absf(float(got[j][1]) - float(w[1])), absf(float(got[j][2]) - float(w[2])))
					worst = maxf(worst, e)
					if str(got[j][0]) != str(w[0]) or e > TOL_M:
						mismatch = "image %d : %s à %.3f m / %.3f m au lieu de %s à %.3f m / %.3f m" % [
							frame, got[j][0], got[j][1], got[j][2], w[0], w[1], w[2]]
						break
			fi += 1
		s += v * dt
		frame += 1
	var ref_log: Array = ref["log"]
	var same_log := log.size() == ref_log.size()
	for i in range(mini(log.size(), ref_log.size())):
		var w: Array = ref_log[i]
		same_log = same_log and str(log[i][0]) == str(w[0]) and str(log[i][1]) == str(w[1]) and int(log[i][2]) == int(w[2])
	_check(same_log, "mêmes groupes tirés dans le même ordre que le core (%d / %d)" % [log.size(), ref_log.size()])
	_check(m.spawned_total == int(ref["spawned"]) and m.passed_total == int(ref["passed"]) and m.overtook_total == int(ref["overtook"]),
		"mêmes comptes : %d tirés, %d doublés, %d qui doublent" % [m.spawned_total, m.passed_total, m.overtook_total])
	_check(fi == frames.size() and mismatch == "", "mêmes cyclistes aux mêmes places sur %d relevés (écart max %.4f m)%s" % [
		fi, worst, "" if mismatch == "" else " : " + mismatch])
	print("test_road_cyclists_parity : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
