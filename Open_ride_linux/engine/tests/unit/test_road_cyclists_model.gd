extends SceneTree

## Tests sans écran des cyclistes du décor `road_cyclists_model.gd` (Lot P28) : 20 km de plaine puis 10 km de
## montée, nombre de groupes, écarts au cycliste et aux bots, groupes doublés et qui doublent, budget, pause,
## vitesse en pente, cadence ; affichage `road_cyclists_renderer.gd` (avatars des bots, garde-robe du décor
## `road_cyclist_look.gd`, lot AS7).
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_cyclists_model.gd

const Model := preload("res://scripts/road_cyclists_model.gd")
const Renderer := preload("res://scripts/road_cyclists_renderer.gd")
const Look := preload("res://scripts/road_cyclist_look.gd")
const WarmupPlan := preload("res://scripts/warmup_plan.gd")
const BotLook := preload("res://scripts/bot_look.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const AvatarModel := preload("res://scripts/avatar_model.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const FLAT_M := 20000.0
const LENGTH_M := 31000.0
const CLIMB_PCT := 6.0
const MIN_CENTRE_M := Model.MIN_GAP_M + 2.0 * Model.RIDER_HALF_WIDTH_M
const PASS_NEAR_M := 30.0   # loin du cycliste, un groupe `ahead` peut en doubler un autre vers l'axe (lot P32)
const ALONGSIDE_M := 2.0     # longueur d'un vélo et demi : « à la même abscisse »

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite vers l'est : 20 km de plaine, puis une montée régulière à 6 %, puis 1 km de plat.
func _route():
	var ds := 10.0
	var n := int(LENGTH_M / ds) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var s := i * ds
		var climbing := s >= FLAT_M and s < FLAT_M + 10000.0
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(200.0 + clampf(s - FLAT_M, 0.0, 10000.0) * CLIMB_PCT / 100.0)
		cols["x"].append(s)
		cols["z"].append(0.0)
		cols["grade_pct"].append(CLIMB_PCT if climbing else 0.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


const CLIMBS := [{"start_s": FLAT_M, "summit_s": FLAT_M + 10000.0}]


class FakeTraffic:
	var vehicles: Array = []


## Séance : 30 km/h en plaine, 14 km/h en montée, un bot à 32 km/h parti 200 m derrière ; relevé des contrôles.
func _ride(route, budget: int, rng_seed: int, traffic = null) -> Dictionary:
	var m = Model.new()
	m.configure(route, CLIMBS, [], budget, rng_seed, 6.0, traffic)
	var dt := 1.0 / 15.0     # 15 images/s : sous la limite de 120 s de run_engine_tests.sh
	var s := 300.0
	var bot := 100.0
	var seen := {}
	var log := []
	var flat_groups := 0
	var climb_groups := 0
	var too_close := 0
	var wrong_side := 0
	var bot_close := 0
	var max_riders := 0
	var cases := {}
	var salut := 0
	var max_kmh := 0.0
	while s < FLAT_M + 10000.0:
		var v := 30.0 / 3.6 if s < FLAT_M else 14.0 / 3.6
		bot += (32.0 if bot < FLAT_M else 15.0) / 3.6 * dt
		m.update(s, v, dt, false, [{"s": bot, "lateral": Model.BOT_LATERAL_M}])
		if not m.last_event.is_empty():
			salut += 1
		max_riders = maxi(max_riders, m.rider_count())
		for g in m.groups:
			max_kmh = maxf(max_kmh, float(g["speed_mps"]) * 3.6)
			if not seen.has(g["id"]):
				seen[g["id"]] = true
				log.append([g["id"], g["case"], (g["members"] as Array).size()])
				cases[g["case"]] = int(cases.get(g["case"], 0)) + 1
				if float(g["s"]) < FLAT_M + (300.0 if g["case"] == "overtake" else 0.0) and s < FLAT_M:
					flat_groups += 1
				else:
					climb_groups += 1
		for r in m.riders():
			# Lot P32 : en face sur le bord gauche (sa droite), devant sur le bord droit, à droite du cycliste
			var case_r := str(r["group"]["case"])
			if (case_r == "oncoming" and float(r["lateral"]) >= 0.0) or (case_r == "ahead" and absf(float(r["s"]) - s) < PASS_NEAR_M and float(r["lateral"]) <= Model.RIDER_LATERAL_M):
				wrong_side += 1
			if absf(float(r["s"]) - s) < ALONGSIDE_M and absf(float(r["lateral"]) - Model.RIDER_LATERAL_M) < MIN_CENTRE_M - 1e-3:
				too_close += 1
			if absf(float(r["s"]) - bot) < ALONGSIDE_M and absf(float(r["lateral"]) - Model.BOT_LATERAL_M) < MIN_CENTRE_M - 1e-3:
				bot_close += 1
		s += v * dt
	return {"flat": flat_groups, "climb": climb_groups, "log": log, "too_close": too_close, "wrong_side": wrong_side, "bot_close": bot_close,
		"max_riders": max_riders, "passed": m.passed_total, "overtook": m.overtook_total, "cases": cases,
		"salut": salut, "max_kmh": max_kmh}


func _test_renderer(route) -> void:
	var sp = SoundPlayer.new()
	root.add_child(sp)
	var rr = Renderer.new()
	root.add_child(rr)
	await process_frame
	var m = Model.new()
	m.configure(route, CLIMBS, [], 16, 3)
	rr.setup(m, sp)
	rr.set_quality("high")
	AvatarView.wait_parts()
	var s := 1000.0
	var match_ok := true
	var cadence_ok := true
	var decor_ok := true
	var max_shown := 0
	var model_usec := 0
	var view_usec := 0
	var frames := 0
	var lods := [0, 0, 0]
	var ids := {}
	for i in range(30 * 240):
		if i == 1:   # un groupe devant, rattrapé et doublé de près, et un groupe en face
			m.place_for_test(s, 30.0 / 3.6, "ahead", 40.0, 3)
			m.place_for_test(s, 30.0 / 3.6, "oncoming", 150.0, 2)
		var t0 := Time.get_ticks_usec()
		m.update(s, 30.0 / 3.6, 1.0 / 30.0)
		var t1 := Time.get_ticks_usec()
		rr.update(1.0 / 30.0, false, s)
		view_usec += Time.get_ticks_usec() - t1
		model_usec += t1 - t0
		frames += 1
		var rs: Array = m.riders()
		max_shown = maxi(max_shown, rr.visible_count())
		match_ok = match_ok and rr.visible_count() == mini(rs.size(), Renderer.MAX_CYCLISTS)
		for j in range(rr.visible_count()):
			var r: Dictionary = rs[j]
			match_ok = match_ok and rr.shown_transform(j).origin.is_equal_approx(
				m.world_transform(float(r["s"]), float(r["lateral"]), int(r["dir"])).origin)
			var want := Model.cadence_rpm(float(r["group"]["speed_mps"]))
			cadence_ok = cadence_ok and absf(rr.shown_cadence(j) - want) < 1e-3
			var v: int = rr.shown_variant(j)
			decor_ok = decor_ok and v == Look.variant_of(int(r["member"]["jersey"]), int(r["member"]["look"]))
			ids[str(r["id"])] = true
			var av = rr.avatar_of(str(r["id"]))
			match_ok = match_ok and av != null and av.is_visible_in_tree()
			if av != null:
				lods[int(av.lod)] += 1
		s += 30.0 / 3.6 / 30.0
	_check(match_ok and max_shown >= 2, "affichage : un avatar visible par cycliste du modèle, à sa place (%d au plus)" % max_shown)
	_check(cadence_ok, "cadence de chaque cycliste affiché d'après sa vitesse")
	_check(decor_ok, "apparence de chaque cycliste tirée de son maillot et de sa tenue")
	_check(lods[0] > 0 and lods[2] > 0, "niveaux de détail des bots selon l'écart (%s images par niveau)" % str(lods))
	_check(rr.created_count() <= ids.size(), "un avatar par cycliste au plus (%d pour %d)" % [rr.created_count(), ids.size()])
	# Cyclistes qui quittent la route puis cyclistes de mêmes apparences : avatars cachés repris, aucun créé
	m.place_for_test(s, 30.0 / 3.6, "ahead", 30.0, 3)
	m.groups = [m.groups[m.groups.size() - 1]]
	rr.update(1.0 / 30.0, false, s)
	var kept: Array = m.groups.duplicate(true)
	var created := rr.created_count()
	m.groups = []
	rr.update(1.0 / 30.0, false, s)
	var hidden := rr.visible_count() == 0
	for g in kept:
		g["id"] = "x" + str(g["id"])
		for mb in g["members"]:
			if mb.has("id"):
				mb["id"] = "x" + str(mb["id"])
	m.groups = kept
	rr.update(1.0 / 30.0, false, s)
	_check(hidden and rr.visible_count() > 0 and rr.created_count() == created,
		"avatars cachés repris par les cyclistes suivants de même apparence (%d créés, %d affichés)" % [rr.created_count() - created, rr.visible_count()])
	var model_avg := model_usec / 1000.0 / frames
	var view_avg := view_usec / 1000.0 / frames
	_check(PerfBudget.check("road_cyclists_frame", model_avg), "16 cyclistes au plus : modèle en %.4f ms par image" % model_avg)
	_check(PerfBudget.check("road_cyclists_view_frame", view_avg), "16 avatars au plus : affichage en %.4f ms par image" % view_avg)
	rr.queue_free()
	sp.queue_free()
	await process_frame


## Préchauffage (lot AS7, banc PC du 5/11) : au chargement, les niveaux du préréglage des 16 apparences, une
## racine de réserve chacune, montrées minuscules devant la caméra quelques images ; ensuite cachées, et les
## cyclistes qui arrivent les reprennent sans rien créer.
func _test_warm_up(route) -> void:
	var cam := Camera3D.new()
	root.add_child(cam)
	cam.current = true
	cam.global_position = Vector3(0.0, 50.0, 0.0)
	var counts := {}
	for q in ["low", "high"]:
		var rr = Renderer.new()
		root.add_child(rr)
		var m = Model.new()
		m.configure(route, CLIMBS, [], 16, 3)
		rr.setup(m)
		rr.set_quality(q)
		counts[q] = rr.warm_up(cam)
		var created := rr.created_count()
		var tiny := true
		var shown_all := true
		for c in rr.get_children():
			if c is Node3D and c.has_meta("variant"):
				tiny = tiny and c.global_position.distance_to(cam.global_position) < 2.1 and c.global_transform.basis.get_scale().x < 0.001
				shown_all = shown_all and c.visible
		_check(created == Look.VARIANTS and rr.spare_count() == Look.VARIANTS and tiny and shown_all,
			"%s : préchauffage, %d avatars de réserve minuscules devant la caméra (%d niveaux construits)" % [q, rr.spare_count(), counts[q]])
		for i in range(Renderer.WARM_FRAMES):
			rr.update(1.0 / 30.0, false, 1000.0)
		var hidden := true
		for c in rr.get_children():
			if c is Node3D and c.has_meta("variant") and rr.spare_count() == Look.VARIANTS:
				hidden = hidden and not c.visible
		_check(hidden, "%s : réserve cachée après %d images" % [q, Renderer.WARM_FRAMES])
		m.update(1000.0, 7.0, 0.0)
		m.place_for_test(1000.0, 7.0, "ahead", 30.0, 3)
		var distinct := {}
		for r in m.riders():
			distinct[Look.variant_of(int(r["member"]["jersey"]), int(r["member"]["look"]))] = true
		rr.update(1.0 / 30.0, false, 1000.0)
		_check(rr.visible_count() > 0 and rr.created_count() == created + (rr.visible_count() - distinct.size()),
			"%s : cyclistes qui arrivent sur les avatars préchauffés (%d créé(s) pour %d affichés)" % [q, rr.created_count() - created, rr.visible_count()])
		rr.queue_free()
	# Lot AC4 : les mêmes temps joués un par image par le plan unique (attente des fils de travail sans bloquer).
	var stepped = Renderer.new()
	root.add_child(stepped)
	var sm = Model.new()
	sm.configure(route, CLIMBS, [], 16, 3)
	stepped.setup(sm)
	stepped.set_quality("high")
	var plan = WarmupPlan.new()
	plan.start(stepped.warm_steps(cam))
	var images := 0
	while plan.pending() > 0 and images < 10000:
		plan.step()
		images += 1
		if plan.pending() > 0 and str(plan._steps[0][0]) == "cyclistes attente":
			OS.delay_msec(1)   # fils de travail
	var tiny_s := true
	for c in stepped.get_children():
		if c is Node3D and c.has_meta("variant"):
			tiny_s = tiny_s and c.visible and c.global_transform.basis.get_scale().x < 0.001
	_check(plan.pending() == 0 and stepped.spare_count() == Look.VARIANTS and tiny_s
		and plan.done.size() == Look.VARIANTS + 3,
		"plan unique : demande, attente, une apparence par image puis affichage (%d étapes, %d images)" % [plan.done.size(), images])
	stepped.queue_free()
	_check(counts["low"] == Look.VARIANTS * 2 and counts["high"] == Look.VARIANTS * 3,
		"niveaux préchauffés : 1 et 2 en low (%d), 0 à 2 en high (%d)" % [counts["low"], counts["high"]])
	cam.queue_free()
	await process_frame


## Lot AC3 (à-coups du décor, 21/11) : hors du champ de la caméra, sans ombre (niveau > 0), un cycliste n'est pas
## reposé, et il l'est dès son retour dans le champ ; un seul niveau de détail construit par image.
func _test_view_skip(route) -> void:
	var planes := []
	var cam0 := Camera3D.new()
	root.add_child(cam0)
	cam0.current = true
	cam0.global_transform = Transform3D(Basis(), Vector3.ZERO)   # regarde vers −z
	await process_frame
	planes = cam0.get_frustum()
	_check(Renderer.in_view(planes, Vector3(0.0, 0.0, -10.0), 0.5) and not Renderer.in_view(planes, Vector3(0.0, 0.0, 10.0), 2.5)
		and Renderer.in_view(planes, Vector3(0.0, 0.0, 1.0), 2.5) and Renderer.in_view([], Vector3(0.0, 0.0, 10.0), 0.0),
		"champ de la caméra : devant oui, derrière non, sphère qui touche le bord oui, sans caméra toujours")
	cam0.queue_free()
	await process_frame
	var cam := Camera3D.new()
	root.add_child(cam)
	cam.current = true
	var rr = Renderer.new()
	root.add_child(rr)
	var m = Model.new()
	m.configure(route, CLIMBS, [], 16, 3)
	rr.setup(m)
	rr.set_quality("high")
	rr.warm_up()
	m.update(1000.0, 7.0, 0.0)
	m.place_for_test(1000.0, 7.0, "ahead", 40.0, 3)
	rr.update(1.0 / 30.0, false, 1000.0)
	var at: Vector3 = rr.shown_transform(0).origin
	# Caméra à 30 m (niveau 1, sans ombre), tournée à l'opposé des cyclistes
	var away := Vector3(30.0, 2.0, 0.0)
	cam.global_transform = Transform3D(Basis(), at + away).looking_at(at + away * 2.0, Vector3.UP)
	var skipped: int = rr.posed_skipped
	for i in range(3):
		rr.update(1.0 / 30.0, false, 1000.0)
	var unposed := true
	for id in rr._by_id:
		unposed = unposed and not (rr._by_id[id] as Node3D).has_meta("posed")
	_check(rr.posed_skipped - skipped >= 3 * rr.visible_count() and unposed,
		"cyclistes derrière la caméra, niveau 1 : pas reposés (%d poses évitées)" % (rr.posed_skipped - skipped))
	cam.global_transform = Transform3D(Basis(), at + away).looking_at(at, Vector3.UP)
	skipped = rr.posed_skipped
	rr.update(1.0 / 30.0, false, 1000.0)
	var posed := true
	for id in rr._by_id:
		posed = posed and (rr._by_id[id] as Node3D).has_meta("posed")
	_check(rr.posed_skipped == skipped and posed, "caméra retournée vers eux : tous reposés à la même image")
	rr.queue_free()
	# Un seul niveau construit par image : deux cyclistes de même apparence sans réserve
	var rb = Renderer.new()
	root.add_child(rb)
	var mb = Model.new()
	mb.configure(route, CLIMBS, [], 16, 3)
	rb.setup(mb)
	rb.set_quality("high")
	AvatarView.request_parts(1, Look.settings_for(0), Look.looks_for(0))
	AvatarView.request_parts(2, Look.settings_for(0), Look.looks_for(0))
	AvatarView.wait_parts()
	mb.update(1000.0, 7.0, 0.0)
	mb.place_for_test(1000.0, 7.0, "ahead", 40.0, 3)
	for g in mb.groups:
		for mm in g["members"]:
			mm["jersey"] = 0
			mm["look"] = 0
	var far := Vector3(150.0, 2.0, 0.0)   # niveau 2 d'abord, puis tous au niveau 1 à la même image
	cam.global_transform = Transform3D(Basis(), at + far).looking_at(at, Vector3.UP)
	for i in range(3):
		rb.update(1.0 / 30.0, false, 1000.0)
	cam.global_transform = Transform3D(Basis(), at + away).looking_at(at, Vector3.UP)
	rb.update(1.0 / 30.0, false, 1000.0)
	var first_frame: int = rb.levels_deferred
	var built := 0
	for id in rb._by_id:
		built += 1 if (rb._by_id[id] as Node3D).has_node("Lod1") else 0
	for i in range(6):
		rb.update(1.0 / 30.0, false, 1000.0)
	var all_lod := true
	for id in rb._by_id:
		var r: Node3D = rb._by_id[id]
		all_lod = all_lod and int(r.get_meta("shown_lod")) == int(r.get_meta("lod"))
	_check(rb.visible_count() >= 2 and first_frame >= 1 and built == 1,
		"un seul niveau construit par image (%d construit, %d remis à l'image suivante)" % [built, first_frame])
	_check(all_lod, "niveaux remis : chaque cycliste a son niveau quelques images plus tard")
	rb.queue_free()
	cam.queue_free()
	await process_frame


## Garde-robe du décor (lot AS7) : couleurs que ne portent ni les bots, ni le fantôme, ni l'avatar par défaut ;
## sans dossard, jamais de cadre de contre-la-montre.
func _test_decor_look() -> void:
	var bot_kits := {}
	for role in ["constant", "profile", "ghost", "other"]:
		for i in range(12):
			for jersey in [null, "sprint", "kom"]:
				bot_kits[int(BotLook.settings_for(i, role, jersey)["kit_primary"])] = true
	bot_kits[int(AvatarModel.DEFAULTS["kit_primary"])] = true
	var distinct := true
	var no_number := true
	var no_tt := true
	var seen := {}
	for v in range(Look.VARIANTS):
		var st: Dictionary = Look.settings_for(v)
		var lk: Dictionary = Look.looks_for(v)
		distinct = distinct and not bot_kits.has(int(st["kit_primary"])) and int(st["kit_primary"]) != int(st["kit_secondary"])
		no_number = no_number and int(st["number"]) == 0
		no_tt = no_tt and str(lk["frame"]) != "frame_tt" and str(lk["wheels"]) != "wheels_disc"
		seen[var_to_str([st, lk])] = true
	_check(distinct, "maillots du décor d'autres couleurs que ceux des bots et de l'avatar par défaut")
	_check(no_number and no_tt, "sans dossard ni matériel de contre-la-montre")
	_check(seen.size() == Look.VARIANTS, "%d apparences différentes" % seen.size())
	var all_variants := {}
	for jersey in range(8):
		for look in range(4):
			var v := Look.variant_of(jersey, look)
			all_variants[v] = true
	_check(all_variants.size() == Look.VARIANTS and all_variants.keys().min() == 0 and all_variants.keys().max() == Look.VARIANTS - 1,
		"chaque maillot et chaque tenue donnent une des %d apparences" % Look.VARIANTS)


## Recette vélo du 7/11 : sur le gravier (chemin de 3,5 m, 1,5 m de demi-largeur sûre), les cyclistes du décor restent
## sur le chemin, en file, roues séparées ; le vélo qui s'écarte est tourné dans le sens où il va.
func _test_gravel(route) -> void:
	var m = Model.new()
	m.configure(route, CLIMBS, [], 16, 7, 6.0, null, func(_s: float) -> float: return 1.5)
	var s := 300.0
	var outside := 0
	var touching := 0
	var groups := {}
	var yawed := false
	for i in range(15 * 600):
		m.update(s, 30.0 / 3.6, 1.0 / 15.0)
		for g in m.groups:
			groups[str(g["id"])] = true
			var members: Array = g["members"]
			for a in members:
				if absf(float(a["lateral"])) + Model.RIDER_HALF_WIDTH_M > 1.5 + 1e-6:
					outside += 1
				for b in members:
					if not is_same(a, b) and absf(float(a["dl"]) - float(b["dl"])) < 1.7 \
							and absf(float(a["lateral"]) - float(b["lateral"])) < 2.0 * Model.RIDER_HALF_WIDTH_M - 0.05:
						touching += 1
		for r in m.riders():
			yawed = yawed or absf(float(r["yaw"])) > 0.02
		s += 30.0 / 3.6 / 15.0
	_check(groups.size() >= 5 and outside == 0, "gravier : %d groupes, tous sur le chemin (%d hors)" % [groups.size(), outside])
	_check(touching == 0, "gravier : en file, roues séparées (%d contacts)" % touching)
	_check(yawed, "un cycliste qui s'écarte ou se rabat est tourné dans le sens où il va")
	_check(Model.FILE_GAP_M >= 1.7 + 0.3, "en file : vélo de 1,7 m et au moins 0,3 m de roue à roue (%.1f m d'axe à axe)" % Model.FILE_GAP_M)


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = _route()
	var r: Dictionary = _ride(route, 16, 7)
	print("30 km : %d groupes en plaine, %d en montée, cas %s, %d doublés, %d qui doublent, %d « Salut ! », %.0f km/h au plus" % [
		r["flat"], r["climb"], str(r["cases"]), r["passed"], r["overtook"], r["salut"], r["max_kmh"]])
	_check(r["flat"] >= 15 and r["flat"] <= 30, "20 km de plaine : de 15 à 30 groupes (%d)" % r["flat"])
	_check(r["climb"] >= 20 and r["climb"] <= 40, "10 km de montée : de 20 à 40 groupes (%d)" % r["climb"])
	_check(r["too_close"] == 0, "aucun cycliste du décor à moins de 0,7 m (épaule à épaule) du cycliste")
	_check(r["wrong_side"] == 0, "en face à gauche de l'axe, devant à droite du cycliste (%d écarts)" % r["wrong_side"])
	_check(r["bot_close"] == 0, "aucun cycliste du décor à moins de 1,2 m latéralement d'un bot")
	_check(r["passed"] >= 1 and r["overtook"] >= 1, "groupes devant doublés (%d), groupes qui doublent (%d)" % [r["passed"], r["overtook"]])
	_check(r["max_riders"] <= 16, "jamais plus que le budget de 16 cyclistes (%d)" % r["max_riders"])
	_check(r["max_kmh"] <= Model.MAX_KMH + 0.01, "jamais plus de 70 km/h (%.1f)" % r["max_kmh"])
	var r2: Dictionary = _ride(route, 16, 7)
	_check(str(r2["log"]) == str(r["log"]), "même graine, même parcours : mêmes groupes")
	var r3: Dictionary = _ride(route, 16, 8)
	_check(str(r3["log"]) != str(r["log"]), "autre graine : autres groupes")
	var safe := true
	var salut := 0
	for sd in range(1, 7):
		var rs: Dictionary = _ride(route, 8, sd)
		salut += int(rs["salut"])
		safe = safe and rs["too_close"] == 0 and rs["wrong_side"] == 0 and rs["bot_close"] == 0 and rs["max_riders"] <= 8
		if not safe:
			print("graine %d : %d trop près, %d du mauvais côté, %d près d'un bot, %d au plus" % [sd, rs["too_close"], rs["wrong_side"], rs["bot_close"], rs["max_riders"]])
	_check(safe, "6 autres graines, budget 8 : mêmes garanties")
	_check(salut >= 1, "un groupe qui double dit « Salut ! » de temps en temps (%d)" % salut)
	var r0: Dictionary = _ride(route, 0, 7)
	_check(r0["log"].is_empty(), "budget nul : aucun cycliste")
	var busy := FakeTraffic.new()
	busy.vehicles = [{"id": "v1"}]
	var rt: Dictionary = _ride(route, 16, 7, busy)
	_check(int(rt["cases"].get("oncoming", 0)) == 0 and int(r["cases"].get("oncoming", 0)) > 0,
		"pas de groupe en face pendant qu'un véhicule est sur la route")

	# Vitesse en pente (puissance constante) et cadence
	var p := Model.power_for(25.0 / 3.6)
	_check(absf(Model.speed_on_grade(p, 0.0) * 3.6 - 25.0) < 0.2, "puissance constante : 25 km/h sur le plat")
	var up := Model.speed_on_grade(Model.power_for(28.0 / 3.6), 6.0) * 3.6
	var down := Model.speed_on_grade(Model.power_for(35.0 / 3.6), -8.0) * 3.6
	_check(up >= Model.MIN_KMH and up < 16.0 and down > 45.0 and down <= Model.MAX_KMH, "montée à 6 %% : %.1f km/h ; descente à 8 %% : %.1f km/h" % [up, down])
	var rpm := Model.cadence_rpm(30.0 / 3.6)
	_check(rpm > 75.0 and rpm < 90.0 and Model.cadence_rpm(60.0 / 3.6) == 0.0, "cadence à 30 km/h en 50 × 17 : %.0f tr/min ; roue libre à 60 km/h" % rpm)

	# Pause : tout est figé
	var m = Model.new()
	m.configure(route, CLIMBS, [], 16, 7)
	var s := 1000.0
	while m.groups.is_empty() and s < FLAT_M:
		m.update(s, 8.0, 0.1)
		s += 0.8
	var before := str(m.groups)
	for i in range(50):
		m.update(s, 0.0, 0.1, true)
	_check(not m.groups.is_empty() and str(m.groups) == before, "pause : cyclistes figés")
	_test_gravel(route)
	await _test_renderer(route)
	_test_decor_look()
	await _test_warm_up(route)
	await _test_view_skip(route)
	print("test_road_cyclists_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
