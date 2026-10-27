extends SceneTree

## Rendu hors écran de la planche de démonstration du Cyber-Rogue (lot R17) : les cinq shaders compilent,
## la planche se construit dans les trois préréglages, l'image n'est pas vide et les arêtes lumineuses
## apparaissent. L'image du préréglage low est écrite dans le dossier temporaire pour contrôle visuel.

const SIZE := Vector2i(640, 360)

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


func _brightest(img: Image) -> float:
	var best := 0.0
	for y in range(0, img.get_height(), 4):
		for x in range(0, img.get_width(), 4):
			var c := img.get_pixel(x, y)
			best = maxf(best, maxf(c.r, maxf(c.g, c.b)))
	return best


func _run() -> void:
	var vp := SubViewport.new()
	vp.size = SIZE
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var sheet = load("res://scenes/rogue_style_sheet.tscn").instantiate()
	vp.add_child(sheet)
	for preset in ["low", "medium", "high"]:
		sheet.set_preset(preset)
		for i in 5:
			await process_frame
		var img := vp.get_texture().get_image()
		_check(img != null and img.get_width() == SIZE.x, "%s : image produite" % preset)
		_check(_brightest(img) > 0.4, "%s : des arêtes lumineuses apparaissent (%.2f)" % [preset, _brightest(img)])
		if preset == "low":
			img.save_png("user://rogue_style_sheet_low.png")
	sheet.set_adapted(true)
	for i in 3:
		await process_frame
	_check(sheet.objects.size() >= 20, "la planche montre %d objets" % sheet.objects.size())
	sheet.play_effect("perfect_shift")
	await process_frame
	_check(sheet.get_node("Flash").scale.x > 0.0, "un effet rejouable allume la sphère de démonstration")
	vp.queue_free()
	await process_frame
	print("test_rogue_style_sheet_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
