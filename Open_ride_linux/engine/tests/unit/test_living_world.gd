extends SceneTree

## Tests sans écran du branchement du décor vivant `living_world.gd` (Lot P16) : ciel de P6, vent du
## core vers le décor et l'indicateur du HUD, nuages qui suivent le vent, voisinage sonore au plus
## 2 fois par seconde, exclusions de l'herbe, coupure complète avec `living = false`, coût par image.
## Lancement : godot --headless --path engine --script res://tests/unit/test_living_world.gd

const LivingWorld := preload("res://scripts/living_world.gd")
const SkyClouds := preload("res://scripts/sky_clouds.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const HudView := preload("res://scripts/hud_view.gd")
const RouteData := preload("res://scripts/route_data.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite et plate vers l'est, de `length_m` mètres.
static func _route(length_m: float):
	var ds := 10.0
	var n := int(length_m / ds) + 1
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		d["lat"].append(48.9)
		d["lon"].append(7.1)
		d["alt_m"].append(300.0)
		d["x"].append(i * ds)
		d["z"].append(0.0)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(90.0)
	var r = RouteData.new()
	r.load_route_dict(d)
	return r


## Faux osm_streamer.gd : une forêt carrée autour de x = 500, une maison à x = 1 500.
class FakeOsm:
	var shapes_version := 1
	var calls := 0

	static func _sq(cx: float, cz: float, half: float) -> Dictionary:
		var pts := PackedVector2Array([Vector2(cx - half, cz - half), Vector2(cx + half, cz - half),
			Vector2(cx + half, cz + half), Vector2(cx - half, cz + half)])
		return {"points": pts, "rect": Rect2(cx - half, cz - half, 2.0 * half, 2.0 * half)}

	func layer_shapes() -> Dictionary:
		calls += 1
		var house := _sq(1500.0, 20.0, 6.0)
		return {"forests": [_sq(500.0, 0.0, 400.0)], "buildings": [house], "waters": []}


static func _env() -> Environment:
	var env := Environment.new()
	env.sky = Sky.new()
	env.sky.sky_material = SkyClouds.current_sky_material()
	return env


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var theme := {"sky": {"clouds": {"coverage": 0.5, "speed_factor": 1.0, "altitude_m": 1500}},
		"wind": {"speed_kmh": 8, "from_deg": 270, "gust_pct": 20}, "ambience": {"volume": 0.6}}
	var route = _route(3000.0)   # vers l'est
	var sp = SoundPlayer.new()
	root.add_child(sp)

	# 1. Décor vivant actif, préréglage low
	var env := _env()
	var old_sky: Material = env.sky.sky_material
	var osm := FakeOsm.new()
	var lw = LivingWorld.new()
	root.add_child(lw)
	lw.configure("low", true, theme, env, sp, osm)
	lw.set_route(route)
	_check(SkyClouds.is_cloud_material(env.sky.sky_material) and env.sky.sky_material != old_sky,
		"ciel de P6 à la place du ciel actuel (nuages « flat » en low)")
	_check(lw.grass.get_capacity() > 0 and lw.grass.get_capacity() <= 1500, "low : touffes d'herbe dans le budget de Y11 H5 (1 500)")

	# Vent de face de 26 km/h : le cycliste roule vers l'est, le vent vient de l'est
	var now := 100.0
	var state := {"wind": {"speed_mps": 26.0 / 3.6, "from_deg": 90.0, "gust": 0.0, "head_mps": 26.0 / 3.6}, "s": 500.0}
	var hud_view: Dictionary = {}
	var off0: Vector2 = env.sky.sky_material.get_shader_parameter("cloud_offset")
	var t0 := Time.get_ticks_usec()
	var frames := 0
	for i in range(120):
		if i % 3 == 0:
			lw.on_state(state, now)
			hud_view = lw.wind_hud(state, 90.0, now)
		lw.step(now, 1.0 / 60.0, Vector3(500.0, 1.4, 0.0), 500.0, 8.0, 90.0, 300.0, false)
		now += 1.0 / 60.0
		frames += 1
	var per_frame_ms := (Time.get_ticks_usec() - t0) / 1000.0 / frames
	var off1: Vector2 = env.sky.sky_material.get_shader_parameter("cloud_offset")
	var dir: Vector3 = lw.last_wind["dir"]
	_check(dir.x < -0.9 and float(lw.last_wind["strength"]) > 0.3, "vent du core vers le décor : souffle vers l'ouest, force %.2f" % float(lw.last_wind["strength"]))
	_check((off1 - off0).x > 0.0, "nuages qui défilent dans le sens du vent (décalage du motif %.1f m)" % (off1 - off0).x)
	_check(hud_view.get("visible", false) and hud_view["label"] == "face" and hud_view["tone"] == "bad"
		and hud_view["level_text"] == "fort", "indicateur : « %s %s », %s, %s" % [hud_view.get("speed_text"), hud_view.get("label"),
		hud_view.get("verdict_text"), hud_view.get("level_text")])
	_check(lw.neigh_updates >= 3 and lw.neigh_updates <= 5, "voisinage sonore recalculé %d fois en 2 s (au plus 2 fois par seconde)" % lw.neigh_updates)
	_check(float(lw.neigh.get("forest_share", 0.0)) > 0.9 and osm.calls == 1, "en forêt : part de forêt %.2f, contours lus une seule fois" % float(lw.neigh.get("forest_share", 0.0)))
	_check(float(lw.neigh.get("wind_strength", 0.0)) > 0.3 and float(lw.neigh.get("alt_m", 0.0)) == 300.0,
		"voisinage complété par la force du vent et l'altitude")
	_check(lw.grass.exclusions.size() == 1, "maison chargée exclue des touffes d'herbe")
	print("Décor vivant : %.3f ms par image (low, voisinage compris)" % per_frame_ms)
	_check(PerfBudget.check("living_world_frame", per_frame_ms), "coût du branchement en %.3f ms par image" % per_frame_ms)
	# Demi-tour : vent de dos
	var back := {"wind": {"speed_mps": 25.0 / 3.6, "from_deg": 90.0, "gust": 0.0, "head_mps": -25.0 / 3.6}}
	for i in range(80):
		hud_view = lw.wind_hud(back, 270.0, now)
		now += 0.05
	_check(hud_view["label"] == "dos" and hud_view["tone"] == "good", "demi-tour : « %s », %s" % [hud_view["label"], hud_view["verdict_text"]])
	var cross := {"wind": {"speed_mps": 25.0 / 3.6, "from_deg": 0.0, "gust": 0.0, "head_mps": 0.0}}
	for i in range(80):
		hud_view = lw.wind_hud(cross, 90.0, now)
		now += 0.05
	_check(hud_view["verdict"] == "neutre" and hud_view["tone"] == "neutral", "route en travers du vent : %s" % hud_view["verdict_text"])

	# 2. HUD : panneau du vent sous le panneau de gauche, caché sans vent
	var hud = HudView.new()
	root.add_child(hud)
	for i in range(80):
		hud_view = lw.wind_hud(state, 90.0, now)
		now += 0.05
	hud.update_wind(hud_view)
	_check(hud.panel_wind.visible and hud.wind_speed_label.text.ends_with("face") and hud.wind_verdict_label.text == "Vent défavorable",
		"HUD : « %s », « %s »" % [hud.wind_speed_label.text, hud.wind_verdict_label.text])
	var left_end: float = hud.panel_left.get_rect().end.y
	_check(hud.panel_wind.get_rect().position.y >= left_end and hud.panel_wind.get_rect().end.x <= hud.panel_left.get_rect().end.x + 0.5,
		"HUD : indicateur sous le panneau de gauche, coin supérieur droit laissé libre")
	hud.update_wind(lw.wind_hud({}, 90.0, now + 10.0))
	_check(not hud.panel_wind.visible, "HUD : indicateur caché sans vent")

	# 3. living = false : rendu et sons de la 1.0
	var env_off := _env()
	var sky_off: Material = env_off.sky.sky_material
	var sp_off = SoundPlayer.new()
	root.add_child(sp_off)
	var off = LivingWorld.new()
	root.add_child(off)
	off.configure("high", false, theme, env_off, sp_off, FakeOsm.new())
	off.set_route(route)
	for i in range(30):
		off.on_state(state, now)
		off.step(now, 1.0 / 60.0, Vector3(500.0, 1.4, 0.0), 500.0, 8.0, 90.0, 300.0, false)
		now += 1.0 / 60.0
	var beds_silent := true
	for bed in sp_off._bed_players:
		beds_silent = beds_silent and (sp_off._bed_players[bed] as AudioStreamPlayer).volume_db <= -79.0
	_check(env_off.sky.sky_material == sky_off and off.grass.get_capacity() == 0 and off.neigh_updates == 0 and beds_silent,
		"living = false : ciel, herbe et ambiance de la 1.0")
	_check(off.wind_hud(state, 90.0, now)["visible"], "living = false : le vent du core reste affiché")

	# 4. high : touffes d'herbe le long de la route
	var hi = LivingWorld.new()
	root.add_child(hi)
	hi.configure("high", true, theme, _env(), null, null)
	hi.set_route(route)
	for i in range(30):
		hi.step(now, 1.0 / 60.0, Vector3(500.0, 1.4, 0.0), 500.0, 8.0, 90.0)
		now += 1.0 / 60.0
	_check(hi.grass.get_capacity() > 0 and hi.grass.get_visible_count() > 0, "high : %d touffes d'herbe placées" % hi.grass.get_visible_count())

	for n in [lw, off, hi, hud, sp, sp_off]:
		n.queue_free()
	await process_frame
	print("test_living_world : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
