extends SceneTree

## Tests unitaires sans écran des préréglages de qualité `quality_presets.gd`
## et des arguments `--quality` / `--theme` de `engine_args.gd` (Lot L4).
## Lancement : godot --headless --path engine --script res://tests/unit/test_quality_presets.gd

const QualityPresets := preload("res://scripts/quality_presets.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")

const EXPECTED_KEYS := [
	"chunks_ahead",
	"chunks_behind",
	"fog_end_m",
	"fog_volumetric",
	"msaa",
	"ssao",
	"vegetation_density_factor",
	"view_distance_m",
]

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


# Critère 3 : engine_args.gd (--quality, --theme, repli sur low avec message, préservation des arguments existants)
func _test_engine_args() -> void:
	var p_def: Dictionary = EngineArgs.parse(PackedStringArray())
	_check(p_def["quality"] == "low" and p_def["theme"] == "default"
		and p_def["state_port"] == 5005 and p_def["cmd_port"] == 5006 and not p_def["test_mode"],
		"engine_args par défaut : quality=low, theme=default, ports 5005/5006")

	var p_med: Dictionary = EngineArgs.parse(PackedStringArray(["--quality=medium", "--theme=x"]))
	_check(p_med["quality"] == "medium" and p_med["theme"] == "x" and EngineArgs.last_error == "",
		"engine_args : parse([\"--quality=medium\", \"--theme=x\"]) -> quality=medium, theme=x")

	var p_bad: Dictionary = EngineArgs.parse(PackedStringArray(["--quality=ultra"]))
	_check(p_bad["quality"] == "low" and "qualité invalide" in EngineArgs.last_error,
		"engine_args : --quality=ultra renvoie low avec message (%s)" % EngineArgs.last_error)

	_check(p_def["living"] == true, "engine_args : décor vivant actif par défaut (lot P16)")
	var p_off: Dictionary = EngineArgs.parse(PackedStringArray(["--living=off"]))
	var p_bad_living: Dictionary = EngineArgs.parse(PackedStringArray(["--living=peut-être"]))
	_check(p_off["living"] == false and p_bad_living["living"] == true and "décor vivant" in EngineArgs.last_error,
		"engine_args : --living=off coupe le décor vivant, une valeur invalide le laisse actif avec message")

	var p_empty_theme: Dictionary = EngineArgs.parse(PackedStringArray(["--theme="]))
	_check(p_empty_theme["theme"] == "default" and "thème vide" in EngineArgs.last_error,
		"engine_args : --theme= vide renvoie default avec message")

	var p_full: Dictionary = EngineArgs.parse(PackedStringArray([
		"--ipc-state-port=6005",
		"--ipc-cmd-port=6006",
		"--routes-dir=/tmp/mes_routes",
		"--test-mode",
		"--quality=high",
		"--theme=alpes",
	]))
	_check(p_full["state_port"] == 6005 and p_full["cmd_port"] == 6006
		and p_full["routes_dir"] == "/tmp/mes_routes" and p_full["test_mode"]
		and p_full["quality"] == "high" and p_full["theme"] == "alpes",
		"engine_args : les arguments existants (ports, --routes-dir, --test-mode) gardent leur comportement")


# Critère 4 : quality_presets.gd (3 préréglages, mêmes clés, distances/densités croissantes, nom inconnu -> low)
func _test_presets_table() -> void:
	var low: Dictionary = QualityPresets.preset("low")
	var med: Dictionary = QualityPresets.preset("medium")
	var high: Dictionary = QualityPresets.preset("high")

	var keys_low := low.keys()
	keys_low.sort()
	var keys_med := med.keys()
	keys_med.sort()
	var keys_high := high.keys()
	keys_high.sort()
	_check(keys_low == EXPECTED_KEYS and keys_med == EXPECTED_KEYS and keys_high == EXPECTED_KEYS,
		"preset : les 3 préréglages exposent exactement les 8 clés attendues")

	_check(float(low["view_distance_m"]) < float(med["view_distance_m"])
		and float(med["view_distance_m"]) < float(high["view_distance_m"]),
		"preset : view_distance_m strictement croissante (%.0f < %.0f < %.0f m)" % [
			low["view_distance_m"], med["view_distance_m"], high["view_distance_m"]])

	_check(int(low["chunks_ahead"]) < int(med["chunks_ahead"])
		and int(med["chunks_ahead"]) < int(high["chunks_ahead"]),
		"preset : chunks_ahead strictement croissant (%d < %d < %d)" % [
			low["chunks_ahead"], med["chunks_ahead"], high["chunks_ahead"]])

	_check(float(low["vegetation_density_factor"]) < float(med["vegetation_density_factor"])
		and float(med["vegetation_density_factor"]) < float(high["vegetation_density_factor"]),
		"preset : vegetation_density_factor strictement croissant (%.1f < %.1f < %.1f)" % [
			low["vegetation_density_factor"], med["vegetation_density_factor"], high["vegetation_density_factor"]])

	# Lot Y1 : brouillard opaque à 4, 6 et 9 km (décision du propriétaire du 27 octobre).
	_check(QualityPresets.fog_end_m("low") == 4000.0 and QualityPresets.fog_end_m("medium") == 6000.0
		and QualityPresets.fog_end_m("high") == 9000.0,
		"fog_end_m : 4 000, 6 000 et 9 000 m")
	_check(QualityPresets.fog_end_m("inexistant") == QualityPresets.fog_end_m("low"),
		"fog_end_m : un nom inconnu renvoie la valeur de low")

	var unk: Dictionary = QualityPresets.preset("inexistant")
	_check(unk == low, "preset : un nom inconnu renvoie le préréglage low")


