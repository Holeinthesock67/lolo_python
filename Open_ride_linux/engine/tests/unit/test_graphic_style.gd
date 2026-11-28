extends SceneTree

## Tests sans écran du style graphique (graphic_style.gd, lot CS1) : `realistic` ne change rien (saturation du
## préréglage gardée, shader rendu tel quel, même objet), `toon` pose la saturation « vif » et fabrique une
## variante du shader derrière `#define STYLE_TOON`, une seule fois par fichier.
## Lancement : godot --headless --path engine --script res://tests/unit/test_graphic_style.gd

const GraphicStyle := preload("res://scripts/graphic_style.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if not cond:
		_failures += 1
		printerr("ÉCHEC : ", msg)


func _init() -> void:
	_check(GraphicStyle.DEFAULT_STYLE == "realistic", "style par défaut : realistic")
	_check(GraphicStyle.is_valid("realistic") and GraphicStyle.is_valid("toon"), "deux styles valides")
	_check(not GraphicStyle.is_valid("") and not GraphicStyle.is_valid("manga"), "style inconnu refusé")

	var base: float = RenderQuality.LOOK["saturation"]
	_check(GraphicStyle.saturation("realistic", base) == base, "réaliste : saturation du préréglage")
	_check(GraphicStyle.saturation("inconnu", base) == base, "style inconnu : saturation du préréglage")
	_check(GraphicStyle.saturation("toon", base) == GraphicStyle.TOON_SATURATION and GraphicStyle.TOON_SATURATION > base,
		"dessin animé : couleurs plus vives que le préréglage")
	var env := Environment.new()
	env.adjustment_saturation = base
	GraphicStyle.apply("realistic", env, base)
	_check(is_equal_approx(env.adjustment_saturation, base), "réaliste appliqué : environnement inchangé")
	GraphicStyle.apply("toon", env, base)
	_check(is_equal_approx(env.adjustment_saturation, GraphicStyle.TOON_SATURATION), "dessin animé appliqué")
	GraphicStyle.apply("realistic", env, base)
	_check(is_equal_approx(env.adjustment_saturation, base), "retour au réaliste : saturation du préréglage")
	GraphicStyle.apply("toon", null, base)   # sans environnement : rien, pas d'erreur

	var code := "shader_type spatial;\nrender_mode cull_back;\nvoid fragment() {\n\tALBEDO = vec3(1.0);\n}\n"
	_check(GraphicStyle.variant_code(code, "realistic") == code, "réaliste : code du shader au caractère près")
	var toon_code := GraphicStyle.variant_code(code, "toon")
	_check(toon_code.begins_with("shader_type spatial;\n#define STYLE_TOON\n"), "dessin animé : définition après shader_type")
	_check(toon_code.replace("\n#define STYLE_TOON\n", "") == code, "dessin animé : rien d'autre ne change")
	_check(GraphicStyle.variant_code("void fragment() {}", "toon") == "void fragment() {}", "sans shader_type : code inchangé")

	var shader: Shader = load("res://shaders/terrain.gdshader")
	_check(GraphicStyle.variant(shader, "realistic") == shader, "réaliste : le même objet Shader, sans copie")
	_check(GraphicStyle.variant(null, "toon") == null, "shader absent : null")
	var v1 := GraphicStyle.variant(shader, "toon")
	_check(v1 != shader and v1.code.contains("#define STYLE_TOON"), "dessin animé : variante à part")
	_check(GraphicStyle.variant(shader, "toon") == v1, "variante gardée en mémoire")
	_check(not shader.code.contains("STYLE_TOON"), "shader d'origine intact")

	print("test_graphic_style : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
