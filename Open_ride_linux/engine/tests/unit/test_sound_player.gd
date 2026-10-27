extends SceneTree

## Tests unitaires sans écran de sound_player.gd (Lot E4 §4.5).
## Vérifie :
## - Jamais plus de 4 lecteurs 3D actifs.
## - Volumes à 0,5 dB près de ceux de sound_model.gd.
## - Aucun nœud créé après le démarrage.
## - Remplacement par .ogg si disponible.
## - Temps CPU de génération des sons au démarrage < 500 ms.
## - Lot P9 : fonds d'ambiance générés (ou .ogg de remplacement), lecteurs réglés par le modèle,
##   cloches de l'heure pleine sur les points church_bell.
## - Lot P10 : vent en bruit passe-bande bouclé sans clic, cliquetis calé sur le modèle, un « clac » par
##   reprise du pédalage.

const SoundPlayer := preload("res://scripts/sound_player.gd")
const SoundModel := preload("res://scripts/sound_model.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")
const AmbienceModel := preload("res://scripts/ambience_model.gd")

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
	print("Génération de tous les sons : %.2f ms" % elapsed_ms)
	_check(PerfBudget.check("sound_generation", elapsed_ms),
		"génération des sons au démarrage dans le budget (%.2f ms)" % elapsed_ms)

	# Vérifier que les 6 sons procéduraux ont été créés
	var all_streams_ok := true
	for k in ["wind", "freewheel", "church_bell", "river", "livestock", "village"]:
		var s: Resource = sp._streams.get(k, null)
		if s == null or not (s is AudioStreamWAV):
			all_streams_ok = false
	_check(all_streams_ok, "tous les flux procéduraux générés et valides")
	var beds_ok := true
	for bed in AmbienceModel.BEDS:
		var b: Resource = sp._streams.get(bed, null)
		beds_ok = beds_ok and b is AudioStreamWAV and (b as AudioStreamWAV).loop_mode == AudioStreamWAV.LOOP_FORWARD \
			and (b as AudioStreamWAV).data.size() == SoundPlayer.BED_SAMPLES * 2
		beds_ok = beds_ok and sp._bed_players.has(bed) and not (sp._bed_players[bed] is AudioStreamPlayer3D)
	_check(beds_ok, "fonds d'ambiance : 6 boucles générées, lecteurs non spatialisés")

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


# Lot P9, critère 5 : fichier ~/OpenRide/Sounds/<fond>.ogg utilisé s'il existe
func _test_ogg_override() -> void:
	var home := OS.get_environment("HOME")
	var tmp := OS.get_user_data_dir().path_join("test_home_p9")
	DirAccess.make_dir_recursive_absolute(tmp.path_join("OpenRide/Sounds"))
	DirAccess.copy_absolute(ProjectSettings.globalize_path("res://tests/data/sounds/rain.ogg"),
		tmp.path_join("OpenRide/Sounds/rain.ogg"))
	OS.set_environment("HOME", tmp)
	var sp = SoundPlayer.new()
	OS.set_environment("HOME", home)
	_check(sp._streams["rain"] is AudioStreamOggVorbis and sp._streams["forest_birds"] is AudioStreamWAV,
		"rain.ogg de remplacement utilisé, les autres fonds restent synthétisés")
	sp.free()
	DirAccess.remove_absolute(tmp.path_join("OpenRide/Sounds/rain.ogg"))


