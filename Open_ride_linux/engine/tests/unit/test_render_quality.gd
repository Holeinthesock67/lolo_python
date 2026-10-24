extends SceneTree

## Tests unitaires sans écran du brouillard de `render_quality.gd` (lot E1, revue E2 R2).
## Lancement : godot --headless --path engine --script res://tests/unit/test_render_quality.gd

const RenderQuality := preload("res://scripts/render_quality.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_fog() -> void:
	for has_terrain in [true, false]:
		var env := Environment.new()
		RenderQuality.apply_fog(env, has_terrain)
		var fog: Dictionary = RenderQuality.FOG_TERRAIN if has_terrain else RenderQuality.FOG_FLAT
		var label := "avec terrain" if has_terrain else "sans terrain"
		_check(env.fog_enabled and env.fog_mode == Environment.FOG_MODE_DEPTH, "brouillard en profondeur " + label)
		# Godot 4.3 multiplie l'opacité du mode profondeur par fog_density : à 1, la limite est couverte.
		_check(is_equal_approx(env.fog_density, 1.0), "fog_density = 1 " + label + " (limite entièrement couverte)")
		_check(is_equal_approx(env.fog_depth_end, fog["end"]), "fin du brouillard à %d m %s" % [int(fog["end"]), label])
	var scene: PackedScene = load("res://scenes/main.tscn")
	var env_node := scene.instantiate().get_node("WorldEnvironment") as WorldEnvironment
	_check(is_equal_approx(env_node.environment.fog_density, 1.0), "main.tscn : fog_density = 1 avant le chargement du parcours")
	env_node.get_parent().free()


func _init() -> void:
	_test_fog()
	print("test_render_quality : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
