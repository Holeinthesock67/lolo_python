extends SceneTree

## Tests unitaires sans écran des préréglages de qualité `quality_presets.gd`
## et des arguments `--quality` / `--theme` de `engine_args.gd` (Lot L4).
## Lancement : godot --headless --path engine --script res://tests/unit/test_quality_presets.gd

const QualityPresets := preload("res://scripts/quality_presets.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")

const EXPECTED_KEYS := [
	"chunks_ahead",
	"chunks_behind",
	"fog_volumetric",
	"msaa",
	"renderer_hint",
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

	_check(low["renderer_hint"] == "mobile" and med["renderer_hint"] == "forward_plus" and high["renderer_hint"] == "forward_plus",
		"preset : renderer_hint mobile en low, forward_plus en medium et high")

	var unk: Dictionary = QualityPresets.preset("inexistant")
	_check(unk == low, "preset : un nom inconnu renvoie le préréglage low")


func _init() -> void:
	_test_engine_args()
	_test_presets_table()
	print("test_quality_presets : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
