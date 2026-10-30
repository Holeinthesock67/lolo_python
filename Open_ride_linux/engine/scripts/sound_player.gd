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
## désagréables) : vent = grondement grave (bruit brun) et souffle doux, en boucle de 4 s (sans « respiration » depuis le 28/10) ;
## roue libre = petits « tic » secs et irréguliers au lieu d'un bip pur à 2,4 kHz.
##
## Lot P13 : deux sons de plus pour les véhicules, `vehicle_pass` (pneus et souffle) et `tractor_engine`
## (moteur grave), joués par les lecteurs 3D de traffic_renderer.gd (`stream(kind)`) ; remplaçables par
## ~/OpenRide/Sounds/<kind>.ogg. Lot P15 : `crowd_cheer` (clameur et applaudissements) pour crowd_renderer.gd.
## Lot P26 : `helicopter_rotor` (battement des pales) et `airliner_rumble` (grondement lointain), joués par
## sky_traffic_renderer.gd ; lot P31 : `paramotor_buzz` (bourdonnement d'un paramoteur). Lot P29 : `barge_engine` (diesel lent d'une péniche) et `ship_horn` (corne de
## brume, jouée une fois), joués par boat_renderer.gd.
##
## Lot P21 : quatre sons brefs, non bouclés, des passants (`VOICE_KINDS` : « Allez ! », « Bonjour ! »,
## aboiement, rire d'enfant), synthétisés par une source glottale filtrée par deux formants, ou lus dans
## ~/OpenRide/Sounds/<kind>.ogg (CC0) ; joués par crowd_renderer.gd en mode « passants ».
##
## Volumes du menu Réglages (audio_mix.gd) : vent, roue libre et « clac » sur le bus `Ride`, fonds,
## cloches et points sonores sur le bus `Ambience`.
## Lot P23 : même synthèse pour deux cris d'oiseaux, `crow_caw` (deux croassements rauques) et `raptor_cry`
## (miaulement de buse qui descend), joués par fauna_renderer.gd. Lot P24 : `cow_moo` (meuglement grave et long),
## `sheep_baa` (bêlement) et `horse_neigh` (hennissement qui descend en trilles) des troupeaux.
## Lot P28 : `voice_salut` (« Salut ! », même synthèse que les passants) pour les cyclistes du décor qui
## doublent (road_cyclists_renderer.gd).
##
## Lot T17 : jingles des événements du parcours (`EventSoundsModel.JINGLES` : sommet, sprint, arche, fin
## de séance), synthétisés note par note ou lus dans ~/OpenRide/Sounds/<nom>.ogg ; `play_event(nom)`
## les joue sur un lecteur non spatialisé du bus `Events` (« Volume bips et événements » des Réglages,
## audio_mix.gd), trois à la fois au plus. Depuis le 29/10 (jingles de départ et de ligne d'une boucle), les
## jingles ne sont plus faits au démarrage mais un par image ensuite (`_process`, 8 à 60 ms chacun), ou tout
## de suite s'il en faut un avant : le budget `sound_generation` du démarrage y gagne ~0,2 s.

const SoundModel := preload("res://scripts/sound_model.gd")
const AmbienceModel := preload("res://scripts/ambience_model.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")
const EventSoundsModel := preload("res://scripts/event_sounds_model.gd")
const EVENT_DB := -6.0
const EVENT_POLYPHONY := 3
const BED_SAMPLES := 44100    # fonds d'ambiance : boucles de 2 secondes
const BELL_INTERVAL_S := 2.2

const MIX_RATE := 22050
const SAMPLE_COUNT := 22050   # 1 seconde de boucle
const ONE_SHOT_KINDS := ["ship_horn", "church_bell"]   # sons joués une fois (P29 ; cloche : un coup par update_bells)
const ONE_SHOT_TAIL_S := 0.03
const NOISE_LOOP_S := 4.0       # boucle des sons à bruit (river et NOISE_LOWPASS), comme le vent
const NOISE_MIX_RATE := 11025   # leur bruit est sourd : demi-fréquence, même coût qu'une boucle de 2 s
## Coefficient du passe-bas du bruit de chaque son en boucle qui en contient un (bruit périodique, sans clic).
const NOISE_LOWPASS := {"vehicle_pass": 0.08, "crowd_cheer": 0.15, "helicopter_rotor": 0.25, "airliner_rumble": 0.02,
	"paramotor_buzz": 0.3, "barge_engine": 0.05}