# Lot P4 : budgets du décor vivant (critère 10)
func _test_living() -> void:
	var keys := ["aircraft", "ambience_voices", "animals", "birds", "boats", "clouds", "cyclists", "distant_vehicles", "grass_tufts",
		"ground_grass", "ground_rocks", "ground_termites", "passersby", "spectators", "tree_sway", "vehicles", "water_shimmer", "weather_particles"]
	for name in ["low", "medium", "high"]:
		var l: Dictionary = QualityPresets.living(name)
		var k := l.keys()
		k.sort()
		_check(k == keys, "living(%s) : les 18 budgets attendus (dont les 3 détails de sol du lot U8)" % name)
	var low: Dictionary = QualityPresets.living("low")
	_check(low["tree_sway"] == true and low["grass_tufts"] == 1500 and low["clouds"] == "flat"
		and low["weather_particles"] == 600 and low["birds"] == 24 and low["animals"] == 20
		and low["vehicles"] == 3 and low["spectators"] == 40 and low["ambience_voices"] == 4
		and low["water_shimmer"] == true,
		"living(low) : valeurs du cahier P4 §4.3 (oiseaux doublés par P23, touffes : Y11 H5)")
	var med: Dictionary = QualityPresets.living("medium")
	var high: Dictionary = QualityPresets.living("high")
	var growing := true
	for key in ["grass_tufts", "weather_particles", "birds", "animals", "vehicles", "distant_vehicles", "aircraft", "boats", "cyclists",
			"spectators",
			"passersby", "ambience_voices"]:
		growing = growing and int(low[key]) <= int(med[key]) and int(med[key]) <= int(high[key])
	_check(growing, "living : budgets croissants de low à high")
	_check(low["passersby"] == 24 and med["passersby"] == 48 and high["passersby"] == 80,
		"living : passants 24, 48 et 80 (cahier P21 §4)")
	_check(low["distant_vehicles"] == 6 and med["distant_vehicles"] == 12 and high["distant_vehicles"] == 24,
		"living : véhicules lointains 6, 12 et 24 (cahier P25 §4)")
	_check(low["cyclists"] == 4 and med["cyclists"] == 8 and high["cyclists"] == 16, "living : cyclistes 4/8/16 (cahier P28)")
	_check(low["aircraft"] == 4 and med["aircraft"] == 8 and high["aircraft"] == 12,
		"living : engins volants 4, 8 et 12 (cahier P26 §4)")
	_check(low["boats"] == 4 and med["boats"] == 8 and high["boats"] == 16,
		"living : bateaux 4, 8 et 16 (cahier P29 §4)")
	var off: Dictionary = QualityPresets.living("high", false)
	var all_off: bool = off["clouds"] == "off"
	for key in off:
		if typeof(off[key]) == TYPE_BOOL:
			all_off = all_off and off[key] == false
		elif typeof(off[key]) == TYPE_INT:
			all_off = all_off and off[key] == 0
	_check(all_off, "living(high, false) : décor vivant coupé, tout à zéro")
	_check(QualityPresets.living("inexistant") == low, "living : nom inconnu -> low")
	low["birds"] = 999
	_check(QualityPresets.living("low")["birds"] == 24, "living : copie, la table n'est pas modifiable")


func _init() -> void:
	_test_engine_args()
	_test_presets_table()
	_test_living()
	print("test_quality_presets : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
