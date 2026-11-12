extends Node

## Bruitages et musique du Cyber-Rogue (lot R18) : joue sur les bus `RogueSfx` et `RogueMusic` (volumes de
## audio_mix.gd) ce que décide rogue_sound_model.gd. Huit lecteurs pour les sons de jeu, deux pour les boucles
## (surchauffe, ronflement du Firewall) et trois pour les couches de musique. Les flux sont synthétisés à la
## première utilisation (rogue_sound_synth.gd) ; `~/OpenRide/Sounds/<nom>.ogg` remplace le son du même nom.
## Préchauffage (2 novembre) : la synthèse (~0,7 s) tourne sur un fil de WorkerThreadPool au lieu du fil
## principal, qui gelait au départ du mode ; sons et musique arrivent dès qu'elle est finie (une fraction de
## seconde), les sons demandés avant sont notés dans `plays` mais pas joués.
## Les sons de vent et de roue libre restent à sound_player.gd et continuent dans le mode.

const AudioMix := preload("res://scripts/audio_mix.gd")
const Synth := preload("res://scripts/rogue/rogue_sound_synth.gd")
const Model := preload("res://scripts/rogue/rogue_sound_model.gd")
const BgTasks := preload("res://scripts/bg_tasks.gd")

const BEAT_HZ := 2.0

var model = Model.new()
var streams: Dictionary = {}         # nom -> AudioStream
var voices: Array[AudioStreamPlayer] = []
var overheat_player: AudioStreamPlayer
var hum_player: AudioStreamPlayer
var music_players: Dictionary = {}   # couche -> AudioStreamPlayer
var plays: Array = []                # sons demandés (tests)
var synth_ms := 0.0                  # durée de la synthèse des sons (mesure)
var _voice_next := 0
var _beat_t := 0.0
var music_ms := 0.0                  # durée de la synthèse de la musique (mesure)
var _ready_streams := false
var threaded := true                 # false : synthèse sur le fil principal (tests)
var _task_id := -1                   # tâche de synthèse en cours, -1 sans tâche
var _rendered: Dictionary = {}       # rempli par la tâche : nom ou couche -> PackedByteArray PCM 16 bits
var _customs: Dictionary = {}        # nom -> flux .ogg de l'utilisateur (chargés sur le fil principal)


func _ready() -> void:
	for _i in Model.MAX_VOICES:
		var p := AudioStreamPlayer.new()
		p.bus = AudioMix.bus(AudioMix.ROGUE_SFX)
		add_child(p)
		voices.append(p)
	overheat_player = _loop_player()
	hum_player = _loop_player()
	for layer in Synth.MUSIC_LAYERS:
		var mp := AudioStreamPlayer.new()
		mp.bus = AudioMix.bus(AudioMix.ROGUE_MUSIC)
		mp.volume_db = Model.SILENCE_DB
		add_child(mp)
		music_players[layer] = mp


func _loop_player() -> AudioStreamPlayer:
	var p := AudioStreamPlayer.new()
	p.bus = AudioMix.bus(AudioMix.ROGUE_SFX)
	p.volume_db = Model.SILENCE_DB
	add_child(p)
	return p


## Synthèse des sons de jeu et de la musique (une fois, au premier état du mode). Avec `threaded`, elle part sur un
## fil de travail et `_process` installe les flux quand elle est finie ; sinon tout est fait tout de suite.
func prepare() -> void:
	if _ready_streams or _task_id >= 0:
		return
	for sound in Synth.names():
		var custom = _try_load_custom(sound)
		if custom != null:
			_customs[sound] = custom
	if threaded:
		_task_id = BgTasks.add(_render_all, false, "Synthèse des sons du Cyber-Rogue")
	else:
		_render_all()
		_install()


## Sur le fil de travail : fonctions statiques pures de rogue_sound_synth.gd, aucun nœud touché.
func _render_all() -> void:
	var out := {}
	var t0 := Time.get_ticks_usec()
	for sound in Synth.names():
		if not _customs.has(sound):
			out[sound] = Synth.to_pcm16(Synth.render(sound))
	var t1 := Time.get_ticks_usec()
	for layer in Synth.MUSIC_LAYERS:
		out["music:" + layer] = Synth.to_pcm16(Synth.render_music(layer))
	synth_ms = float(t1 - t0) / 1000.0
	music_ms = float(Time.get_ticks_usec() - t1) / 1000.0
	_rendered = out