## Coups de la sonnaille sur la boucle d'une seconde : [instant s, force], irréguliers pour ne pas battre la mesure.
const LIVESTOCK_STRIKES := [[0.0, 1.0], [0.29, 0.55], [0.71, 0.8]]
const FREEWHEEL_LOOP_CLICKS := 140.0   # coups par seconde de la boucle à pitch_scale = 1 (≈ 30 km/h)
const FREEWHEEL_MIN_PITCH := 0.05
const FREEWHEEL_JITTER := 0.08         # décalage aléatoire de chaque coup, en fraction de période
const WIND_LOOP_SAMPLES := 88200       # boucle du vent : 4 s, sans motif qui se répète à l'oreille
const WIND_RUMBLE_HZ := 160.0          # grondement : bruit blanc passé deux fois dans un passe-bas
const WIND_BAND_HZ := 600.0            # souffle : passe-bande doux, plus discret que le grondement
const WIND_BAND_Q := 0.6
const WIND_RMS := 0.22
const CLAC_SAMPLES := 1323     # 60 ms
const VOICE_KINDS := ["voice_allez", "voice_bonjour", "dog_bark", "kid_laugh", "crow_caw", "raptor_cry", "cow_moo", "sheep_baa",
	"horse_neigh", "voice_salut"]
## Syllabes des sons de passants : [début s, fin s, f0 début Hz, f0 fin Hz, formant 1 Hz, formant 2 Hz, souffle 0 à 1].
const VOICE_SYLLABLES := {
	"voice_allez": [[0.0, 0.16, 190.0, 210.0, 800.0, 1250.0, 0.05], [0.2, 0.52, 230.0, 290.0, 420.0, 2000.0, 0.08]],
	"voice_bonjour": [[0.0, 0.2, 200.0, 220.0, 500.0, 900.0, 0.05], [0.26, 0.6, 230.0, 170.0, 320.0, 800.0, 0.15]],
	"dog_bark": [[0.0, 0.12, 420.0, 260.0, 1000.0, 2200.0, 0.4], [0.3, 0.42, 440.0, 270.0, 1000.0, 2200.0, 0.4]],
	"kid_laugh": [[0.0, 0.09, 380.0, 360.0, 900.0, 1500.0, 0.5], [0.14, 0.23, 390.0, 370.0, 900.0, 1500.0, 0.5],
		[0.28, 0.37, 380.0, 350.0, 900.0, 1500.0, 0.5], [0.42, 0.53, 360.0, 300.0, 900.0, 1500.0, 0.5]],
	"crow_caw": [[0.0, 0.22, 520.0, 430.0, 1100.0, 1900.0, 0.55], [0.36, 0.58, 500.0, 410.0, 1100.0, 1900.0, 0.55]],
	"raptor_cry": [[0.0, 0.85, 1800.0, 1150.0, 2200.0, 3300.0, 0.12]],
	"voice_salut": [[0.0, 0.17, 210.0, 235.0, 760.0, 1300.0, 0.3], [0.22, 0.5, 245.0, 190.0, 300.0, 1800.0, 0.1]],
	"cow_moo": [[0.0, 0.3, 105.0, 125.0, 320.0, 700.0, 0.1], [0.3, 0.98, 125.0, 95.0, 380.0, 820.0, 0.12]],
	"sheep_baa": [[0.0, 0.12, 270.0, 300.0, 600.0, 1300.0, 0.25], [0.12, 0.72, 300.0, 255.0, 750.0, 1400.0, 0.3]],
	"horse_neigh": [[0.0, 0.18, 950.0, 880.0, 1000.0, 2300.0, 0.3], [0.2, 0.34, 860.0, 760.0, 1000.0, 2300.0, 0.3],
		[0.36, 0.5, 740.0, 640.0, 950.0, 2200.0, 0.3], [0.52, 0.8, 620.0, 420.0, 850.0, 2000.0, 0.35]],
}

