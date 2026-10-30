extends SceneTree

## Mesure des bruitages et de la musique du Cyber-Rogue (lot X51, principe « doux d'abord » du lot R18) : aucun son
## plus fort que le vent à haute vitesse, aux volumes par défaut, et aucun son aigu et strident (part d'énergie
## au-dessus de 4 kHz bornée). Ce que l'oreille garde pour la recette : la douceur ressentie, sur la page
## d'écoute (tests/rogue_ecoute.py). Lancement :
## godot --headless --path engine --script res://tests/unit/test_rogue_sound_levels.gd

const Synth := preload("res://scripts/rogue/rogue_sound_synth.gd")
const Model := preload("res://scripts/rogue/rogue_sound_model.gd")
const SoundModel := preload("res://scripts/sound_model.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")

const WINDOW_S := 0.1               # niveau court terme : la fenêtre de 100 ms la plus forte
const HIGH_HZ := 4000.0
const HIGH_SHARE_MAX := 0.10        # au plus 10 % de l'énergie au-dessus de 4 kHz

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


## Niveau de la fenêtre de 100 ms la plus forte (dB efficaces, 0 dB = sinus plein niveau × √2).
static func short_term_db(b: PackedFloat32Array, rate: int) -> float:
	var w := maxi(int(WINDOW_S * rate), 1)
	var acc := 0.0
	var best := 0.0
	for i in range(b.size()):
		acc += b[i] * b[i]
		if i >= w:
			acc -= b[i - w] * b[i - w]
		best = maxf(best, acc)
	var n := mini(w, b.size())
	return linear_to_db(sqrt(maxf(best, 0.0) / maxf(n, 1))) if best > 0.0 else -120.0


## Part de l'énergie au-dessus de HIGH_HZ : passe-haut du 2e ordre (biquad RBJ, Q 0,707), deux passes.
static func high_share(b: PackedFloat32Array, rate: int) -> float:
	var y := b
	for _pass in range(2):
		y = _highpass(y, rate)
	var e := 0.0
	var eh := 0.0
	for i in range(b.size()):
		e += b[i] * b[i]
		eh += y[i] * y[i]
	return eh / e if e > 0.0 else 0.0


static func _highpass(x: PackedFloat32Array, rate: int) -> PackedFloat32Array:
	var w0 := TAU * HIGH_HZ / rate
	var alpha := sin(w0) / (2.0 * 0.7071)
	var c := cos(w0)
	var a0 := 1.0 + alpha
	var b0 := (1.0 + c) / 2.0 / a0
	var b1 := -(1.0 + c) / a0
	var a1 := -2.0 * c / a0
	var a2 := (1.0 - alpha) / a0
	var out := PackedFloat32Array()
	out.resize(x.size())
	var x1 := 0.0
	var x2 := 0.0
	var y1 := 0.0
	var y2 := 0.0
	for i in range(x.size()):
		var v := b0 * x[i] + b1 * x1 + b0 * x2 - a1 * y1 - a2 * y2
		x2 = x1
		x1 = x[i]
		y2 = y1
		y1 = v
		out[i] = v
	return out


static func pcm16_to_float(bytes: PackedByteArray) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(bytes.size() / 2)
	for i in range(out.size()):
		out[i] = bytes.decode_s16(2 * i) / 32768.0
	return out


## Gain de lecture d'un son du mode aux réglages par défaut : niveau du mode, bus RogueSfx (70 %), niveau des boucles.
static func play_gain_db(sound: String) -> float:
	var bus := AudioMix.pct_to_db(int(AudioMix.ROGUE_DEFAULTS[AudioMix.ROGUE_SFX])) + Model.MODE_DB
	if sound == "rogue_overheat":
		return bus + Model.OVERHEAT_DB
	if sound == "rogue_firewall_hum":
		return bus + Model.HUM_MAX_DB
	return bus


func _run() -> void:
	var wind := pcm16_to_float(SoundPlayer._wind_noise_bytes())
	var wind_db := short_term_db(wind, SoundPlayer.MIX_RATE) + SoundModel.WIND_MAX_DB   # bus Ride à 100 %
	print("vent à %d km/h : %.1f dB" % [int(SoundModel.WIND_MAX_KMH), wind_db])
	var loud: Array = []
	var shrill: Array = []
	for sound in Synth.names():
		var b: PackedFloat32Array = Synth.render(sound)
		var db := short_term_db(b, Synth.RATE) + play_gain_db(sound)
		var hs := high_share(b, Synth.RATE)
		print("  %-22s %6.1f dB  aigus %4.1f %%" % [sound, db, 100.0 * hs])
		if db > wind_db:
			loud.append("%s %.1f dB" % [sound, db])
		if hs > HIGH_SHARE_MAX:
			shrill.append("%s %.0f %%" % [sound, 100.0 * hs])
	var music_bus := AudioMix.pct_to_db(int(AudioMix.ROGUE_DEFAULTS[AudioMix.ROGUE_MUSIC])) + Model.MODE_DB
	var mix := PackedFloat32Array()
	for layer in Synth.MUSIC_LAYERS:
		var m: PackedFloat32Array = Synth.render_music(layer)
		if mix.is_empty():
			mix.resize(m.size())
		for i in range(mini(m.size(), mix.size())):
			mix[i] += m[i]
		var hs := high_share(m, Synth.RATE)
		print("  musique %-14s aigus %4.1f %%" % [layer, 100.0 * hs])
		if hs > HIGH_SHARE_MAX:
			shrill.append("musique %s %.0f %%" % [layer, 100.0 * hs])
	var music_db := short_term_db(mix, Synth.RATE) + music_bus
	print("  musique (3 couches)    %6.1f dB" % music_db)
	if music_db > wind_db:
		loud.append("musique %.1f dB" % music_db)
	_check(loud.is_empty(), "aucun son plus fort que le vent à %d km/h (%.1f dB) aux volumes par défaut%s"
			% [int(SoundModel.WIND_MAX_KMH), wind_db, "" if loud.is_empty() else " : " + ", ".join(loud)])
	_check(shrill.is_empty(), "aucun son strident : au plus %d %% de l'énergie au-dessus de %d Hz%s"
			% [int(100 * HIGH_SHARE_MAX), int(HIGH_HZ), "" if shrill.is_empty() else " : " + ", ".join(shrill)])
	# Les mesures elles-mêmes : un sinus aigu est jugé strident, un bruit grave non ; le niveau d'un sinus est connu.
	var sine := PackedFloat32Array()
	var low := PackedFloat32Array()
	sine.resize(Synth.RATE / 2)
	low.resize(Synth.RATE / 2)
	for i in range(sine.size()):
		sine[i] = 0.5 * sin(TAU * 6000.0 * i / Synth.RATE)
		low[i] = 0.5 * sin(TAU * 220.0 * i / Synth.RATE)
	_check(high_share(sine, Synth.RATE) > 0.8 and high_share(low, Synth.RATE) < 0.01,
			"mesure des aigus : sinus 6 kHz aigu, 220 Hz grave")
	_check(absf(short_term_db(low, Synth.RATE) - linear_to_db(0.5 / sqrt(2.0))) < 0.2, "mesure du niveau d'un sinus")
	print("test_rogue_sound_levels : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
