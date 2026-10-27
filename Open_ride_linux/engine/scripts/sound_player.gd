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
##
## Lot P10 : le vent est un bruit filtré (boucle raccordée en fondu enchaîné), dont la hauteur suit la
## vitesse dans l'air ; la boucle de roue libre contient `FREEWHEEL_LOOP_CLICKS` coups par seconde et
## `pitch_scale` la cale sur `freewheel.clicks_per_s` du modèle ; un lecteur dédié joue le « clac » de
## reprise (60 ms, `clacs_played` compte les reprises jouées). Sons refaits après la recette P16 (jugés
## désagréables) : vent = grondement grave (bruit brun) et souffle doux qui respire, en boucle de 4 s ;
## roue libre = petits « tic » secs et irréguliers au lieu d'un bip pur à 2,4 kHz.
##
## Lot P13 : deux sons de plus pour les véhicules, `vehicle_pass` (pneus et souffle) et `tractor_engine`
## (moteur grave), joués par les lecteurs 3D de traffic_renderer.gd (`stream(kind)`) ; remplaçables par
## ~/OpenRide/Sounds/<kind>.ogg. Lot P15 : `crowd_cheer` (clameur et applaudissements) pour crowd_renderer.gd.
##
## Lot P21 : quatre sons brefs, non bouclés, des passants (`VOICE_KINDS` : « Allez ! », « Bonjour ! »,
## aboiement, rire d'enfant), synthétisés par une source glottale filtrée par deux formants, ou lus dans
## ~/OpenRide/Sounds/<kind>.ogg (CC0) ; joués par crowd_renderer.gd en mode « passants ».
##
## Volumes du menu Réglages (audio_mix.gd) : vent, roue libre et « clac » sur le bus `Ride`, fonds,
## cloches et points sonores sur le bus `Ambience`.
## Lot P23 : même synthèse pour deux cris d'oiseaux, `crow_caw` (deux croassements rauques) et `raptor_cry`
## (miaulement de buse qui descend), joués par fauna_renderer.gd.

const SoundModel := preload("res://scripts/sound_model.gd")
const AmbienceModel := preload("res://scripts/ambience_model.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")
const BED_SAMPLES := 44100    # fonds d'ambiance : boucles de 2 secondes
const BELL_INTERVAL_S := 2.2

const MIX_RATE := 22050
const SAMPLE_COUNT := 22050   # 1 seconde de boucle
const FREEWHEEL_LOOP_CLICKS := 140.0   # coups par seconde de la boucle à pitch_scale = 1 (≈ 30 km/h)
const FREEWHEEL_MIN_PITCH := 0.05
const FREEWHEEL_JITTER := 0.08         # décalage aléatoire de chaque coup, en fraction de période
const WIND_LOOP_SAMPLES := 88200       # boucle du vent : 4 s, sans motif qui se répète à l'oreille
const WIND_RUMBLE_HZ := 160.0          # grondement : bruit blanc passé deux fois dans un passe-bas
const WIND_BAND_HZ := 600.0            # souffle : passe-bande doux, plus discret que le grondement
const WIND_BAND_Q := 0.6
const WIND_RMS := 0.22
const CLAC_SAMPLES := 1323     # 60 ms
const VOICE_KINDS := ["voice_allez", "voice_bonjour", "dog_bark", "kid_laugh", "crow_caw", "raptor_cry"]
## Syllabes des sons de passants : [début s, fin s, f0 début Hz, f0 fin Hz, formant 1 Hz, formant 2 Hz, souffle 0 à 1].
const VOICE_SYLLABLES := {
	"voice_allez": [[0.0, 0.16, 190.0, 210.0, 800.0, 1250.0, 0.05], [0.2, 0.52, 230.0, 290.0, 420.0, 2000.0, 0.08]],
	"voice_bonjour": [[0.0, 0.2, 200.0, 220.0, 500.0, 900.0, 0.05], [0.26, 0.6, 230.0, 170.0, 320.0, 800.0, 0.15]],
	"dog_bark": [[0.0, 0.12, 420.0, 260.0, 1000.0, 2200.0, 0.4], [0.3, 0.42, 440.0, 270.0, 1000.0, 2200.0, 0.4]],
	"kid_laugh": [[0.0, 0.09, 380.0, 360.0, 900.0, 1500.0, 0.5], [0.14, 0.23, 390.0, 370.0, 900.0, 1500.0, 0.5],
		[0.28, 0.37, 380.0, 350.0, 900.0, 1500.0, 0.5], [0.42, 0.53, 360.0, 300.0, 900.0, 1500.0, 0.5]],
	"crow_caw": [[0.0, 0.22, 520.0, 430.0, 1100.0, 1900.0, 0.55], [0.36, 0.58, 500.0, 410.0, 1100.0, 1900.0, 0.55]],
	"raptor_cry": [[0.0, 0.85, 1800.0, 1150.0, 2200.0, 3300.0, 0.12]],
}