var model := SoundModel.new()

var _wind_player: AudioStreamPlayer
var _freewheel_player: AudioStreamPlayer
var _clac_player: AudioStreamPlayer
var _wheel_player: AudioStreamPlayer     # ronronnement / sifflement des roues (lot V7)
var clacs_played := 0                   # « clac » de reprise joués (tests)
var _poi_players: Array[AudioStreamPlayer3D] = []

var _streams: Dictionary = {}

var ambience := AmbienceModel.new()
var _bed_players: Dictionary = {}       # fond -> AudioStreamPlayer
var _bell_queue := 0                    # coups de cloche restant à sonner
var _bell_next_s := 0.0
var _bell_hour := NAN
var bell_strikes_rung := 0              # coups effectivement sonnés (tests)
var _event_player: AudioStreamPlayer
var events_played := []                # jingles demandés (tests)


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

	_wheel_player = AudioStreamPlayer.new()
	_wheel_player.name = "WheelPlayer"
	_wheel_player.volume_db = SoundModel.SILENCE_DB
	_wheel_player.bus = AudioMix.bus(AudioMix.RIDE)
	add_child(_wheel_player)

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

	_event_player = AudioStreamPlayer.new()
	_event_player.name = "EventPlayer"
	_event_player.bus = AudioMix.bus(AudioMix.EVENTS)
	_event_player.max_polyphony = EVENT_POLYPHONY
	_event_player.volume_db = EVENT_DB
	add_child(_event_player)

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
	if not _streams.has(kind) and EventSoundsModel.JINGLES.has(kind):
		_make_jingle(kind)
	return _streams.get(kind, null)


## Jingles restant à faire, un par image après le démarrage.
func _process(_delta: float) -> void:
	for jingle in EventSoundsModel.JINGLES:
		if not _streams.has(jingle):
			_make_jingle(jingle)
			return
	set_process(false)


func _make_jingle(jingle: String) -> void:
	var custom_jingle = _try_load_custom(jingle)
	_streams[jingle] = custom_jingle if custom_jingle != null else _synthesize_jingle(jingle)


## Nom du son d'un flux de `stream` (« » s'il n'en vient pas) : sons du décor entendus (lot P30).
func kind_of(st: Resource) -> String:
	for k in _streams:
		if _streams[k] == st:
			return k
	return ""


## Joue un jingle d'événement (lot T17) ; nom inconnu : rien.
func play_event(jingle: String) -> void:
	if not EventSoundsModel.JINGLES.has(jingle):
		return
	var st: Resource = stream(jingle)
	events_played.append(jingle)
	_event_player.stream = st
	if is_inside_tree():
		_event_player.play()


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

	# Roues (lot V7)
	var wh: Dictionary = eval["wheel"]
	_wheel_player.volume_db = float(wh["volume_db"])
	_wheel_player.pitch_scale = float(wh["pitch"])
	if str(wh["kind"]) != "none":
		var stream = _streams.get("wheel_" + str(wh["kind"]), null)
		if _wheel_player.stream != stream:
			_wheel_player.stream = stream
	if is_inside_tree():
		if str(wh["kind"]) != "none" and float(wh["volume_db"]) > SoundModel.SILENCE_DB:
			if not _wheel_player.playing and _wheel_player.stream != null:
				_wheel_player.play()
		elif _wheel_player.playing:
			_wheel_player.stop()

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
			# Un son joué une fois (cloche : un coup par update_bells) n'est pas relancé dès qu'il se tait
			if is_inside_tree() and not player.playing and player.stream != null and kind not in ONE_SHOT_KINDS:
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
	var kinds := ["wind", "freewheel", "church_bell", "river", "livestock", "village", "vehicle_pass", "tractor_engine", "crowd_cheer",
		"helicopter_rotor", "airliner_rumble", "paramotor_buzz", "barge_engine", "ship_horn"]
	for k in kinds:
		var custom_stream = _try_load_custom(k)
		if custom_stream != null:
			_streams[k] = custom_stream
		else:
			_streams[k] = _synthesize_stream(k)
			if k in ONE_SHOT_KINDS:
				(_streams[k] as AudioStreamWAV).loop_mode = AudioStreamWAV.LOOP_DISABLED
	for k in VOICE_KINDS:
		var custom_voice = _try_load_custom(k)
		_streams[k] = custom_voice if custom_voice != null else _synthesize_voice(k)
	_streams["wheel_hum"] = _synthesize_wheel("hum")
	_streams["wheel_whistle"] = _synthesize_wheel("whistle")
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


