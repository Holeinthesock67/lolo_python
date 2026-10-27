extends Node

## Gestionnaire audio du parcours (Lot E4 §4.5, SRS §8 « Audio »).
##
## Gère la lecture continue du vent, de la roue libre et de jusqu'à 4 points d'intérêt spatialisés (L5).
## Génère des sons procéduraux au démarrage sans aucun fichier audio externe requis.
## Permet le remplacement optionnel par des fichiers ~/OpenRide/Sounds/<kind>.ogg.
##
## Lot P9 : six fonds d'ambiance non spatialisés (`AmbienceModel.BEDS` : oiseaux, insectes, eau, village,
## vent d'altitude, pluie), synthétisés au lancement ou lus dans ~/OpenRide/Sounds/<fond>.ogg, réglés par
## `update_ambience(neigh, now_s)` ; les cloches des points `church_bell` sonnent l'heure pleine
## (`update_bells(hour, now_s)`, heure du PC par défaut).

const SoundModel := preload("res://scripts/sound_model.gd")
const AmbienceModel := preload("res://scripts/ambience_model.gd")
const BED_SAMPLES := 44100    # fonds d'ambiance : boucles de 2 secondes
const BELL_INTERVAL_S := 2.2

const MIX_RATE := 22050
const SAMPLE_COUNT := 22050   # 1 seconde de boucle

var model := SoundModel.new()

var _wind_player: AudioStreamPlayer
var _freewheel_player: AudioStreamPlayer
var _poi_players: Array[AudioStreamPlayer3D] = []

var _streams: Dictionary = {}

var ambience := AmbienceModel.new()
var _bed_players: Dictionary = {}       # fond -> AudioStreamPlayer
var _bell_queue := 0                    # coups de cloche restant à sonner
var _bell_next_s := 0.0
var _bell_hour := NAN
var bell_strikes_rung := 0              # coups effectivement sonnés (tests)


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

	for bed in AmbienceModel.BEDS:
		var bp := AudioStreamPlayer.new()
		bp.name = "Ambience_%s" % bed
		bp.stream = _streams.get(bed, null)
		bp.volume_db = SoundModel.SILENCE_DB
		add_child(bp)
		_bed_players[bed] = bp


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


## Fonds d'ambiance (Lot P9) : une fois par image, avec le voisinage décrit par AmbienceModel.describe.
func update_ambience(neigh: Dictionary, now_s: float) -> Dictionary:
	var vols: Dictionary = ambience.evaluate(neigh, now_s)
	for bed in AmbienceModel.BEDS:
		var bp: AudioStreamPlayer = _bed_players[bed]
		var db := float(vols[bed])
		bp.volume_db = db
		if is_inside_tree():
			if db > SoundModel.SILENCE_DB and not bp.playing and bp.stream != null:
				bp.play()
			elif db <= SoundModel.SILENCE_DB and bp.playing:
				bp.stop()
	return vols


## Cloches à l'heure pleine : `hour` en heures décimales (NAN : heure du PC). Les coups sont joués par
## les lecteurs des points `church_bell` en cours (hors de portée : rien), espacés de BELL_INTERVAL_S.
func update_bells(hour: float, now_s: float) -> void:
	var h := AmbienceModel.local_hour() if is_nan(hour) else hour
	var strikes := AmbienceModel.bell_strikes(_bell_hour, h)
	_bell_hour = h
	if strikes > 0:
		_bell_queue = strikes
		_bell_next_s = now_s
	if _bell_queue <= 0 or now_s < _bell_next_s:
		return
	_bell_queue -= 1
	_bell_next_s = now_s + BELL_INTERVAL_S
	bell_strikes_rung += 1
	for p in _poi_players:
		if p.stream == _streams.get("church_bell", null) and p.volume_db > SoundModel.SILENCE_DB and is_inside_tree():
			p.play(0.0)


# --- Génération et chargement des flux audio ---

