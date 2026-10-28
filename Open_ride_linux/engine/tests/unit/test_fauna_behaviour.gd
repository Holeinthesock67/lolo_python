extends SceneTree

## Tests sans écran du comportement des animaux `fauna_behaviour.gd` et de l'affichage
## `fauna_renderer.gd` (Lot P11) : chevreuil, écart des oiseaux, budget, coût par image ; corneilles,
## volées en V, rapaces et leurs cris (Lot P23).
## Lancement : godot --headless --path engine --script res://tests/unit/test_fauna_behaviour.gd

const FaunaBehaviour := preload("res://scripts/fauna_behaviour.gd")
const FaunaRenderer := preload("res://scripts/fauna_renderer.gd")
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


func _deer() -> Dictionary:
	# Site à 20 m de la route (axe z = 0), fuite vers la forêt au nord (+z)
	return {"type": "deer", "id": "d1", "species": "deer", "pos": Vector3(0.0, 0.0, 20.0), "yaw": 0.0, "flee_dir": Vector3(0.0, 0.0, 1.0)}


func _test_deer() -> void:
	var beh = FaunaBehaviour.new()
	var g := _deer()
	beh.setup([g])
	beh.update(Vector3(-56.0, 0.0, 0.0), 0.0)   # 59,5 m
	_check(g["state"] == "flee", "chevreuil : « fuite » dès que le cycliste est à 59,5 m")
	var beh2 = FaunaBehaviour.new()
	var g2 := _deer()
	beh2.setup([g2])
	beh2.update(Vector3(-58.0, 0.0, 0.0), 0.0)  # 61,4 m
	_check(g2["state"] == "idle", "chevreuil : « immobile » à 61 m")
	var z0 := (FaunaBehaviour.deer_position(g, 0.0)).z
	var z2 := (FaunaBehaviour.deer_position(g, 2.0)).z
	_check(z2 > z0 + 10.0, "en fuite, il s'éloigne de la route (%.1f m -> %.1f m de l'axe en 2 s)" % [z0, z2])
	var gone_at := -1.0
	for i in range(1, 80):
		var t := i * 0.1
		beh.update(Vector3(-56.0, 0.0, 0.0), t)
		if FaunaBehaviour.wild_alpha(g, t) <= 0.0 and gone_at < 0.0:
			gone_at = t
	_check(gone_at > 0.0 and gone_at < 6.0 and g["state"] == "gone", "il disparaît en %.1f s (< 6 s)" % gone_at)


func _test_bird_dodge() -> void:
	var flock := {"type": "birds", "id": "f1", "center": Vector3(0.0, 40.0, 0.0), "ground_y": 0.0, "radius_m": 20.0,
		"members": [{"angle": 0.0, "r": 20.0, "h": 0.0, "phase": 0.0, "omega": 0.15}]}
	var beh = FaunaBehaviour.new()
	beh.setup([flock])
	beh.update(Vector3(200.0, 0.0, 0.0), 0.0)
	_check((flock["dodge"] as Vector3).length() < 1e-6, "oiseaux : aucun écart quand le cycliste est loin")
	for i in range(1, 60):
		beh.update(Vector3(-15.0, 0.0, 0.0), i * 0.05)
	var d: Vector3 = flock["dodge"]
	_check(d.x > 3.0 and d.y > 1.0, "cycliste à 15 m : la bande s'écarte de lui et monte (%s)" % str(d))
	for i in range(60, 400):
		beh.update(Vector3(500.0, 0.0, 0.0), i * 0.05)
	_check((flock["dodge"] as Vector3).length() < 0.5, "cycliste parti : la bande revient")


func _herds(n_groups: int, per: int, origin: Vector3) -> Array:
	var out := []
	for gi in range(n_groups):
		var members := []
		for i in range(per):
			members.append({"pos": origin + Vector3(gi * 50.0 + i * 2.0, 0.0, 30.0), "yaw": float(i)})
		out.append({"type": "herd", "id": "h%d" % gi, "species": "cow" if gi % 2 == 0 else "sheep", "members": members})
	return out


