extends SceneTree

## Tests unitaires sans écran du compteur d'images/s du HUD (`fps_counter.gd`, réglage `render.fps`).
## Vérifie : caché par défaut et pour une valeur inconnue ; texte « N images/s · p99 M ms » mis à jour
## une fois par seconde ; p99 tiré des images de la seconde ; police d'au moins 16 px ; aucun calcul
## quand il est caché ; choix `detail` : temps CPU et GPU ajoutés à la fin de la ligne, sur une seule ligne
## dans la bande du haut, retirés en revenant à `on` ; effets coupés par le garde-fou de charge en fin de ligne.
## Lancement : godot --headless --path engine --script res://tests/unit/test_fps_counter.gd

const FpsCounter := preload("res://scripts/fps_counter.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _run() -> void:
	var c = FpsCounter.new()
	root.add_child(c)
	_check(not c.visible, "caché par défaut")
	c.add_frame(0.5)
	c.add_frame(0.6)
	_check(c.text == "", "aucun calcul quand il est caché")
	c.set_mode("on")
	_check(c.visible, "montré par « on »")
	for i in range(59):
		c.add_frame(1.0 / 60.0)
	_check(c.text == "", "texte inchangé avant une seconde")
	c.add_frame(1.0 / 60.0)
	_check(c.text == "60 images/s · p99 17 ms", "60 images régulières : « %s »" % c.text)
	# Une seconde de 50 images dont 2 saccades : le p99 les montre, la moyenne non.
	var frames: Array = []
	for i in range(48):
		frames.append(19.0)
	frames.append(60.0)
	frames.append(61.0)
	_check(FpsCounter.format(frames, 1.0) == "50 images/s · p99 61 ms", "saccades visibles dans le p99 (%s)" % FpsCounter.format(frames, 1.0))
	_check(FpsCounter.format([], 1.0) == "", "aucune image : texte vide")
	_check(FpsCounter.format_detail(4.24, 10.76) == " · CPU 4.2 ms · GPU 10.8 ms",
		"suite détaillée « %s »" % FpsCounter.format_detail(4.24, 10.76))
	c.set_mode("detail")
	_check(c.visible and c.text == "", "« detail » : montré, texte remis à zéro")
	for i in range(60):
		c.add_frame(1.0 / 60.0)
	_check(c.text.begins_with("60 images/s · p99 17 ms · CPU ") and c.text.contains(" ms · GPU ") and c.text.ends_with(" ms"),
		"ligne détaillée : « %s »" % c.text)
	_check(not c.text.contains("\n") and c.offset_bottom - c.offset_top <= 20.0 and c.offset_right - c.offset_left >= 520.0,
		"ligne détaillée sur une seule ligne dans la bande du haut")
	c.set_mode("on")
	for i in range(60):
		c.add_frame(1.0 / 60.0)
	_check(c.text == "60 images/s · p99 17 ms", "retour à « on » : temps CPU et GPU retirés (%s)" % c.text)
	# Garde-fou de charge (lot Y6) : effets coupés en fin de ligne, retirés quand tout est rendu.
	c.shed = "SSIL, SSAO"
	for i in range(60):
		c.add_frame(1.0 / 60.0)
	_check(c.text == "60 images/s · p99 17 ms · allégé : SSIL, SSAO", "effets coupés en fin de ligne : « %s »" % c.text)
	c.shed = ""
	for i in range(60):
		c.add_frame(1.0 / 60.0)
	_check(c.text == "60 images/s · p99 17 ms", "plus rien de coupé : ligne normale")
	c.set_mode("oui")
	_check(not c.visible, "valeur inconnue : caché")
	_check(c.get_theme_font_size("font_size") >= 16, "police d'au moins 16 px")
	var item := {"key": "render.fps", "type": "choice", "choices": ["off", "on", "detail"]}
	_check(SettingsViewModel.format_value(item, "on") == "oui" and SettingsViewModel.format_value(item, "off") == "non"
		and SettingsViewModel.format_value(item, "detail") == "détaillé",
		"réglage affiché « oui » / « non » / « détaillé »")
	c.queue_free()
	print("test_fps_counter : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _init() -> void:
	call_deferred("_run")
