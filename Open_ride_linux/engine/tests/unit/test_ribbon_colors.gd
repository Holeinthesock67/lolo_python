extends SceneTree

## Tests sans écran des couleurs du ruban du Cyber-Rogue (lot R10) : bornes du tableau de pentes, jetons de la
## charte, éclat au-delà des 200 m.
## Lancement : godot --headless --path engine --script res://tests/unit/test_ribbon_colors.gd

const Colors := preload("res://scripts/rogue/ribbon_colors.gd")
const Palette := preload("res://scripts/rogue/neon_palette.gd")

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


func _run() -> void:
	for pair in [[-10.0, "grade_down"], [-3.01, "grade_down"], [-3.0, "grade_flat"], [0.0, "grade_flat"],
			[1.49, "grade_flat"], [1.5, "grade_up"], [3.99, "grade_up"], [4.0, "grade_hard"], [6.49, "grade_hard"],
			[6.5, "grade_wall"], [12.0, "grade_wall"]]:
		_check(Colors.token_for(pair[0]) == pair[1], "pente %.2f %% : %s" % [pair[0], pair[1]])
	_check(Colors.color_for(0.0).is_equal_approx(Palette.color("grade_flat")), "la couleur vient de la charte")
	var cols := Colors.segment_colors([[0.0, -5.0], [10.0, 0.0], [20.0, 8.0]])
	_check(cols.size() == 3 and cols[0].is_equal_approx(Palette.color("grade_down")) and cols[2].is_equal_approx(Palette.color("grade_wall")),
		"une couleur par intervalle du profil")
	_check(Colors.brightness(100.0, 0.0) == 1.0, "franche à 100 m devant le joueur")
	_check(Colors.brightness(200.0, 0.0) == 1.0, "franche à 200 m")
	_check(is_equal_approx(Colors.brightness(240.0, 0.0), Colors.FAR_DIM), "atténuée à 240 m")
	var mid := Colors.brightness(220.0, 0.0)
	_check(mid < 1.0 and mid > Colors.FAR_DIM, "fondu entre 200 et 240 m (%.2f)" % mid)
	_check(Colors.brightness(50.0, 400.0) == 1.0, "derrière le joueur : franche")
	await process_frame
	print("test_ribbon_colors : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
