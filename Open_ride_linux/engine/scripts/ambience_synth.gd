extends RefCounted

## Synthèse des fonds d'ambiance (lots P9 et U11), sans nœud ni ressource : chaque fonction rend des
## échantillons (−1 à 1) et peut donc tourner dans un fil de travail (sound_player.gd fait chaque fond à la
## première demande, hors du fil principal). Pas de class_name : charger par preload("res://scripts/ambience_synth.gd").
##
## Règles communes, celles des boucles de P9 (« tac-tac » du 28/10, « vague » du 29/10) :
## - boucle de `loop_s(bed)` secondes à MIX_RATE ; les événements (chants, coups, croassements, vagues)
##   qui débordent de la fin reprennent au début, les bruits filtrés sont périodiques (`periodic_lowpass`)
##   et les sons tenus font un nombre entier de cycles par boucle (`_fq`) : la fin enchaîne sur le début ;
## - tirages d'un générateur de graine `hash(bed)` : même son à chaque lancement ;
## - aucun fondu au silence aux bords de la boucle.
##
## Lot U11 : dix fonds propres aux biomes (AmbienceModel.BIOME_BEDS) : cigales, chorus de la jungle, vent dans
## les résineux, sonnailles, vagues, mouettes, grenouilles, sable qui chante, craquements de la banquise,
## fumerolles ; fond marin du lot SM1 (`underwater`). Le niveau de chaque fond ne varie que par AmbienceModel (biome, saison, heure, vent, rivage).

const MIX_RATE := 22050
## Durée de la boucle de chaque fond (s). Fonds de P9 : 2 s. Fonds de U11 faits d'événements espacés
## (vagues, mouettes, sonnailles, glace) : assez longs pour que la répétition ne s'entende pas.
const LOOP_S := {
	"forest_birds": 2.0, "field_insects": 2.0, "water_flow": 2.0, "village_murmur": 2.0, "high_wind": 2.0, "rain": 2.0,
	"cicadas": 3.0, "jungle_chorus": 6.0, "conifer_wind": 4.0, "cowbells": 6.0, "waves": 24.0, "gulls": 7.0,
	"frogs": 5.0, "singing_sand": 4.0, "ice_cracks": 7.0, "fumaroles": 4.0,
	"underwater": 6.0,
}


static func loop_samples(bed: String) -> int:
	return int(float(LOOP_S.get(bed, 2.0)) * MIX_RATE)


## Fréquence la plus proche de `f` qui fait un nombre entier de cycles sur `loop_s` secondes.
static func _fq(f: float, loop_s: float) -> float:
	return maxf(round(f * loop_s), 1.0) / loop_s


## Passe-bas à un pôle (coefficient `alpha`) d'un bruit bouclé, en régime établi : le filtre fait d'abord un
## tour de boucle à vide (ses 12/alpha derniers échantillons suffisent), si bien que la sortie est elle-même
## périodique (fin raccordée au début, sans clic).
static func periodic_lowpass(noise: PackedFloat32Array, alpha: float, gain: float = 1.0) -> PackedFloat32Array:
	var n := noise.size()
	var out := PackedFloat32Array()
	out.resize(n)
	var lp := 0.0
	# Mise en régime sur la fin de la boucle seulement : l'écart restant vaut (1 − alpha)^warm ≈ e^−12
	var warm := mini(n, int(ceil(12.0 / maxf(alpha, 1e-3))))
	for i in range(n - warm, n):
		lp += alpha * (noise[i] - lp)
	for i in range(n):
		lp += alpha * (noise[i] - lp)
		out[i] = lp * gain
	return out


static func _noise(rng: RandomNumberGenerator, n: int) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(n)
	for i in range(n):
		out[i] = rng.randf() * 2.0 - 1.0
	return out


