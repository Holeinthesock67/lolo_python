extends RefCounted

## Hôte de la scène du Cyber-Rogue (lot R10 §4.1) : instancie `rogue.tscn` comme enfant de la scène principale
## quand `state.mode` devient « ROGUE », masque le monde classique (terrain, décor, soleil, caméra) et son
## environnement, puis rend tout à la sortie. Garde les salles reçues (`room_store.gd`) même hors scène, car le
## core envoie la salle avant le premier état du mode. Pas de class_name :
## preload("res://scripts/rogue/rogue_host.gd").

const RoomStore := preload("res://scripts/rogue/room_store.gd")
const RogueEnvironment := preload("res://scripts/rogue/rogue_environment.gd")
const SCENE := preload("res://scenes/rogue.tscn")

var store = RoomStore.new()
var last_loot: Dictionary = {}
var ftp_w := 0.0                   # hello_ack.config.ftp_w
var scene = null                   # rogue_scene.gd
var resync_requests := 0          # demandes `rogue_resync` émises (lues par main.gd)
var _hidden: Array = []           # [Node3D, était visible]
var _classic_camera: Camera3D = null
var _classic_env: Environment = null
var _world_env: WorldEnvironment = null
var _rogue_env: Environment = null


func is_active() -> bool:
	return scene != null


## Pour les tests (lot X41) : {} hors du mode, sinon ce que la scène affiche et les demandes `rogue_resync`.
func test_info() -> Dictionary:
	if scene == null:
		return {}
	var info: Dictionary = scene.test_info()
	info["resync_requests"] = resync_requests
	return info


func on_room(msg: Dictionary) -> void:
	store.add_part(msg)


## Message `loot` : cartes et portes du couloir, affichées par le modèle du HUD.
func on_loot(msg: Dictionary) -> void:
	last_loot = msg
	if scene != null:
		scene.hud_model.set_loot(msg)
		scene.audio.on_loot(msg, float(Time.get_ticks_msec()) / 1000.0)


## Appelé à chaque trame `state`. `classic` : nœuds 3D du monde classique à masquer ; `world_env` et `camera`
## : environnement et caméra de la scène principale (peuvent être null dans les tests). Renvoie true si une
## demande `rogue_resync` doit être envoyée.
func update(state: Dictionary, parent: Node, classic: Array, world_env: WorldEnvironment, camera: Camera3D,
		preset: String, now_s: float) -> bool:
	var rogue = state.get("rogue", null)
	var in_rogue: bool = str(state.get("mode", "")) == "ROGUE" and typeof(rogue) == TYPE_DICTIONARY
	if in_rogue and scene == null:
		_enter(parent, classic, world_env, camera, preset)
	elif not in_rogue and scene != null:
		_leave()
	if scene == null:
		return false
	scene.resync_requested = false
	scene.on_state(rogue, now_s)
	scene.on_hud(state, now_s)
	if scene.resync_requested:
		resync_requests += 1
		return true
	return false


func _enter(parent: Node, classic: Array, world_env: WorldEnvironment, camera: Camera3D, preset: String) -> void:
	scene = SCENE.instantiate()
	scene.store = store
	scene.preset = preset
	scene.hud_model.set_ftp(ftp_w)
	scene.hud_model.set_loot(last_loot)
	parent.add_child(scene)
	for n in classic:
		if n is Node3D:
			_hidden.append([n, n.visible])
			n.visible = false
	_classic_camera = camera
	_world_env = world_env
	if world_env != null:
		_classic_env = world_env.environment
		_rogue_env = Environment.new()
		RogueEnvironment.apply(_rogue_env, preset)
		world_env.environment = _rogue_env


func _leave() -> void:
	if scene != null:
		scene.queue_free()
		scene = null
	for pair in _hidden:
		if is_instance_valid(pair[0]):
			pair[0].visible = pair[1]
	_hidden.clear()
	if _world_env != null and is_instance_valid(_world_env) and _classic_env != null:
		_world_env.environment = _classic_env
	if _classic_camera != null and is_instance_valid(_classic_camera) and _classic_camera.is_inside_tree():
		_classic_camera.make_current()
	_classic_env = null
	_rogue_env = null
	store.clear()
	last_loot = {}