var model := SoundModel.new()

var _wind_player: AudioStreamPlayer
var _freewheel_player: AudioStreamPlayer
var _clac_player: AudioStreamPlayer
var clacs_played := 0                   # « clac » de reprise joués (tests)
var _poi_players: Array[AudioStreamPlayer3D] = []

var _streams: Dictionary = {}
var _lp := 0.0                          # état du filtre passe-bas de la synthèse

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
	_wind_player.bus = AudioMix.bus(AudioMix.RIDE)
	add_child(_wind_player)

	_freewheel_player = AudioStreamPlayer.new()
	_freewheel_player.name = "FreewheelPlayer"
	_freewheel_player.stream = _streams.get("freewheel", null)
	_freewheel_player.volume_db = SoundModel.SILENCE_DB
	_freewheel_player.bus = AudioMix.bus(AudioMix.RIDE)
	add_child(_freewheel_player)

	_clac_player = AudioStreamPlayer.new()
	_clac_player.name = "ClacPlayer"
	_clac_player.stream = _streams.get("clac", null)
	_clac_player.volume_db = -12.0
	_clac_player.bus = AudioMix.bus(AudioMix.RIDE)
	add_child(_clac_player)

	for i in range(SoundModel.MAX_POI_SOURCES):
		var p := AudioStreamPlayer3D.new()
		p.name = "PoiPlayer_%d" % i
		p.unit_size = 10.0
		p.max_distance = 150.0
		p.volume_db = SoundModel.SILENCE_DB
		p.bus = AudioMix.bus(AudioMix.AMBIENCE)
		add_child(p)
		_poi_players.append(p)

	for bed in AmbienceModel.BEDS:
		var bp := AudioStreamPlayer.new()
		bp.name = "Ambience_%s" % bed
		bp.stream = _streams.get(bed, null)
		bp.volume_db = SoundModel.SILENCE_DB
		bp.bus = AudioMix.bus(AudioMix.AMBIENCE)
		add_child(bp)
		_bed_players[bed] = bp