func _generate_all_streams() -> void:
	var kinds := ["wind", "freewheel", "church_bell", "river", "livestock", "village"]
	for k in kinds:
		var custom_stream = _try_load_custom(k)
		if custom_stream != null:
			_streams[k] = custom_stream
		else:
			_streams[k] = _synthesize_stream(k)
	for bed in AmbienceModel.BEDS:
		var custom_bed = _try_load_custom(bed)
		_streams[bed] = custom_bed if custom_bed != null else _synthesize_bed(bed)


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


## Fonds d'ambiance procéduraux (Lot P9), boucles de 2 s sans raccord audible : modulations à un nombre
## entier de cycles par boucle, motifs tirés d'un générateur déterministe (même son à chaque lancement).
static func _synthesize_bed(bed: String) -> AudioStreamWAV:
	var n := BED_SAMPLES
	var buf := PackedFloat32Array()
	buf.resize(n)
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(bed)
	var loop_s := float(n) / float(MIX_RATE)
	match bed:
		"forest_birds":
			# Chants : courtes glissades de 2,5 à 5 kHz, par motifs de 2 à 4 notes
			var t0 := 0.05
			while t0 < loop_s - 0.4:
				var notes := rng.randi_range(2, 4)
				var f0 := rng.randf_range(2500.0, 4200.0)
				for k in range(notes):
					var dur := rng.randf_range(0.05, 0.12)
					var f1 := f0 + rng.randf_range(-600.0, 900.0)
					var amp := rng.randf_range(0.18, 0.35)
					var start := int((t0 + k * (dur + 0.03)) * MIX_RATE)
					var len := int(dur * MIX_RATE)
					var ph := 0.0
					for i in range(len):
						var idx := start + i
						if idx >= n:
							break
						var u := float(i) / float(len)
						ph += TAU * lerpf(f0, f1, u) / MIX_RATE
						buf[idx] += sin(ph) * sin(PI * u) * amp
				t0 += rng.randf_range(0.25, 0.6)
		"field_insects":
			# Stridulation : porteuse de 4,6 kHz hachée à 30 Hz, par salves de 0,4 s
			for i in range(n):
				var t := float(i) / MIX_RATE
				var burst := 1.0 if fmod(t, 0.5) < 0.4 else 0.0
				var chop := maxf(sin(TAU * 30.0 * t), 0.0)
				buf[i] = sin(TAU * 4600.0 * t) * chop * burst * 0.25
		"water_flow", "village_murmur", "high_wind", "rain":
			# Bruits filtrés passe-bas (un pôle), plus ou moins sourds
			var alpha: float = {"water_flow": 0.18, "village_murmur": 0.04, "high_wind": 0.02, "rain": 0.6}[bed]
			var lp := 0.0
			for i in range(n):
				var t := float(i) / MIX_RATE
				var r := rng.randf() * 2.0 - 1.0
				lp += alpha * (r - lp)
				var v := lp
				match bed:
					"water_flow":
						v = lp * (0.8 + 0.2 * sin(TAU * 3.0 * t / loop_s)) * 1.6
					"village_murmur":
						v = lp * 2.5 + sin(TAU * 110.0 * t) * 0.05 * (0.5 + 0.5 * sin(TAU * t / loop_s))
					"high_wind":
						v = lp * 4.0 * (0.6 + 0.4 * sin(TAU * t / loop_s))
					"rain":
						v = (r - lp) * 0.35
				buf[i] = v
			if bed == "rain":
				for d in range(40):   # gouttes
					var at := rng.randi_range(0, n - 400)
					for i in range(300):
						buf[at + i] += sin(TAU * 1800.0 * i / MIX_RATE) * exp(-float(i) / 40.0) * 0.3
	# Fondu de 10 ms aux bords pour éviter un clic au raccord
	var edge := int(0.01 * MIX_RATE)
	for i in range(edge):
		var g := float(i) / float(edge)
		buf[i] *= g
		buf[n - 1 - i] *= g
	var bytes := PackedByteArray()
	bytes.resize(n * 2)
	for i in range(n):
		bytes.encode_s16(i * 2, clampi(int(buf[i] * 32767.0), -32768, 32767))
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = MIX_RATE
	wav.stereo = false
	wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
	wav.loop_begin = 0
	wav.loop_end = n
	wav.data = bytes
	return wav