## Glissade tonale ajoutée à `buf` à partir de l'échantillon `start` (repris au début de la boucle au-delà de
## la fin) : fréquence de `f0` à `f1` sur `dur` s, harmoniques `harm` (amplitudes), enveloppe en arche dont
## l'attaque dure `attack` (part de la durée), vibrato `vib_hz` de `vib_depth` (part de la fréquence).
static func _glide(buf: PackedFloat32Array, start: int, dur: float, f0: float, f1: float, amp: float,
		harm: Array = [1.0], attack: float = 0.5, vib_hz: float = 0.0, vib_depth: float = 0.0) -> void:
	var n := buf.size()
	var len := int(dur * MIX_RATE)
	var ph := 0.0
	for i in range(len):
		var u := float(i) / float(len)
		var env := sin(0.5 * PI * u / attack) if u < attack else cos(0.5 * PI * (u - attack) / (1.0 - attack))
		var f := lerpf(f0, f1, u) * (1.0 + vib_depth * sin(TAU * vib_hz * float(i) / MIX_RATE))
		ph += TAU * f / MIX_RATE
		var s := 0.0
		for k in range(harm.size()):
			s += float(harm[k]) * sin(ph * (k + 1))
		buf[(start + i) % n] += s * env * amp


## Coup amorti à partiels inharmoniques (sonnaille, cloche), ajouté à `buf` à partir de `start`.
static func _strike(buf: PackedFloat32Array, start: int, f: float, amp: float, ratios: Array, amps: Array,
		decays: Array, dur: float) -> void:
	var n := buf.size()
	var len := int(dur * MIX_RATE)
	for i in range(len):
		var t := float(i) / MIX_RATE
		var s := 0.0
		for k in range(ratios.size()):
			s += float(amps[k]) * sin(TAU * f * float(ratios[k]) * t) * exp(-float(decays[k]) * t)
		# attaque de 2 ms, sans clic
		buf[(start + i) % n] += s * amp * minf(1.0, t / 0.002)