## Sons en boucle d'une seconde, ou de NOISE_LOOP_S pour ceux qui contiennent du bruit (et sons joués une fois,
## ONE_SHOT_KINDS). Raccord sans clic : les
## fréquences et modulations font un nombre entier de cycles par boucle et les bruits filtrés sont
## périodiques (`_periodic_lowpass`), donc la fin de la boucle enchaîne exactement sur son début.
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

	# Sons à bruit : boucle de NOISE_LOOP_S à NOISE_MIX_RATE (un bruit figé d'une seconde se répétait et
	# s'entendait comme une pulsation régulière d'une seconde, mesure du 30/10) ; graine propre à chaque son.
	var noisy: bool = kind == "river" or NOISE_LOWPASS.has(kind)
	var rate := NOISE_MIX_RATE if noisy else MIX_RATE
	var n := int(NOISE_LOOP_S * rate) if noisy else SAMPLE_COUNT
	wav.mix_rate = rate
	wav.loop_end = n
	var noise: PackedFloat32Array = _lcg_noise(n, hash(kind) & 0x7FFFFFFF) if noisy else PackedFloat32Array()
	var lp := PackedFloat32Array()
	if NOISE_LOWPASS.has(kind):
		# Même fréquence de coupure qu'à MIX_RATE
		var alpha := 1.0 - pow(1.0 - float(NOISE_LOWPASS[kind]), float(MIX_RATE) / float(rate))
		lp = _periodic_lowpass(noise, alpha)
	var buf := PackedFloat32Array()
	buf.resize(n)
	for i in range(n):
		var t := float(i) / float(rate)
		var sample := 0.0

		match kind:
			"church_bell":
				# Tintement de cloche amorti avec partiels, joué une fois par coup (update_bells)
				sample = (sin(TAU * 440.0 * t) + 0.5 * sin(TAU * 880.0 * t) + 0.25 * sin(TAU * 1320.0 * t)) * exp(-t * 2.5) * 0.5
			"river":
				# Murmure d'eau vive (bruit doux, niveau constant)
				sample = (sin(TAU * 240.0 * t) * 0.4 + noise[i] * 0.3) * 0.8
			"livestock":
				# Sonnaille métallique : coups à des instants irréguliers (LIVESTOCK_STRIKES), amortis sur la boucle
				var env := 0.0
				for s in LIVESTOCK_STRIKES:
					env += float(s[1]) * exp(-fposmod(t - float(s[0]), 1.0) * 6.0)
				sample = (sin(TAU * 720.0 * t) + sin(TAU * 1150.0 * t)) * env * 0.4
			"village":
				# Rumeur de village
				sample = sin(TAU * 85.0 * t) * 0.3 + sin(TAU * 140.0 * t) * 0.2
			"vehicle_pass":
				# Lot P13 : roulement de pneus et souffle d'une voiture (bruit filtré, ronflement à 60 Hz) ;
				# l'effet Doppler vient de l'AudioStreamPlayer3D qui suit le véhicule.
				sample = lp[i] * 2.2 + sin(TAU * 60.0 * t) * 0.12
			"crowd_cheer":
				# Lot P15 : clameur (bruit filtré qui ondule) et applaudissements (claquements brefs à 9 Hz,
				# décalés par une phase tirée au hasard), joués par crowd_renderer.gd sur le groupe le plus proche
				var swell := 0.7 + 0.3 * sin(TAU * 2.0 * t) * sin(TAU * 3.0 * t)
				var clap_phase := fmod(t * 9.0 + 0.37 * sin(TAU * t), 1.0)
				var clap := exp(-clap_phase * 60.0) * noise[(i * 7919) % n]
				sample = lp[i] * 1.8 * swell + clap * 0.5
			"helicopter_rotor":
				# Lot P26 : battement des pales (6 coups par seconde, un nombre entier sur la boucle) sur un
				# sifflement de turbine
				var blade := pow(0.5 + 0.5 * cos(TAU * 6.0 * t), 6.0)
				sample = lp[i] * (0.25 + 1.6 * blade) + sin(TAU * 1900.0 * t) * 0.03
			"airliner_rumble":
				# Lot P26 : grondement lointain d'un avion de ligne (bruit très filtré ; il monte et descend avec la distance)
				sample = lp[i] * 4.0
			"paramotor_buzz":
				# Lot P31 : bourdonnement d'un paramoteur (deux-temps à 120 Hz et harmoniques, explosions à 60 Hz
				# dans un souffle d'hélice), nombres entiers de périodes sur la boucle
				var fire := pow(0.5 + 0.5 * cos(TAU * 60.0 * t), 4.0)
				sample = sin(TAU * 120.0 * t) * 0.22 + sin(TAU * 240.0 * t) * 0.16 + sin(TAU * 360.0 * t) * 0.08 + lp[i] * (0.2 + 0.6 * fire)
			"barge_engine":
				# Lot P29 : diesel lent d'une péniche (22 Hz et harmoniques, battement des cylindres à 5 Hz)
				var beat := 0.7 + 0.3 * pow(0.5 + 0.5 * sin(TAU * 5.0 * t), 2.0)
				sample = (sin(TAU * 22.0 * t) * 0.4 + sin(TAU * 44.0 * t) * 0.3 + sin(TAU * 66.0 * t) * 0.12 + lp[i] * 0.6) * beat
			"ship_horn":
				# Lot P29 : corne de brume d'un ferry, une fois (non bouclée) : 98 Hz et harmoniques, attaque et
				# fin adoucies
				var env := smoothstep(0.0, 0.12, t) * (1.0 - smoothstep(0.75, 1.0, t))
				sample = (sin(TAU * 98.0 * t) * 0.45 + sin(TAU * 196.0 * t) * 0.25 + sin(TAU * 294.0 * t) * 0.15
					+ sin(TAU * 392.0 * t) * 0.07) * env
			"tractor_engine":
				# Lot P13 : moteur grave du tracteur (28 Hz et harmoniques, battement des cylindres à 7 Hz)
				var beat := 0.75 + 0.25 * sin(TAU * 7.0 * t)
				sample = (sin(TAU * 28.0 * t) * 0.45 + sin(TAU * 56.0 * t) * 0.25 + sin(TAU * 84.0 * t) * 0.12) * beat
		buf[i] = sample

	if kind in ONE_SHOT_KINDS:
		# Son joué une fois : fin fondue en ONE_SHOT_TAIL_S, sans coupure sèche
		var tail := int(ONE_SHOT_TAIL_S * rate)
		for j in range(tail):
			buf[n - 1 - j] *= float(j) / float(tail)
	var bytes := PackedByteArray()
	bytes.resize(n * 2)
	for i in range(n):
		bytes.encode_s16(i * 2, clampi(int(buf[i] * 32767.0), -32768, 32767))
	wav.data = bytes
	return wav


