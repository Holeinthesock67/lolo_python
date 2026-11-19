extends SceneTree

## Rejeu de l'affichage des usagers de la route (lot AS11), sans écran : rejoue les trames `state` du vrai core écrites
## par `python -m openride_core.tools.contacts_replay --traces DOSSIER` dans traffic_model.gd et road_cyclists_model.gd,
## dans l'ordre de living_decor.gd (sens de marche, `sync_core` avec `road_part`, `update`), images à 60 Hz avec 2 %
## d'à-coups de 30 à 80 ms (seule la dernière trame reçue est lue, comme main.gd), cycliste et bots extrapolés à
## l'image ; compte les contacts comme living_decor._count_contacts (300 m autour du cycliste, vélos de 1,7 m) et
## les range par paire de types d'usagers.
## Les appels à 6 arguments passent par `callv` : le même script rejoue aussi un engine d'avant AS11 (main).
## Lancement : godot --headless --path engine --script res://tests/rejeu_contacts.gd -- MONDE.world TRACE.json [QUALITÉ]
const TrafficModel := preload("res://scripts/traffic_model.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const LivingDecor := preload("res://scripts/living_decor.gd")
const ClimbDetector := preload("res://scripts/climb_detector.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

func _init() -> void:
	call_deferred("_run")


static func _kind(name: String) -> String:
	if TrafficModel.KINDS.has(name):
		return "vehicule"
	if name == "cycliste":
		return "cycliste"
	if name == "bot":
		return "bot"
	return "decor"


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	var world_dir: String = args[0]
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	var quality: String = args[2] if args.size() > 2 else "medium"
	var route = RouteDataScript.new()
	if not route.load_world_dir(world_dir):
		print("ERREUR parcours illisible : ", world_dir)
		quit(2)
		return
	var living: Dictionary = QualityPresets.living(quality)
	var pois := []
	for k in range(maxi(1, int(ceil(float(route.length_m) / LivingDecor.CHUNK_M)))):
		var p := OsmLayers.load_chunk(world_dir, "poi", k)
		if p.get("ok", false):
			pois.append_array(p.get("items", []))
	var traffic = TrafficModel.new()
	traffic.configure(route, {}, pois, int(living.get("vehicles", 0)))
	var cyclists = RoadCyclistsModel.new()
	cyclists.configure(route, LivingDecor.climbs_of(route), pois, int(living.get("cyclists", 0)), 0,
		RoadBuilder.ROAD_WIDTH_M, traffic, Callable())
	cyclists.set_back_climbs(ClimbDetector.detect_back(route))
	var frames: Array = data["frames"]
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	var now := float(frames[0][0])
	var fi := 0
	var seq := 0
	var f: Array = frames[0]
	var contacts := 0
	var kinds := {}
	var firsts := {}
	var touching := {}
	var episodes := {}
	var t_end := float(frames[-1][0])
	while now < t_end:
		var dt := 1.0 / 60.0
		if rng.randf() < 0.02:
			dt = rng.randf_range(0.03, 0.08)
		now += dt
		var got := false
		while fi < frames.size() and float(frames[fi][0]) + 0.005 <= now:
			f = frames[fi]
			fi += 1
			got = true
		if got:
			seq += 1
		var age := now - float(f[0])
		var dir := -1 if int(f[3]) < 0 else 1
		var cam_s := float(f[1]) + dir * float(f[2]) * age
		var lane := float(f[4])
		traffic.set_direction(dir)
		cyclists.set_direction(dir, cam_s)
		var model_s: float = traffic.model_s(cam_s)
		var bots_m := []
		for b in f[5]:
			bots_m.append({"s": traffic.model_s(float(b[0]) + float(b[1]) * age), "lateral": dir * float(b[2])})
		var part := -1
		var parts := 0
		if typeof(f[8]) == TYPE_ARRAY:
			part = int(f[8][0])
			parts = maxi(1, int(f[8][1]))
		if got and typeof(f[7]) == TYPE_ARRAY:
			if parts > 0:
				cyclists.callv("sync_core", [_core_list(f[7], dir, traffic), seq, model_s, traffic.model_s(float(f[1])), part, parts])
			else:   # trace d'un core d'avant le lot AS11 (main) : listes proches seulement
				cyclists.sync_core(_core_list(f[7], dir, traffic), seq, model_s)
		cyclists.update(model_s, float(f[2]), dt, false, bots_m, dir * lane)
		var others: Array = cyclists.riders()
		for b in bots_m:
			others.append({"s": float(b["s"]), "lateral": float(b["lateral"]), "dir": dir})
		if got and typeof(f[6]) == TYPE_ARRAY:
			if parts > 0:
				traffic.callv("sync_core", [_core_list(f[6], dir, traffic), seq, model_s, traffic.model_s(float(f[1])), part, parts])
			else:
				traffic.sync_core(_core_list(f[6], dir, traffic), seq, model_s, traffic.model_s(float(f[1])))
		traffic.update(model_s, float(f[2]), dt, false, others)
		# living_decor._count_contacts
		var items := []
		for v in traffic.vehicles:
			if absf(float(v["s"]) - model_s) <= LivingDecor.CONTACT_M:
				var k: Dictionary = TrafficModel.KINDS[v["kind"]]
				items.append({"name": str(v["kind"]), "id": str(v["id"]), "s": float(v["s"]), "lateral": float(v["lateral"]),
					"half_len": float(k["length"]) * 0.5, "half_width": float(k["half_width"]), "group": v})
		var you := {"s": model_s, "lateral": dir * lane, "name": "cycliste"}
		for o in others + [you]:
			if absf(float(o["s"]) - model_s) <= LivingDecor.CONTACT_M:
				items.append({"name": str(o["group"]["case"]) if o.has("group") else str(o.get("name", "bot")),
					"id": str(o.get("id", o.get("name", "bot"))) + str(o["group"]["id"] if o.has("group") else ""),
					"s": float(o["s"]), "lateral": float(o["lateral"]), "half_len": LivingDecor.CONTACT_BIKE_HALF_M,
					"half_width": TrafficModel.RIDER_HALF_WIDTH_M, "group": o.get("group", o)})
		var now_touch := {}
		for i in range(items.size()):
			for j in range(i + 1, items.size()):
				var a: Dictionary = items[i]
				var b: Dictionary = items[j]
				if is_same(a["group"], b["group"]):
					continue
				if absf(float(a["s"]) - float(b["s"])) < float(a["half_len"]) + float(b["half_len"]) \
						and absf(float(a["lateral"]) - float(b["lateral"])) < float(a["half_width"]) + float(b["half_width"]):
					contacts += 1
					var ka := [_kind(str(a["name"])), _kind(str(b["name"]))]
					ka.sort()
					var key := "%s / %s" % ka
					kinds[key] = int(kinds.get(key, 0)) + 1
					var pk := "%s|%s" % [a["id"], b["id"]]
					now_touch[pk] = true
					if not touching.has(pk):
						episodes[key] = int(episodes.get(key, 0)) + 1
					if not firsts.has(key):
						firsts[key] = "%s / %s à %.0f m (écarts %.1f et %.1f m, t = %.0f s)" % [a["name"], b["name"],
							float(a["s"]) - model_s, float(a["lateral"]), float(b["lateral"]), now]
		touching = now_touch
	print("contacts=%d episodes=%s images=%s" % [contacts, JSON.stringify(episodes), JSON.stringify(kinds)])
	for key in firsts:
		print("   %s : %s" % [key, firsts[key]])
	quit(0)


## living_decor._core_list : à rebours, listes du core dans le repère de la circulation (u = L - s).
static func _core_list(list: Array, dir: int, traffic) -> Array:
	if dir > 0:
		return list
	var out: Array = []
	for item in list:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var c: Dictionary = item.duplicate()
		if typeof(c.get("s")) in [TYPE_INT, TYPE_FLOAT]:
			c["s"] = traffic.model_s(float(c["s"]))
		c["dir"] = -1 if int(c.get("dir", 1)) >= 0 else 1
		if typeof(c.get("lane_m")) in [TYPE_INT, TYPE_FLOAT]:
			c["lane_m"] = -float(c["lane_m"])
		out.append(c)
	return out
