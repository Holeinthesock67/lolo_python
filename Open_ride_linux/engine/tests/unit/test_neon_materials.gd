extends SceneTree

## Tests sans écran de la fabrique de matériaux du Cyber-Rogue (lot R17) : un matériau par jeton, sorte et
## préréglage (cache), couleurs prises dans la charte, shaders chargés.
## Lancement : godot --headless --path engine --script res://tests/unit/test_neon_materials.gd

const Materials := preload("res://scripts/rogue/neon_materials.gd")
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
	Materials.clear_cache()
	var a := Materials.edge("player")
	var b := Materials.edge("player")
	_check(a == b, "même jeton, même sorte : même matériau (cache)")
	_check(Materials.edge("danger") != a, "autre jeton : autre matériau")
	_check(Materials.edge("player", 2.0, "high") != a, "autre préréglage : autre matériau")
	_check(Materials.edge("danger", 2.0, "low", true) != Materials.edge("danger"), "variante adaptée : autre matériau")
	_check(a.shader != null and a.shader.code.contains("fwidth"), "arêtes : shader à épaisseur constante à l'écran")
	_check(a.get_shader_parameter("body_color").is_equal_approx(Palette.body_color()), "volume sombre de la charte")
	_check(a.get_shader_parameter("line_color").is_equal_approx(Palette.glow_color("player", "low")), "arête de la couleur du jeton")
	_check(Materials.hologram("gold") == Materials.hologram("gold"), "hologramme en cache")
	_check(Materials.wall("danger") == Materials.wall("danger"), "mur de lumière en cache")
	_check(Materials.grid() == Materials.grid(), "grille en cache")
	_check(Materials.grid("high") != Materials.grid("low"), "grille : intensité selon le préréglage")
	_check(Materials.glass("parry", 0.2).get_shader_parameter("scan_strength") == 0.0, "verre : sans balayage")
	_check(Materials.glass("parry", 0.2) != Materials.hologram("parry"), "verre et hologramme sont deux matériaux")
	var g := Materials.glitch(2.0)
	_check(is_equal_approx(g.get_shader_parameter("intensity"), 1.0), "glitch : intensité bornée à 1")
	_check(Materials.glitch(0.5) != g, "glitch : un matériau neuf par appel (intensité propre)")
	for sh in [Materials.EDGE_SHADER, Materials.GRID_SHADER, Materials.HOLOGRAM_SHADER, Materials.GLITCH_SHADER, Materials.WALL_SHADER]:
		_check(sh is Shader and sh.code.length() > 100, "shader chargé (%d caractères)" % sh.code.length())
	_check(Materials.GLITCH_SHADER.code.contains("TIME * 3.0"), "glitch : le motif change au plus 3 fois par seconde")
	var before := Materials.cache_size()
	Materials.edge("player")
	_check(Materials.cache_size() == before, "un second appel n'agrandit pas le cache")
	await process_frame
	print("test_neon_materials : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
