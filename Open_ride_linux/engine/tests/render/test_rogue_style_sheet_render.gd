extends SceneTree

## Rendu hors écran de la planche de démonstration du Cyber-Rogue (lot R17) : les cinq shaders compilent,
## la planche se construit dans les trois préréglages, l'image n'est pas vide et les arêtes lumineuses
## apparaissent. L'image du préréglage low est écrite dans user:// pour contrôle visuel.

const SIZE := Vector2i(640, 360)
## Fin des compilations de pipelines : compteurs du serveur de rendu inchangés depuis SETTLE_S secondes et
## SETTLE_FRAMES images, attente bornée à SETTLE_MAX_S secondes.
const SETTLE_FRAMES := 10
const SETTLE_S := 1.0
const SETTLE_MAX_S := 30.0
const PIPELINE_INFOS := [RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_CANVAS,
	RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_MESH, RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SURFACE,
	RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_DRAW,
	RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SPECIALIZATION]

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


func _pipeline_compilations() -> int:
	var total := 0
	for info in PIPELINE_INFOS:
		total += RenderingServer.get_rendering_info(info)
	return total


func _settle_pipelines() -> void:
	var start := Time.get_ticks_msec()
	var last := _pipeline_compilations()
	var since := start
	var frames := 0
	while Time.get_ticks_msec() - start < SETTLE_MAX_S * 1000.0:
		await process_frame
		var now := _pipeline_compilations()
		if now != last:
			last = now
			since = Time.get_ticks_msec()
			frames = 0
		else:
			frames += 1
		if frames >= SETTLE_FRAMES and Time.get_ticks_msec() - since >= SETTLE_S * 1000.0:
			break
	print("compilations de pipelines : %d, attente %d ms" % [last, Time.get_ticks_msec() - start])


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
	# Sortie en ordre (Godot 4.7, Forward+) : quitter pendant que Godot compile encore des pipelines en
	# arrière-plan bloque la sortie (sur la GTX 1060, au premier lancement, cache des shaders vide). Les
	# vérifications sont faites : on attend la fin des compilations avant et après la libération de la vue.
	await _settle_pipelines()
	vp.queue_free()
	await _settle_pipelines()
	print("test_rogue_style_sheet_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
