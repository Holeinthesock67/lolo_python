extends SceneTree

## Tests sans écran du ciel du Lot P26 : maillages `sky_mesh.gd` (tailles, zones, faces), modèle
## `sky_traffic_model.gd` (horaires des avions de ligne et de l'hélicoptère, homothétie des avions lointains,
## parapentes au-dessus des montées, montgolfières par vent faible, météo qui cloue tout au sol, budget et
## priorités, déterminisme, pause, coût par image) et affichage `sky_traffic_renderer.gd`. Lot P31 : ciel
## selon le biome (BIOME_SKY), paramoteurs, motifs d'enveloppe des montgolfières.
## Lancement : godot --headless --path engine --script res://tests/unit/test_sky_traffic_model.gd

const SkyModel := preload("res://scripts/sky_traffic_model.gd")
const SkyRenderer := preload("res://scripts/sky_traffic_renderer.gd")
const SkyMesh := preload("res://scripts/sky_mesh.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")

const CLEAR := {"rain": 0.0, "fog_boost": 0.0}
const CALM := {"dir": Vector3(1.0, 0.0, 0.0), "strength": 0.2, "gust": 0.0}
const CLIMBS := [{"summit_s": 3000.0, "gain_m": 200.0}, {"summit_s": 8000.0, "gain_m": 150.0},
	{"summit_s": 12000.0, "gain_m": 300.0}, {"summit_s": 16000.0, "gain_m": 250.0}, {"summit_s": 18000.0, "gain_m": 40.0}]

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _route():
	var ds := 10.0
	var n := 2001
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(400.0)
		cols["x"].append(i * ds)
		cols["z"].append(0.0)
		cols["grade_pct"].append(0.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


## `biome` : biome forcé sur tout le parcours (lot P31), "" : sans couche biome.
func _model(route, budget: int, theme: Dictionary = {}, rng_seed: int = 5, biome: String = ""):
	var m = SkyModel.new()
	if biome != "":
		var bm = BiomeModel.new()
		bm.set_forced(biome)
		m.biome_model = bm
	m.configure(route, theme, CLIMBS, budget, rng_seed)
	return m


## Deux heures à 10 images/s, caméra immobile : relevé des engins.
func _fly(m, cam: Vector3, wind: Dictionary, weather: Dictionary, seconds: float = 7200.0) -> Dictionary:
	var ids := {}
	var max_kind := {}
	var bad_far := 0
	var low_plane := 0
	var heli_bad := 0
	var motor_bad := 0
	var styles := {}
	var log := []
	var steps := int(seconds * 10.0)
	for i in range(steps):
		m.update(cam, 0.1, wind, weather)
		var per := {}
		for c in m.craft:
			ids[c["id"]] = c["kind"]
			per[c["kind"]] = int(per.get(c["kind"], 0)) + 1
			var tr: Transform3D = c["xform"]
			if c["kind"] == "airliner":
				var k := tr.basis.get_scale().x
				var d := tr.origin - cam
				if d.length() > SkyModel.RENDER_M + 1.0 or absf(d.length() / k - float(c["dist"])) > 1.0:
					bad_far += 1
				if d.normalized().y < sin(deg_to_rad(9.0)):
					low_plane += 1
			elif c["kind"] == "helicopter":
				var up := tr.origin.y - cam.y
				if up < SkyModel.HELI_AGL_M.x - 0.1 or up > SkyModel.HELI_AGL_M.y + 0.1:
					heli_bad += 1
			elif c["kind"] == "paramotor":
				var up := tr.origin.y - cam.y
				if up < SkyModel.PARAMOTOR_AGL_M.x - 0.1 or up > SkyModel.PARAMOTOR_AGL_M.y + SkyModel.PARAMOTOR_WINGMAN.y + 0.1:
					motor_bad += 1
			elif c["kind"] == "balloon":
				styles[int(c["style"])] = true
		for k in per:
			max_kind[k] = maxi(int(max_kind.get(k, 0)), per[k])
		if i % 600 == 0:
			log.append(str(m.craft))
	var counts := {}
	for id in ids:
		counts[ids[id]] = int(counts.get(ids[id], 0)) + 1
	return {"counts": counts, "max": max_kind, "bad_far": bad_far, "low_plane": low_plane, "heli_bad": heli_bad,
		"motor_bad": motor_bad, "styles": styles, "log": log}


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_meshes()
	var route = _route()
	var cam := Vector3(5000.0, 401.4, 0.0)

	# 1. Deux heures de ciel clair, vent faible
	var r: Dictionary = _fly(_model(route, 12), cam, CALM, CLEAR)
	var c: Dictionary = r["counts"]
	print("2 h : %s ; au plus à la fois : %s" % [str(c), str(r["max"])])
	_check(int(c.get("airliner", 0)) >= 35 and int(c.get("airliner", 0)) <= 75 and int(r["max"].get("airliner", 0)) <= SkyRenderer.POOL["airliner"],
		"avions de ligne : %d vols en 2 h, %d à la fois au plus" % [int(c.get("airliner", 0)), int(r["max"].get("airliner", 0))])
	_check(int(c.get("helicopter", 0)) >= 3 and int(c.get("helicopter", 0)) <= 16 and int(r["max"].get("helicopter", 0)) <= 2,
		"hélicoptère : %d passages en 2 h" % int(c.get("helicopter", 0)))
	_check(int(c.get("balloon", 0)) >= 1 and int(r["max"].get("balloon", 0)) <= SkyRenderer.POOL["balloon"] and int(r["max"].get("paraglider", 0)) <= SkyRenderer.POOL["paraglider"],
		"montgolfières par vent faible : %d" % int(c.get("balloon", 0)))
	_check(r["bad_far"] == 0 and r["low_plane"] == 0,
		"avions lointains : dessinés à %.0f m au plus dans leur vraie direction, toujours à plus de 9° au-dessus de l'horizon" % SkyModel.RENDER_M)
	_check(r["heli_bad"] == 0, "hélicoptère à %d à %d m au-dessus de la caméra" % [int(SkyModel.HELI_AGL_M.x), int(SkyModel.HELI_AGL_M.y)])
	_check(int(c.get("paramotor", 0)) >= 2 and int(r["max"].get("paramotor", 0)) <= SkyRenderer.POOL["paramotor"] and r["motor_bad"] == 0,
		"paramoteurs sans couche biome : %d en 2 h, à %d à %d m au-dessus de la caméra" % [int(c.get("paramotor", 0)),
		int(SkyModel.PARAMOTOR_AGL_M.x), int(SkyModel.PARAMOTOR_AGL_M.y)])
	_check((r["styles"] as Dictionary).size() >= 3, "montgolfières de %d motifs d'enveloppe" % (r["styles"] as Dictionary).size())
	var r2: Dictionary = _fly(_model(route, 12), cam, CALM, CLEAR)
	_check(r2["log"] == r["log"], "même graine : même ciel")
	var r3: Dictionary = _fly(_model(route, 12, {}, 6), cam, CALM, CLEAR, 1800.0)
	_check(r3["log"] != (r["log"] as Array).slice(0, (r3["log"] as Array).size()), "autre graine : autre ciel")

	# 2. Parapentes au-dessus des montées
	var m = _model(route, 12)
	var groups := {}
	var near_ok := true
	for p in m.paragliders:
		var climb := int((p["id"] as String).substr(1).get_slice("_", 0))
		groups[climb] = true
		var top: Vector3 = route.sample_point(float(CLIMBS[climb]["summit_s"]))
		var centre: Vector3 = p["centre"]
		var side := absf(centre.z - top.z)
		near_ok = near_ok and climb != 4 and side >= SkyModel.PARA_SIDE_M.x - 0.01 and side <= SkyModel.PARA_SIDE_M.y + 0.01 \
			and centre.y - top.y >= SkyModel.PARA_ABOVE_M.x - 0.01 and centre.y - top.y <= SkyModel.PARA_ABOVE_M.y + 0.01
	_check(m.paragliders.size() >= 1 and near_ok, "parapentes : %d voiles au-dessus de %d montées (pas sur une bosse de 40 m)" % [m.paragliders.size(), groups.size()])
	var first: Dictionary = m.paragliders[0]
	var pcam: Vector3 = first["centre"] + Vector3(0.0, -200.0, 300.0)
	var circling := true
	var seen_para := false
	for i in range(300):
		m.update(pcam, 0.1, CALM, CLEAR)
		for cr in m.craft:
			if cr["id"] == first["id"]:
				seen_para = true
				var o: Vector3 = (cr["xform"] as Transform3D).origin
				var flat := Vector2(o.x - first["centre"].x, o.z - first["centre"].z).length()
				circling = circling and absf(flat - float(first["radius"])) < 0.01 and absf(o.y - first["centre"].y) <= SkyModel.PARA_BOB_M + 0.01
	_check(seen_para and circling, "parapente qui tourne dans son ascendance (rayon %.0f m)" % float(first["radius"]))
	var windy := {"dir": Vector3(1.0, 0.0, 0.0), "strength": 0.8, "gust": 0.3}
	m.update(pcam, 0.1, windy, CLEAR)
	_check(m.count("paraglider") == 0 and m.count("balloon") == 0, "grand vent : ni parapente ni montgolfière")

	# 3. Montgolfières qui dérivent avec le vent
	var mb = _model(route, 12)
	var b0 := {}
	var b1 := {}
	for i in range(int(SkyModel.BALLOON_SLOT_S * 2.0)):
		mb.update(cam, 1.0, CALM, CLEAR)
		for cr in mb.craft:
			if cr["kind"] == "balloon":
				if not b0.has(cr["id"]):
					b0[cr["id"]] = [mb.clock_s, (cr["xform"] as Transform3D).origin]
				b1[cr["id"]] = [mb.clock_s, (cr["xform"] as Transform3D).origin]
	var drift_ok := not b0.is_empty()
	var want := SkyModel.BALLOON_DRIFT_MPS * (0.5 + float(CALM["strength"]))
	for id in b0:
		var dt := float(b1[id][0]) - float(b0[id][0])
		if dt < 300.0:
			continue
		var dp: Vector3 = b1[id][1] - b0[id][1]
		drift_ok = drift_ok and absf(dp.x / dt - want) < 0.01 and absf(dp.z) < 0.01
	_check(drift_ok, "montgolfières : dérive avec le vent à %.1f m/s" % want)

	# 3 bis. Ciel selon le biome (lot P31)
	_test_biomes(route, cam)

	# 4. Météo : pluie, brume, ciel couvert
	var mw = _model(route, 12)
	for i in range(3000):
		mw.update(cam, 1.0, CALM, {"rain": 0.5, "fog_boost": 0.0})
		if not mw.craft.is_empty():
			break
	_check(mw.craft.is_empty(), "pluie : rien ne vole")
	var mf = _model(route, 12)
	for i in range(3000):
		mf.update(cam, 1.0, CALM, {"rain": 0.0, "fog_boost": 0.7})
		if not mf.craft.is_empty():
			break
	_check(mf.craft.is_empty(), "brume : rien ne vole")
	var rc: Dictionary = _fly(_model(route, 12, {"sky": {"clouds": {"coverage": 0.85}}}), cam, CALM, CLEAR, 1800.0)
	_check(not rc["counts"].has("airliner") and rc["counts"].size() >= 1, "ciel couvert : pas d'avion de ligne, le reste vole (%s)" % str(rc["counts"].keys()))

	# 5. Budget, priorités, pause
	var m1 = _model(route, 1)
	var only_ok := true
	var heli_first := false
	for i in range(30000):
		m1.update(cam, 0.25, CALM, CLEAR)
		only_ok = only_ok and m1.craft.size() <= 1
		if m1.craft.size() == 1 and m1.craft[0]["kind"] == "helicopter":
			heli_first = true
	_check(only_ok and heli_first, "budget 1 : un seul engin, l'hélicoptère d'abord quand il passe")
	var m0 = _model(route, 0)
	m0.update(cam, 100.0, CALM, CLEAR)
	_check(m0.craft.is_empty(), "budget nul : rien")
	var mp = _model(route, 12)
	for i in range(600):
		mp.update(cam, 1.0, CALM, CLEAR)
	var before := str(mp.craft)
	for i in range(50):
		mp.update(cam, 0.1, CALM, CLEAR, true)
	_check(str(mp.craft) == before and not mp.craft.is_empty(), "pause : ciel figé")

	# 6. Affichage
	var sp = SoundPlayer.new()
	root.add_child(sp)
	var view = SkyRenderer.new()
	root.add_child(view)
	await process_frame
	var n0: int = view.get_child_count()
	var mv = _model(route, 12)
	view.setup(mv, sp)
	var match_ok := true
	var trail_ok := false
	var rotor_ok := false
	var usec := 0
	var frames := 0
	var heli_rot := 0.0
	var styles_ok := true
	var styles_seen := {}
	for i in range(18000):
		var t0 := Time.get_ticks_usec()
		mv.update(cam, 0.2, CALM, CLEAR)
		view.update()
		usec += Time.get_ticks_usec() - t0
		frames += 1
		for kind in SkyRenderer.POOL:
			match_ok = match_ok and view.visible_count(kind) == mini(mv.count(kind), SkyRenderer.POOL[kind])
		for slot in view._slots["airliner"]:
			if slot["root"].visible and slot["contrail"].visible and slot["contrail"].scale.z > 100.0:
				trail_ok = true
		for j in range(mv.craft.size()):
			var cr: Dictionary = mv.craft[j]
			if cr["kind"] != "balloon":
				continue
			var shown := false
			for slot in view._slots["balloon"]:
				if slot["id"] == cr["id"]:
					shown = true
					styles_ok = styles_ok and slot["root"].mesh == view._meshes[SkyRenderer._mesh_key("balloon", int(cr["style"]))]
			styles_ok = styles_ok and shown
			styles_seen[int(cr["style"])] = true
		var hs: Dictionary = view._slots["helicopter"][0]
		if hs["root"].visible:
			var rot: float = hs["rotor"].rotation.y
			rotor_ok = rotor_ok or (heli_rot != 0.0 and absf(rot - heli_rot) > 0.01)
			heli_rot = rot
	_check(match_ok, "affichage : un nœud par engin du modèle, de sa sorte")
	_check(trail_ok and rotor_ok, "traînées qui s'allongent derrière les avions, rotor qui tourne")
	var snd_ok: bool = view._slots["helicopter"][0]["audio"].stream == sp.stream("helicopter_rotor") \
		and view._slots["airliner"][0]["audio"].stream == sp.stream("airliner_rumble") \
		and view._slots["paramotor"][0]["audio"].stream == sp.stream("paramotor_buzz")
	_check(snd_ok and view.get_child_count() == n0, "sons du rotor, des réacteurs et des paramoteurs ; aucun nœud créé après le démarrage")
	_check(styles_ok and styles_seen.size() >= 2, "montgolfières affichées avec le maillage de leur motif (%d motifs vus)" % styles_seen.size())
	var avg := usec / 1000.0 / frames
	print("Ciel : %.4f ms par image" % avg)
	_check(PerfBudget.check("sky_traffic_frame", avg), "modèle et affichage du ciel en %.4f ms par image" % avg)
	view.queue_free()
	sp.queue_free()
	await process_frame
	print("test_sky_traffic_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)


## Lot P31 : biomes forcés, deux heures de ciel clair par vent faible chacun.
func _test_biomes(route, cam: Vector3) -> void:
	var by := {}
	for b in ["alpine", "farmland", "savanna", "polar"]:
		var m = _model(route, 12, {}, 5, b)
		var r: Dictionary = _fly(m, cam, CALM, CLEAR)
		by[b] = {"para": m.paragliders.size(), "counts": r["counts"], "max": r["max"], "motor_bad": r["motor_bad"]}
	print("Ciel par biome : %s" % str(by))
	var base = _model(route, 12)
	_check(int(by["alpine"]["para"]) > base.paragliders.size() and int(by["alpine"]["counts"].get("paramotor", 0)) == 0,
		"montagne : %d voiles au-dessus des montées (%d sans biome), pas de paramoteur" % [int(by["alpine"]["para"]), base.paragliders.size()])
	_check(int(by["farmland"]["counts"].get("paramotor", 0)) >= 4 and int(by["farmland"]["max"].get("paramotor", 0)) <= SkyRenderer.POOL["paramotor"]
		and int(by["farmland"]["motor_bad"]) == 0, "campagne : %d paramoteurs en 2 h" % int(by["farmland"]["counts"].get("paramotor", 0)))
	_check(int(by["savanna"]["counts"].get("balloon", 0)) > int(by["alpine"]["counts"].get("balloon", 0)),
		"savane : plus de montgolfières (%d) qu'en montagne (%d)" % [int(by["savanna"]["counts"].get("balloon", 0)), int(by["alpine"]["counts"].get("balloon", 0))])
	var pc: Dictionary = by["polar"]["counts"]
	_check(int(by["polar"]["para"]) == 0 and not pc.has("balloon") and not pc.has("paramotor") and pc.has("airliner"),
		"ciel polaire : ni voile ni montgolfière, les avions de ligne passent (%s)" % str(pc.keys()))
	# Duo de paramoteurs : le second suit le premier à sa place
	var duo := false
	var md = _model(route, 12, {}, 5, "farmland")
	for i in range(72000):
		md.update(cam, 0.1, CALM, CLEAR)
		var lead := {}
		for cr in md.craft:
			if cr["kind"] == "paramotor":
				var parts: PackedStringArray = (cr["id"] as String).split("_")
				if parts[1] == "0":
					lead[parts[0]] = cr["xform"]
				elif lead.has(parts[0]):
					var tl: Transform3D = lead[parts[0]]
					duo = ((cr["xform"] as Transform3D).origin - (tl.origin + tl.basis * SkyModel.PARAMOTOR_WINGMAN)).length() < 0.01
		if duo:
			break
	_check(duo, "paramoteurs en duo : le second à droite, au-dessus et derrière le premier")


func _test_meshes() -> void:
	var sizes := {"airliner": [35.0, 39.0], "helicopter": [2.0, 12.0], "paraglider": [11.5, 2.0], "paramotor": [11.5, 2.0], "balloon": [18.0, 18.0]}
	var ok := true
	var faces_ok := true
	var report := []
	for kind in SkyMesh.KINDS:
		var mesh: ArrayMesh = SkyMesh.build(kind)
		var arr := mesh.surface_get_arrays(0)
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		var a := mesh.get_aabb()
		report.append("%s %d" % [kind, verts.size() / 3])
		ok = ok and verts.size() / 3 <= 1500 and absf(a.size.x - float(sizes[kind][0])) < 1.0 and absf(a.size.z - float(sizes[kind][1])) < 1.0
		for t in range(0, verts.size(), 3):
			var fn := (verts[t + 1] - verts[t]).cross(verts[t + 2] - verts[t])
			if fn.length() > 1e-7 and fn.dot(normals[t] + normals[t + 1] + normals[t + 2]) > 0.0:
				faces_ok = false
	_check(ok, "maillages du ciel à leur taille, 1 500 triangles au plus (%s)" % ", ".join(report))
	_check(faces_ok, "faces orientées comme leurs normales")
	var b := SkyMesh.build("balloon").get_aabb()
	var c := SkyMesh.build("contrail").get_aabb()
	_check(absf(b.end.y - SkyMesh.BALLOON_TOP_M) < 0.01 and b.position.y >= -0.01 and absf(c.end.z - 1.0) < 1e-4 and c.position.z >= -1e-4,
		"montgolfière posée sous sa nacelle ; traînée de longueur 1 derrière les réacteurs")
	var tris := []
	var regions_differ := true
	var first_regions = null
	for style in range(SkyMesh.BALLOON_STYLES.size()):
		var arr := SkyMesh.build("balloon", style).surface_get_arrays(0)
		tris.append((arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3)
		var reg = arr[Mesh.ARRAY_CUSTOM0]   # zone de couleur (people_mesh.gd Builder, canal r)
		if style == 0:
			first_regions = reg
		else:
			regions_differ = regions_differ and reg != first_regions
	_check(tris.min() == tris.max() and regions_differ, "%d motifs d'enveloppe, même maillage (%d triangles), zones de couleur différentes" % [tris.size(), int(tris[0])])
	var cs: Array = SkyMesh.colors("balloon", 5)
	_check(cs[0] == SkyMesh.BALLOON_PAINT[1] and cs[1] == SkyMesh.BALLOON_SECOND[1], "couleurs reprises modulo leur palette")