func _test_budget() -> void:
	var r = FaunaRenderer.new()
	root.add_child(r)
	r.set_preset("low")
	var n0: int = r.get_child_count()
	r.set_chunk(0, _herds(20, 10, Vector3.ZERO))   # 200 candidats, de 30 m à plus de 1 km
	r.update(Vector3.ZERO, Vector3.ZERO, 0.0)
	var shown: int = r.visible_count("cow") + r.visible_count("sheep")
	var max_kept := 0.0
	for sel in r._sel_animals:
		var m: Dictionary = r.behaviour.groups[sel.x]["members"][sel.y]
		max_kept = maxf(max_kept, (m["pos"] as Vector3).length())
	_check(shown == r.budget_animals and r.budget_animals == 20, "200 candidats : %d affichés pour un budget de %d" % [shown, r.budget_animals])
	_check(max_kept < 125.0, "ce sont les plus proches qui restent (le plus loin gardé à %.0f m, 20 bêtes sous 125 m)" % max_kept)
	r.set_preset("high")
	r.update(Vector3.ZERO, Vector3.ZERO, 0.1)
	_check(r.visible_count("cow") + r.visible_count("sheep") == 80 and r.get_child_count() == n0,
		"préréglage high : 80 bêtes, aucun nœud créé")
	r.set_preset("high", false)
	r.update(Vector3.ZERO, Vector3.ZERO, 0.2)
	_check(r.visible_count("cow") + r.visible_count("sheep") + r.visible_count("bird") == 0, "décor vivant coupé : aucun animal")
	r.queue_free()


func _test_cost() -> void:
	var r = FaunaRenderer.new()
	root.add_child(r)
	r.set_preset("high")
	var groups := _herds(9, 10, Vector3.ZERO)   # 90 bêtes
	for f in range(4):                           # 4 bandes de 13 oiseaux (P11)
		var members := []
		for i in range(13):
			members.append({"angle": i * 0.5, "r": 25.0, "h": 0.0, "phase": i * 0.3, "omega": 0.15})
		groups.append({"type": "birds", "id": "f%d" % f, "center": Vector3(f * 80.0, 40.0, 60.0), "ground_y": 0.0,
			"radius_m": 25.0, "members": members})
	for f in range(2):                           # P23 : 2 rapaces, 3 volées de 3, 6 groupes de 3 corneilles
		groups.append({"type": "raptor", "id": "r%d" % f, "center": Vector3(f * 300.0, 80.0, 100.0), "radius_m": 40.0, "angle": 0.0, "omega": 0.1})
	for f in range(3):
		var v := _vee()
		v["id"] = "v%d" % f
		v["origin"] = Vector3(f * 200.0, 120.0, 0.0)
		groups.append(v)
	for f in range(6):
		var c := _crows()
		c["id"] = "c%d" % f
		c["pos"] = Vector3(f * 100.0, 0.0, 30.0)
		for m in c["members"]:
			m["pos"] += Vector3(f * 100.0, 0.0, 0.0)
			m["land"] += Vector3(f * 100.0, 0.0, 0.0)
		groups.append(c)
	for d in range(6):
		groups.append({"type": "deer", "id": "d%d" % d, "species": "deer", "pos": Vector3(d * 120.0, 0.0, 90.0), "yaw": 0.0, "flee_dir": Vector3(0, 0, 1)})
	r.set_chunk(0, groups)   # 90 + 52 + 2 + 9 + 18 + 6 = 177 animaux
	var total := 0
	var frames := 300
	for i in range(frames):
		var cam := Vector3(i * 2.0, 2.0, 0.0)
		r.update(cam, cam, i / 60.0)
		total += r.last_update_usec
	var avg_ms := total / 1000.0 / frames
	print("Mise à jour de 177 animaux de toutes les sortes (high : 81 oiseaux et 80 bêtes) : %.3f ms par image" % avg_ms)
	_check(PerfBudget.check("fauna_frame_200", avg_ms), "mise à jour de tous les animaux en %.3f ms par image" % avg_ms)
	r.queue_free()


func _crows() -> Dictionary:
	var members := []
	for i in range(3):
		members.append({"pos": Vector3(i * 2.0, 0.0, 30.0), "land": Vector3(i * 2.0 + 10.0, 1.0, 90.0), "yaw": float(i)})
	return {"type": "crows", "id": "c1", "pos": Vector3(0.0, 0.0, 30.0), "away": Vector3(0.0, 0.0, 1.0), "members": members}


