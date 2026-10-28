extends SceneTree

## Tests sans écran de la construction du ruban du Cyber-Rogue (lot R10) : longueur, pentes, tailles des
## tableaux, couleurs, marqueurs à la bonne distance, maillage valide.
## Lancement : godot --headless --path engine --script res://tests/unit/test_ribbon_builder.gd

const Builder := preload("res://scripts/rogue/ribbon_builder.gd")
const Markers := preload("res://scripts/rogue/marker_views.gd")
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


func _profile(n: int, grade: float) -> Array:
	var p: Array = []
	for i in n:
		p.append([i * 10.0, grade])
	return p


func _run() -> void:
	# 100 m à 5 % : 10 intervalles, 11 sections ; exagération 2 -> +10 m de dénivelé visible
	var sts := Builder.stations(_profile(10, 5.0), 100.0, 2.0)
	_check(sts.size() == 11, "11 sections pour 100 m (%d)" % sts.size())
	_check(is_equal_approx(sts[10].x, 100.0), "dernière section à la fin de la salle")
	_check(is_equal_approx(sts[10].y, 10.0), "100 m à 5 % exagéré ×2 : +10 m (%.2f)" % sts[10].y)
	_check(is_equal_approx(Builder.y_at(sts, 50.0), 5.0), "interpolation à 50 m : 5 m")
	_check(Builder.y_at(sts, -5.0) == 0.0 and is_equal_approx(Builder.y_at(sts, 500.0), 10.0), "bornée aux extrémités")
	var down := Builder.stations(_profile(5, -4.0), 50.0, 1.0)
	_check(is_equal_approx(down[5].y, -2.0), "descente de 4 % sur 50 m : −2 m")
	var flat := Builder.stations([], 80.0)
	_check(flat.size() == 2 and flat[1].x == 80.0, "profil vide : ruban plat de la longueur de la salle")
	# tableaux du maillage
	var d := Builder.arrays(_profile(10, 3.0), 100.0)
	_check(d["vertices"].size() == 44 and d["colors"].size() == 44 and d["uvs"].size() == 44, "4 sommets par section")
	_check(d["triangle_count"] == 10 * 8, "8 triangles par tronçon (%d)" % d["triangle_count"])
	var max_idx := 0
	for i in d["indices"]:
		max_idx = maxi(max_idx, i)
	_check(max_idx < d["vertices"].size(), "indices dans les bornes")
	_check(is_equal_approx(d["vertices"][0].x, -3.0) and is_equal_approx(d["vertices"][1].x, 3.0), "largeur de 6 m")
	_check(is_equal_approx(d["vertices"][0].y - d["vertices"][3].y, 0.3), "épaisseur de 0,3 m")
	_check(is_equal_approx(d["vertices"][40].z, -100.0), "l'avant est −Z : section de 100 m en z = −100")
	_check(d["colors"][0].is_equal_approx(Palette.color("grade_up")), "3 % : jaune")
	var mixed := Builder.arrays([[0.0, -5.0], [10.0, 0.0], [20.0, 8.0]], 30.0)
	_check(mixed["colors"][0].is_equal_approx(Palette.color("grade_down")) and mixed["colors"][8].is_equal_approx(Palette.color("grade_wall")),
		"couleurs par tronçon : bleu puis magenta")
	var m := Builder.mesh(_profile(10, 3.0), 100.0)
	_check(m is ArrayMesh and m.get_surface_count() == 1, "ArrayMesh à une surface")
	var aabb := m.get_aabb()
	_check(absf(aabb.size.z - 100.0) < 0.01, "emprise de 100 m (%.2f)" % aabb.size.z)
	# marqueurs
	for kind in ["arch", "strike_target", "parry_zone", "pad", "purge", "tunnel", "rock", "shockwave"]:
		_check(Markers.catalog_id(kind) != "", "marqueur %s -> %s" % [kind, Markers.catalog_id(kind)])
		var node := Markers.make(kind, 30.0)
		_check(node.get_child_count() >= 1, "marqueur %s construit" % kind)
		node.free()
	var tunnel := Markers.make("tunnel", 60.0)
	_check(tunnel.get_child_count() == 6, "tunnel de 60 m : 6 anneaux espacés de 10 m (%d)" % tunnel.get_child_count())
	tunnel.free()
	var arch := Markers.make("arch", 5.0)
	Markers.set_active(arch, true)
	_check(arch.scale.x > 1.0, "fenêtre active : le marqueur grossit")
	Markers.set_active(arch, false)
	_check(arch.scale.x == 1.0, "fenêtre fermée : taille normale")
	arch.free()
	await process_frame
	print("test_ribbon_builder : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
