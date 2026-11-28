extends SceneTree

## Tests unitaires sans écran de la préparation des graphismes (graphics_prep.gd et shader_warm.prime, lot PG1).
## Lancement : godot --headless --path engine --script res://tests/unit/test_graphics_prep.gd

const ShaderWarm := preload("res://scripts/shader_warm.gd")
const GraphicsPrep := preload("res://scripts/graphics_prep.gd")
const Catalog := preload("res://scripts/graphics_catalog.gd")
const PerfProbe := preload("res://scripts/perf_probe.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _proxy(tag: String) -> MeshInstance3D:
	var sh := Shader.new()
	sh.code = "shader_type spatial;\n// %s\nvoid fragment() { ALBEDO = vec3(0.3); }\n" % tag
	var m := ShaderMaterial.new()
	m.shader = sh
	var mi := MeshInstance3D.new()
	mi.mesh = BoxMesh.new()
	mi.material_override = m
	return mi


func _initialize() -> void:
	await process_frame
	var world := Node3D.new()
	root.add_child(world)
	var cam := Camera3D.new()
	world.add_child(cam)
	var warm = ShaderWarm.new()
	world.add_child(warm)
	warm.set_process(false)   # images pas à pas

	# Clé de la préparation : absente, différente ou cache vide : à faire ; écrite et cache là : rien.
	var base := "user://test_prep_%d" % Time.get_ticks_usec()
	var key_file := base + "/prepare.json"
	var cache := base + "/cache"
	_check(GraphicsPrep.needed(key_file, cache), "jamais préparé : à faire")
	GraphicsPrep.write_key(key_file)
	_check(GraphicsPrep.needed(key_file, cache), "clé écrite mais cache de shaders absent : à faire")
	DirAccess.make_dir_recursive_absolute(cache)
	_check(not GraphicsPrep.needed(key_file, cache), "clé à jour et cache là : rien à faire")
	var f := FileAccess.open(key_file, FileAccess.WRITE)
	f.store_string(JSON.stringify({"key": "autre version"}))
	f = null
	_check(GraphicsPrep.needed(key_file, cache), "version, Godot ou pilote changés : à faire")

	# prime : une doublure par couple nouveau, en file comme les autres ; un couple déjà connu est passé.
	var a := _proxy("a")
	var b := _proxy("b")
	var a2 := a.duplicate() as MeshInstance3D   # même shader que a
	var kept: int = warm.prime([a, b, a2])
	_check(kept == 2 and warm.primed_left() == 2 and warm.pending() == 2, "deux doublures gardées, une en double libérée")
	for i in range(12):
		warm.step(cam)
	_check(warm.primed_left() == 0 and warm.primed_shown == 2 and warm.pending() == 0,
		"passées une par image (%d dessinées)" % warm.primed_shown)

	# Préparation complète : la barre suit, la clé est écrite à la fin.
	DirAccess.remove_absolute(key_file)
	var prep = GraphicsPrep.new()
	prep.warm = warm
	prep.key_file = key_file
	world.add_child(prep)
	prep.set_process(false)
	var shown0: int = warm.primed_shown
	prep.start([_proxy("c"), _proxy("d"), _proxy("e")])
	_check(prep.running and prep.total == 3 and prep.get_child_count() == 1, "trois doublures, barre affichée")
	var label_ok := false
	for i in range(20):
		warm.step(cam)
		prep._process(0.0)
		if prep.running and prep._label != null and prep._label.text.contains("première fois seulement"):
			label_ok = true
	_check(label_ok and not prep.running, "texte écrit pendant la préparation, puis fin")
	# La clé n'est écrite que si toutes ont été dessinées (le compteur de warm est cumulé : 2 + 3).
	_check(warm.primed_shown - shown0 == 3 and FileAccess.file_exists(key_file), "les trois dessinées, clé écrite")

	# Séance partie avant la fin : préparation abandonnée, clé non écrite (refaite au lancement suivant).
	var warm2 = ShaderWarm.new()
	world.add_child(warm2)
	warm2.set_process(false)
	var prep2 = GraphicsPrep.new()
	prep2.warm = warm2
	prep2.key_file = base + "/prepare2.json"
	world.add_child(prep2)
	prep2.set_process(false)
	prep2.start([_proxy("f"), _proxy("g")])
	warm2.step(cam)
	warm2.set_active(false)
	prep2._process(0.0)
	_check(not prep2.running and warm2.primed_left() == 0 and warm2.primed_shown < prep2.total
		and not FileAccess.file_exists(base + "/prepare2.json"), "séance partie : abandonnée, clé non écrite")

	# Fichiers du catalogue : chargés un par un, le suivant quand la doublure d'avant est passée (banc r1097 : les
	# 49 d'un coup compilaient tout dans une image de 21 s).
	var cat_dir := base + "/catalogue"
	var cat = Catalog.new()
	cat.dir = cat_dir
	var srcs: Array = [_proxy("h"), _proxy("i"), _proxy("j")]
	for s in srcs:
		cat.record(s)
	cat.flush()
	for s in srcs:
		s.free()
	var paths: Array = Catalog.list_paths([cat_dir])
	var warm3 = ShaderWarm.new()
	world.add_child(warm3)
	warm3.set_process(false)
	var prep4 = GraphicsPrep.new()
	prep4.warm = warm3
	prep4.key_file = base + "/prepare4.json"
	world.add_child(prep4)
	prep4.set_process(false)
	prep4.start(paths)
	_check(paths.size() == 3 and prep4.running and warm3.pending() == 0, "trois fichiers, aucun chargé avant la première image")
	var most := 0
	for i in range(40):
		prep4._process(0.0)
		most = maxi(most, int(warm3.pending()))
		warm3.step(cam)
	_check(most == 1 and not prep4.running and prep4.done == 3 and FileAccess.file_exists(base + "/prepare4.json"),
		"une doublure à la fois (au plus %d en file), toutes passées, clé écrite" % most)
	for cf in DirAccess.get_files_at(cat_dir):
		DirAccess.remove_absolute(cat_dir.path_join(cf))
	DirAccess.remove_absolute(cat_dir)
	DirAccess.remove_absolute(base + "/prepare4.json")

	# Banc j26r2 : chaque image de la préparation est notée « préparation graphismes » pour la sonde (jugée comme
	# chargement par tests/perf_probe.py), plus TAIL_FRAMES images après la fin ; rien ensuite.
	var warm5 = ShaderWarm.new()
	world.add_child(warm5)
	warm5.set_process(false)
	var prep5 = GraphicsPrep.new()
	prep5.warm = warm5
	prep5.key_file = base + "/prepare5.json"
	world.add_child(prep5)
	prep5.set_process(false)
	var was_active: bool = PerfProbe.active
	PerfProbe.active = true
	PerfProbe._steps.clear()
	prep5.start([_proxy("k"), _proxy("l")])
	var marked_running := 0
	var frames_running := 0
	var marked_after := 0
	for i in range(20):
		var before: bool = prep5.running
		warm5.step(cam)
		prep5._process(0.0)
		var marked := false
		for st in PerfProbe._steps:
			if st[0] == GraphicsPrep.PROBE_KIND and st[1] == GraphicsPrep.PROBE_ID:
				marked = true
		PerfProbe._steps.clear()
		if before:
			frames_running += 1
			marked_running += int(marked)
		else:
			marked_after += int(marked)
	PerfProbe.active = was_active
	_check(frames_running > 0 and marked_running == frames_running and marked_after == GraphicsPrep.TAIL_FRAMES,
		"images de la préparation notées pour la sonde (%d sur %d, puis %d après la fin)"
		% [marked_running, frames_running, marked_after])
	DirAccess.remove_absolute(base + "/prepare5.json")

	# Catalogue vide : rien ne s'affiche.
	var prep3 = GraphicsPrep.new()
	prep3.warm = warm
	prep3.key_file = base + "/prepare3.json"
	world.add_child(prep3)
	prep3.start([])
	_check(not prep3.running and prep3.get_child_count() == 0, "catalogue vide : pas d'écran")

	DirAccess.remove_absolute(key_file)
	DirAccess.remove_absolute(cache)
	DirAccess.remove_absolute(base)
	world.free()
	print("test_graphics_prep : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