func _test_crows() -> void:
	var beh = FaunaBehaviour.new()
	var g := _crows()
	beh.setup([g])
	beh.update(Vector3(0.0, 0.0, -6.0), 0.0)   # 36 m
	_check(g["state"] == "idle" and beh.events.is_empty(), "corneilles : posées tant que le cycliste est à 36 m")
	beh.update(Vector3(0.0, 0.0, -4.0), 0.1)   # 34 m
	_check(g["state"] == "flight" and beh.events.size() == 1 and beh.events[0]["sound"] == "crow_caw",
		"à 34 m, elles s'envolent en croassant (un seul son)")
	beh.update(Vector3(0.0, 0.0, -3.0), 0.2)
	_check(beh.events.is_empty(), "pas de deuxième croassement pour le même envol")
	var p_mid := FaunaBehaviour.crow_position(g, 0, 0.1 + FaunaBehaviour.CROW_FLIGHT_S * 0.5)
	_check(p_mid.y > 10.0 and FaunaBehaviour.crow_flying(g, 0, 2.6), "à mi-vol, elles sont à plus de 10 m du sol (%.1f m)" % p_mid.y)
	_check(not FaunaBehaviour.crow_flying(g, 2, 0.15) and FaunaBehaviour.crow_position(g, 2, 0.15) == g["members"][2]["pos"],
		"elles partent l'une après l'autre (la troisième est encore au sol 0,05 s après la première)")
	var yaw_fly := FaunaBehaviour.crow_yaw(g, 0, 2.0)
	_check(absf(yaw_fly) < 1e-4, "en vol, cap vers `away` (loin de la route)")
	for i in range(1, 80):
		beh.update(Vector3(0.0, 0.0, 200.0), 0.2 + i * 0.1)
	_check(g["state"] == "landed" and FaunaBehaviour.crow_position(g, 1, 9.0) == g["members"][1]["land"]
		and not FaunaBehaviour.crow_flying(g, 1, 9.0), "après le vol, elles sont reposées à leur point d'arrivée")


func _vee() -> Dictionary:
	return {"type": "vee", "id": "v1", "origin": Vector3(0.0, 120.0, 0.0), "dir": Vector3(1.0, 0.0, 0.0), "speed_mps": 12.0,
		"span_m": 1800.0, "phase_m": 900.0, "members": [{"back": 0.0, "side": 0.0}, {"back": 4.0, "side": 3.5}, {"back": 4.0, "side": -3.5}]}