## Échantillons d'une boucle du fond `bed` (−1 à 1), `loop_samples(bed)` valeurs ; vide si le fond est inconnu.
static func bed_samples(bed: String) -> PackedFloat32Array:
	var n := loop_samples(bed)
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
			var noise := _noise(rng, n)
			var lp := periodic_lowpass(noise, alpha)
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
		"cicadas":
			# Deux cigales : porteuses de 6,1 et 5,3 kHz hachées en impulsions serrées (110 et 87 par seconde),
			# chacune enflant et retombant une fois par boucle, en décalé (le chœur ne s'arrête jamais).
			var c1 := _fq(6100.0, loop_s)
			var c2 := _fq(5300.0, loop_s)
			var r1 := _fq(110.0, loop_s)
			var r2 := _fq(87.0, loop_s)
			for i in range(n):
				var t := float(i) / MIX_RATE
				var sw1 := 0.55 + 0.45 * pow(sin(PI * t / loop_s), 2.0)
				var sw2 := 0.55 + 0.45 * pow(cos(PI * t / loop_s), 2.0)
				var p1 := pow(maxf(sin(TAU * r1 * t), 0.0), 6.0)
				var p2 := pow(maxf(sin(TAU * r2 * t + 1.3), 0.0), 6.0)
				buf[i] = (sin(TAU * c1 * t) + 0.3 * sin(TAU * 2.0 * c1 * t)) * p1 * sw1 * 0.32 \
					+ (sin(TAU * c2 * t) + 0.3 * sin(TAU * 2.0 * c2 * t)) * p2 * sw2 * 0.28
		"jungle_chorus":
			# Nappe d'insectes (trois porteuses hachées), cris d'oiseaux sifflés avec vibrato et un appel grave.
			var a := _fq(3300.0, loop_s)
			var b := _fq(4700.0, loop_s)
			var c := _fq(7400.0, loop_s)
			var ra := _fq(40.0, loop_s)
			var rc := _fq(140.0, loop_s)
			for i in range(n):
				var t := float(i) / MIX_RATE
				var burst := 1.0 if fmod(t, 0.35) < 0.25 else 0.0
				buf[i] = sin(TAU * a * t) * pow(maxf(sin(TAU * ra * t), 0.0), 3.0) * 0.12 \
					+ sin(TAU * b * t) * maxf(sin(TAU * 23.0 * t), 0.0) * burst * 0.08 \
					+ sin(TAU * c * t) * (0.5 + 0.5 * sin(TAU * rc * t)) * 0.035
			var t0 := 0.2
			while t0 < loop_s:
				var f0 := rng.randf_range(1200.0, 2600.0)
				var f1 := f0 * rng.randf_range(0.6, 1.5)
				var dur := rng.randf_range(0.18, 0.55)
				var calls := rng.randi_range(1, 3)
				for k in range(calls):
					_glide(buf, int((t0 + k * (dur + 0.08)) * MIX_RATE), dur, f0, f1, rng.randf_range(0.12, 0.22),
						[1.0, 0.25], 0.3, rng.randf_range(6.0, 11.0), 0.03)
				t0 += calls * (dur + 0.08) + rng.randf_range(0.4, 1.2)
			_glide(buf, int(rng.randf_range(0.0, loop_s) * MIX_RATE), 0.45, 420.0, 340.0, 0.16, [1.0, 0.5, 0.2], 0.2)
		"conifer_wind":
			# Souffle dans les aiguilles : bruit passe-bande (passe-bas double moins passe-bas grave) et un soupçon d'aigu,
			# de niveau constant (le vent du modèle règle le volume).
			var noise := _noise(rng, n)
			var lo := periodic_lowpass(noise, 0.03)
			var hi := periodic_lowpass(periodic_lowpass(noise, 0.18), 0.18)
			var top := periodic_lowpass(noise, 0.6)
			for i in range(n):
				buf[i] = (hi[i] * 2.2 - lo[i] * 0.9) + (noise[i] - top[i]) * 0.025
		"cowbells":
			# Trois sonnailles (620, 840 et 1 030 Hz, partiels inharmoniques) : chaque vache tinte par grappes de
			# 2 à 4 coups quand elle bouge la tête, à des instants irréguliers.
			for f in [620.0, 840.0, 1030.0]:
				var t0 := rng.randf_range(0.0, 1.5)
				while t0 < loop_s:
					var hits := rng.randi_range(2, 4)
					for k in range(hits):
						_strike(buf, int((t0 + k * rng.randf_range(0.22, 0.42)) * MIX_RATE), f * rng.randf_range(0.99, 1.01),
							rng.randf_range(0.05, 0.11), [1.0, 2.32, 4.25, 6.63], [1.0, 0.6, 0.35, 0.2], [5.0, 7.0, 10.0, 14.0], 0.9)
					t0 += rng.randf_range(1.6, 3.2)
		"waves":
			# Mer (refaite le 8/11 : la houle grave constante et deux vagues régulières sonnaient « machine d'usine ») :
			# six à huit vagues de 2,6 à 5,5 s et de forces inégales sur une boucle de 24 s ; chacune est un souffle
			# d'écume (bruit moyen, sans bourdon) qui enfle, déferle puis se retire en sifflant, les vagues se
			# chevauchent ; entre elles, un ressac très faible. La texture de l'écume varie lentement (deux bruits
			# mêlés selon une modulation irrégulière) pour qu'aucune vague ne ressemble à la précédente.
			var na := _noise(rng, n)
			var nb := _noise(rng, n)
			var foam_a := periodic_lowpass(na, 0.22, 2.2)
			var foam_b := periodic_lowpass(nb, 0.09, 3.0)
			var top_a := periodic_lowpass(na, 0.6)
			var body := periodic_lowpass(periodic_lowpass(nb, 0.05), 0.05, 6.0)
			var env := PackedFloat32Array()
			env.resize(n)
			var wash := PackedFloat32Array()
			wash.resize(n)
			var t0 := 0.0
			while t0 < loop_s - 1.0:
				var l := rng.randf_range(2.6, 5.5)
				var force := rng.randf_range(0.45, 1.0)
				var rise := rng.randf_range(0.35, 0.6)
				var at := int(t0 * MIX_RATE)
				var len := int(l * MIX_RATE)
				for i in range(len):
					var u := float(i) / float(len)
					var e := pow(sin(0.5 * PI * u / rise), 2.0) if u < rise else exp(-(u - rise) / (1.0 - rise) * 3.0) * (1.0 - u * u * u)
					env[(at + i) % n] += e * force
					var w := (smoothstep(rise, rise + 0.1, u) * exp(-(u - rise) / (1.0 - rise) * 2.0) * (1.0 - u * u)) if u > rise else 0.0
					wash[(at + i) % n] += w * force
				t0 += l * rng.randf_range(0.55, 0.9)
			var mix_f := _fq(1.0 / 11.0, loop_s)
			for i in range(n):
				var t := float(i) / MIX_RATE
				var k := 0.5 + 0.35 * sin(TAU * mix_f * t) + 0.15 * sin(TAU * 3.0 * mix_f * t + 1.1)
				var foam := foam_a[i] * k + foam_b[i] * (1.0 - k)
				buf[i] = foam * (0.06 + 0.8 * env[i]) + body[i] * 0.12 * env[i] + (na[i] - top_a[i]) * 0.22 * wash[i]
		"gulls":
			# Mouettes : séries de 1 à 3 cris « kiou » (montée puis chute de 1,3 à 1,7 puis 1,1 kHz, timbre nasal),
			# l'une proche, les autres plus loin.
			var t0 := rng.randf_range(0.0, 0.8)
			while t0 < loop_s:
				var calls := rng.randi_range(1, 3)
				var amp := rng.randf_range(0.08, 0.2)
				var f0 := rng.randf_range(1250.0, 1450.0)
				for k in range(calls):
					var dur := rng.randf_range(0.22, 0.4)
					var at := int((t0 + k * (dur + 0.1)) * MIX_RATE)
					_glide(buf, at, dur * 0.3, f0, f0 * 1.25, amp, [1.0, 0.55, 0.3, 0.12], 0.6)
					_glide(buf, at + int(dur * 0.3 * MIX_RATE), dur * 0.7, f0 * 1.25, f0 * 0.8, amp, [1.0, 0.55, 0.3, 0.12], 0.1)
				t0 += calls * 0.5 + rng.randf_range(1.0, 2.6)
		"frogs":
			# Grenouilles : croassements en trains d'impulsions graves (350 à 600 Hz, 18 à 26 par seconde), par
			# deux (« crôa-crôa »), et rainettes qui piaillent par 3 à 5 notes à 2,9 kHz.
			for f in [380.0, 470.0, 560.0]:
				var rate := rng.randf_range(18.0, 26.0)
				var t0 := rng.randf_range(0.0, 1.0)
				while t0 < loop_s:
					for pair in range(2):
						var len_s := rng.randf_range(0.18, 0.32)
						var k := 0.0
						while k < len_s:
							_strike(buf, int((t0 + pair * (len_s + 0.12) + k) * MIX_RATE), f, 0.09, [1.0, 2.0], [1.0, 0.3],
								[110.0, 160.0], 0.035)
							k += 1.0 / rate
					t0 += rng.randf_range(1.2, 2.4)
			var t1 := rng.randf_range(0.0, 0.5)
			while t1 < loop_s:
				for k in range(rng.randi_range(3, 5)):
					_glide(buf, int((t1 + k * 0.07) * MIX_RATE), 0.03, 2850.0, 3000.0, 0.05)
				t1 += rng.randf_range(0.6, 1.4)
		"singing_sand":
			# Dune qui chante : bourdon grave de 95 Hz et ses harmoniques, avec un lent vibrato, sur un souffle de
			# sable (bruit aigu) ; niveau constant (le vent règle le volume).
			var f := _fq(95.0, loop_s)
			var vib := _fq(0.5, loop_s)
			var noise := _noise(rng, n)
			var lp := periodic_lowpass(noise, 0.4)
			for i in range(n):
				var t := float(i) / MIX_RATE
				var ph := TAU * f * t + 2.0 * sin(TAU * vib * t)
				buf[i] = (sin(ph) * 0.22 + sin(2.0 * ph) * 0.12 + sin(3.0 * ph) * 0.06 + sin(4.0 * ph) * 0.03) \
					+ (noise[i] - lp[i]) * 0.1
		"ice_cracks":
			# Banquise : craquements secs (claquement bref), suivis du « piou » de la glace qui chante (glissade
			# de 2,6 kHz à 250 Hz) et d'un choc sourd.
			var t0 := rng.randf_range(0.2, 1.2)
			while t0 < loop_s:
				var at := int(t0 * MIX_RATE)
				var amp := rng.randf_range(0.2, 0.45)
				for i in range(int(0.006 * MIX_RATE)):
					buf[(at + i) % n] += (rng.randf() * 2.0 - 1.0) * amp * (1.0 - float(i) / (0.006 * MIX_RATE))
				_glide(buf, at, rng.randf_range(0.18, 0.3), 2600.0, 250.0, amp * 0.6, [1.0, 0.3], 0.03)
				_strike(buf, at, 60.0, amp * 0.8, [1.0, 1.5], [1.0, 0.4], [9.0, 12.0], 0.4)
				t0 += rng.randf_range(1.6, 3.2)
		"fumaroles":
			# Fumerolles : sifflement de vapeur (bruit aigu tenu), grondement sourd et glouglous de boue.
			var noise := _noise(rng, n)
			var top := periodic_lowpass(noise, 0.35)
			var rumble := periodic_lowpass(noise, 0.01, 5.0)
			for i in range(n):
				buf[i] = (noise[i] - top[i]) * 0.3 + rumble[i] * 0.6
			for k in range(36):
				_strike(buf, rng.randi_range(0, n - 1), rng.randf_range(120.0, 260.0), rng.randf_range(0.04, 0.09),
					[1.0, 1.6], [1.0, 0.3], [30.0, 45.0], 0.12)
		"underwater":
			# Fond marin (lot SM1) : grondement très sourd qui enfle lentement (houle lointaine, deux cycles
			# entiers par boucle) et bulles qui montent : courts sifflements dont la note grimpe en s'éteignant.
			var noise := _noise(rng, n)
			var rumble := periodic_lowpass(noise, 0.004, 14.0)
			var swell := _fq(0.33, float(LOOP_S["underwater"]))
			for i in range(n):
				var t := float(i) / MIX_RATE
				buf[i] = rumble[i] * (0.65 + 0.35 * sin(TAU * swell * t))
			for k in range(28):
				var start := rng.randi_range(0, n - 1)
				var f0 := rng.randf_range(380.0, 1100.0)
				var amp := rng.randf_range(0.05, 0.14)
				var dur := rng.randf_range(0.03, 0.07)
				var phase := 0.0
				for i in range(int(dur * MIX_RATE)):
					var t := float(i) / MIX_RATE
					phase += TAU * f0 * (1.0 + 1.8 * t / dur) / MIX_RATE
					buf[(start + i) % n] += amp * sin(phase) * exp(-t / (dur * 0.35)) * minf(1.0, t / 0.002)
		_:
			return PackedFloat32Array()
	return buf


## Échantillons en PCM 16 bits petit-boutiste.
static func pcm16(buf: PackedFloat32Array) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(buf.size() * 2)
	for i in range(buf.size()):
		bytes.encode_s16(i * 2, clampi(int(buf[i] * 32767.0), -32768, 32767))
	return bytes


## Flux bouclé (mono, 16 bits, MIX_RATE) d'une boucle déjà convertie par `pcm16(bed_samples(…))`. Appelé dans
## le fil de travail avec la conversion (copie des échantillons comprise) : le fil principal ne fait que poser le flux.
static func to_wav(pcm: PackedByteArray) -> AudioStreamWAV:
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = MIX_RATE
	wav.stereo = false
	wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
	wav.loop_begin = 0
	wav.loop_end = pcm.size() / 2
	wav.data = pcm
	return wav
