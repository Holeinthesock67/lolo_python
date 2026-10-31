extends SceneTree

## Export des sons du Cyber-Rogue pour la page d'écoute (lot X51) : chaque bruitage et la musique au niveau où
## le mode les joue (réglages par défaut), le vent de référence à 30 et 60 km/h, et une scène de salle de 20 s
## (vent à 35 km/h, deux couches de musique, bruitages d'une salle). Fichiers WAV mono 16 bits dans le dossier
## donné après `--`. Lancé par tests/rogue_ecoute.py :
## godot --headless --path engine --script res://tests/rogue_sound_export.gd -- DOSSIER

const Synth := preload("res://scripts/rogue/rogue_sound_synth.gd")
const Model := preload("res://scripts/rogue/rogue_sound_model.gd")
const SoundModel := preload("res://scripts/sound_model.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")
const Levels := preload("res://tests/unit/test_rogue_sound_levels.gd")

const SCENE_S := 20.0
const SCENE_WIND_KMH := 35.0
## Bruitages de la scène de salle : (instant en s, son).
const SCENE_EVENTS := [
	[1.0, "rogue_shift_tick"], [1.6, "rogue_shift_tick"], [2.5, "rogue_perfect_shift"], [4.0, "rogue_hit"],
	[5.5, "rogue_shield_hit"], [6.5, "rogue_hack"], [8.0, "rogue_parry"], [9.5, "rogue_hit"], [10.2, "rogue_crit"],
	[12.0, "rogue_parry_miss"], [13.5, "rogue_gold"], [15.0, "rogue_room_won"], [17.0, "rogue_card_pick"],
	[18.0, "rogue_door"],
]


func _init() -> void:
	call_deferred("_run")


func _save(path: String, samples: PackedFloat32Array, rate: int) -> void:
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = rate
	wav.stereo = false
	wav.data = Synth.to_pcm16(samples)
	wav.save_to_wav(path)


func _gain(b: PackedFloat32Array, db: float) -> PackedFloat32Array:
	var g := db_to_linear(db)
	var out := b.duplicate()
	for i in range(out.size()):
		out[i] *= g
	return out


## Vent au rythme du jeu (22 050 Hz) : la boucle de sound_player.gd au niveau de sound_model.gd pour `kmh`.
func _wind(kmh: float, seconds: float) -> PackedFloat32Array:
	var loop := Levels.pcm16_to_float(SoundPlayer._wind_noise_bytes())
	var db := SoundModel.WIND_MAX_DB + 20.0 * SoundModel.WIND_LOG_K * log(kmh / SoundModel.WIND_MAX_KMH) / log(10.0)
	var out := PackedFloat32Array()
	out.resize(int(seconds * Synth.RATE))
	for i in range(out.size()):
		out[i] = loop[i % loop.size()]
	return _gain(out, db)


## Couches de musique mêlées avec les poids d'une phase (rogue_sound_model.gd), crête des couches gardée.
func _music_mix(phase: String) -> PackedFloat32Array:
	var w: Dictionary = Model.MUSIC_BY_PHASE[phase]
	var mix := PackedFloat32Array()
	for layer in Synth.MUSIC_LAYERS:
		var m: PackedFloat32Array = Synth.render_music(layer)
		if mix.is_empty():
			mix.resize(m.size())
		for i in range(mini(m.size(), mix.size())):
			mix[i] += m[i] * float(w.get(layer, 0.0))
	return mix


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		printerr("dossier de sortie attendu après --")
		quit(2)
		return
	var dir: String = args[0]
	DirAccess.make_dir_recursive_absolute(dir)
	var rate := Synth.RATE
	for sound in Synth.names():
		var b: PackedFloat32Array = Synth.render(sound)
		if Synth.is_loop(sound):          # boucle : trois tours, pour l'entendre durer
			var once := b
			b = PackedFloat32Array()
			for _k in 3:
				b.append_array(once)
		_save("%s/%s.wav" % [dir, sound], _gain(b, Levels.play_gain_db(sound)), rate)
	var music_db := AudioMix.pct_to_db(int(AudioMix.ROGUE_DEFAULTS[AudioMix.ROGUE_MUSIC])) + Model.MODE_DB
	var mix := _music_mix("BOSS")
	var two := _music_mix("ROOM")
	_save("%s/musique_boss.wav" % dir, _gain(mix, music_db), rate)
	_save("%s/vent_30.wav" % dir, _wind(30.0, 4.0), rate)
	_save("%s/vent_60.wav" % dir, _wind(60.0, 4.0), rate)
	# Scène de salle : vent, deux couches de musique, bruitages aux instants de SCENE_EVENTS.
	var scene := _wind(SCENE_WIND_KMH, SCENE_S)
	var g_music := db_to_linear(music_db)
	for i in range(scene.size()):
		scene[i] += two[i % two.size()] * g_music
	for ev in SCENE_EVENTS:
		var b := _gain(Synth.render(String(ev[1])), Levels.play_gain_db(String(ev[1])))
		var i0 := int(float(ev[0]) * rate)
		for j in range(mini(b.size(), scene.size() - i0)):
			scene[i0 + j] += b[j]
	for i in range(scene.size()):
		scene[i] = clampf(scene[i], -1.0, 1.0)
	_save("%s/scene_salle.wav" % dir, scene, rate)
	print("export : %d fichiers dans %s" % [Synth.names().size() + 4, dir])
	quit(0)