func _test_vee_and_raptor() -> void:
	var v := _vee()
	_check(absf(FaunaBehaviour.vee_along(v, 0.0)) < 1e-6 and FaunaBehaviour.vee_scale(v, 0.0) == 1.0,
		"volée : au-dessus de son point de passage à t = 0, à sa taille normale")
	var p0 := FaunaBehaviour.vee_position(v, 0, 0.0)
	var p1 := FaunaBehaviour.vee_position(v, 0, 10.0)
	_check(absf(p1.x - p0.x - 120.0) < 1e-3 and absf(FaunaBehaviour.vee_yaw(v) - PI / 2.0) < 1e-6,
		"elle file à 12 m/s dans sa direction, tête dans le sens du vol")
	var lead := FaunaBehaviour.vee_position(v, 0, 3.0)
	var left := FaunaBehaviour.vee_position(v, 1, 3.0)
	var right := FaunaBehaviour.vee_position(v, 2, 3.0)
	_check(left.x < lead.x and right.x < lead.x and absf(left.z + right.z - 2.0 * lead.z) < 1e-3 and absf(left.z - right.z) > 6.0,
		"forme en V : les suivants derrière la tête, de part et d'autre")
	_check(FaunaBehaviour.vee_scale(v, 74.9) < 0.01 and absf(FaunaBehaviour.vee_along(v, 0.0) - FaunaBehaviour.vee_along(v, 150.0)) < 1e-3,
		"au bout de sa trajectoire, elle a rétréci jusqu'à rien, puis elle reprend au début (période 150 s)")
	var r := {"type": "raptor", "id": "r1", "center": Vector3(0.0, 80.0, 0.0), "radius_m": 40.0, "angle": 0.0, "omega": -0.1}
	var radius_ok := true
	for i in range(50):
		var p := FaunaBehaviour.raptor_position(r, i * 1.3)
		radius_ok = radius_ok and absf(Vector2(p.x, p.z).length() - 40.0) < 1e-3 and absf(p.y - 80.0) <= 2.0 + 1e-4
	_check(radius_ok, "rapace : il tourne sur son cercle de 40 m, à ± 2 m de son altitude")
	var t := 3.0
	var fwd := FaunaBehaviour.raptor_position(r, t + 0.01) - FaunaBehaviour.raptor_position(r, t)
	var yaw := FaunaBehaviour.raptor_yaw(r, t)
	var head := Vector3(sin(yaw), 0.0, cos(yaw))
	_check(head.dot(Vector3(fwd.x, 0.0, fwd.z).normalized()) > 0.99, "sens inverse : sa tête reste dans le sens du vol")
	var beh = FaunaBehaviour.new()
	beh.setup([r])
	var cries := 0
	for i in range(0, 1210):
		beh.update(Vector3(100.0, 0.0, 0.0), i * 0.1)
		cries += beh.events.size()
	_check(cries == 4, "à 100 m, il crie une fois toutes les 30 s (%d cris en 121 s)" % cries)
	var far := {"type": "raptor", "id": "r2", "center": Vector3(0.0, 80.0, 0.0), "radius_m": 40.0, "angle": 0.0, "omega": 0.1}
	var beh2 = FaunaBehaviour.new()
	beh2.setup([far])
	var cries2 := 0
	for i in range(0, 1210):
		beh2.update(Vector3(400.0, 0.0, 0.0), i * 0.1)
		cries2 += beh2.events.size()
	_check(cries2 == 0, "à 400 m, on ne l'entend pas")


func _test_renderer_p23() -> void:
	var r = FaunaRenderer.new()
	root.add_child(r)
	r.set_preset("low")
	var groups := [_crows(), _vee(), {"type": "raptor", "id": "r1", "center": Vector3(0.0, 80.0, 60.0), "radius_m": 40.0, "angle": 0.0, "omega": 0.1}]
	r.set_chunk(0, groups)
	r.update(Vector3(0.0, 2.0, -200.0), Vector3(0.0, 0.0, -200.0), 0.0)
	_check(r.visible_count("bird") == 7 and r.budget_birds == 24, "corneilles, volée et rapace : 7 oiseaux affichés (budget low : 24)")
	var crows: Dictionary = r.behaviour.groups[0]
	_check(FaunaRenderer._bird_custom(crows, 0, 0.0).b == 0.0 and FaunaRenderer.bird_transform(crows, 0, 0.0).basis.x.length() < 0.5,
		"corneille posée : ailes repliées, sans battement")
	r.update(Vector3(0.0, 2.0, 0.0), Vector3(0.0, 0.0, 0.0), 0.5)
	r.update(Vector3(0.0, 2.0, 5.0), Vector3(0.0, 0.0, 5.0), 2.0)
	_check(r.sounds_played.has("crow_caw") and FaunaRenderer._bird_custom(crows, 0, 2.0).b == 1.0
		and FaunaRenderer.bird_transform(crows, 0, 2.0).basis.x.length() > 1.0,
		"au passage, elles s'envolent en battant des ailes et le croassement est joué")
	var raptor: Dictionary = r.behaviour.groups[2]
	_check(FaunaRenderer._bird_custom(raptor, 0, 0.0).b < 0.1 and absf(FaunaRenderer.bird_transform(raptor, 0, 0.0).basis.x.length() - 1.5) < 1e-4,
		"rapace : plus grand (x 1,5), il plane presque sans battre des ailes")
	var n0: int = r.get_child_count()
	r.set_preset("high")
	r.update(Vector3(0.0, 2.0, 5.0), Vector3(0.0, 0.0, 5.0), 2.1)
	_check(r.budget_birds == 80 and r.get_child_count() == n0, "préréglage high : budget de 80 oiseaux, aucun nœud créé")
	r.queue_free()