## Sur le fil principal : flux WAV, boucles et musique (démarrée d'un coup pour que les couches restent alignées).
func _install() -> void:
	_ready_streams = true
	for sound in Synth.names():
		streams[sound] = _customs[sound] if _customs.has(sound) \
				else _wav(_rendered[sound], Synth.is_loop(sound))
	overheat_player.stream = streams["rogue_overheat"]
	hum_player.stream = streams["rogue_firewall_hum"]
	for layer in Synth.MUSIC_LAYERS:
		var mp: AudioStreamPlayer = music_players[layer]
		mp.stream = _wav(_rendered["music:" + layer], true)
		mp.volume_db = Model.SILENCE_DB
		if is_inside_tree():
			mp.play()
	_rendered = {}


## Vrai quand sons et musique sont prêts (tests).
func streams_ready() -> bool:
	return _ready_streams


## Attend la fin de la synthèse et installe les flux (tests, sortie du mode).
func finish_now() -> void:
	if _task_id >= 0:
		BgTasks.wait(_task_id)
		_task_id = -1
		_install()


func _poll_task() -> void:
	if _task_id >= 0 and BgTasks.done(_task_id):
		finish_now()


func _exit_tree() -> void:
	if _task_id >= 0:
		BgTasks.wait(_task_id)
		_task_id = -1


func _wav(pcm: PackedByteArray, loop: bool) -> AudioStreamWAV:
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = Synth.RATE
	wav.stereo = false
	wav.data = pcm
	if loop:
		wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
		wav.loop_begin = 0
		wav.loop_end = pcm.size() / 2
	return wav


func _try_load_custom(sound: String) -> Resource:
	var home := OS.get_environment("HOME")
	if home.is_empty():
		home = OS.get_environment("USERPROFILE")
	if home.is_empty():
		return null
	var path := home.path_join("OpenRide").path_join("Sounds").path_join(sound + ".ogg")
	return AudioStreamOggVorbis.load_from_file(path) if FileAccess.file_exists(path) else null


func on_loot(msg: Dictionary, now_s: float) -> void:
	model.on_loot(msg, now_s)


## Trame `state` du mode : `rogue` (ou null), `gear`, `seq`, instant `now_s` en secondes, `result` du bilan.
func on_state(rogue: Variant, gear: int, seq: int, now_s: float, result: String = "") -> void:
	if typeof(rogue) == TYPE_DICTIONARY:
		prepare()
	model.update(rogue, gear, seq, now_s, result)
	for sound in model.take_plays():
		_play(sound)


func _play(sound: String) -> void:
	plays.append(sound)
	if not streams.has(sound):
		return
	var p := voices[_voice_next]
	_voice_next = (_voice_next + 1) % voices.size()
	p.stream = streams[sound]
	p.volume_db = Model.MODE_DB
	if is_inside_tree():
		p.play()


## Appelé à chaque image : volume des boucles (battement de l'alarme à 2 Hz) et couches de musique.
func _process(delta: float) -> void:
	_poll_task()
	if not _ready_streams:
		return
	var loops: Dictionary = model.loops()
	_beat_t += delta
	var beat_db := 0.0
	if bool(loops["beat"]):
		beat_db = -6.0 * (0.5 - 0.5 * cos(TAU * BEAT_HZ * _beat_t))
	_set_loop(overheat_player, float(loops["overheat_db"]))
	_set_loop(hum_player, float(loops["hum_db"]) + beat_db)
	var levels: Dictionary = model.music()
	for layer in Synth.MUSIC_LAYERS:
		var lv := float(levels[layer])
		music_players[layer].volume_db = Model.SILENCE_DB if lv <= 0.001 else linear_to_db(lv) + Model.MODE_DB


func _set_loop(p: AudioStreamPlayer, db: float) -> void:
	if p.stream == null:
		return
	p.volume_db = db + Model.MODE_DB
	if db > Model.SILENCE_DB + 0.5 and not p.playing and is_inside_tree():
		p.play()
	elif db <= Model.SILENCE_DB + 0.5 and p.playing:
		p.stop()
