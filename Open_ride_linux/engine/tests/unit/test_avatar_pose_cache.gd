extends SceneTree

## Lot AC3 (à-coups du décor, 21/11) : avatar_view.gd ne replace le haut du corps (buste, bras, tête, casque,
## dossard) qu'à un changement de position (assis ou en danseuse), puisque AvatarMesh.pose ne le fait dépendre que
## d'elle. Vérifie que toutes les pièces sont exactement à la même place qu'avec un haut du corps reposé à chaque
## image, pour les trois niveaux de détail, sur des tours de pédalier assis puis en danseuse.
## Lancement : godot --headless --path engine --script res://tests/unit/test_avatar_pose_cache.gd

const AvatarView := preload("res://scripts/avatar_view.gd")
const AvatarModel := preload("res://scripts/avatar_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Transformations locales de toutes les pièces de l'avatar (et du dossard), dans l'ordre des nœuds.
static func _snapshot(av: Node) -> Array:
	var out := []
	var stack: Array = [av]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n is Node3D:
			out.append([str(n.get_path()), (n as Node3D).transform, (n as Node3D).visible])
		for c in n.get_children():
			stack.append(c)
	return out


static func _same(a: Array, b: Array) -> bool:
	if a.size() != b.size():
		return false
	for i in range(a.size()):
		if not (a[i][1] as Transform3D).is_equal_approx(b[i][1]) or a[i][2] != b[i][2]:
			return false
	return true


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var settings: Dictionary = AvatarModel.DEFAULTS.duplicate()
	settings["number"] = 7
	for lod in [0, 1, 2]:
		var cached := AvatarView.new()
		var fresh := AvatarView.new()
		root.add_child(cached)
		root.add_child(fresh)
		cached.configure(settings, lod)
		fresh.configure(settings, lod)
		var same := true
		var steps := 0
		var upper0: int = cached.upper_posed
		for i in range(120):
			var standing := i >= 60 and i < 100   # assis, en danseuse, puis assis
			var angle := fposmod(i * 0.37, TAU)
			cached.apply_pose(angle, standing)
			fresh._upper_pose = -1                # comme avant le lot : haut du corps reposé à chaque image
			fresh.apply_pose(angle, standing)
			same = same and _same(_snapshot(cached), _snapshot(fresh))
			steps += 1
		_check(same, "niveau %d : %d poses identiques à un haut du corps reposé à chaque image" % [lod, steps])
		_check(cached.upper_posed - upper0 == 2,
			"niveau %d : haut du corps replacé 2 fois seulement (en danseuse, puis assis) au lieu de %d" % [lod, steps])
		cached.queue_free()
		fresh.queue_free()
	await process_frame
	print("test_avatar_pose_cache : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
