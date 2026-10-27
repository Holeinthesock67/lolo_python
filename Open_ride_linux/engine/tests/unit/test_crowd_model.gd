extends SceneTree

## Tests sans écran des spectateurs `crowd_model.gd` et de leur affichage `crowd_renderer.gd` (Lot P15) :
## placement dans le dernier kilomètre, réaction, clameur, budget, coût par image.
## Lancement : godot --headless --path engine --script res://tests/unit/test_crowd_model.gd

const ClimbDetector := preload("res://scripts/climb_detector.gd")
const CrowdModel := preload("res://scripts/crowd_model.gd")
const CrowdRenderer := preload("res://scripts/crowd_renderer.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const ClimbTest := preload("res://tests/unit/test_climb_detector.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Col de 8 km à 7 % (2 à 10 km), puis montée de 2 km à 6 % (13 à 15 km).
func _profile(s: float) -> float:
	if s >= 2000.0 and s < 10000.0:
		return 7.0
	if s >= 13000.0 and s < 15000.0:
		return 6.0
	return 0.0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = ClimbTest.make_route(17000.0, Callable(self, "_profile"))
	var climbs: Array = ClimbDetector.detect(route)
	_check(climbs.size() == 2, "deux montées détectées (8 km et 2 km)")
	var cm = CrowdModel.new()
	cm.configure(route, climbs, {}, false, 3)
	var n: int = cm.spectators.size()
	var outside := 0
	var first200 := 0
	var last200 := 0
	var too_close := 0
	for sp in cm.spectators:
		var s := float(sp["s"])
		if s < 9000.0 - 1.0 or s > 10000.0 + 1.0:
			outside += 1
		if s < 9200.0:
			first200 += 1
		if s >= 9800.0:
			last200 += 1
		var c: Vector3 = route.sample_point(s)
		var lateral := absf((sp["pos"] as Vector3).z - c.z)   # route vers l'est : écart en z
		if lateral - 3.0 < 0.3 - 0.05:
			too_close += 1
	_check(n > 0 and outside == 0, "col de 8 km : %d spectateurs, tous dans le dernier kilomètre ; montée de 2 km : aucun" % n)
	_check(last200 > first200, "plus nombreux dans les 200 derniers mètres (%d) que dans les 200 premiers (%d)" % [last200, first200])
	_check(too_close == 0, "aucun spectateur à moins de 0,3 m du bord de la chaussée")
	var both := {}
	for sp in cm.spectators:
		both[sp["side"]] = true
	_check(both.size() == 2, "des deux côtés de la route")
	var all = CrowdModel.new()
	all.configure(route, climbs, {}, true, 3)
	_check(all.spectators.filter(func(sp): return float(sp["s"]) > 14000.0).size() > 0, "crowd_all_climbs : spectateurs aussi sur la montée de 2 km")
	var water := {"areas": [{"id": "l", "kind": "pond", "level_y": 0.0, "outer": [[9400.0, 3.0], [9600.0, 3.0], [9600.0, 30.0], [9400.0, 30.0]]}]}
	var wet = CrowdModel.new()
	wet.configure(route, climbs, water, false, 3)
	var in_pond: Array = wet.spectators.filter(func(sp): return (sp["pos"] as Vector3).x >= 9400.0 and (sp["pos"] as Vector3).x <= 9600.0 and (sp["pos"] as Vector3).z > 3.0)
	_check(in_pond.is_empty() and wet.spectators.size() < n, "aucun spectateur dans l'eau")
	var again = CrowdModel.new()
	again.configure(route, climbs, {}, false, 3)
	_check(str(again.spectators) == str(cm.spectators), "placement déterministe")

	# Réaction : à moins de 25 m « encourage » (après le délai propre), à 100 m « calme »
	var probe := -1
	for i in range(n):
		if float(cm.spectators[i]["s"]) > 9500.0:
			probe = i
			break
	var sp_pos: Vector3 = cm.spectators[probe]["pos"]
	var s_probe := float(cm.spectators[probe]["s"])
	for k in range(30):
		cm.update(route.sample_point(s_probe - 100.0), s_probe - 100.0, k * 0.05)
	var far_state: String = cm.state(probe)
	var rider: Vector3 = route.sample_point(s_probe - 10.0)
	for k in range(30):
		cm.update(rider, s_probe - 10.0, 2.0 + k * 0.05)
	_check(far_state == "calme" and cm.state(probe) == "encourage" and rider.distance_to(sp_pos) < 25.0,
		"spectateur à %.0f m : « encourage » ; à 100 m : « calme »" % rider.distance_to(sp_pos))

	# Clameur
	var cheers := []
	for d in [400.0, 140.0, 80.0, 20.0]:
		cheers.append(cm.cheer(9000.0 - d + 10.0, 100.0))
	_check(cm.cheer(5000.0, 100.0) == 0.0 and cheers[0] == 0.0 and cheers[1] < cheers[2] and cheers[2] < cheers[3],
		"clameur nulle hors des zones, croissante à l'approche (%s)" % str(cheers))
	var base: float = cm.cheer(9600.0, 200.0, 250.0, 250.0)
	cm.observe_bots(9600.0, [{"id": "b1", "s": 9605.0}], 199.0)
	cm.observe_bots(9606.0, [{"id": "b1", "s": 9604.0}], 200.0)
	var boosted: float = cm.cheer(9600.0, 200.5, 250.0, 250.0)
	_check(boosted > base and cm.cheer(9600.0, 210.0, 250.0, 250.0) == base,
		"plus forte juste après un dépassement de bot (%.2f contre %.2f), puis comme avant" % [boosted, base])

	# Affichage, budget et coût
	var sp_player = SoundPlayer.new()
	root.add_child(sp_player)
	var r = CrowdRenderer.new()
	root.add_child(r)
	await process_frame
	var n0: int = r.get_child_count()
	r.setup(cm, sp_player)
	r.set_preset("low")
	r.update(route.sample_point(9900.0), 0.0, 0.5)
	_check(r.visible_count() == r.budget and r.budget == 40, "préréglage low : %d silhouettes pour un budget de 40" % r.visible_count())
	var far_kept := 0.0
	for m in range(2):
		for i in r._sel[m]:
			far_kept = maxf(far_kept, (cm.spectators[i]["pos"] as Vector3).distance_to(route.sample_point(9900.0)))
	_check(far_kept < 60.0, "les plus proches de la caméra (le plus loin gardé à %.0f m)" % far_kept)
	r.set_preset("high", false)
	r.update(route.sample_point(9950.0), 0.1, 0.0)
	_check(r.visible_count() == 0, "décor vivant coupé : aucun spectateur")
	# 200 spectateurs affichés (budget de 200) : coût par image
	r.budget = 200
	for mmi in r._mmi:
		mmi.multimesh.instance_count = 200
	var total := 0
	var frames := 300
	for k in range(frames):
		var s := 9300.0 + k * 0.25   # 15 m/s à 60 images/s
		var p: Vector3 = route.sample_point(s)
		var t0 := Time.get_ticks_usec()
		cm.update(p, s, 10.0 + k / 60.0)
		var c: float = cm.cheer(s, 10.0 + k / 60.0)
		r.update(p, 10.0 + k / 60.0, c)
		total += Time.get_ticks_usec() - t0
	var avg := total / 1000.0 / frames
	print("200 spectateurs (modèle, clameur, affichage) : %.3f ms par image" % avg)
	_check(r.visible_count() == 200 and avg < 0.2, "mise à jour en %.3f ms par image pour 200 spectateurs (< 0,2 ms)" % avg)
	_check(r.get_child_count() == n0 and r._audio.stream == sp_player.stream("crowd_cheer"), "aucun nœud créé ; clameur jouée par le lecteur 3D")
	r.queue_free()
	sp_player.queue_free()
	await process_frame
	print("test_crowd_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
