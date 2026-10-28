extends RefCounted

## Formes d'onde des bruitages et de la musique du Cyber-Rogue (lot R18) : synthèse monophonique à 22 050 Hz, sans
## aucun fichier audio. Sons doux d'abord (recette P16) : sinus et triangles filtrés, bruit passé dans un
## passe-bas, aucun son aigu et strident, crête à 0,6 (−4,4 dBFS). Palette commune avec les jingles de
## event_sounds_model.gd (gamme de do majeur) pour les fanfares, graves et médiums pour les impacts.
## Pas de class_name : preload("res://scripts/rogue/rogue_sound_synth.gd").

const RATE := 22050
const PEAK := 0.6
const TEMPO_BPM := 96.0
const MUSIC_BARS := 8
const BEATS_PER_BAR := 4
## Progression de la boucle (une note fondamentale par mesure, en Hz) : la mineur, fa, do, sol, deux mesures chacun.
const MUSIC_ROOTS := [110.0, 110.0, 87.31, 87.31, 130.81, 130.81, 98.0, 98.0]
const MUSIC_LAYERS := ["bass", "pulse", "arp"]

## Nom du son -> [durée en secondes, en boucle].
const SOUNDS := {
	"rogue_shift_tick": [0.04, false],
	"rogue_perfect_shift": [0.25, false],
	"rogue_hit": [0.15, false],
	"rogue_crit": [0.28, false],
	"rogue_parry": [0.30, false],
	"rogue_parry_miss": [0.22, false],
	"rogue_shield_hit": [0.12, false],
	"rogue_overheat": [1.0, true],
	"rogue_firewall_hum": [2.0, true],
	"rogue_hack": [0.40, false],
	"rogue_purge": [0.35, false],
	"rogue_card_pick": [0.15, false],
	"rogue_door": [0.30, false],
	"rogue_reroll": [0.20, false],
	"rogue_room_won": [0.60, false],
	"rogue_room_fled": [0.50, false],
	"rogue_room_skipped": [0.45, false],
	"rogue_gold": [0.08, false],
	"rogue_boss_phase": [0.90, false],
	"rogue_boss_won": [1.80, false],
	"rogue_defeat": [2.0, false],
	"rogue_recovery_end": [0.30, false],
	"rogue_chest": [0.90, false],
	"rogue_result": [1.20, false],
	"rogue_result_lost": [1.20, false],
}

const C5 := 523.25
const D5 := 587.33
const E5 := 659.25
const G5 := 783.99
const A5 := 880.0
const C6 := 1046.5


static func names() -> Array:
	return SOUNDS.keys()


static func duration_s(sound: String) -> float:
	return float(SOUNDS[sound][0])


static func is_loop(sound: String) -> bool:
	return bool(SOUNDS[sound][1])


static func bar_duration_s() -> float:
	return 60.0 / TEMPO_BPM * BEATS_PER_BAR


static func music_duration_s() -> float:
	return bar_duration_s() * MUSIC_BARS


static func _buf(duration: float) -> PackedFloat32Array:
	var b := PackedFloat32Array()
	b.resize(int(round(duration * RATE)))
	return b


## Note de sinus qui glisse de f0 à f1 (Hz), attaque de 5 ms, fondu final de 15 ms, décroissance exp(−decay·t/dur),
## deuxième harmonique `harm`. Ajoutée dans `b` à partir de `start` secondes.
static func _note(b: PackedFloat32Array, start: float, f0: float, f1: float, duration: float, level: float,
		decay: float = 3.0, harm: float = 0.0) -> void:
	var i0 := int(start * RATE)
	var n := mini(int(duration * RATE), b.size() - i0)
	var ph := 0.0
	for j in n:
		var t := float(j) / RATE
		var k := t / duration
		var f := f0 * pow(f1 / f0, k)
		ph += TAU * f / RATE
		var env := minf(1.0, t / 0.005) * minf(1.0, (duration - t) / 0.015) * exp(-decay * k)
		b[i0 + j] += (sin(ph) + harm * sin(2.0 * ph)) * env * level


