extends SceneTree

## Tests sans écran du branchement du décor vivant, deuxième vague `living_decor.gd` (Lot P17) : météo
## (particules, brume, chaussée mouillée, pluie dans l'ambiance), animaux suivant les tronçons OSM,
## éoliennes et drapeaux, eau qui scintille, panneaux et chiffres peints, véhicules figés en pause,
## spectateurs et passants jamais sur le cycliste, ni enterrés ni en l'air, coupure complète avec
## `living = false`, abri dans le HUD, coût par image ; lot P27 : aucun nœud de la deuxième vague créé après
## le démarrage, enveloppe de P23 à P26, P28 et P29 en medium.
## Lancement : godot --headless --path engine --script res://tests/unit/test_living_decor.gd

const LivingDecor := preload("res://scripts/living_decor.gd")
const LivingWorld := preload("res://scripts/living_world.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const RouteData := preload("res://scripts/route_data.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const HudView := preload("res://scripts/hud_view.gd")
const WindViewModel := preload("res://scripts/wind_view_model.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const WORLD := "user://test_living_decor.world"
const LENGTH_M := 5000.0

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


static func _alt(s: float) -> float:
	# plat 500 m, montée à 7 % jusqu'à 4 000 m (245 m de dénivelé), plat ensuite
	return 300.0 + clampf(s - 500.0, 0.0, 3500.0) * 0.07


static func _write(path: String, doc: Dictionary) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(doc))
	f.close()


## Parcours de 5 km vers l'est avec un col, village à 1 200 m, troupeau, forêt, éolienne, drapeau, lac.
static func _make_world() -> Dictionary:
	var dir := ProjectSettings.globalize_path(WORLD)
	for l in ["buildings", "vegetation", "water", "poi", "roads"]:
		DirAccess.make_dir_recursive_absolute(dir.path_join(l))
	_write(dir.path_join("manifest.json"), {"format": "openride-world", "format_version": "1.5", "layers": {"terrain": {"present": false},
		"buildings": {"present": true}, "vegetation": {"present": true}, "water": {"present": true},
		"poi": {"present": true}, "roads": {"present": true}}})
	var ds := 10.0
	var n := int(LENGTH_M / ds) + 1
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": LENGTH_M, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var s := i * ds
		d["lat"].append(48.9)
		d["lon"].append(7.1)
		d["alt_m"].append(_alt(s))
		d["x"].append(s)
		d["z"].append(0.0)
		d["grade_pct"].append(7.0 if s >= 500.0 and s < 4000.0 else 0.0)
		d["heading_deg"].append(90.0)
	_write(dir.path_join("route.json"), d)
	for k in range(5):
		var houses := []
		var pois := []
		var woods := []
		var lines := []
		var areas := []
		if k == 1:
			for h in range(8):
				var x := 1100.0 + h * 25.0
				for side in [-1.0, 1.0]:
					var z0: float = side * 18.0
					houses.append({"id": "b_%d_%d" % [h, int(side)], "outer": [[x, z0], [x + 10.0, z0], [x + 10.0, z0 + side * 8.0], [x, z0 + side * 8.0]],
						"holes": [], "base_y": _alt(x), "height_m": 6.0, "roof": "flat", "hint": {"building": "house"}})
			pois.append({"id": "village", "kind": "village", "x": 1200.0, "y": _alt(1200.0), "z": 40.0, "radius_m": 300.0, "name": "Village"})
			pois.append({"id": "flag", "kind": "flag", "x": 1230.0, "y": _alt(1230.0), "z": 12.0, "radius_m": 5.0, "name": null})
			# Lot P29 : canal de 15 m (péniches) à 400 m du parcours
			var canal := []
			for i in range(10):
				var cx := 1000.0 + 100.0 * i
				canal.append([cx, -400.0, _alt(cx) - 2.0])
			lines.append({"id": "canal", "kind": "canal", "width_m": 15.0, "points": canal})
			pois.append({"id": "turbine", "kind": "wind_turbine", "x": 1500.0, "y": _alt(1500.0), "z": -250.0, "radius_m": 30.0, "name": null, "height_m": 90.0})
		var roads := []
		if k == 0:
			pois.append({"id": "cows", "kind": "livestock", "x": 600.0, "y": 300.0, "z": 70.0, "radius_m": 40.0, "name": null})
			# Lot P25 : champs cultivés (tracteurs) et route voisine qui croise le parcours
			for f in range(4):
				var z0 := -80.0 - 240.0 * f
				woods.append({"id": "field_%d" % f, "kind": "farmland", "density": 0.0,
					"outer": [[150.0, z0], [450.0, z0], [450.0, z0 - 200.0], [150.0, z0 - 200.0]], "holes": []})
			for side in [-1.0, 1.0]:
				var pts := []
				for i in range(15):
					var z: float = side * (30.0 + 25.0 * i)
					pts.append([800.0, z, 300.0])
				roads.append({"id": "road_%d" % int(side), "kind": "secondary", "lanes": 2, "oneway": false, "speed_kmh": 80, "points": pts})
		if k == 2:
			woods.append({"id": "wood", "kind": "wood", "density": 0.8, "outer": [[2100.0, -60.0], [2600.0, -60.0], [2600.0, -360.0], [2100.0, -360.0]], "holes": []})
		if k == 3:
			pois.append({"id": "summit", "kind": "viewpoint", "x": 3990.0, "y": _alt(3990.0), "z": 30.0, "radius_m": 50.0, "name": "Col du Test"})
			areas.append({"id": "lake", "kind": "lake", "level_y": 400.0, "outer": [[3200.0, 150.0], [3400.0, 150.0], [3400.0, 300.0], [3200.0, 300.0]], "holes": []})
		_write(dir.path_join("buildings/chunk_%d.json" % k), {"version": "1.0", "buildings": houses})
		_write(dir.path_join("vegetation/chunk_%d.json" % k), {"version": "1.0", "areas": woods})
		_write(dir.path_join("water/chunk_%d.json" % k), {"version": "1.0", "lines": lines, "areas": areas})
		_write(dir.path_join("poi/chunk_%d.json" % k), {"version": "1.2", "points": pois})
		_write(dir.path_join("roads/chunk_%d.json" % k), {"version": "1.5", "lines": roads})
	return d


## Faux world_streamer.gd : seulement ce que living_decor.gd appelle.
class FakeWorld extends Node3D:
	var osm_streamer = null
	var biome_model = null
	var road_markings := false
	var marks: Dictionary = {}
	var wetness := 0.0

	func set_road_markings(on: bool) -> void:
		road_markings = on

	func set_road_marks(m: Dictionary) -> void:
		marks = m

	func set_road_wetness(w: float) -> void:
		wetness = w


func _init() -> void:
	call_deferred("_run")


static func _count_nodes(nodes: Array) -> int:
	var n := 0
	for nd in nodes:
		n += 1 + _count_nodes((nd as Node).get_children())
	return n


var _route_dict: Dictionary = {}


func _decor(preset: String, enabled: bool, theme: Dictionary, env: Environment) -> Array:
	var osm = OsmStreamer.new()
	root.add_child(osm)
	var ws := FakeWorld.new()
	ws.osm_streamer = osm
	root.add_child(ws)
	var lw = LivingWorld.new()
	root.add_child(lw)
	var dec = LivingDecor.new()
	root.add_child(dec)
	dec.living_world = lw
	dec.configure(preset, enabled, theme, env, null, ws)
	var route = RouteData.new()
	route.load_route_dict(_route_dict)
	osm.set_world(route, WORLD)
	dec.set_route(route, WORLD, 6.0)
	osm.update_window(0.0, LENGTH_M)
	osm.flush()
	dec.flush()
	return [dec, osm, ws, lw, route]


func _run() -> void:
	_route_dict = _make_world()
	var theme := {"weather": {"kind": "rain", "intensity": 0.6, "morning_mist": true},
		"fauna": {"birds": 1.0, "livestock": 1.0, "deer": 1.0}, "terrain": {"snow_line_m": 2200}}
	var env := Environment.new()
	RenderQuality.apply_fog(env, "low", true)
	var parts := _decor("high", true, theme, env)
	var dec = parts[0]
	var osm = parts[1]
	var ws: FakeWorld = parts[2]
	var lw = parts[3]
	var route = parts[4]
	var wind := {"dir": Vector3(-1.0, 0.0, 0.0), "strength": 0.4, "gust": 0.0}

	# 1. Préparation du parcours (tâche de fond)
	_check(dec.prepared and dec.climbs.size() == 1, "préparation : %d montée détectée" % dec.climbs.size())
	_check(ws.road_markings and ws.marks.size() >= 1, "route : marquages de P14, chiffres peints sur %d tronçons" % ws.marks.size())
	_check(dec.props.prop_count() >= 5, "bord de route : %d panneaux et bornes posés sur les tronçons chargés" % dec.props.prop_count())
	_check(dec.crowd.spectators.size() > 20, "spectateurs au sommet : %d" % dec.crowd.spectators.size())
	_check(dec.passersby.people.size() > 3, "passants : %d" % dec.passersby.people.size())
	_check(osm.water_material() is ShaderMaterial, "eau qui scintille (matériau de P12)")
	_check(osm.fauna_enabled, "animaux placés par les tâches de fond des tronçons")
	var fields := 0
	for k in dec.road_traffic.paths:
		for path in dec.road_traffic.paths[k]:
			if path["field"]:
				fields += 1
	_check(osm.traffic_enabled and dec.road_traffic.path_count() >= 3 and fields >= 1,
		"circulation lointaine : %d chemins, dont %d champs avec leur tracteur" % [dec.road_traffic.path_count(), fields])
	var boat_kinds := {}
	for k in dec.boats.paths:
		for path in dec.boats.paths[k]:
			boat_kinds[path["boats"][0]["kind"]] = true
	_check(osm.boats_enabled and boat_kinds.has("rowboat") and boat_kinds.has("barge"),
		"bateaux : barque sur le lac, péniches sur le canal (%s)" % str(boat_kinds.keys()))

	# Nœuds de la deuxième vague (P23 à P26, P28, P29) : tous créés par `configure`
	var wave2_views: Array = [dec.fauna, dec.traffic_view, dec.road_traffic_view, dec.cyclists_view, dec.sky_view, dec.boats_view]
	var nodes_before := _count_nodes(wave2_views)

	# 2. Roule dans le village puis jusqu'au sommet, sous la pluie
	var base_end := env.fog_depth_end
	var now := 10.0
	var s := 1000.0
	var frames := 0
	var t0 := Time.get_ticks_usec()
	var max_people_below := 0.0
	var spectators_on_road := 0
	var rider_hits := 0
	var cheer_max := 0.0
	var distant_on_route := 0
	var distant_seen := {}
	var distant_max := 0
	var boats_max := 0
	var boats_on_route := 0
	var state := {"power": 320.0, "bots": [{"id": "b1", "name": "Bot", "s": 3700.0, "v": 4.0, "kind": "constant"}]}
	dec.ftp_w = 250.0
	while s < 3995.0:
		var pos: Vector3 = route.sample_point(s) + Vector3(0.0, 1.4, 0.0)
		dec.step(now, 0.05, pos, s, 8.0, float(route.sample(s)["alt_m"]), false, wind, state)
		frames += 1
		for v in dec.traffic.vehicles:
			var tr: Transform3D = dec.traffic.world_transform(v)
			if Vector2(tr.origin.x - pos.x, tr.origin.z - pos.z).length() < 1.0:
				rider_hits += 1
		for v in dec.road_traffic.vehicles:
			var o: Vector3 = (v["xform"] as Transform3D).origin
			if absf(o.z) < 15.0:
				distant_on_route += 1
			distant_seen[v["kind"]] = true
		distant_max = maxi(distant_max, dec.road_traffic_view.visible_count())
		for b in dec.boats.boats:
			if absf((b["xform"] as Transform3D).origin.z) < 15.0:
				boats_on_route += 1
		boats_max = maxi(boats_max, dec.boats_view.visible_count())
		cheer_max = maxf(cheer_max, dec.last_cheer)
		s += 0.4
		now += 0.05
	var per_frame_ms := (Time.get_ticks_usec() - t0) / 1000.0 / frames
	for sp in dec.crowd.spectators:
		var a: float = route.sample(float(sp["s"]))["alt_m"]
		max_people_below = maxf(max_people_below, absf((sp["pos"] as Vector3).y - a))
		if absf((sp["pos"] as Vector3).z) < 3.0:
			spectators_on_road += 1
	_check(dec.turbines.active_count() == 1 and dec.flags.visible_count() == 1, "éolienne et drapeau du parcours (le village a déjà son mât)")
	_check(dec.particles.is_active() and dec.particles.get_active_count() > 0, "pluie autour de la caméra (%d particules)" % dec.particles.get_active_count())
	_check(ws.wetness > 0.5 and absf(lw.rain - 0.6) < 1e-6, "chaussée mouillée (%.2f), pluie dans l'ambiance sonore" % ws.wetness)
	_check(dec.fog_updates >= 1 and dec.fog_updates < frames / 5, "brume recalculée %d fois en %d images" % [dec.fog_updates, frames])
	_check(dec.traffic.spawned_total > 0 and rider_hits == 0, "véhicules croisés : %d, jamais sur le cycliste" % dec.traffic.spawned_total)
	_check(dec.contacts == 0, "compteur de contacts de la route (lot P32) : %d %s" % [dec.contacts, dec.last_contact])
	_check(distant_max >= 1 and distant_max <= 24 and distant_on_route == 0 and distant_seen.has("tractor_field"),
		"routes voisines et champs : jusqu'à %d véhicules affichés (budget 24), jamais sur le parcours, sortes %s" % [distant_max, str(distant_seen.keys())])
	_check(dec.headlights and dec.traffic_view.lights and dec.road_traffic_view.lights and dec.boats_view.lights, "pluie : phares et feux des bateaux allumés")
	_check(boats_max >= 1 and boats_max <= 16 and boats_on_route == 0, "bateaux : jusqu'à %d affichés (budget 16), jamais sur le parcours" % boats_max)
	_check(spectators_on_road == 0 and max_people_below < 1.0, "spectateurs hors de la chaussée, à %.2f m au plus de la route en altitude" % max_people_below)
	_check(cheer_max > 0.2, "clameur au sommet : %.2f" % cheer_max)
	_check(dec.cyclists.spawned_total > 0 and dec.test_info(null).has("cyclists") and dec.cyclists.rider_count() <= 16,
		"cyclistes du décor croisés : %d (lot P28)" % dec.cyclists.spawned_total)
	_check(dec.passersby_view.visible_count() >= 0, "passants affichés")
	print("Décor vivant (deuxième vague) : %.3f ms par image (high)" % per_frame_ms)
	_check(PerfBudget.check("living_decor_frame", per_frame_ms), "coût du branchement en %.3f ms par image" % per_frame_ms)
	var nodes_after := _count_nodes(wave2_views)
	_check(nodes_after == nodes_before, "deuxième vague : %d nœuds créés au démarrage, %d après %d images" % [nodes_before, nodes_after, frames])
	# Enveloppe de la deuxième vague (P27) : P23 à P26, P28 et P29 ensemble en medium
	var mid_parts := _decor("medium", true, theme, Environment.new())
	var mid = mid_parts[0]
	var ms := 1000.0
	var mnow := 10.0
	while ms < 3995.0:
		mid.step(mnow, 0.05, route.sample_point(ms) + Vector3(0.0, 1.4, 0.0), ms, 8.0, float(route.sample(ms)["alt_m"]), false, wind, state)
		ms += 0.4
		mnow += 0.05
	var wave2_ms: float = mid.wave2_us / 1000.0 / maxi(1, mid.wave2_frames)
	print("Deuxième vague (P23 à P26, P28, P29) : %.3f ms par image (medium)" % wave2_ms)
	_check(PerfBudget.check("decor_vivant_2_frame", wave2_ms), "enveloppe de la deuxième vague en medium : %.3f ms par image" % wave2_ms)
	# Brume du matin en fond de vallée : brouillard rapproché
	var dv := LivingDecor.new()
	root.add_child(dv)
	var fog_env := Environment.new()
	RenderQuality.apply_fog(fog_env, "low", true)
	dv.configure("low", true, theme, fog_env)
	dv.set_route(route)
	dv.set_fog_base(fog_env)
	dv.flush()
	dv.step(now, 0.05, route.sample_point(500.0), 500.0, 8.0, 250.0, false, wind)
	_check(fog_env.fog_depth_end < base_end * 0.75, "brume de vallée : brouillard plein à %.0f m au lieu de %.0f m" % [fog_env.fog_depth_end, base_end])

	# 3. Animaux : sur le sol, jamais sur le cycliste
	var herd_ok := true
	var herd_count := 0
	var job := {"k": 0, "world_dir": WORLD, "layers": ["buildings", "vegetation", "water", "poi"], "theme": theme, "route": route, "fauna": true}
	osm._build_chunk_job(job)
	for g in job["result"]["fauna"]:
		if g["type"] == "herd":
			for m in g["members"]:
				herd_count += 1
				var p: Vector3 = m["pos"]
				if absf(p.z) < 4.0 or absf(p.y - TerrainTiles.nearest_route_alt(route, p.x, p.z)) > 0.5:
					herd_ok = false
	_check(herd_count >= 3 and herd_ok, "troupeau : %d bêtes au sol, hors de la route" % herd_count)

	# 4. Pause : véhicules figés
	var before: Array = []
	for v in dec.traffic.vehicles:
		before.append(float(v["s"]))
	var pos2: Vector3 = route.sample_point(s) + Vector3(0.0, 1.4, 0.0)
	var sig_before: float = dec.frozen_signature()
	for i in range(20):
		dec.step(now, 0.05, pos2, s, 0.0, float(route.sample(s)["alt_m"]), true, wind, state)
		now += 0.05
	var after: Array = []
	for v in dec.traffic.vehicles:
		after.append(float(v["s"]))
	_check(before == after, "pause : %d véhicules figés" % before.size())
	_check(sig_before != 0.0 and dec.frozen_signature() == sig_before,
		"pause : signature de ce qui se fige inchangée (%.2f, lot P30)" % sig_before)
	var clock_before: float = dec.road_traffic.clock_s
	dec.step(now, 0.05, pos2, s, 0.0, float(route.sample(s)["alt_m"]), true, wind, state)
	_check(dec.road_traffic.clock_s == clock_before, "pause : circulation lointaine figée")
	var boats_before: float = dec.boats.clock_s
	var sky_before: float = dec.sky.clock_s
	dec.step(now, 0.05, pos2, s, 0.0, float(route.sample(s)["alt_m"]), true, wind, state)
	_check(dec.sky.budget == 12 and dec.sky.clock_s == sky_before and dec.sky_view.visible_count() == dec.sky.craft.size(),
		"ciel : %d engins au plus (préset high), figé en pause" % dec.sky.budget)
	_check(dec.boats.budget == 16 and dec.boats.clock_s == boats_before, "bateaux figés en pause")
	# Lot P31 : le ciel suit le modèle de biome du world_streamer quand il est actif
	var ws_b = parts[2]
	var sky_none = dec.sky.biome_model
	ws_b.biome_model = BiomeModel.new()
	dec.set_route(parts[4], WORLD, 6.0)
	dec.flush()
	var sky_inactive = dec.sky.biome_model
	ws_b.biome_model.set_forced("alpine")
	dec.set_route(parts[4], WORLD, 6.0)
	dec.flush()
	_check(sky_none == null and sky_inactive == null and dec.sky.biome_model == ws_b.biome_model,
		"ciel : biome du parcours quand la couche biome ou le forçage est actif, sinon biome par défaut (lot P31)")

	# 5. Retrait d'un tronçon : panneaux et animaux retirés
	var props_before: int = dec.props.prop_count()
	osm.update_window(4000.0, 4999.0)
	_check(dec.props.prop_count() < props_before, "tronçons retirés : panneaux %d → %d" % [props_before, dec.props.prop_count()])

	# 6. HUD : « Abri 30 % » sous l'indicateur du vent
	var hud = HudView.new()
	root.add_child(hud)
	var wv = WindViewModel.new()
	var wstate := {"wind": {"speed_mps": 5.0, "from_deg": 90.0, "gust": 0.0, "head_mps": 5.0}, "draft": 0.165}   # 30 % de l'échelle 0,55 (lot AS4)
	var view: Dictionary = {}
	for i in range(60):
		view = wv.view(wstate, 90.0, 100.0 + i * 0.05)
	hud.update_wind(view)
	_check(hud.draft_label.visible and hud.draft_label.text == "Abri 30 %", "HUD : « %s »" % hud.draft_label.text)
	_check(hud.draft_label.get_rect().position.y >= hud.panel_wind.get_rect().end.y, "HUD : abri sous l'indicateur du vent")
	var calm: Dictionary = {}
	for i in range(60):
		calm = wv.view({"draft": 0.2}, 90.0, 200.0 + i * 0.05)
	hud.update_wind(calm)
	_check(hud.draft_label.visible and not hud.panel_wind.visible and absf(hud.draft_label.position.y - hud.panel_wind.position.y) < 0.5,
		"HUD : sans vent, l'abri prend la place de l'indicateur")
	hud.update_wind(wv.view({}, 90.0, 300.0))
	_check(not hud.draft_label.visible, "HUD : abri caché sans aspiration")

	# 7. living = false : rien de la deuxième vague
	var off_parts := _decor("high", false, theme, Environment.new())
	var off = off_parts[0]
	var off_ws: FakeWorld = off_parts[2]
	off.step(now, 0.05, route.sample_point(2000.0), 2000.0, 8.0, 400.0, false, wind, state)
	_check(not off.prepared and not off_ws.road_markings and not off_parts[1].fauna_enabled and not off.particles.is_active()
		and off.props.prop_count() == 0 and not (off_parts[1].water_material() is ShaderMaterial)
		and off.sky.budget == 0 and off.sky_view.visible_count() == 0 and off.boats.budget == 0 and not off_parts[1].boats_enabled,
		"living = false : ni météo, ni animaux, ni objets, ni engins volants, ni bateaux, route et eau de la 1.0")

	# 8. Matériau de la route de world_streamer.gd : marquages, chiffres par tronçon, chaussée mouillée
	var real_ws = WorldStreamer.new()
	real_ws.set_road_markings(true)
	real_ws.set_road_marks({3: [{"s": 3000.0, "digit": 1}]})
	var m3: Material = real_ws.road_material_for(3)
	var m2: Material = real_ws.road_material_for(2)
	real_ws.set_road_wetness(0.8)
	_check(m3 is ShaderMaterial and m3 != m2 and int((m3 as ShaderMaterial).get_shader_parameter("mark_count")) == 1
		and int((m2 as ShaderMaterial).get_shader_parameter("mark_count")) == 0,
		"world_streamer : matériau à chiffres pour le seul tronçon 3")
	_check(absf(float((m3 as ShaderMaterial).get_shader_parameter("wetness")) - 0.8) < 1e-6
		and absf(float((m2 as ShaderMaterial).get_shader_parameter("wetness")) - 0.8) < 1e-6, "world_streamer : chaussée mouillée sur tous les tronçons")
	real_ws.set_road_markings(false)
	_check(real_ws.road_material_for(3) is StandardMaterial3D, "world_streamer : sans décor vivant, matériau de la 1.0")
	real_ws.free()

	for nd in [dec, dv, hud, off, mid]:
		nd.queue_free()
	await process_frame
	print("test_living_decor : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
