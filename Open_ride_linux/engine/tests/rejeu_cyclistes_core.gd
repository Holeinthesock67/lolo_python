extends SceneTree

## Rejeu core → engine des cyclistes du décor (lot AS9) : rejoue une trace écrite par rejeu_cyclistes_core.py
## (listes `riders` du vrai core à 10 Hz, cycliste à vitesse tenue) dans road_cyclists_model.gd, comme living_decor.gd :
## images à 60 Hz avec 2 % d'à-coups de 30 à 80 ms, trames `state` à 30 Hz reçues 5 ms plus tard, cycliste affiché
## extrapolé comme camera_follow.gd, `sync_core` puis `update` ; compte les contacts comme living_decor._count_contacts
## (1,7 m en long, 0,6 m en travers, cycliste compris). Lot AS10 : une trace peut porter la place du cycliste en travers
## (`lane_m`, 4e champ de chaque liste) et sa vitesse (5e champ, cycliste d'un banc rejoué), et une boucle (`type`).
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
	# Lot AS10 : boucle (`type` « loop », cercle de même longueur) pour rejouer un passage de ligne
	var loop := str(data.get("type", "open")) == "loop"
	var radius := L / TAU
	for i in range(n):
		var a := TAU * i * 10.0 / L
		cols["lat"].append(48.9); cols["lon"].append(7.1); cols["alt_m"].append(200.0)
		cols["x"].append(radius * sin(a) if loop else i * 10.0); cols["z"].append(radius * (1.0 - cos(a)) if loop else 0.0)
		cols["grade_pct"].append(0.0); cols["heading_deg"].append(fposmod(90.0 - rad_to_deg(a), 360.0) if loop else 90.0)
	var d := {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": L, "type": "loop" if loop else "open"}
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
	var moving: bool = frames[0].size() > 4   # 5e champ : vitesse du cycliste (trace d'un banc rejoué)
	var fk := 0
	var lane := 1.2   # lot AS10 : place du cycliste en travers (`lane_m` de la trame, 4e champ), 1,2 m sans placement
	while now < t_end:
		var dt := 1.0 / 60.0
		if rng.randf() < 0.02:
			dt = rng.randf_range(0.03, 0.08)   # à-coups
		now += dt
		# trame state à 30 Hz : position du core au temps de la trame, reçue 5 ms plus tard
		var t_state := floorf((now - 0.005) * 30.0) / 30.0
		var core_s := s0 + v * t_state
		if moving:   # lot AS10 : trace d'un banc (s et v du cycliste à chaque liste), s au temps de la trame
			var k := clampi(fk, 0, frames.size() - 2)
			while k < frames.size() - 2 and float(frames[k + 1][0]) <= t_state:
				k += 1
			fk = k
			var f0: Array = frames[k]
			var f1: Array = frames[k + 1]
			var u := clampf((t_state - float(f0[0])) / maxf(1e-6, float(f1[0]) - float(f0[0])), 0.0, 1.0)
			core_s = lerpf(float(f0[1]), float(f1[1]), u)
			v = lerpf(float(f0[4]), float(f1[4]), u)
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
			if pending.size() > 3:
				lane = float(pending[3])
			var fs := float(pending[1])
			# trame de la liste : s à son temps
			m.sync_core(list, seq, cam_s, fs)
		m.update(cam_s, v, dt, false, [], lane)
		var items: Array = m.riders()
		items.append({"s": cam_s, "lateral": lane, "group": {"case": "cycliste"}, "id": "you"})
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