## Éclat de bruit déterministe passé dans un passe-bas à un pôle (`alpha` de 0 à 1 : plus petit = plus sourd).
static func _noise(b: PackedFloat32Array, start: float, duration: float, level: float, alpha: float,
		decay: float = 4.0, seed_value: int = 12345) -> void:
	var i0 := int(start * RATE)
	var n := mini(int(duration * RATE), b.size() - i0)
	var s := seed_value
	var lp := 0.0
	for j in n:
		s = (s * 1103515245 + 12345) & 0x7fffffff
		var white := float(s) / 1073741823.5 - 1.0
		lp += alpha * (white - lp)
		var t := float(j) / RATE
		var k := t / duration
		var env := minf(1.0, t / 0.002) * minf(1.0, (duration - t) / 0.01) * exp(-decay * k)
		b[i0 + j] += lp * env * level * 3.0


static func _normalize(b: PackedFloat32Array) -> PackedFloat32Array:
	var peak := 0.0
	for v in b:
		peak = maxf(peak, absf(v))
	if peak > 1e-6:
		var g := PEAK / peak
		for i in b.size():
			b[i] *= g
	return b


## Forme d'onde d'un son de la table SOUNDS (flottants, crête PEAK).
static func render(sound: String) -> PackedFloat32Array:
	var b := _buf(duration_s(sound))
	match sound:
		"rogue_shift_tick":
			_note(b, 0.0, 1200.0, 1200.0, 0.04, 0.3, 6.0)
		"rogue_perfect_shift":
			_note(b, 0.0, C5, C5, 0.13, 0.7, 3.0, 0.25)
			_note(b, 0.10, G5, G5, 0.15, 0.7, 4.0, 0.25)
		"rogue_hit":
			_note(b, 0.0, 180.0, 70.0, 0.15, 1.0, 3.0)
			_noise(b, 0.0, 0.02, 0.4, 0.3, 4.0)
		"rogue_crit":
			_note(b, 0.0, 200.0, 60.0, 0.28, 1.0, 3.0, 0.2)
			_noise(b, 0.0, 0.03, 0.4, 0.3, 4.0)
			_note(b, 0.05, 880.0, 880.0, 0.10, 0.3, 4.0)
		"rogue_parry":
			_note(b, 0.0, 660.0, 660.0, 0.30, 0.5, 6.0)
			_note(b, 0.0, 1017.0, 1017.0, 0.30, 0.4, 7.0)
			_note(b, 0.0, 1580.0, 1580.0, 0.30, 0.25, 8.0)
		"rogue_parry_miss":
			_note(b, 0.0, 160.0, 80.0, 0.22, 1.0, 3.0)
		"rogue_shield_hit":
			_noise(b, 0.0, 0.12, 0.5, 0.15, 4.0)
			_note(b, 0.0, 110.0, 110.0, 0.06, 0.6, 3.0)
		"rogue_overheat":
			_noise(b, 0.0, 1.0, 0.5, 0.2, 0.0)
			for i in b.size():
				b[i] *= 0.5 - 0.5 * cos(TAU * float(i) / b.size())
		"rogue_firewall_hum":
			for i in b.size():
				var t := float(i) / RATE
				b[i] = (sin(TAU * 50.0 * t) + 0.5 * sin(TAU * 100.0 * t)) * (1.0 + 0.3 * sin(TAU * 0.5 * t))
		"rogue_hack":
			for q in 4:
				_noise(b, 0.1 * q, 0.06, 0.6, 0.5, 3.0, 777 + q)
		"rogue_purge":
			_note(b, 0.0, 1200.0, 300.0, 0.20, 0.6, 1.0)
			_note(b, 0.20, G5, G5, 0.15, 0.7, 4.0)
		"rogue_card_pick":
			_note(b, 0.0, E5, E5, 0.06, 0.6, 2.0)
			_note(b, 0.07, A5, A5, 0.08, 0.6, 3.0)
		"rogue_door":
			_note(b, 0.0, 80.0, 160.0, 0.30, 0.8, -1.5)
			_noise(b, 0.0, 0.30, 0.2, 0.08, -1.5)
		"rogue_reroll":
			for q in 3:
				_noise(b, 0.06 * q, 0.015, 0.5, 0.6, 2.0, 99 + q)
		"rogue_room_won":
			_note(b, 0.0, C5, C5, 0.20, 0.6, 3.0, 0.2)
			_note(b, 0.15, E5, E5, 0.20, 0.6, 3.0, 0.2)
			_note(b, 0.30, G5, G5, 0.30, 0.7, 3.0, 0.2)
		"rogue_room_fled":
			_note(b, 0.0, 392.0, 392.0, 0.50, 0.7, 5.0, 0.3)
		"rogue_room_skipped":
			_note(b, 0.0, 392.0, 392.0, 0.20, 0.7, 6.0, 0.1)
			_note(b, 0.20, 294.0, 294.0, 0.25, 0.7, 6.0, 0.1)
		"rogue_gold":
			_note(b, 0.0, 1319.0, 1319.0, 0.08, 0.5, 5.0)
		"rogue_boss_phase":
			_note(b, 0.0, 98.0, 98.0, 0.90, 0.6, 1.5, 0.3)
			_note(b, 0.25, 147.0, 147.0, 0.65, 0.5, 1.5, 0.3)
			_note(b, 0.50, 196.0, 196.0, 0.40, 0.5, 1.5, 0.3)
		"rogue_boss_won":
			_note(b, 0.0, C5, C5, 0.35, 0.6, 2.0, 0.25)
			_note(b, 0.35, E5, E5, 0.35, 0.6, 2.0, 0.25)
			_note(b, 0.70, G5, G5, 0.35, 0.6, 2.0, 0.25)
			_note(b, 1.05, C6, C6, 0.75, 0.7, 3.0, 0.25)
		"rogue_defeat":
			_note(b, 0.0, 220.0, 55.0, 2.0, 0.8, 2.0, 0.3)
		"rogue_recovery_end":
			_note(b, 0.0, E5, E5, 0.30, 0.6, 4.0)
		"rogue_chest":
			var fan := [C5, D5, E5, G5, A5, C6]
			for q in fan.size():
				_note(b, 0.1 * q, fan[q], fan[q], 0.4 if q == fan.size() - 1 else 0.3, 0.5, 3.0, 0.15)
		"rogue_result":
			_note(b, 0.0, C5, C5, 1.2, 0.4, 2.5, 0.2)
			_note(b, 0.0, E5, E5, 1.2, 0.4, 2.5, 0.2)
			_note(b, 0.0, G5, G5, 1.2, 0.4, 2.5, 0.2)
		"rogue_result_lost":
			_note(b, 0.0, 220.0, 220.0, 1.2, 0.8, 2.0, 0.3)
	return _normalize(b)