## Flux d'une sorte de son (synthétisé ou .ogg de remplacement), null si inconnue.
func stream(kind: String) -> Resource:
	return _streams.get(kind, null)


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
	if bool(fw["playing"]):
		_freewheel_player.pitch_scale = maxf(float(fw["clicks_per_s"]) / FREEWHEEL_LOOP_CLICKS, FREEWHEEL_MIN_PITCH)
	if bool(fw["clac"]):
		clacs_played += 1
		if is_inside_tree() and _clac_player.stream != null:
			_clac_player.play()
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
	var kinds := ["wind", "freewheel", "church_bell", "river", "livestock", "village", "vehicle_pass", "tractor_engine", "crowd_cheer"]
	for k in kinds:
		var custom_stream = _try_load_custom(k)
		if custom_stream != null:
			_streams[k] = custom_stream
		else:
			_streams[k] = _synthesize_stream(k)
	for k in VOICE_KINDS:
		var custom_voice = _try_load_custom(k)
		_streams[k] = custom_voice if custom_voice != null else _synthesize_voice(k)
	var custom_clac = _try_load_custom("clac")
	_streams["clac"] = custom_clac if custom_clac != null else _synthesize_clac()
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
	if kind == "wind":
		wav.loop_end = WIND_LOOP_SAMPLES
		wav.data = _wind_noise_bytes()   # Lot P10 : bruit filtré, sans la boucle d'échantillons ci-dessous
		return wav
	if kind == "freewheel":
		wav.data = _freewheel_bytes()
		return wav

	var bytes := PackedByteArray()
	bytes.resize(SAMPLE_COUNT * 2)

	var seed_val := 0x12345678
	var h := func() -> int:
		seed_val = (seed_val * 1103515245 + 12345) & 0x7FFFFFFF
		return seed_val

	_lp = 0.0
	for i in range(SAMPLE_COUNT):
		var t := float(i) / float(MIX_RATE)
		var sample := 0.0

		match kind:
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
			"vehicle_pass":
				# Lot P13 : roulement de pneus et souffle d'une voiture (bruit filtré, ronflement à 60 Hz) ;
				# l'effet Doppler vient de l'AudioStreamPlayer3D qui suit le véhicule.
				var r := float(h.call() & 0xFFFF) / 32768.0 - 1.0
				_lp = _lp + 0.08 * (r - _lp)
				sample = _lp * 2.2 + sin(TAU * 60.0 * t) * 0.12
			"crowd_cheer":
				# Lot P15 : clameur (bruit filtré qui ondule) et applaudissements (claquements brefs à 9 Hz,
				# décalés par une phase tirée au hasard), joués par crowd_renderer.gd sur le groupe le plus proche
				var r := float(h.call() & 0xFFFF) / 32768.0 - 1.0
				_lp = _lp + 0.15 * (r - _lp)
				var swell := 0.7 + 0.3 * sin(TAU * 2.0 * t) * sin(TAU * 3.0 * t)
				var clap_phase := fmod(t * 9.0 + 0.37 * sin(TAU * t), 1.0)
				var clap := exp(-clap_phase * 60.0) * (float(h.call() & 0xFFFF) / 32768.0 - 1.0)
				sample = _lp * 1.8 * swell + clap * 0.5
			"tractor_engine":
				# Lot P13 : moteur grave du tracteur (28 Hz et harmoniques, battement des cylindres à 7 Hz)
				var beat := 0.75 + 0.25 * sin(TAU * 7.0 * t)
				sample = (sin(TAU * 28.0 * t) * 0.45 + sin(TAU * 56.0 * t) * 0.25 + sin(TAU * 84.0 * t) * 0.12) * beat

		var s16 := clampi(int(sample * 32767.0), -32768, 32767)
		if s16 < 0:
			s16 += 65536
		bytes[i * 2] = s16 & 0xFF
		bytes[i * 2 + 1] = (s16 >> 8) & 0xFF

	wav.data = bytes
	return wav


