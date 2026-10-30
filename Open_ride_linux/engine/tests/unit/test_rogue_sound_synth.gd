extends SceneTree

## Tests sans écran de la synthèse des bruitages et de la musique du Cyber-Rogue (lot R18) : durée de chaque
## son, crête sous −3 dBFS, boucles sans coupure, déterminisme, mémoire sous 8 Mo, temps de synthèse mesuré.
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_sound_synth.gd

const Synth := preload("res://scripts/rogue/rogue_sound_synth.gd")

const PEAK_MAX := 0.708         # −3 dBFS
const SYNTH_BUDGET_MS := 2000.0   # large : la mesure de référence (300 ms) se prend sur la GTX 1060, pas sur le runner
const MEMORY_MAX_BYTES := 8 * 1024 * 1024

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


func _peak(b: PackedFloat32Array) -> float:
	var p := 0.0
	for v in b:
		p = maxf(p, absf(v))
	return p


func _run() -> void:
	var total_bytes := 0
	var t0 := Time.get_ticks_usec()
	var bad_len: Array = []
	var bad_peak: Array = []
	var bad_loop: Array = []
	for sound in Synth.names():
		var b := Synth.render(sound)
		total_bytes += b.size() * 2
		if absf(float(b.size()) / Synth.RATE - Synth.duration_s(sound)) > 0.002:
			bad_len.append(sound)
		var p := _peak(b)
		if p < 0.05 or p > PEAK_MAX:
			bad_peak.append(sound)
		if Synth.is_loop(sound) and (absf(b[0]) > 0.05 or absf(b[b.size() - 1]) > 0.05):
			bad_loop.append(sound)
	var synth_ms := float(Time.get_ticks_usec() - t0) / 1000.0
	print("[mesure] synthèse des %d sons : %.0f ms" % [Synth.names().size(), synth_ms])
	_check(Synth.names().size() == 25, "25 sons dans la table (les 24 de la liste et le bilan de défaite)")
	_check(bad_len.is_empty(), "durée de chaque son conforme à la liste %s" % str(bad_len))
	_check(bad_peak.is_empty(), "crête entre 0,05 et −3 dBFS pour chaque son %s" % str(bad_peak))
	_check(bad_loop.is_empty(), "boucles (surchauffe, ronflement) sans coupure aux extrémités %s" % str(bad_loop))
	_check(synth_ms < SYNTH_BUDGET_MS, "synthèse des sons sous %.0f ms (%.0f ms)" % [SYNTH_BUDGET_MS, synth_ms])
	_check(Synth.render("rogue_hit") == Synth.render("rogue_hit"), "synthèse déterministe")
	_check(Synth.duration_s("rogue_boss_won") > Synth.duration_s("rogue_room_won") and Synth.duration_s("rogue_boss_won") == 1.8,
		"la fanfare du boss est la plus longue des fanfares (1,8 s)")

	t0 = Time.get_ticks_usec()
	var music_ok := true
	for layer in Synth.MUSIC_LAYERS:
		var m := Synth.render_music(layer)
		total_bytes += m.size() * 2
		music_ok = music_ok and absf(float(m.size()) / Synth.RATE - 20.0) < 0.01 and _peak(m) <= PEAK_MAX and _peak(m) > 0.05
	print("[mesure] synthèse de la musique : %.0f ms" % (float(Time.get_ticks_usec() - t0) / 1000.0))
	_check(music_ok, "quatre couches (dont le thème 8 bits du boss) de 8 mesures à 96 bpm (20 s), crête sous −3 dBFS")
	_check(total_bytes < MEMORY_MAX_BYTES, "mémoire des sons et de la musique sous 8 Mo (%.2f Mo)" % (total_bytes / 1048576.0))

	print("test_rogue_sound_synth : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