## Bruit blanc de `n` échantillons (−1 à 1), générateur congruentiel de graine `seed_val` (même son à chaque lancement).
static func _lcg_noise(n: int, seed_val: int) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(n)
	for i in range(n):
		seed_val = (seed_val * 1103515245 + 12345) & 0x7FFFFFFF
		out[i] = float(seed_val & 0xFFFF) / 32768.0 - 1.0
	return out


## Passe-bas à un pôle (coefficient `alpha`) d'un bruit bouclé, en régime établi : le filtre fait d'abord un
## tour de boucle à vide, si bien que la sortie est elle-même périodique (fin raccordée au début, sans clic).
static func _periodic_lowpass(noise: PackedFloat32Array, alpha: float) -> PackedFloat32Array:
	var n := noise.size()
	var out := PackedFloat32Array()
	out.resize(n)
	var lp := 0.0
	for pass_i in range(2):
		for i in range(n):
			lp += alpha * (noise[i] - lp)
			out[i] = lp
	return out


## Vent (Lot P10, refait après la recette P16, puis le 28/10) : grondement grave (bruit blanc passé deux fois
## dans un passe-bas à WIND_RUMBLE_HZ) et souffle doux (passe-bande WIND_BAND_HZ, Q WIND_BAND_Q), de niveau
## constant, ramenés à WIND_RMS. Les filtres font d'abord un tour de boucle à vide sur le même bruit : la sortie
## est périodique et la boucle de WIND_LOOP_SAMPLES se raccorde exactement, sans fondu enchaîné. Ni fondu ni
## « respiration » à 0,5 Hz : tous deux revenaient toutes les 4 s et s'entendaient comme une vague.
static func _wind_noise_bytes() -> PackedByteArray:
	var n := WIND_LOOP_SAMPLES
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x77696e64
	var noise := PackedFloat32Array()
	noise.resize(n)
	for i in range(n):
		noise[i] = rng.randf() * 2.0 - 1.0
	var k_lp := 1.0 - exp(-TAU * WIND_RUMBLE_HZ / MIX_RATE)
	var w0 := TAU * WIND_BAND_HZ / MIX_RATE
	var alpha := sin(w0) / (2.0 * WIND_BAND_Q)
	var a0 := 1.0 + alpha
	var b0 := alpha / a0
	var a1 := -2.0 * cos(w0) / a0
	var a2 := (1.0 - alpha) / a0
	var rumble := PackedFloat32Array()
	var band := PackedFloat32Array()
	rumble.resize(n)
	band.resize(n)
	var lp1 := 0.0
	var lp2 := 0.0
	var x1 := 0.0
	var x2 := 0.0
	var y1 := 0.0
	var y2 := 0.0
	for pass_i in range(2):
		for i in range(n):
			var x := noise[i]
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
	buf.resize(n)
	var rms := 0.0
	for i in range(n):
		buf[i] = rumble[i] / rms_r + band[i] / rms_b * 0.45
		rms += buf[i] * buf[i]
	var gain := WIND_RMS / sqrt(rms / n)
	var bytes := PackedByteArray()
	bytes.resize(n * 2)
	for i in range(n):
		bytes.encode_s16(i * 2, clampi(int(buf[i] * gain * 32767.0), -32768, 32767))
	return bytes


