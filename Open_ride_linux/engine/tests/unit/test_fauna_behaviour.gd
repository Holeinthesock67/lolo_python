extends SceneTree

## Tests sans écran du comportement des animaux `fauna_behaviour.gd` et de l'affichage
## `fauna_renderer.gd` (Lot P11) : chevreuil, écart des oiseaux, budget, coût par image.
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
	return {"type": "deer", "id": "d1", "pos": Vector3(0.0, 0.0, 20.0), "yaw": 0.0, "flee_dir": Vector3(0.0, 0.0, 1.0)}


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
		if FaunaBehaviour.deer_alpha(g, t) <= 0.0 and gone_at < 0.0:
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
	for f in range(8):                           # 8 bandes de 13 oiseaux
		var members := []
		for i in range(13):
			members.append({"angle": i * 0.5, "r": 25.0, "h": 0.0, "phase": i * 0.3, "omega": 0.15})
		groups.append({"type": "birds", "id": "f%d" % f, "center": Vector3(f * 80.0, 40.0, 60.0), "ground_y": 0.0,
			"radius_m": 25.0, "members": members})
	for d in range(6):
		groups.append({"type": "deer", "id": "d%d" % d, "pos": Vector3(d * 120.0, 0.0, 90.0), "yaw": 0.0, "flee_dir": Vector3(0, 0, 1)})
	r.set_chunk(0, groups)   # 90 + 104 + 6 = 200 animaux
	var total := 0
	var frames := 300
	for i in range(frames):
		var cam := Vector3(i * 2.0, 2.0, 0.0)
		r.update(cam, cam, i / 60.0)
		total += r.last_update_usec
	var avg_ms := total / 1000.0 / frames
	print("Mise à jour de 200 animaux (high : 40 oiseaux et 80 bêtes affichés) : %.3f ms par image" % avg_ms)
	_check(PerfBudget.check("fauna_frame_200", avg_ms), "mise à jour de tous les animaux en %.3f ms par image" % avg_ms)
	r.queue_free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_deer()
	_test_bird_dodge()
	_test_budget()
	_test_cost()
	print("test_fauna_behaviour : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
