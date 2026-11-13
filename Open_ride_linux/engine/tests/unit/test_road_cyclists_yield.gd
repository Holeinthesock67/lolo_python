extends SceneTree

## Lot AS8 (recette rPK1 du 13/11 sur les cols : contacts « ahead / core » et « oncoming / core » vers 60 m) : un
## groupe de l'engine rattrapé par un groupe du core plus rapide de son sens (que le core fait rouler sans le voir)
## s'écarte vers l'axe et le laisse passer, puis se rabat ; s'il ne peut pas s'écarter à temps, il roule à sa
## vitesse ; aucun cycliste ne passe dans un autre. Route large et chemin étroit, dans les deux sens.
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_cyclists_yield.gd

const Model := preload("res://scripts/road_cyclists_model.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

const DT := 1.0 / 30.0
## Contact comme living_decor.gd (_count_contacts) : vélos de 1,7 m, 0,6 m de large
const CONTACT_LEN_M := 1.7
const CONTACT_WIDTH_M := 0.6

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite et plate de 10 km vers l'est.
func _route():
	var ds := 10.0
	var n := 1001
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(200.0)
		cols["x"].append(i * ds)
		cols["z"].append(0.0)
		cols["grade_pct"].append(0.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


func _model(route, width_m: float):
	var m = Model.new()
	m.configure(route, [], [], 16, 7, width_m)
	m.update(1000.0, 7.0, 0.0)
	m._next_slot = 1 << 30            # aucune case tirée : seuls les groupes posés roulent
	return m


## Un groupe de l'engine `case_name` posé à `rel_m`, un groupe du core de `size` cyclistes en file, du même sens,
## parti de `core_rel_m` à `core_v` m/s sur la même ligne ; le core donne sa liste une image sur trois et ne voit
## pas le groupe de l'engine ; `bots` : {d, lateral}, bots qui roulent à `d` m du groupe de l'engine. Rend {contacts, passed, engine_lat_min, engine_lat_end, own}.
func _run_case(route, width_m: float, case_name: String, rel_m: float, core_rel_m: float, core_v: float,
		size: int = 2, seconds: float = 30.0, bots: Array = []) -> Dictionary:
	var s := 1000.0
	var m = _model(route, width_m)
	m.place_for_test(s, 7.0, case_name, rel_m, 1)
	var eg: Dictionary = m.groups[0]
	var dir := int(eg["dir"])
	var own := float(eg["members"][0]["lateral"])
	var core_s := s + core_rel_m
	var contacts := 0
	var lat_far := own
	var seq := 0
	for i in range(int(seconds / DT)):
		core_s += float(dir) * core_v * DT
		if i % 3 == 0:
			seq += 1
			var list := []
			for k in range(size):
				list.append({"id": "c77-%d" % k, "s": core_s - float(dir) * float(k) * Model.FILE_GAP_M, "dir": dir,
					"v": core_v, "lane_m": own, "look": k})
			m.sync_core(list, seq, s)
		var bot_places := []
		for b in bots:        # bots qui roulent avec le groupe de l'engine, à `d` m de lui
			bot_places.append({"s": float(eg["s"]) + float(b["d"]), "lateral": float(b["lateral"])})
		m.update(s, 7.0, DT, false, bot_places)
		var rs: Array = m.riders()
		for a in rs:
			if str(a["group"]["case"]) == "core":
				continue
			lat_far = minf(lat_far, float(a["lateral"])) if dir == 1 else maxf(lat_far, float(a["lateral"]))
			for b in rs:
				if str(b["group"]["case"]) != "core":
					continue
				if absf(float(a["s"]) - float(b["s"])) < CONTACT_LEN_M and absf(float(a["lateral"]) - float(b["lateral"])) < CONTACT_WIDTH_M:
					contacts += 1
	var e_s := INF
	var e_lat := NAN
	var c_tail := INF
	for r in m.riders():
		if str(r["group"]["case"]) == "core":
			c_tail = minf(c_tail, float(r["s"]) * dir)
		else:
			e_s = float(r["s"])
			e_lat = float(r["lateral"])
	return {"contacts": contacts, "passed": c_tail > e_s * dir, "lat_far": lat_far, "lat_end": e_lat, "own": own}


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = _route()
	for width in [6.0, 4.0]:
		var label := "route de %.0f m%s" % [width, " (chemin étroit, en file)" if Model._narrow(width * 0.5) else ""]
		# Sens du parcours : « ahead » à 18 km/h rattrapé par un groupe du core à 33 km/h (Hakone, Stelvio)
		var r := _run_case(route, width, "ahead", 70.0, 45.0, 9.0)
		_check(r["contacts"] == 0, "%s, « ahead » rattrapé par le core : aucun contact (%d)" % [label, r["contacts"]])
		_check(r["passed"], "%s, « ahead » : le groupe du core est passé" % label)
		_check(absf(float(r["own"]) - float(r["lat_far"])) >= Model.MIN_CENTRE_M - 0.06,
			"%s, « ahead » : s'est écarté vers l'axe (%.2f → %.2f m)" % [label, r["own"], r["lat_far"]])
		_check(absf(float(r["lat_end"]) - float(r["own"])) < 0.05, "%s, « ahead » : revenu sur sa place (%.2f m)" % [label, r["lat_end"]])
		# En face : un groupe « oncoming » rattrapé par un groupe du core de son sens
		r = _run_case(route, width, "oncoming", 400.0, 440.0, 12.0, 2, 20.0)
		_check(r["contacts"] == 0, "%s, « oncoming » rattrapé par le core : aucun contact (%d)" % [label, r["contacts"]])
		_check(r["passed"], "%s, « oncoming » : le groupe du core est passé" % label)
		_check(absf(float(r["lat_end"]) - float(r["own"])) < 0.05, "%s, « oncoming » : revenu sur sa place (%.2f m)" % [label, r["lat_end"]])
		# Rattrapé de tout près, très vite : pas le temps de s'écarter, il roule à la vitesse du core le temps de sortir
		r = _run_case(route, width, "ahead", 70.0, 64.0, 16.0, 3)
		_check(r["contacts"] == 0, "%s, rattrapé à 2 m par un groupe à 58 km/h : aucun contact (%d)" % [label, r["contacts"]])
		_check(r["passed"], "%s, ... puis le groupe du core est passé" % label)
		# Place visée occupée par un bot : il ne s'écarte pas et reste devant, à la vitesse du core
		var bot_lat := float(r["own"]) - Model.MIN_CENTRE_M
		r = _run_case(route, width, "ahead", 70.0, 50.0, 9.0, 2, 20.0, [{"d": -1.0, "lateral": bot_lat}])
		_check(r["contacts"] == 0, "%s, bot sur la place visée : aucun contact (%d)" % [label, r["contacts"]])
		_check(absf(float(r["lat_far"]) - float(r["own"])) < 0.05, "%s, bot sur la place visée : ne s'écarte pas (%.2f m)" % [label, r["lat_far"]])
	print("test_road_cyclists_yield : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
