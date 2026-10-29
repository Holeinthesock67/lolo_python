extends SceneTree

## Vitrine de l'écran de couloir du Cyber-Rogue (rogue_corridor_view.gd, lot R13) sans core : trois cartes aux
## textes longs du catalogue et deux portes, sur un fond de la charte, pour comparer avant et après une retouche
## et vérifier que rien ne sort de l'écran. Une capture par focus (carte, porte de gauche, porte de droite).
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_couloir.gd -- --out DOSSIER [--size 1024x600]
##
## Écrit DOSSIER/couloir_<focus>_<taille>.png ; code de sortie 1 si un bloc (carte, porte, relance) dépasse
## de l'écran.

const CorridorView := preload("res://scripts/rogue/rogue_corridor_view.gd")
const NeonPalette := preload("res://scripts/rogue/neon_palette.gd")

const CORRIDOR := {
	"cards": [
		{"name": "Terraformeur : pente douce", "kind": "terraformer", "text": "La prochaine salle perd 1 % de pente sur toutes ses montées, mais le Firewall avance 5 % plus vite."},
		{"name": "Plateau compact", "kind": "gear", "text": "Remplace le plateau : braquets plus serrés, changement parfait plus facile à réussir."},
		{"name": "Module de parade", "kind": "module", "text": "Une parade réussie rend 2 kJ de W'."},
	],
	"doors": [{"side": "left", "room_id": 3, "archetype": "grimpeur"}, {"side": "right", "room_id": 4, "archetype": "puncheur"}],
	"reroll_cost": 25, "can_reroll": true,
}
const FOCUS := {"carte": 1, "porte_gauche": 3, "porte_droite": 4}

var _out_dir := "user://vitrine_couloir"
var _size := Vector2i(1280, 720)


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--size":
			var wh := args[i + 1].split("x")
			_size = Vector2i(int(wh[0]), int(wh[1]))
	call_deferred("_run")


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	root.size = _size
	var bg := ColorRect.new()
	bg.color = NeonPalette.color("night")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(bg)
	var view = CorridorView.new()
	root.add_child(view)
	var failures := 0
	for name in FOCUS:
		var c: Dictionary = CORRIDOR.duplicate(true)
		c["focus"] = FOCUS[name]
		view.apply(c)
		for f in 6:
			await process_frame
		var visible := root.get_visible_rect()
		for ctl in view.cards + view.doors + [view.reroll]:
			var r: Rect2 = (ctl as Control).get_global_rect()
			if not visible.encloses(r):
				failures += 1
				printerr("[ÉCHEC] %s : %s sort de l'écran %s" % [name, str(r), str(visible)])
		var img := root.get_texture().get_image()
		var path := _out_dir.path_join("couloir_%s_%dx%d.png" % [name, _size.x, _size.y])
		img.save_png(path)
		print("[vitrine] %s" % path)
	print("vitrine_couloir : %d dépassement(s)" % failures)
	quit(0 if failures == 0 else 1)
