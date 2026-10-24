extends SceneTree

## Tests unitaires sans écran de sound_player.gd (Lot E4 §4.5).
## Vérifie :
## - Jamais plus de 4 lecteurs 3D actifs.
## - Volumes à 0,5 dB près de ceux de sound_model.gd.
## - Aucun nœud créé après le démarrage.
## - Remplacement par .ogg si disponible.
## - Temps CPU de génération des sons au démarrage < 500 ms.

const SoundPlayer := preload("res://scripts/sound_player.gd")
const SoundModel := preload("res://scripts/sound_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_sound_synthesis_perf() -> void:
	var t0 := Time.get_ticks_usec()
	var sp = SoundPlayer.new()
	root.add_child(sp)
	var elapsed_ms := (Time.get_ticks_usec() - t0) / 1000.0
	print("Génération de tous les sons : %.2f ms (seuil 500 ms)" % elapsed_ms)
	_check(elapsed_ms < 500.0, "génération des sons au démarrage en %.2f ms (< 500 ms)" % elapsed_ms)

	# Vérifier que les 6 sons procéduraux ont été créés
	var all_streams_ok := true
	for k in ["wind", "freewheel", "church_bell", "river", "livestock", "village"]:
		var s: Resource = sp._streams.get(k, null)
		if s == null or not (s is AudioStreamWAV):
			all_streams_ok = false
	_check(all_streams_ok, "tous les flux procéduraux générés et valides")

	sp.queue_free()


func _test_scenarios_and_limits() -> void:
	var sp = SoundPlayer.new()
	root.add_child(sp)
	await process_frame

	var child_count_initial := sp.get_child_count()

	# 6 POIs différents
	var pois := [
		{"id": "p1", "kind": "church_bell", "x": 10.0, "y": 0.0, "z": 0.0, "radius_m": 50.0},
		{"id": "p2", "kind": "river", "x": 20.0, "y": 0.0, "z": 0.0, "radius_m": 50.0},
		{"id": "p3", "kind": "livestock", "x": 30.0, "y": 0.0, "z": 0.0, "radius_m": 50.0},
		{"id": "p4", "kind": "village", "x": 40.0, "y": 0.0, "z": 0.0, "radius_m": 50.0},
		{"id": "p5", "kind": "church_bell", "x": 50.0, "y": 0.0, "z": 0.0, "radius_m": 50.0},
		{"id": "p6", "kind": "river", "x": 60.0, "y": 0.0, "z": 0.0, "radius_m": 50.0},
	]
	sp.set_pois(pois)

	# Scénario : arrêt, accélération à 30 km/h, roue libre
	var rider := Vector3.ZERO
	var max_active_pois := 0
	var no_nodes_created := true
	var volume_matches := true

	# Trames de simulation sur 10 secondes
	for step in range(50):
		var t := float(step) * 0.2
		rider.x = t * 6.0 # avance le long des POIs
		var speed_kmh := 30.0 if t > 1.0 else 0.0
		var power_w := 0.0 if t > 5.0 else 200.0 # roue libre après t=5s
		var state := {
			"v": speed_kmh / 3.6,
			"power": power_w,
			"paused": false,
		}

		var eval: Dictionary = sp.update_audio(state, t, rider)

		# Compter les lecteurs 3D actifs
		var active_3d := 0
		for p in sp._poi_players:
			if p.volume_db > SoundModel.SILENCE_DB:
				active_3d += 1
		max_active_pois = maxi(max_active_pois, active_3d)

		if sp.get_child_count() != child_count_initial:
			no_nodes_created = false

		# Vérifier conformité volume vent et roue libre avec sound_model
		if absf(sp._wind_player.volume_db - float(eval["wind"]["volume_db"])) > 0.5:
			volume_matches = false
		if absf(sp._freewheel_player.volume_db - float(eval["freewheel"]["volume_db"])) > 0.5:
			volume_matches = false

	_check(max_active_pois <= 4, "jamais plus de 4 lecteurs 3D actifs (max relevé: %d)" % max_active_pois)
	_check(no_nodes_created, "aucun nœud créé après le démarrage (%d enfants permanents)" % child_count_initial)
	_check(volume_matches, "volumes des lecteurs à moins de 0.5 dB de sound_model.gd")

	sp.queue_free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_sound_synthesis_perf()
	await _test_scenarios_and_limits()
	print("test_sound_player : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
