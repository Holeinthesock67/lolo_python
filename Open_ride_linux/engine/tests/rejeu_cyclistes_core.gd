extends SceneTree

## Rejeu core → engine des cyclistes du décor (lot AS9) : rejoue une trace écrite par rejeu_cyclistes_core.py
## (listes `riders` du vrai core à 10 Hz, cycliste à vitesse tenue) dans road_cyclists_model.gd, comme living_decor.gd :
## images à 60 Hz avec 2 % d'à-coups de 30 à 80 ms, trames `state` à 30 Hz reçues 5 ms plus tard, cycliste affiché
## extrapolé comme camera_follow.gd, `sync_core` puis `update` ; compte les contacts comme living_decor._count_contacts
## (1,7 m en long, 0,6 m en travers, cycliste compris).
## Lancement : godot --headless --path engine --script res://tests/rejeu_cyclistes_core.gd -- TRACE.json [BUDGET]
const Model := preload("res://scripts/road_cyclists_model.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var args := OS.get_cmdline_user_args()
	var path: String = args[0]
	var budget := int(args[1]) if args.size() > 1 else 8
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var L := float(data["length_m"])
	var n := int(L / 10.0) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		cols["lat"].append(48.9); cols["lon"].append(7.1); cols["alt_m"].append(200.0)
		cols["x"].append(i * 10.0); cols["z"].append(0.0); cols["grade_pct"].append(0.0); cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": L, "type": "open"}
	d.merge(cols)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	var m = Model.new()
	m.configure(route, [], [], budget, int(data["seed"]))
	var v := float(data["kmh"]) / 3.6
	var frames: Array = data["frames"]
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	var now := 0.0
	var fi := 0
	var contacts := 0
	var kinds := {}
	var last := ""
	var t_end := float(frames[-1][0])
	var s0 := float(frames[0][1])
	var seq := 0
	var last_list := {}
	var shown := 0
	while now < t_end:
		var dt := 1.0 / 60.0
		if rng.randf() < 0.02:
			dt = rng.randf_range(0.03, 0.08)   # à-coups
		now += dt
		# trame state à 30 Hz : position du core au temps de la trame, reçue 5 ms plus tard
		var t_state := floorf((now - 0.005) * 30.0) / 30.0
		var core_s := s0 + v * t_state
		var cam_s := core_s + v * (now - t_state)
		var pending := []
		while fi < frames.size() and float(frames[fi][0]) + 0.005 <= now:
			pending = frames[fi]
			fi += 1
		if not pending.is_empty():
			var list := []
			for r in pending[2]:
				list.append({"id": r[0], "s": r[1], "dir": r[2], "v": r[3], "lane_m": r[4], "look": r[5]})
			seq += 1
			last_list = {}
			for r in pending[2]:
				last_list[r[0]] = [snappedf(float(r[1]) - float(pending[1]), 0.01), r[4]]
			last_list["n"] = pending[2].size()
			var fs := float(pending[1])
			# trame de la liste : s à son temps
			m.sync_core(list, seq, cam_s, fs)
		m.update(cam_s, v, dt)
		var items: Array = m.riders()
		items.append({"s": cam_s, "lateral": 1.2, "group": {"case": "cycliste"}, "id": "you"})
		for i in range(items.size()):
			for j in range(i + 1, items.size()):
				var a: Dictionary = items[i]
				var b: Dictionary = items[j]
				if is_same(a["group"], b["group"]):
					continue
				if absf(float(a["s"]) - float(b["s"])) < 1.7 and absf(float(a["lateral"]) - float(b["lateral"])) < 0.6:
					contacts += 1
					var key := "%s / %s" % [a["group"]["case"], b["group"]["case"]]
					kinds[key] = int(kinds.get(key, 0)) + 1
					if shown < 6:
						shown += 1
						print("t=%.2f %s(%s) rel %.2f lat %.2f / %s(%s) rel %.2f lat %.2f | liste %s" % [now, a["id"], a["group"]["case"], float(a["s"]) - cam_s, float(a["lateral"]), b["id"], b["group"]["case"], float(b["s"]) - cam_s, float(b["lateral"]), str(last_list)])
					last = "%s / %s à %.1f m (%.2f et %.2f)" % [a["group"]["case"], b["group"]["case"], float(a["s"]) - cam_s, float(a["lateral"]), float(b["lateral"])]
	print("contacts=%d %s dernier: %s" % [contacts, str(kinds), last])
	quit(0)
