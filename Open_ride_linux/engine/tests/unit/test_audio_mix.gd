extends SceneTree

## Tests unitaires sans écran des volumes du menu Réglages (`audio_mix.gd`, docs/AUDIO.md).
## Vérifie :
## - Bus `Ride`, `Ambience` et `Events` créés une seule fois, envoyés au bus Master.
## - Courbe des volumes : 100 % = 0 dB, 50 % ≈ −12 dB, 0 % = bus coupé ; lecture en % inverse.
## - `apply_settings` : seuls les réglages `audio.*` numériques règlent un bus.
## - Chaque lecteur est sur le bus de sa catégorie (sound_player, traffic_renderer, crowd_renderer).
## - Volumes affichés en curseur dans Réglages, comme la difficulté.
## Lancement : godot --headless --path engine --script res://tests/unit/test_audio_mix.gd

const AudioMix := preload("res://scripts/audio_mix.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const TrafficRenderer := preload("res://scripts/traffic_renderer.gd")
const CrowdRenderer := preload("res://scripts/crowd_renderer.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")
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


static func _volume_item(key: String, value) -> Dictionary:
	return {"key": key, "label": key, "type": "int", "value": value, "min": 0, "max": 100, "step": 10,
		"unit": "%", "applies": "now"}


func _test_buses() -> void:
	AudioMix.ensure_buses()
	var n := AudioServer.bus_count
	AudioMix.ensure_buses()
	_check(AudioServer.bus_count == n, "bus créés une seule fois (%d bus)" % n)
	var sends_ok := true
	for b in [AudioMix.RIDE, AudioMix.AMBIENCE, AudioMix.EVENTS]:
		var i := AudioServer.get_bus_index(b)
		sends_ok = sends_ok and i > 0 and AudioServer.get_bus_send(i) == AudioMix.MASTER
	_check(sends_ok, "Ride, Ambience et Events existent et passent par Master")


func _test_curve() -> void:
	AudioMix.set_volume(AudioMix.RIDE, 100)
	var i := AudioServer.get_bus_index(AudioMix.RIDE)
	_check(is_zero_approx(AudioServer.get_bus_volume_db(i)) and not AudioServer.is_bus_mute(i), "100 % : 0 dB")
	AudioMix.set_volume(AudioMix.RIDE, 50)
	_check(absf(AudioServer.get_bus_volume_db(i) + 12.04) < 0.05, "50 %% : −12 dB (%.2f dB)" % AudioServer.get_bus_volume_db(i))
	var round_trip := true
	for pct in range(10, 101, 10):
		AudioMix.set_volume(AudioMix.RIDE, pct)
		round_trip = round_trip and AudioMix.volume_pct(AudioMix.RIDE) == pct
	_check(round_trip, "lecture en % inverse de la courbe, de 10 à 100 %")
	AudioMix.set_volume(AudioMix.RIDE, 0)
	_check(AudioServer.is_bus_mute(i) and AudioMix.volume_pct(AudioMix.RIDE) == 0, "0 % : bus coupé")
	AudioMix.set_volume(AudioMix.RIDE, 140)
	_check(AudioMix.volume_pct(AudioMix.RIDE) == 100 and not AudioServer.is_bus_mute(i), "valeur bornée à 100 %")


func _test_apply_settings() -> void:
	var items := [
		_volume_item("audio.master_pct", 80),
		_volume_item("audio.ride_pct", 60),
		_volume_item("audio.ambience_pct", 0),
		_volume_item("audio.events_pct", 100),
		_volume_item("trainer.difficulty_pct", 30),
		{"key": "render.quality", "type": "choice", "value": "low"},
		{"key": "audio.inconnu_pct", "value": 10},
		"pas un dictionnaire",
	]
	var n := AudioMix.apply_settings(items)
	_check(n == 4, "quatre volumes appliqués, le reste ignoré (%d)" % n)
	_check(AudioMix.volume_pct(AudioMix.MASTER) == 80 and AudioMix.volume_pct(AudioMix.RIDE) == 60
			and AudioMix.volume_pct(AudioMix.AMBIENCE) == 0 and AudioMix.volume_pct(AudioMix.EVENTS) == 100,
		"chaque réglage audio.* règle son bus")
	_check(AudioMix.apply_settings([_volume_item("audio.master_pct", "fort")]) == 0, "valeur non numérique ignorée")
	AudioMix.apply_settings([_volume_item("audio.master_pct", 100), _volume_item("audio.ambience_pct", 100)])


func _test_players_on_buses() -> void:
	var sp = SoundPlayer.new()
	root.add_child(sp)
	var ride_ok: bool = sp._wind_player.bus == AudioMix.RIDE and sp._freewheel_player.bus == AudioMix.RIDE \
		and sp._clac_player.bus == AudioMix.RIDE
	_check(ride_ok, "vent, roue libre et « clac » sur le bus Ride")
	var amb_ok := true
	for p in sp._poi_players:
		amb_ok = amb_ok and p.bus == AudioMix.AMBIENCE
	for bed in AmbienceModel.BEDS:
		amb_ok = amb_ok and sp._bed_players[bed].bus == AudioMix.AMBIENCE
	_check(amb_ok, "points sonores et fonds d'ambiance sur le bus Ambience")
	var tr = TrafficRenderer.new()
	root.add_child(tr)
	var traffic_ok := true
	for audio in tr._audio:
		traffic_ok = traffic_ok and audio.bus == AudioMix.AMBIENCE
	_check(traffic_ok and tr._audio.size() > 0, "véhicules sur le bus Ambience")
	var crowd = CrowdRenderer.new()
	var passers = CrowdRenderer.new("passersby")
	root.add_child(crowd)
	root.add_child(passers)
	_check(crowd._audio.bus == AudioMix.AMBIENCE and passers._audio.bus == AudioMix.AMBIENCE,
		"foule et passants sur le bus Ambience")
	for n in [sp, tr, crowd, passers]:
		n.queue_free()


func _test_menu_slider() -> void:
	var vol := _volume_item("audio.master_pct", 70)
	_check(SettingsViewModel.format_value(vol, 70) == "■■■■■■■□□□ 70 %", "volume affiché en curseur")
	var diff := _volume_item("trainer.difficulty_pct", 50)
	_check(SettingsViewModel.format_value(diff, 50) == "■■■■■□□□□□ 50 %", "difficulté toujours en curseur")
	var cap := {"key": "wind.max_grade_offset_pct", "type": "int", "min": 0, "max": 8, "unit": "pts"}
	_check(SettingsViewModel.format_value(cap, 4) == "4 pts", "plafond du vent en nombre, pas en curseur")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_buses()
	_test_curve()
	_test_apply_settings()
	_test_players_on_buses()
	_test_menu_slider()
	print("test_audio_mix : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