## Son des roues (lot V7), boucle d'une seconde à nombre entier de périodes (raccord sans clic) : ronronnement
## grave de roue lenticulaire (110 Hz et harmoniques) ou sifflement léger de jante haute (1760 Hz).
static func _synthesize_wheel(kind: String) -> AudioStreamWAV:
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = MIX_RATE
	wav.stereo = false
	wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
	wav.loop_begin = 0
	wav.loop_end = SAMPLE_COUNT
	var bytes := PackedByteArray()
	bytes.resize(SAMPLE_COUNT * 2)
	for i in range(SAMPLE_COUNT):
		var t := float(i) / float(MIX_RATE)
		var v := 0.0
		if kind == "hum":
			v = 0.5 * sin(TAU * 110.0 * t) + 0.25 * sin(TAU * 220.0 * t) + 0.12 * sin(TAU * 330.0 * t)
		else:
			v = 0.4 * sin(TAU * 1760.0 * t) * (0.8 + 0.2 * sin(TAU * 6.0 * t))
		bytes.encode_s16(i * 2, clampi(int(v * 0.6 * 32767.0), -32768, 32767))
	wav.data = bytes
	return wav


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


## Jingle d'événement (lot T17) : somme des notes de `EventSoundsModel.JINGLES`. Timbre `tone` : attaque
## de 8 ms, fondamentale et harmoniques 2 et 3 (0,3 et 0,1), décroissance douce puis fondu de 30 ms ;
## timbre `bell` : partiels 1 ; 2,76 ; 5,40 (0,5 et 0,25) amortis en exp(−4 t / durée). Pic ramené à 0,8.
static func _synthesize_jingle(jingle: String) -> AudioStreamWAV:
	var notes: Array = EventSoundsModel.JINGLES[jingle]
	var n := int(ceil(EventSoundsModel.duration_s(jingle) * MIX_RATE)) + 1
	var out := PackedFloat32Array()
	out.resize(n)
	var peak := 0.0
	for note in notes:
		var i0 := int(float(note[0]) * MIX_RATE)
		var dur := float(note[2])
		var m := mini(int(dur * MIX_RATE), n - i0)
		var f := float(note[1])
		var level := float(note[3])
		var bell: bool = note[4] == "bell"
		for j in range(m):
			var t := float(j) / MIX_RATE
			var v := 0.0
			if bell:
				v = (sin(TAU * f * t) + 0.5 * sin(TAU * f * 2.76 * t) + 0.25 * sin(TAU * f * 5.4 * t)) \
						* exp(-4.0 * t / dur) * minf(1.0, t / 0.002)
			else:
				var env := minf(1.0, t / 0.008) * minf(1.0, (dur - t) / 0.03) * exp(-1.5 * t / dur)
				v = (sin(TAU * f * t) + 0.3 * sin(TAU * 2.0 * f * t) + 0.1 * sin(TAU * 3.0 * f * t)) * env
			out[i0 + j] += v * level
	for i in range(n):
		peak = maxf(peak, absf(out[i]))
	var gain := 0.8 / maxf(peak, 1e-6)
	var bytes := PackedByteArray()
	bytes.resize(n * 2)
	for i in range(n):
		bytes.encode_s16(i * 2, clampi(int(out[i] * gain * 32767.0), -32768, 32767))
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
## entier de cycles par boucle, bruits filtrés périodiques (`_periodic_lowpass`), chants et
## gouttes qui débordent de la fin reprennent au début ; motifs tirés d'un générateur déterministe (même son
## à chaque lancement). Aucun fondu au silence aux bords : il s'entendait comme un « tac » toutes les 2 s.
## Niveaux constants (29/10) : les ondulations de 0,5 à 1,5 Hz (vent d'altitude, eau, rumeur) s'entendaient comme
## une vague, même à l'arrêt ; le niveau ne varie que par AmbienceModel (altitude, vent, voisinage).
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
						var u := float(i) / float(len)
						ph += TAU * lerpf(f0, f1, u) / MIX_RATE
						buf[(start + i) % n] += sin(ph) * sin(PI * u) * amp
				t0 += rng.randf_range(0.25, 0.6)
		"field_insects":
			# Stridulation : porteuse de 4,6 kHz hachée à 30 Hz, par salves de 0,4 s (bords sur des zéros)
			for i in range(n):
				var t := float(i) / MIX_RATE
				var burst := 1.0 if fmod(t, 0.5) < 0.4 else 0.0
				var chop := maxf(sin(TAU * 30.0 * t), 0.0)
				buf[i] = sin(TAU * 4600.0 * t) * chop * burst * 0.25
		"water_flow", "village_murmur", "high_wind", "rain":
			# Bruits filtrés passe-bas (un pôle), plus ou moins sourds
			var alpha: float = {"water_flow": 0.18, "village_murmur": 0.04, "high_wind": 0.02, "rain": 0.6}[bed]
			var noise := PackedFloat32Array()
			noise.resize(n)
			for i in range(n):
				noise[i] = rng.randf() * 2.0 - 1.0
			var lp := _periodic_lowpass(noise, alpha)
			for i in range(n):
				var t := float(i) / MIX_RATE
				var v := lp[i]
				match bed:
					"water_flow":
						v = lp[i] * 1.3
					"village_murmur":
						v = lp[i] * 2.5 + sin(TAU * 110.0 * t) * 0.025
					"high_wind":
						v = lp[i] * 2.6
					"rain":
						v = (noise[i] - lp[i]) * 0.35
				buf[i] = v
			if bed == "rain":
				for d in range(40):   # gouttes
					var at := rng.randi_range(0, n - 1)
					for i in range(300):
						buf[(at + i) % n] += sin(TAU * 1800.0 * i / MIX_RATE) * exp(-float(i) / 40.0) * 0.3
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
