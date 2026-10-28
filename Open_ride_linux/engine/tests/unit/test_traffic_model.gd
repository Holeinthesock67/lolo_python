extends SceneTree

## Tests sans écran de la circulation `traffic_model.gd` (Lot P13) : séance simulée de 30 km à 30 km/h,
## sécurité (écarts, dépassements), déterminisme, budget, coût par image ; affichage `traffic_renderer.gd`.
## Lot P25 : sept sortes et leurs vitesses, phares, affichage refait (caisse, roues, son par sorte).
## Lancement : godot --headless --path engine --script res://tests/unit/test_traffic_model.gd

const TrafficModel := preload("res://scripts/traffic_model.gd")
const TrafficRenderer := preload("res://scripts/traffic_renderer.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const LENGTH_M := 32000.0
const SNOW_FROM := 12000.0      # de 12 à 15 km : au-dessus de la limite de neige
const SNOW_TO := 15000.0
const STEEP_FROM := 20000.0     # de 20 à 22 km : pente de 10 %
const STEEP_TO := 22000.0

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite vers l'est, avec un passage enneigé et une rampe raide.
func _route():
	var ds := 10.0
	var n := int(LENGTH_M / ds) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var s := i * ds
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(2500.0 if s >= SNOW_FROM and s < SNOW_TO else 400.0)
		cols["x"].append(s)
		cols["z"].append(0.0)
		cols["grade_pct"].append(10.0 if s >= STEEP_FROM and s < STEEP_TO else 2.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


func _villages() -> Array:
	var out := []
	for x in [3000.0, 9000.0, 17000.0, 26000.0]:
		out.append({"id": "v%d" % int(x), "kind": "village", "x": x, "y": 400.0, "z": 300.0, "radius_m": 300, "name": null})
	return out


## Séance de 30 km à 30 km/h (pas de 1/30 s) ; rend le relevé des contrôles.
func _ride(route, budget: int, rng_seed: int) -> Dictionary:
	var tm = TrafficModel.new()
	tm.configure(route, {"terrain": {"snow_line_m": 2200.0}}, _villages(), budget, rng_seed)
	var v_mps := 30.0 / 3.6
	var dt := 1.0 / 30.0
	var s := 500.0
	var seen := {}
	var log := []
	var max_live := 0
	var overlap := 0
	var too_close := 0
	var bad_pass := 0
	var bad_spawn := 0
	var usec := 0
	var frames := 0
	while s < 30500.0:
		var t0 := Time.get_ticks_usec()
		tm.update(s, v_mps, dt)
		usec += Time.get_ticks_usec() - t0
		frames += 1
		var vs: Array = tm.vehicles
		max_live = maxi(max_live, vs.size())
		for v in vs:
			if not seen.has(v["id"]):
				seen[v["id"]] = true
				log.append([v["id"], v["kind"], v["dir"], snappedf(float(v["s"]), 0.01)])
				var sp := float(v["s"])
				if (sp >= SNOW_FROM and sp < SNOW_TO) or (sp >= STEEP_FROM and sp < STEEP_TO):
					bad_spawn += 1
			var k: Dictionary = TrafficModel.KINDS[v["kind"]]
			if absf(float(v["s"]) - s) < float(k["length"]) * 0.5 + 0.5:
				if absf(float(v["lateral"])) - float(k["half_width"]) - TrafficModel.RIDER_HALF_WIDTH_M < TrafficModel.LATERAL_CLEARANCE_M - 1e-4:
					too_close += 1
			if int(v["dir"]) == 1 and float(v["lateral"]) < 0.0:
				for o in vs:
					if int(o["dir"]) == -1 and float(o["s"]) > float(v["s"]) and float(o["s"]) - float(v["s"]) < 150.0:
						bad_pass += 1
		for i in range(vs.size()):
			for j in range(i + 1, vs.size()):
				var a: Dictionary = vs[i]
				var b: Dictionary = vs[j]
				var ka: Dictionary = TrafficModel.KINDS[a["kind"]]
				var kb: Dictionary = TrafficModel.KINDS[b["kind"]]
				if absf(float(a["s"]) - float(b["s"])) < (float(ka["length"]) + float(kb["length"])) * 0.5 \
						and absf(float(a["lateral"]) - float(b["lateral"])) < float(ka["half_width"]) + float(kb["half_width"]):
					overlap += 1
		s += v_mps * dt
	return {"count": seen.size(), "overtakes": tm.overtakes_total, "log": log, "max_live": max_live, "overlap": overlap,
		"too_close": too_close, "bad_pass": bad_pass, "bad_spawn": bad_spawn, "avg_ms": usec / 1000.0 / frames}


func _test_renderer(route) -> void:
	var sp = SoundPlayer.new()
	root.add_child(sp)
	var tr = TrafficRenderer.new()
	root.add_child(tr)
	await process_frame
	var n0: int = tr.get_child_count()
	var tm = TrafficModel.new()
	tm.configure(route, {}, _villages(), 3, 7)
	tr.setup(tm, sp)
	var s := 500.0
	var max_shown := 0
	var match_ok := true
	var spun := false
	var sound_ok := true
	var usec := 0
	for i in range(9000):
		var t0 := Time.get_ticks_usec()
		tm.update(s, 30.0 / 3.6, 1.0 / 30.0)
		tr.update()
		usec += Time.get_ticks_usec() - t0
		max_shown = maxi(max_shown, tr.visible_count())
		match_ok = match_ok and tr.visible_count() == tm.vehicles.size()
		for j in range(tm.vehicles.size()):
			var slot: Dictionary = tr._slots[j]
			var v: Dictionary = tm.vehicles[j]
			match_ok = match_ok and slot["root"].transform.origin.is_equal_approx(tm.world_transform(v).origin) \
				and slot["body"].mesh == tr._bodies[v["kind"]]
			var w: Node3D = slot["wheels"][0]
			spun = spun or absf(w.rotation.x) > 0.1
			var snd: Array = TrafficRenderer.SOUND[v["kind"]]
			sound_ok = sound_ok and slot["audio"].stream == sp.stream(snd[0]) and is_equal_approx(slot["audio"].pitch_scale, snd[2])
		s += 30.0 / 3.6 / 30.0
	_check(match_ok and max_shown >= 1 and max_shown <= 3, "affichage : un véhicule du pool par véhicule du modèle, à sa place (%d au plus)" % max_shown)
	_check(spun and sound_ok, "roues qui tournent, son du passage (à la hauteur de la sorte) ou du tracteur sur chaque véhicule")
	var mat: ShaderMaterial = tr._slots[0]["mat"]
	tr.set_lights(true)
	var lit: bool = float(mat.get_shader_parameter("lights")) == 1.0
	tr.set_lights(false)
	_check(lit and float(mat.get_shader_parameter("lights")) == 0.0, "phares allumés puis éteints")
	# Chaque sorte habillée : sa caisse, ses roues, sa peinture
	var fake := {"vehicles": []}
	var kinds: Array = TrafficModel.KINDS.keys()
	for j in range(kinds.size()):
		fake["vehicles"].append({"id": "f%d" % j, "kind": kinds[j], "color": j, "s": 600.0 + 30.0 * j, "dir": -1,
			"lateral": -3.0, "wheel": 0.0})
	var fm = TrafficModel.new()
	fm.configure(route, {}, [], 8, 1)
	fm.vehicles = fake["vehicles"]
	tr.setup(fm, sp)
	tr.update()
	var dressed := true
	for j in range(kinds.size()):
		var slot: Dictionary = tr._slots[j]
		var nw := VehicleMesh.wheel_list(kinds[j]).size()
		var shown := 0
		for w in slot["wheels"]:
			if w.visible:
				shown += 1
		dressed = dressed and slot["body"].mesh == tr._bodies[kinds[j]] and shown == nw \
			and slot["mat"].get_shader_parameter("paint") == VehicleMesh.paint(kinds[j], j)
	_check(dressed and tr.visible_count() == kinds.size(), "les %d sortes habillées : caisse, roues et peinture" % kinds.size())
	_check(tr.get_child_count() == n0, "aucun nœud créé après le démarrage")
	var avg := usec / 1000.0 / 9000.0
	_check(PerfBudget.check("traffic_frame", avg), "modèle et affichage mis à jour en %.4f ms par image" % avg)
	tr.queue_free()
	sp.queue_free()
	await process_frame


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = _route()
	var r: Dictionary = _ride(route, 3, 7)
	print("30 km : %d véhicules, %d dépassements, %d à la fois au plus ; %.4f ms par image" % [
		r["count"], r["overtakes"], r["max_live"], r["avg_ms"]])
	_check(r["count"] >= 3 and r["count"] <= 15 and r["overtakes"] >= 1,
		"30 km à 30 km/h : entre 3 et 15 véhicules (%d), au moins un dépassement (%d)" % [r["count"], r["overtakes"]])
	_check(r["bad_spawn"] == 0, "aucun véhicule au-dessus de la limite de neige ni sur la pente de 10 %")
	_check(r["overlap"] == 0, "jamais deux véhicules au même endroit")
	_check(r["too_close"] == 0, "jamais un véhicule à moins de 1,5 m latéralement du cycliste")
	_check(r["bad_pass"] == 0, "jamais de dépassement face à un véhicule venant en sens inverse")
	_check(r["max_live"] <= 3, "jamais plus que le budget de 3 (%d)" % r["max_live"])
	var r2: Dictionary = _ride(route, 3, 7)
	_check(str(r2["log"]) == str(r["log"]), "même graine, même parcours : même suite de véhicules")
	var r3: Dictionary = _ride(route, 3, 8)
	_check(str(r3["log"]) != str(r["log"]), "autre graine : autre suite")
	var safe := true
	var counts := []
	for sd in range(1, 13):
		var rs: Dictionary = _ride(route, 5, sd)
		counts.append(rs["count"])
		safe = safe and rs["overlap"] == 0 and rs["too_close"] == 0 and rs["bad_pass"] == 0 and rs["bad_spawn"] == 0 \
			and rs["max_live"] <= 5 and rs["count"] >= 3 and rs["count"] <= 15
	_check(safe, "12 autres graines, budget 5 : mêmes garanties, de 3 à 15 véhicules (%s)" % str(counts))
	# Lot P25 : les sept sortes, d'après leurs parts
	var drawn := {}
	var tm_k = TrafficModel.new()
	for sd in range(200):
		tm_k.configure(route, {}, _villages(), 5, 100 + sd)
		for k in range(int(LENGTH_M / TrafficModel.SLOT_M)):
			var ev: Dictionary = tm_k.slot_event(k)
			if ev.is_empty():
				continue
			drawn[ev["kind"]] = int(drawn.get(ev["kind"], 0)) + 1
			var kmh: Vector2 = TrafficModel.KINDS[ev["kind"]]["kmh"]
			safe = safe and float(ev["cruise_mps"]) * 3.6 >= kmh.x - 1e-3 and float(ev["cruise_mps"]) * 3.6 <= kmh.y + 1e-3
	var share_sum := 0.0
	for kind in TrafficModel.KINDS:
		share_sum += float(TrafficModel.KINDS[kind]["share"])
	_check(drawn.size() == TrafficModel.KINDS.size() and safe and absf(share_sum - 1.0) < 1e-6,
		"sept sortes tirées sur 200 graines, vitesses dans la plage de chaque sorte (%s)" % str(drawn))
	_check(TrafficModel.pick_kind(0.0) == "car_a" and TrafficModel.pick_kind(0.999) == "tractor",
		"tirage de la sorte dans l'ordre de la table")
	var sun := 45.0
	_check(not TrafficModel.headlights({"fog_boost": 0.0, "rain": 0.0}, sun) and TrafficModel.headlights({"fog_boost": 0.5}, sun)
		and TrafficModel.headlights({"rain": 0.6}, sun) and TrafficModel.headlights({}, 3.0),
		"phares : éteints par beau temps, allumés dans la brume, sous la pluie ou au soleil bas")
	var r0: Dictionary = _ride(route, 0, 7)
	_check(r0["count"] == 0, "budget nul : aucun véhicule")
	_check(PerfBudget.check("traffic_view_frame", r["avg_ms"]), "mise à jour en %.4f ms par image" % r["avg_ms"])

	# Pause : véhicules figés
	var tm = TrafficModel.new()
	tm.configure(route, {}, _villages(), 3, 7)
	var s := 2000.0
	while tm.vehicles.is_empty() and s < 30000.0:
		tm.update(s, 8.0, 0.1)
		s += 0.8
	var before := str(tm.vehicles)
	for i in range(50):
		tm.update(s, 0.0, 0.1, true)
	_check(not tm.vehicles.is_empty() and str(tm.vehicles) == before, "pause : véhicules figés")
	await _test_renderer(route)
	print("test_traffic_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
