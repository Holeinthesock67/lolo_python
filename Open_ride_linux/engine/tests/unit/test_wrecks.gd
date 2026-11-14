extends SceneTree

## Tests sans écran des épaves `wrecks.gd` (lot SM2) : coque fermée tournée vers l'extérieur, forme du navire,
## points `wreck` seuls retenus, pose (enfoncée, gîtée, même cap à chaque chargement), échelle de `length_m`,
## limite des épaves affichées et coût par image.
## Lancement : godot --headless --path engine --script res://tests/unit/test_wrecks.gd

const Wrecks := preload("res://scripts/wrecks.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _wreck(id: String, x: float, z: float, length = null) -> Dictionary:
	var p := {"id": id, "kind": "wreck", "x": x, "y": -12.0, "z": z, "radius_m": 400, "name": "Épave"}
	if length != null:
		p["length_m"] = length
	return p


func _test_hull() -> void:
	var mesh: ArrayMesh = Wrecks.hull_mesh()
	var arrays := mesh.surface_get_arrays(0)
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var aabb := mesh.get_aabb()
	_check(verts.size() > 0 and verts.size() % 3 == 0, "coque : triangles (%d sommets)" % verts.size())
	_check(absf(aabb.size.z - Wrecks.LENGTH_REF_M) < 0.01 and absf(aabb.size.x - Wrecks.BEAM_M) < 0.01,
		"coque : %.1f m de long, %.1f m de large" % [aabb.size.z, aabb.size.x])
	# Faces avant vers l'extérieur (le rendu cache les faces arrière) : Godot tient pour faces avant les triangles
	# dont (b − a) × (c − a) pointe vers l'intérieur (sens de la boîte de référence ci-dessous) ; mesuré depuis
	# l'axe du navire, à 40 % de la hauteur.
	var inward := 0
	for i in range(0, verts.size(), 3):
		var c := (verts[i] + verts[i + 1] + verts[i + 2]) / 3.0
		var n := (verts[i + 1] - verts[i]).cross(verts[i + 2] - verts[i])
		var axis := Vector3(0.0, aabb.position.y + aabb.size.y * 0.4, clampf(c.z, -15.0, 15.0))
		if n.length() > 1e-6 and n.dot(c - axis) > 0.0:
			inward += 1
			print("  face retournée : ", verts[i], verts[i + 1], verts[i + 2])
	# Même convention que les primitives de Godot (faces avant dans ce sens) : boîte de référence
	var box := BoxMesh.new()
	var ba := box.get_mesh_arrays()
	var bv: PackedVector3Array = ba[Mesh.ARRAY_VERTEX]
	var bi: PackedInt32Array = ba[Mesh.ARRAY_INDEX]
	var bn := (bv[bi[1]] - bv[bi[0]]).cross(bv[bi[2]] - bv[bi[0]])
	var box_out := bn.dot((bv[bi[0]] + bv[bi[1]] + bv[bi[2]]) / 3.0) > 0.0
	_check(inward == 0, "coque fermée : aucune face tournée vers l'intérieur (%d)" % inward)
	_check(not box_out, "sens des faces : celui des primitives de Godot (boîte de référence)")
	var mean_n := Vector3.ZERO
	for i in range(verts.size()):
		if verts[i].x > 3.5 and absf(verts[i].z) < 5.0:
			mean_n += normals[i]
	_check(mean_n.normalized().x > 0.8, "normales du flanc tribord vers +x (%s)" % str(mean_n.normalized()))
	_check(Wrecks.sheer(1.0) > Wrecks.sheer(0.3) and Wrecks.half_beam(1.0) < 0.01
		and Wrecks.half_beam(0.0) < Wrecks.half_beam(0.4),
		"étrave relevée et pointue, tableau arrière plus étroit que le maître-bau")


func _test_points() -> void:
	var w = Wrecks.new()
	root.add_child(w)
	var n0: int = w.get_child_count()
	w.set_points([_wreck("n1", 100.0, 0.0), _wreck("n2", 0.0, 300.0, 63.0),
		{"id": "n3", "kind": "wind_turbine", "x": 0.0, "y": 0.0, "z": 0.0, "radius_m": 5000, "name": null},
		_wreck("n4", 10.0, 10.0, -5.0)])
	_check(w.point_count() == 3, "points `wreck` seuls retenus (%d)" % w.point_count())
	w.update(Vector3.ZERO)
	_check(w.active_count() == 3 and w.get_child_count() == n0, "trois épaves affichées, aucun nœud créé")
	var t: Transform3D = w.wreck_transform(0)
	_check(t.origin.y < -12.0 and t.origin.y > -12.0 - Wrecks.SINK_M - 0.01,
		"épave enfoncée dans le sable (quille à %.2f m pour un fond à −12 m)" % t.origin.y)
	var up := t.basis.y.normalized()
	var heel := rad_to_deg(acos(clampf(up.y, -1.0, 1.0)))
	_check(heel > Wrecks.HEEL_DEG - 1.0 and heel < Wrecks.HEEL_DEG + Wrecks.TRIM_DEG + 1.0,
		"épave couchée sur le flanc (%.1f°)" % heel)
	var top := -INF
	for mi in w.find_children("*", "MeshInstance3D", true, false):
		if (mi as MeshInstance3D).is_visible_in_tree() and (mi as Node3D).get_parent().get_parent().position.x == 100.0:
			var box: AABB = (mi as MeshInstance3D).global_transform * (mi as MeshInstance3D).get_aabb()
			top = maxf(top, box.end.y)
	_check(top - (-12.0) > 5.0 and top - (-12.0) < 8.0,
		"navire de %.1f m au-dessus du fond (moins de 8 m : sous la surface du récif)" % (top + 12.0))
	var s2: float = w.wreck_transform(1).basis.get_scale().x
	var s4: float = w.wreck_transform(2).basis.get_scale().x
	_check(is_equal_approx(s2, 1.5) and is_equal_approx(s4, 1.0),
		"échelle de `length_m` (63 m : ×%.2f), longueur invalide remise à 42 m (×%.2f)" % [s2, s4])
	var again = Wrecks.new()
	root.add_child(again)
	again.set_points([_wreck("n1", 100.0, 0.0)])
	again.update(Vector3.ZERO)
	_check(again.wreck_transform(0).is_equal_approx(t), "même pose à chaque chargement (cap tiré de l'id)")
	var many := []
	for i in range(10):
		many.append(_wreck("m%d" % i, float(i) * 100.0, 0.0))
	w.set_points(many)
	var t0 := Time.get_ticks_usec()
	for f in range(60):
		w.update(Vector3(float(f), 0.0, 0.0))
	var per_frame_ms := float(Time.get_ticks_usec() - t0) / 60.0 / 1000.0
	_check(w.active_count() == Wrecks.MAX_ACTIVE, "10 épaves : %d affichées au plus" % Wrecks.MAX_ACTIVE)
	_check(PerfBudget.check("wrecks_frame", per_frame_ms), "mise à jour de 10 épaves en %.4f ms par image" % per_frame_ms)
	w.set_points([])
	w.update(Vector3.ZERO)
	_check(w.active_count() == 0, "parcours sans épave : rien d'affiché")
	w.queue_free()
	again.queue_free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_hull()
	_test_points()
	await process_frame   # nœuds libérés avant la sortie (sinon erreurs du serveur de rendu factice)
	print("test_wrecks : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