## Une couche de la musique (« bass », « pulse » ou « arp ») : 8 mesures à 96 bpm, boucle sans coupure
## (chaque note s'éteint avant la mesure suivante). Les quatre accords sont rendus une fois et recopiés.
static func render_music(layer: String) -> PackedFloat32Array:
	var beat := 60.0 / TEMPO_BPM
	var bars: Dictionary = {}
	var out := PackedFloat32Array()
	for bar in MUSIC_BARS:
		var root: float = MUSIC_ROOTS[bar]
		if not bars.has(root):
			var b := _buf(bar_duration_s())
			match layer:
				"bass":
					_note(b, 0.0, root, root, beat * 2.0 - 0.02, 0.6, 1.2, 0.3)
					_note(b, beat * 2.0, root, root, beat * 2.0 - 0.02, 0.5, 1.2, 0.3)
				"pulse":
					for q in BEATS_PER_BAR:
						_note(b, beat * q, root * 2.0, root * 2.0, 0.12, 0.4, 5.0)
				"arp":
					var steps := [1.0, 1.5, 2.0, 3.0]
					for q in BEATS_PER_BAR * 2:
						_note(b, beat * 0.5 * q, root * 2.0 * steps[q % 4], root * 2.0 * steps[q % 4], beat * 0.5 - 0.02, 0.3, 3.0)
			bars[root] = b
		out.append_array(bars[root])
	return _normalize(out)


## Octets PCM 16 bits mono d'une forme d'onde (pour AudioStreamWAV).
static func to_pcm16(samples: PackedFloat32Array) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(samples.size() * 2)
	for i in samples.size():
		bytes.encode_s16(i * 2, clampi(int(samples[i] * 32767.0), -32768, 32767))
	return bytes