## Vent (Lot P10, refait après la recette P16) : grondement grave (bruit blanc passé deux fois dans un
## passe-bas à WIND_RUMBLE_HZ) et souffle doux (passe-bande WIND_BAND_HZ, Q WIND_BAND_Q) qui respire
## lentement (0,5 et 0,75 Hz : nombre entier de cycles sur la boucle), ramenés à WIND_RMS ; boucle de
## WIND_LOOP_SAMPLES dont les 250 dernières ms sont fondues dans les premières (raccord sans clic).
static func _wind_noise_bytes() -> PackedByteArray:
	var n := WIND_LOOP_SAMPLES
	var fade := int(0.25 * MIX_RATE)
	var total := n + fade
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x77696e64
	var k_lp := 1.0 - exp(-TAU * WIND_RUMBLE_HZ / MIX_RATE)
	var w0 := TAU * WIND_BAND_HZ / MIX_RATE
	var alpha := sin(w0) / (2.0 * WIND_BAND_Q)
	var a0 := 1.0 + alpha
	var b0 := alpha / a0
	var a1 := -2.0 * cos(w0) / a0
	var a2 := (1.0 - alpha) / a0
	var rumble := PackedFloat32Array()
	var band := PackedFloat32Array()
	rumble.resize(total)
	band.resize(total)
	var lp1 := 0.0
	var lp2 := 0.0
	var x1 := 0.0
	var x2 := 0.0
	var y1 := 0.0
	var y2 := 0.0
	for i in range(total):
		var x := rng.randf() * 2.0 - 1.0
		lp1 += k_lp * (x - lp1)
		lp2 += k_lp * (lp1 - lp2)
		rumble[i] = lp2
		var y := b0 * x - b0 * x2 - a1 * y1 - a2 * y2
		x2 = x1
		x1 = x
		y2 = y1
		y1 = y
		band[i] = y
	var rms_r := 0.0
	var rms_b := 0.0
	for i in range(n):
		rms_r += rumble[i] * rumble[i]
		rms_b += band[i] * band[i]
	rms_r = sqrt(rms_r / n)
	rms_b = sqrt(rms_b / n)
	var buf := PackedFloat32Array()
	buf.resize(total)
	for i in range(total):
		var t := float(i % n) / MIX_RATE
		var breath := 0.75 + 0.15 * sin(TAU * 0.5 * t) + 0.1 * sin(TAU * 0.75 * t + 1.0)
		buf[i] = rumble[i] / rms_r * (0.9 + 0.1 * breath) + band[i] / rms_b * 0.55 * breath
	var rms := 0.0
	for i in range(n):
		rms += buf[i] * buf[i]
	var gain := WIND_RMS / sqrt(rms / n)
	var bytes := PackedByteArray()
	bytes.resize(n * 2)
	for i in range(n):
		var v := buf[i]
		if i < fade:
			var g := float(i) / float(fade)
			v = buf[i] * g + buf[n + i] * (1.0 - g)
		bytes.encode_s16(i * 2, clampi(int(v * gain * 32767.0), -32768, 32767))
	return bytes


## Roue libre (Lot P10, refaite après la recette P16) : FREEWHEEL_LOOP_CLICKS « tic » par seconde, chacun
## un bref bruit sec (deux résonances amorties en moins de 2 ms et un grain de bruit), d'intensité et de
## place légèrement irrégulières (± FREEWHEEL_JITTER de période), comme les cliquets d'un vrai moyeu.
## Boucle d'une seconde : les coups qui dépassent la fin reprennent au début (raccord sans clic).
static func _freewheel_bytes() -> PackedByteArray:
	var n := SAMPLE_COUNT
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x636c6963
	var buf := PackedFloat32Array()
	buf.resize(n)
	var period := float(n) / FREEWHEEL_LOOP_CLICKS
	var click_len := int(0.004 * MIX_RATE)
	for k in range(int(FREEWHEEL_LOOP_CLICKS)):
		var at := int((float(k) + rng.randf_range(-FREEWHEEL_JITTER, FREEWHEEL_JITTER)) * period + n) % n
		var amp := rng.randf_range(0.55, 1.0)
		var ph := rng.randf() * TAU
		for j in range(click_len):
			var t := float(j) / MIX_RATE
			var v := sin(TAU * 3200.0 * t + ph) * exp(-t / 0.0007) + 0.5 * sin(TAU * 5400.0 * t) * exp(-t / 0.0004)
			v += (rng.randf() * 2.0 - 1.0) * 0.4 * exp(-t / 0.0003)
			buf[(at + j) % n] += v * amp
	var peak := 0.0
	for i in range(n):
		peak = maxf(peak, absf(buf[i]))
	var bytes := PackedByteArray()
	bytes.resize(n * 2)
	for i in range(n):
		bytes.encode_s16(i * 2, clampi(int(buf[i] / maxf(peak, 1e-6) * 0.5 * 32767.0), -32768, 32767))
	return bytes


