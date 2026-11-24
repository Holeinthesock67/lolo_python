extends Node3D

## Premier affichage du monde à froid (lot AC6, fil « à-coup du premier départ à froid », 24 novembre).
##
## Au tout premier lancement (installation, mise à jour du pilote : caches de shaders vides), les bancs DB1 et
## monde ouvert (rAC, rACow, 23 novembre) gardent avant le premier mètre une ou deux images de 5,4 à 6,6 s :
## la première tuile proche et ses arbres sont dessinés pour la première fois, 22 à 49 pipelines compilés dans
## la même image. Les essais au cloud (Godot 4.7.2, 24 novembre) donnent la cause et le remède :
## - un objet ajouté et dessiné dans la même image compile tout sur le fil principal (24 matériaux : 5,1 s) ;
## - un objet ajouté caché fait compiler ses pipelines « de surface » en tâche de fond, sans bloquer l'image,
##   mais son premier dessin compile encore ses pipelines « spécialisés » d'un coup s'ils sont tous dessinés
##   dans la même image (4,3 s) ;
## - dessinés un par image, ces pipelines spécialisés ne coûtent plus qu'une image de 30 à 400 ms chacun, et le
##   premier vrai dessin ne compile plus rien.
##
## Ce nœud applique ce remède aux tuiles du monde tant que la séance n'est pas partie (`active`) : la tuile (et
## ses arbres) que `world_streamer.gd` vient de créer reste cachée si un de ses couples (format de sommets,
## shader) n'a jamais été dessiné. Pour chaque couple nouveau, une doublure minuscule (même maillage, même
## matériau, mêmes ombres) est créée cachée, puis montrée devant la caméra une à la fois, une image chacune.
## La tuile réapparaît quand tous ses couples ont été dessinés. Le départ attend la fin (`pending`, compté
## dans `world_streamer.pending_count`), l'écran de chargement ou le menu restent animés entre deux images.
## Shaders déjà en cache : chaque doublure coûte une image ordinaire, la tuile réapparaît quelques images plus
## tard, sous le menu. En séance, rien n'est caché (une tuile retardée pourrait se voir apparaître).
## Pas de class_name : charger par preload("res://scripts/shader_warm.gd").

const PerfProbe := preload("res://scripts/perf_probe.gd")

## Distance de la doublure devant la caméra (m) et échelle : dans le champ, plus petite qu'un pixel.
const WARM_DIST_M := 2.0
const PROXY_SCALE := 0.001
## Images d'attente après la création de doublures cachées : leurs pipelines de surface se compilent en fond.
const SETTLE_FRAMES := 2
## Images où chaque doublure est dessinée.
const SHOW_FRAMES := 1
## Garde-fou : au-delà de ce nombre d'images sans fin (caméra absente…), tout est rendu visible.
const MAX_HOLD_FRAMES := 3600

## Faux en séance : `hold` ne cache rien et rend tout ce qui attend (main.gd).
var active := true
## Couples déjà vus : clé -> vrai (dessiné) ou faux (doublure en file).
var _known: Dictionary = {}
## Doublures en attente : [{key, node}] ; la première est montrée.
var _queue: Array = []
var _current: Dictionary = {}
var _current_left := 0
var _settle := 0
## Nœuds cachés en attente de leurs couples : [{nodes: [[GeometryInstance3D, visible d'avant]], keys: Array}].
var _held: Array = []
var _hold_frames := 0
## Doublures dessinées depuis le lancement (journal et tests).
var shown := 0


## Couples (format de sommets, shader, ombres) d'un objet dessiné : MeshInstance3D ou MultiMeshInstance3D.
## Deux matériaux du même shader (tuiles : un ShaderMaterial dupliqué par tuile) donnent la même clé.
static func keys_of(n: Node) -> Array:
	var out: Array = []
	var gi := n as GeometryInstance3D
	if gi == null:
		return out
	var mesh: Mesh = null
	var prefix := ""
	if gi is MeshInstance3D:
		mesh = (gi as MeshInstance3D).mesh
		prefix = "m"
	elif gi is MultiMeshInstance3D:
		var mm: MultiMesh = (gi as MultiMeshInstance3D).multimesh
		if mm == null:
			return out
		mesh = mm.mesh
		prefix = "mm%d%d%d" % [mm.transform_format, int(mm.use_colors), int(mm.use_custom_data)]
	if mesh == null:
		return out
	for i in range(mesh.get_surface_count()):
		var fmt: int = (mesh as ArrayMesh).surface_get_format(i) if mesh is ArrayMesh else -mesh.get_instance_id()
		out.append("%s|%d|%s|%d" % [prefix, fmt, material_key(_material_of(gi, mesh, i)), int(gi.cast_shadow)])
	return out


static func _material_of(gi: GeometryInstance3D, mesh: Mesh, surface: int) -> Material:
	if gi.material_override != null:
		return gi.material_override
	if gi is MeshInstance3D:
		var m: Material = (gi as MeshInstance3D).get_surface_override_material(surface)
		if m != null:
			return m
	return mesh.surface_get_material(surface)


## Même shader, même clé (les paramètres ne changent pas les pipelines) ; autre matériau : le sien.
static func material_key(mat: Material) -> String:
	if mat == null:
		return "-"
	var k := ""
	if mat is ShaderMaterial:
		var sh: Shader = (mat as ShaderMaterial).shader
		k = "s%d" % (sh.get_instance_id() if sh != null else 0)
	else:
		k = "b%d" % mat.get_instance_id()
	if mat.next_pass != null:
		k += "+" + material_key(mat.next_pass)
	return k


