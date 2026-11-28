extends SceneTree

## Tests sans écran des essais de rendu du dessin animé (toon_essai.gd, lot CS0) : sans variable, rien n'est
## demandé ni créé ; avec `contours` ou `paliers=N`, un seul quad sous la caméra, réglé comme demandé.
## Lancement : godot --headless --path engine --script res://tests/unit/test_toon_essai.gd

const RenderDiag := preload("res://scripts/render_diag.gd")
const ToonEssai := preload("res://scripts/toon_essai.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if not cond:
		_failures += 1
		printerr("ÉCHEC : ", msg)


func _force(text: String) -> void:
	# La variable est lue une seule fois : on remplit l'état comme le ferait la lecture (test_render_diag.gd).
	var d := RenderDiag.parse(text)
	RenderDiag._parsed = true
	RenderDiag._flags = d["flags"]
	RenderDiag._values = d["values"]


func _init() -> void:
	var cam := Camera3D.new()
	_force("")
	_check(ToonEssai.wanted().is_empty(), "sans essai : rien de demandé")
	_check(ToonEssai.attach(cam) == null and cam.get_child_count() == 0, "sans essai : aucun nœud sous la caméra")
	_force("msaa=0,sans_ssao")
	_check(ToonEssai.wanted().is_empty(), "autres essais seuls : rien de demandé")

	_force("contours")
	var w := ToonEssai.wanted()
	_check(w["outlines"] == true and w["levels"] == 0.0, "contours : trait sans paliers")
	_check(w["thickness_px"] == ToonEssai.DEFAULT_THICKNESS_PX and w["fade_m"] == ToonEssai.DEFAULT_FADE_M, "contours : valeurs par défaut")
	_check(ToonEssai.attach(null) == null, "sans caméra : rien")
	var quad := ToonEssai.attach(cam)
	_check(quad != null and quad.name == ToonEssai.NODE_NAME and cam.get_child_count() == 1, "contours : un quad sous la caméra")
	_check(ToonEssai.attach(cam) == quad and cam.get_child_count() == 1, "second appel : le même quad")
	var mat := quad.material_override as ShaderMaterial
	_check(mat != null and mat.shader != null and mat.shader.resource_path == ToonEssai.SHADER_PATH, "shader de l'essai chargé")
	_check(mat.render_priority == ToonEssai.RENDER_PRIORITY, "dessiné avant les autres objets transparents")
	_check(mat.get_shader_parameter("outlines") == true and mat.get_shader_parameter("levels") == 0.0, "paramètres des contours")
	_check(quad.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF, "quad sans ombre")

	_force("paliers=5,contours_px=2,contours_m=120")
	w = ToonEssai.wanted()
	_check(w["outlines"] == false and w["levels"] == 5.0, "paliers seuls : pas de trait")
	_check(w["thickness_px"] == 2.0 and w["fade_m"] == 120.0, "épaisseur et fondu lus")
	_force("contours,contours_px=99,contours_m=1")
	w = ToonEssai.wanted()
	_check(w["thickness_px"] == 6.0 and w["fade_m"] == 20.0, "valeurs bornées")
	cam.free()
	_force("")

	print("test_toon_essai : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
