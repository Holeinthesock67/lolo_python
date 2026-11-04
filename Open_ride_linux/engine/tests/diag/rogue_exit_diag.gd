extends SceneTree

## Diagnostic temporaire (fil « Corriger l'échec du test de rendu rogue ») : même déroulé que
## tests/render/test_rogue_style_sheet_render.gd, avec des parties retirées selon les arguments après « -- » :
## nolabels, noglow, nofog, noeffect, nopresets (low seulement), waitfree (30 images après la libération).
## Sert à trouver ce qui bloque la sortie de Godot sous NVIDIA + Xvfb. Ce fichier ne reste pas dans main.

var args := PackedStringArray()


func _init() -> void:
	args = OS.get_cmdline_user_args()
	call_deferred("_run")


func _run() -> void:
	var vp := SubViewport.new()
	vp.size = Vector2i(640, 360)
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var sheet = load("res://scenes/rogue_style_sheet.tscn").instantiate()
	vp.add_child(sheet)
	if "nolabels" in args:
		for id in sheet.objects:
			for c in sheet.objects[id].get_children():
				if c is Label3D:
					c.free()
	var presets := ["low"] if "nopresets" in args else ["low", "medium", "high"]
	for preset in presets:
		sheet.set_preset(preset)
		if "noglow" in args:
			sheet._env.glow_enabled = false
		if "nofog" in args:
			sheet._env.fog_enabled = false
		for i in 5:
			await process_frame
		var img := vp.get_texture().get_image()
		print("%s : image %dx%d" % [preset, img.get_width(), img.get_height()])
	if "noeffect" not in args:
		sheet.play_effect("perfect_shift")
		await process_frame
	if "waitbefore" in args:
		for i in 30:
			await process_frame
	if "nofree" not in args:
		vp.queue_free()
	var n := 30 if "waitfree" in args else 1
	for i in n:
		await process_frame
	print("rogue_exit_diag ", " ".join(args), " : quit demandé")
	quit(0)