## Objets que le monde vient de créer (une tuile et ses arbres). Ceux dont un couple n'a jamais été dessiné
## restent cachés jusqu'au passage de leurs doublures. Renvoie vrai si quelque chose est caché.
func hold(nodes: Array) -> bool:
	if not active:
		return false
	var waiting: Array = []
	for n in nodes:
		if not is_instance_valid(n) or not (n is GeometryInstance3D):
			continue
		for k in keys_of(n):
			if not _known.has(k):
				_known[k] = false
				_queue.append({"key": k, "node": _make_proxy(n)})
				_settle = SETTLE_FRAMES
			if not bool(_known[k]) and not waiting.has(k):
				waiting.append(k)
	if waiting.is_empty():
		return false
	var held_nodes: Array = []
	for n in nodes:
		if is_instance_valid(n) and n is GeometryInstance3D:
			held_nodes.append([n, (n as Node3D).visible])
			(n as Node3D).visible = false
	_held.append({"nodes": held_nodes, "keys": waiting})
	return true


## Doublure cachée : même maillage et matériaux, une seule instance pour un MultiMesh, sans plage de visibilité.
func _make_proxy(n: GeometryInstance3D) -> GeometryInstance3D:
	var p: GeometryInstance3D
	if n is MultiMeshInstance3D:
		var src: MultiMesh = (n as MultiMeshInstance3D).multimesh
		var mm := MultiMesh.new()
		mm.transform_format = src.transform_format
		mm.use_colors = src.use_colors
		mm.use_custom_data = src.use_custom_data
		mm.mesh = src.mesh
		mm.instance_count = 1
		if mm.transform_format == MultiMesh.TRANSFORM_3D:
			mm.set_instance_transform(0, Transform3D.IDENTITY)
		else:
			mm.set_instance_transform_2d(0, Transform2D.IDENTITY)
		if mm.use_colors:
			mm.set_instance_color(0, Color.WHITE)
		if mm.use_custom_data:
			mm.set_instance_custom_data(0, Color(0, 0, 0, 0))
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		p = mmi
	else:
		var src_mi := n as MeshInstance3D
		var mi := MeshInstance3D.new()
		mi.mesh = src_mi.mesh
		for i in range(src_mi.get_surface_override_material_count()):
			mi.set_surface_override_material(i, src_mi.get_surface_override_material(i))
		p = mi
	p.material_override = n.material_override
	p.cast_shadow = n.cast_shadow
	p.layers = n.layers
	p.transparency = n.transparency
	p.visible = false
	p.name = "doublure"
	add_child(p, true)   # nom lisible : doublure, doublure2…
	return p


## Une image (appelée par `_process`, ou par les tests avec la caméra voulue).
func step(camera: Node3D) -> void:
	if _held.is_empty() and _queue.is_empty() and _current.is_empty():
		_hold_frames = 0
		return
	_hold_frames += 1
	if _hold_frames > MAX_HOLD_FRAMES:
		print("Préchauffage des shaders abandonné après %d images (caméra absente ?)" % MAX_HOLD_FRAMES)
		release_all()
		return
	if camera == null or not camera.is_inside_tree():
		return
	if not _current.is_empty():
		_current_left -= 1
		if _current_left > 0:
			_place(_current["node"], camera)
			return
		_finish_current()
	if _settle > 0:
		_settle -= 1
		return
	if _queue.is_empty():
		return
	var t0 := Time.get_ticks_usec()
	_current = _queue.pop_front()
	_current_left = SHOW_FRAMES
	var p: Node3D = _current["node"]
	p.visible = true
	_place(p, camera)
	shown += 1
	PerfProbe.mark("shaders", "doublure %d" % shown, (Time.get_ticks_usec() - t0) / 1000.0)


func _place(p: Node3D, camera: Node3D) -> void:
	if is_instance_valid(p) and p.is_inside_tree():
		p.global_transform = camera.global_transform * Transform3D(Basis().scaled(Vector3.ONE * PROXY_SCALE),
			Vector3(0.0, 0.0, -WARM_DIST_M))


func _finish_current() -> void:
	_known[_current["key"]] = true
	var p: Node = _current["node"]
	if is_instance_valid(p):
		p.queue_free()
	_current = {}
	_release_ready()
	if _held.is_empty() and _queue.is_empty():
		print("Préchauffage des shaders du monde : %d doublures dessinées (à %d ms)" % [shown, Time.get_ticks_msec()])


## Rend visibles les objets dont tous les couples ont été dessinés.
func _release_ready() -> void:
	var still: Array = []
	for h in _held:
		var ready := true
		for k in h["keys"]:
			if not bool(_known.get(k, true)):
				ready = false
				break
		if ready:
			_show(h)
		else:
			still.append(h)
	_held = still


func _show(h: Dictionary) -> void:
	for pair in h["nodes"]:
		if is_instance_valid(pair[0]):
			(pair[0] as Node3D).visible = bool(pair[1])


## Tout ce qui attend redevient visible, les doublures restantes sont jetées (séance partie, garde-fou).
## Leurs couples ne sont pas comptés comme dessinés : un prochain chargement les reprendra.
func release_all() -> void:
	for h in _held:
		_show(h)
	_held.clear()
	if not _current.is_empty():
		_queue.push_front(_current)
		_current = {}
	for q in _queue:
		_known.erase(q["key"])
		if is_instance_valid(q["node"]):
			(q["node"] as Node).queue_free()
	_queue.clear()
	_settle = 0
	_hold_frames = 0


func set_active(on: bool) -> void:
	if active == on:
		return
	active = on
	if not on:
		release_all()


## Objets cachés et doublures en attente : le départ attend zéro.
func pending() -> int:
	return _held.size() + _queue.size() + (0 if _current.is_empty() else 1)


func _process(_delta: float) -> void:
	step(get_viewport().get_camera_3d() if is_inside_tree() else null)