## Lot P24 : cris des troupeaux, fuite en zigzag du lièvre, chevaux et lièvres affichés.
func _test_p24() -> void:
	var beh := FaunaBehaviour.new()
	var cows := {"type": "herd", "id": "m1_herd", "species": "cow", "members": [{"pos": Vector3(0.0, 0.0, 100.0), "yaw": 0.0}]}
	var horses := {"type": "herd", "id": "m2_herd", "species": "horse", "members": [{"pos": Vector3(400.0, 0.0, 100.0), "yaw": 0.0}]}
	beh.setup([cows, horses])
	var sounds := []
	for i in range(0, 1211):
		beh.update(Vector3.ZERO, i * 0.1)
		for ev in beh.events:
			sounds.append(ev["sound"])
	_check(sounds.count("cow_moo") == 3 and not sounds.has("horse_neigh"),
		"à 100 m, 3 meuglements en 121 s (un par période de 40 s) ; à 412 m, aucun hennissement (%s)" % str(sounds))
	var horses2 := {"type": "herd", "id": "m2_herd", "species": "horse", "members": [{"pos": Vector3(400.0, 0.0, 100.0), "yaw": 0.0}]}
	beh.setup([horses2])
	sounds.clear()
	for i in range(0, 1211):
		beh.update(Vector3(400.0, 0.0, 0.0), 200.0 + i * 0.1)
		for ev in beh.events:
			sounds.append(ev["sound"])
	_check(sounds.count("horse_neigh") == 3, "chevaux : hennissements (%d)" % sounds.count("horse_neigh"))

	var hare := {"type": "hare", "id": "c0_hare0", "species": "hare", "pos": Vector3(0.0, 0.0, 30.0), "yaw": 0.0,
		"flee_dir": Vector3(0.0, 0.0, 1.0)}
	beh.setup([hare])
	beh.update(Vector3(0.0, 0.0, 4.0), 0.0)
	_check(hare["state"] == "idle", "lièvre : immobile, cycliste à 26 m")
	beh.update(Vector3(0.0, 0.0, 6.0), 1.0)
	_check(hare["state"] == "flee", "lièvre : il file, cycliste à 24 m")
	var p1 := FaunaBehaviour.hare_position(hare, 2.0)
	var lateral := 0.0
	for j in range(20):
		lateral = maxf(lateral, absf(FaunaBehaviour.hare_position(hare, 1.0 + j * 0.1).x))
	_check(absf(p1.z - 41.0) < 0.1 and lateral > 2.0, "lièvre : 11 m en 1 s, loin de la route, en zigzag (écart %.1f m)" % lateral)
	beh.update(Vector3(0.0, 0.0, 6.0), 4.6)
	_check(hare["state"] == "gone" and FaunaBehaviour.wild_alpha(hare, 4.6) == 0.0, "lièvre : disparu après 3,5 s")

	var r = FaunaRenderer.new()
	root.add_child(r)
	r.set_preset("low")
	var herd := {"type": "herd", "id": "m3_herd", "species": "horse", "members": [
		{"pos": Vector3(0.0, 0.0, 40.0), "yaw": 0.0}, {"pos": Vector3(3.0, 0.0, 42.0), "yaw": 1.0}]}
	r.set_chunk(0, [herd, {"type": "hare", "id": "c0_hare1", "species": "hare", "pos": Vector3(0.0, 0.0, 30.0), "yaw": 0.0,
		"flee_dir": Vector3(0.0, 0.0, 1.0)}])
	r.update(Vector3(0.0, 2.0, -100.0), Vector3(0.0, 0.0, -100.0), 0.0)
	_check(r.visible_count("horse") == 2 and r.visible_count("hare") == 1, "deux chevaux et un lièvre affichés")
	r.update(Vector3(0.0, 2.0, 10.0), Vector3(0.0, 0.0, 10.0), 1.0)
	r.update(Vector3(0.0, 2.0, 10.0), Vector3(0.0, 0.0, 10.0), 5.0)
	var hare_g: Dictionary = r.behaviour.groups[1]
	_check(FaunaRenderer.wild_transform(hare_g, 5.0).origin.y < -40.0, "lièvre parti : caché sous le sol jusqu'au tri suivant")
	r.queue_free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_deer()
	_test_bird_dodge()
	_test_budget()
	_test_crows()
	_test_vee_and_raptor()
	_test_renderer_p23()
	_test_p24()
	_test_cost()
	print("test_fauna_behaviour : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
