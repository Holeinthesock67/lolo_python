extends Node

## Gestionnaire audio du parcours (Lot E4 §4.5, SRS §8 « Audio »).
##
## Gère la lecture continue du vent, de la roue libre et de jusqu'à 4 points d'intérêt spatialisés (L5).
## Génère des sons procéduraux au démarrage sans aucun fichier audio externe requis.
## Permet le remplacement optionnel par des fichiers ~/OpenRide/Sounds/<kind>.ogg.

const SoundModel := preload("res://scripts/sound_model.gd")

const MIX_RATE := 22050
const SAMPLE_COUNT := 22050   # 1 seconde de boucle

var model := SoundModel.new()

var _wind_player: AudioStreamPlayer
var _freewheel_player: AudioStreamPlayer
var _poi_players: Array[AudioStreamPlayer3D] = []

var _streams: Dictionary = {}


func _init() -> void:
	_generate_all_streams()
	_init_players()


func _init_players() -> void:
	_wind_player = AudioStreamPlayer.new()
	_wind_player.name = "WindPlayer"
	_wind_player.stream = _streams.get("wind", null)
	_wind_player.volume_db = SoundModel.SILENCE_DB
	add_child(_wind_player)

	_freewheel_player = AudioStreamPlayer.new()
	_freewheel_player.name = "FreewheelPlayer"
	_freewheel_player.stream = _streams.get("freewheel", null)
	_freewheel_player.volume_db = SoundModel.SILENCE_DB
	add_child(_freewheel_player)

	for i in range(SoundModel.MAX_POI_SOURCES):
		var p := AudioStreamPlayer3D.new()
		p.name = "PoiPlayer_%d" % i
		p.unit_size = 10.0
		p.max_distance = 150.0
		p.volume_db = SoundModel.SILENCE_DB
		add_child(p)
		_poi_players.append(p)


func set_pois(points: Array) -> void:
	model.set_pois(points)


func update_audio(state: Dictionary, now_s: float, rider_pos: Vector3) -> Dictionary:
	model.on_state(state, rider_pos, now_s)
	var eval: Dictionary = model.evaluate(now_s)

	# Vent
	var w: Dictionary = eval["wind"]
	_wind_player.volume_db = float(w["volume_db"])
	_wind_player.pitch_scale = float(w["pitch"])
	if is_inside_tree():
		if float(w["volume_db"]) > SoundModel.SILENCE_DB and not _wind_player.playing:
			_wind_player.play()
		elif float(w["volume_db"]) <= SoundModel.SILENCE_DB and _wind_player.playing:
			_wind_player.stop()

	# Roue libre
	var fw: Dictionary = eval["freewheel"]
	_freewheel_player.volume_db = float(fw["volume_db"])
	if is_inside_tree():
		if bool(fw["playing"]) and float(fw["volume_db"]) > SoundModel.SILENCE_DB:
			if not _freewheel_player.playing:
				_freewheel_player.play()
		else:
			if _freewheel_player.playing:
				_freewheel_player.stop()

	# POIs spatialisés (au plus 4)
	var pois: Array = eval["pois"]
	for i in range(_poi_players.size()):
		var player := _poi_players[i]
		if i < pois.size():
			var poi: Dictionary = pois[i]
			var kind := str(poi["kind"])
			if player.stream != _streams.get(kind, null):
				player.stream = _streams.get(kind, null)
			if is_inside_tree():
				player.global_position = poi["position"]
			else:
				player.position = poi["position"]
			player.volume_db = float(poi["volume_db"])
			if is_inside_tree() and not player.playing and player.stream != null:
				player.play()
		else:
			player.volume_db = SoundModel.SILENCE_DB
			if is_inside_tree() and player.playing:
				player.stop()

	return eval


# --- Génération et chargement des flux audio ---

func _generate_all_streams() -> void:
	var kinds := ["wind", "freewheel", "church_bell", "river", "livestock", "village"]
	for k in kinds:
		var custom_stream = _try_load_custom(k)
		if custom_stream != null:
			_streams[k] = custom_stream
		else:
			_streams[k] = _synthesize_stream(k)


func _try_load_custom(kind: String) -> Resource:
	var home := OS.get_environment("HOME")
	if home.is_empty():
		home = OS.get_environment("USERPROFILE")
	if not home.is_empty():
		var path := home.path_join("OpenRide").path_join("Sounds").path_join(kind + ".ogg")
		if FileAccess.file_exists(path):
			return AudioStreamOggVorbis.load_from_file(path)
	return null


func _synthesize_stream(kind: String) -> AudioStreamWAV:
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = MIX_RATE
	wav.stereo = false
	wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
	wav.loop_begin = 0
	wav.loop_end = SAMPLE_COUNT

	var bytes := PackedByteArray()
	bytes.resize(SAMPLE_COUNT * 2)

	var seed_val := 0x12345678
	var h := func() -> int:
		seed_val = (seed_val * 1103515245 + 12345) & 0x7FFFFFFF
		return seed_val

	for i in range(SAMPLE_COUNT):
		var t := float(i) / float(MIX_RATE)
		var sample := 0.0

		match kind:
			"wind":
				# Bruit de souffle filtré passe-bas
				var r := float(h.call() & 0xFFFF) / 32768.0 - 1.0
				sample = sin(TAU * 120.0 * t) * 0.3 + r * 0.25
			"freewheel":
				# Cliquetis de roue libre périodique (20 clics par seconde)
				var phase := fmod(t * 20.0, 1.0)
				sample = (sin(TAU * 1800.0 * t) * exp(-phase * 25.0)) * 0.6
			"church_bell":
				# Tintement de cloche amorti avec partiels
				sample = (sin(TAU * 440.0 * t) + 0.5 * sin(TAU * 880.0 * t) + 0.25 * sin(TAU * 1320.0 * t)) * exp(-t * 2.5) * 0.5
			"river":
				# Murmure d'eau vive (bruit doux avec ondulations)
				var r := float(h.call() & 0xFFFF) / 32768.0 - 1.0
				sample = (sin(TAU * 240.0 * t) * 0.4 + r * 0.3) * (0.8 + 0.2 * sin(TAU * 3.0 * t))
			"livestock":
				# Sonnaille métallique
				var phase := fmod(t * 1.5, 1.0)
				sample = (sin(TAU * 720.0 * t) + sin(TAU * 1150.0 * t)) * exp(-phase * 6.0) * 0.4
			"village":
				# Rumeur de village
				sample = sin(TAU * 85.0 * t) * 0.3 + sin(TAU * 140.0 * t) * 0.2

		var s16 := clampi(int(sample * 32767.0), -32768, 32767)
		if s16 < 0:
			s16 += 65536
		bytes[i * 2] = s16 & 0xFF
		bytes[i * 2 + 1] = (s16 >> 8) & 0xFF

	wav.data = bytes
	return wav