## « Clac » d'engagement du cliquet à la reprise du pédalage (Lot P10) : 60 ms, sans boucle.
## Son bref d'un passant (Lot P21) : source en dents de scie à la hauteur f0 (glissante sur la syllabe)
## et souffle, filtrée par deux passe-bandes (formants), fondus de 15 ms aux bords de chaque syllabe.
static func _synthesize_voice(kind: String) -> AudioStreamWAV:
	var sylls: Array = VOICE_SYLLABLES[kind]
	var n := int(ceil(float(sylls[-1][1]) * MIX_RATE)) + 220
	var out := PackedFloat32Array()
	out.resize(n)
	var seed_val := 0x2468ACE
	var peak := 0.0
	for syl in sylls:
		var i0 := int(float(syl[0]) * MIX_RATE)
		var i1 := int(float(syl[1]) * MIX_RATE)
		var bp := []
		for f: float in [float(syl[4]), float(syl[5])]:
			var w0 := TAU * f / MIX_RATE
			var alpha := sin(w0) / (2.0 * 4.0)
			var a0 := 1.0 + alpha
			bp.append([alpha / a0, -alpha / a0, -2.0 * cos(w0) / a0, (1.0 - alpha) / a0])
		var z := [[0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]]   # x1, x2, y1, y2 de chaque filtre
		var ph := 0.0
		var fade := int(0.015 * MIX_RATE)
		for i in range(i0, i1):
			var u := float(i - i0) / float(maxi(i1 - i0, 1))
			ph = fmod(ph + lerpf(float(syl[2]), float(syl[3]), u) / MIX_RATE, 1.0)
			seed_val = (seed_val * 1103515245 + 12345) & 0x7FFFFFFF
			var noise := float(seed_val & 0xFFFF) / 32768.0 - 1.0
			var x := (2.0 * ph - 1.0) * (1.0 - float(syl[6])) + noise * float(syl[6])
			var y := 0.0
			for b in range(2):
				var c: Array = bp[b]
				var zz: Array = z[b]
				var yb: float = c[0] * x + c[1] * zz[1] - c[2] * zz[2] - c[3] * zz[3]
				zz[1] = zz[0]
				zz[0] = x
				zz[3] = zz[2]
				zz[2] = yb
				y += yb * (1.0 if b == 0 else 0.6)
			var env := minf(1.0, minf(float(i - i0) / fade, float(i1 - i) / fade))
			out[i] += y * env
			peak = maxf(peak, absf(out[i]))
	var bytes := PackedByteArray()
	bytes.resize(n * 2)
	var gain := 0.8 / maxf(peak, 1e-6)
	for i in range(n):
		var s16 := clampi(int(out[i] * gain * 32767.0), -32768, 32767)
		if s16 < 0:
			s16 += 65536
		bytes[i * 2] = s16 & 0xFF
		bytes[i * 2 + 1] = (s16 >> 8) & 0xFF
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = MIX_RATE
	wav.stereo = false
	wav.loop_mode = AudioStreamWAV.LOOP_DISABLED
	wav.data = bytes
	return wav


static func _synthesize_clac() -> AudioStreamWAV:
	var bytes := PackedByteArray()
	bytes.resize(CLAC_SAMPLES * 2)
	for i in range(CLAC_SAMPLES):
		var t := float(i) / MIX_RATE
		var v := (sin(TAU * 1300.0 * t) * 0.6 + sin(TAU * 3100.0 * t) * 0.3) * exp(-t * 90.0)
		bytes.encode_s16(i * 2, clampi(int(v * 32767.0), -32768, 32767))
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = MIX_RATE
	wav.stereo = false
	wav.loop_mode = AudioStreamWAV.LOOP_DISABLED
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
