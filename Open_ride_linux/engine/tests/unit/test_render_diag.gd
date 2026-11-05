extends SceneTree

## Tests sans écran des essais de rendu (render_diag.gd, OPENRIDE_RENDER_DIAG, 5 novembre 2026) : lecture des
## drapeaux et des réglages, qualité d'image du préréglage inchangée sans variable, puis modifiée par les essais.
## Lancement : godot --headless --path engine --script res://tests/unit/test_render_diag.gd

const RenderDiag := preload("res://scripts/render_diag.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	var d := RenderDiag.parse(" msaa=2, sans_ombres,herbe=0.5,,")
	_check(Array(d["flags"]) == ["sans_ombres"], "drapeaux lus : %s" % [d["flags"]])
	_check(d["values"] == {"msaa": "2", "herbe": "0.5"}, "réglages lus : %s" % [d["values"]])
	_check(RenderDiag.parse("")["flags"].is_empty() and RenderDiag.parse("")["values"].is_empty(), "variable vide : rien")

	var medium := QualityPresets.image("medium")
	if OS.get_environment("OPENRIDE_RENDER_DIAG") == "":
		_check(RenderQuality.diagnostic_image(medium) == medium, "sans variable : qualité d'image inchangée")
		_check(RenderDiag.number("herbe", 1.0) == 1.0, "sans variable : valeur par défaut")
	# Essai forcé après coup (la variable est lue une seule fois) : on remplit l'état comme le ferait _load.
	RenderDiag._parsed = true
	var forced := RenderDiag.parse("msaa=2,ssao=low,atlas=2048,filtre=low,ombres_2_cascades,sans_ssil,sans_brume,sans_glow")
	RenderDiag._flags = forced["flags"]
	RenderDiag._values = forced["values"]
	var img := RenderQuality.diagnostic_image(medium)
	_check(img["msaa"] == 2 and img["ssao"] == "low" and img["shadow_atlas"] == 2048 and img["shadow_filter"] == "low",
		"réglages appliqués : %s" % [img])
	_check(img["shadow_splits"] == 2 and img["ssil"] == "off" and img["fog_volumetric"] == "off" and not img["glow"],
		"drapeaux appliqués")
	_check(medium["msaa"] == 4 and medium["ssil"] == "low", "préréglage d'origine non modifié")
	print("test_render_diag : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		print("[ÉCHEC] ", msg)