func _test_ambience_and_bells() -> void:
	var sp = SoundPlayer.new()
	root.add_child(sp)
	await process_frame
	var n0: int = sp.get_child_count()
	var neigh := {"forest_share": 0.9, "built_share": 0.0, "solar_hour": 12.0, "alt_m": 300.0}
	var vols := {}
	for i in range(600):
		vols = sp.update_ambience(neigh, i / 60.0)
	var match_ok := true
	for bed in AmbienceModel.BEDS:
		match_ok = match_ok and absf(sp._bed_players[bed].volume_db - float(vols[bed])) < 0.01
	_check(match_ok and float(vols["forest_birds"]) > SoundModel.SILENCE_DB and sp.get_child_count() == n0,
		"fonds : volumes des lecteurs égaux à ceux du modèle, aucun nœud créé")
	sp.set_pois([{"id": "b", "kind": "church_bell", "x": 5.0, "y": 0.0, "z": 0.0, "radius_m": 80.0}])
	var t := 0.0
	var hour := 14.995
	for i in range(900):   # 15 s : passage de 15 h
		sp.update_audio({"v": 0.0, "power": 0.0, "paused": false}, t, Vector3.ZERO)
		sp.update_bells(hour, t)
		t += 1.0 / 60.0
		hour += 1.0 / 60.0 / 3600.0 * 60.0   # horloge accélérée : une minute par seconde
	_check(sp.bell_strikes_rung == 3, "15 h : 3 coups de cloche (%d)" % sp.bell_strikes_rung)
	var before: int = sp.bell_strikes_rung
	for i in range(600):
		sp.update_bells(15.3 + i * 0.0005, t + i / 60.0)
	_check(sp.bell_strikes_rung == before, "aucun coup hors de l'heure pleine")
	sp.queue_free()


# Lot P10 : boucle du vent sans clic, pitch du cliquetis égal au rythme du modèle, un « clac » par reprise
func _test_p10_wind_and_freewheel() -> void:
	var sp = SoundPlayer.new()
	root.add_child(sp)
	await process_frame
	var n0: int = sp.get_child_count()
	var wind: AudioStreamWAV = sp._streams["wind"]
	var d := wind.data
	var last := d.decode_s16(d.size() - 2)
	var first := d.decode_s16(0)
	var max_step := 0
	for i in range(1, d.size() / 2):
		max_step = maxi(max_step, absi(d.decode_s16(i * 2) - d.decode_s16(i * 2 - 2)))
	_check(absi(first - last) <= max_step, "boucle du vent : raccord (%d) pas plus brusque que le bruit lui-même (%d)" % [
		absi(first - last), max_step])
	var clac: AudioStreamWAV = sp._streams["clac"]
	_check(clac.loop_mode == AudioStreamWAV.LOOP_DISABLED and clac.data.size() / 2.0 / clac.mix_rate < 0.08,
		"« clac » : son court sans boucle (%.0f ms)" % (clac.data.size() / 2.0 / clac.mix_rate * 1000.0))

	var pitch_ok := true
	var t := 0.0
	for phase in [[36.0, 0.0, 40], [36.0, 200.0, 10], [18.0, 0.0, 40], [18.0, 200.0, 10]]:
		for i in range(int(phase[2])):
			var ev: Dictionary = sp.update_audio({"v": float(phase[0]) / 3.6, "power": phase[1], "paused": false}, t, Vector3.ZERO)
			if bool(ev["freewheel"]["playing"]):
				var want := float(ev["freewheel"]["clicks_per_s"]) / SoundPlayer.FREEWHEEL_LOOP_CLICKS
				pitch_ok = pitch_ok and is_equal_approx(sp._freewheel_player.pitch_scale, want)
			t += 0.05
	_check(pitch_ok and absf(sp._freewheel_player.pitch_scale - 0.857) < 0.02,
		"cliquetis : pitch_scale = coups/s du modèle / %d (%.3f à 18 km/h)" % [
			int(SoundPlayer.FREEWHEEL_LOOP_CLICKS), sp._freewheel_player.pitch_scale])
	_check(sp.clacs_played == 2 and sp.get_child_count() == n0,
		"deux reprises du pédalage : %d « clac », aucun nœud créé" % sp.clacs_played)
	sp.queue_free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_sound_synthesis_perf()
	await _test_scenarios_and_limits()
	_test_ogg_override()
	await _test_ambience_and_bells()
	await _test_p10_wind_and_freewheel()
	print("test_sound_player : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
