extends SceneTree

## Maillages des avatars construits pendant que le fil principal crée les siens (CI du 7 novembre) : les
## tableaux de sommets se calculent dans un fil de travail (avatar_view.gd request_parts), les ArrayMesh se
## créent sur le fil principal. Avant, le fil de travail créait lui-même ses ArrayMesh et, sans écran, le
## serveur de rendu factice se corrompait de temps en temps (« Initializing already initialized RID »,
## « Parameter "mem" is null », « unimplemented base type encountered in renderer scene cull »), au hasard
## des tests qui montrent des cyclistes du décor ou des bots. Ce test provoque le croisement à coup sûr :
## 40 tours de 8 demandes en fil de travail pendant que le fil principal crée 400 maillages ; le lanceur
## (run_engine_tests.sh) le fait échouer sur la moindre ligne ERROR de Godot.
## Lancement : godot --headless --path engine --script res://tests/unit/test_avatar_parts_threads.gd

const AvatarView := preload("res://scripts/avatar_view.gd")
const AvatarModel := preload("res://scripts/avatar_model.gd")
const AvatarMesh := preload("res://scripts/avatar_mesh.gd")
const EquipmentMeshes := preload("res://scripts/equipment_meshes.gd")

const ROUNDS := 40
const PER_ROUND := 8
const MAIN_MESHES := 400

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _settings(n: int) -> Dictionary:
	var st: Dictionary = AvatarModel.DEFAULTS.duplicate()
	st["kit_primary"] = n % AvatarModel.KIT_COLORS.size()
	st["kit_secondary"] = (n * 5 + n / 8 * 3) % AvatarModel.KIT_COLORS.size()
	st["hair_color"] = (n / 8) % AvatarModel.HAIR_COLORS.size()
	st["skin"] = n % AvatarModel.SKIN_COLORS.size()
	return st


func _init() -> void:
	var lk: Dictionary = EquipmentMeshes.DEFAULT_LOOK.duplicate()
	# 1. Le calcul du fil de travail ne crée aucune ressource du serveur de rendu
	var arrays := AvatarMesh.build_arrays(0, AvatarMesh.dims(AvatarModel.DEFAULTS), lk)
	var only_arrays := true
	for part in arrays:
		only_arrays = only_arrays and arrays[part]["mesh"] is Array
	_check(only_arrays and arrays.size() > 10, "build_arrays : %d pièces, des tableaux de sommets et aucun maillage" % arrays.size())

	# 2. Mêmes maillages que la construction directe
	var direct := AvatarMesh.build(0, AvatarMesh.dims(AvatarModel.DEFAULTS), lk)
	var via := AvatarMesh.to_meshes(arrays)
	var same := direct.size() == via.size()
	for part in direct:
		same = same and via.has(part) and int(via[part]["count"]) == int(direct[part]["count"]) \
			and AvatarMesh.triangles_of(via[part]["mesh"]) == AvatarMesh.triangles_of(direct[part]["mesh"])
	_check(same, "to_meshes(build_arrays) : mêmes pièces, mêmes nombres et mêmes triangles que build")

	# 3. Demandes en fil de travail croisées avec des maillages créés sur le fil principal
	var keep := []
	var ready := 0
	for round in range(ROUNDS):
		for i in range(PER_ROUND):
			AvatarView.request_parts(i % 2, _settings(round * PER_ROUND + i), lk)
		for k in range(MAIN_MESHES):
			var m := BoxMesh.new()
			m.size = Vector3(0.1, 0.1, 0.1 + k * 0.001)
			var mi := MeshInstance3D.new()
			mi.mesh = m
			root.add_child(mi)
			keep.append(mi)
		AvatarView.wait_parts()
		for i in range(PER_ROUND):
			if AvatarView.parts_ready(i % 2, _settings(round * PER_ROUND + i), lk):
				ready += 1
	_check(ready == ROUNDS * PER_ROUND, "%d demandes sur %d prêtes après wait_parts" % [ready, ROUNDS * PER_ROUND])

	# 4. Avatars configurés depuis ces tableaux : maillages créés sur le fil principal et affichés
	var view := AvatarView.new()
	root.add_child(view)
	view.configure(_settings(3), 1)
	var info: Dictionary = view.test_info()
	_check(int(info["nodes"]) > 10 and int(info["triangles"]) > 0,
		"avatar configuré depuis les tableaux du fil de travail : %d nœuds, %d triangles" % [info["nodes"], info["triangles"]])
	view.free()
	for n in keep:
		n.free()

	print("test_avatar_parts_threads : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
