extends Node3D

## Gags en 3D du mode « What the fuck » (série WTF, lots WTF5 et WTF6) : pose les objets de
## wtf_scene_model.gd le long de la route (tronçons qui tombent, meule de fromage, tornade de vaches, boule
## Katamari et objets à ramasser, poissons, cuisine géante, chef en tandem et ses plats, costumes des bots),
## voile de couleur sur l'image, roulis et vues de caméra imposées, soleil réglé par l'horloge.
## Formes simples (primitives) aux couleurs des maquettes, ombres coupées : coût négligeable. Les nœuds sont
## créés à la première utilisation puis réutilisés ; rien n'existe hors mode WTF.
## Ne décide rien : main.gd appelle step() puis apply_camera() une fois par image.
## Pas de class_name : preload("res://scripts/wtf/wtf_scene.gd").

const WtfSceneModel := preload("res://scripts/wtf/wtf_scene_model.gd")
const WtfHudModel := preload("res://scripts/wtf/wtf_hud_model.gd")

const BLEND_S := 1.0          # transitions de caméra et de roulis : 1 s au moins (cahier WTF5)
const SKIN_HEIGHT_M := 1.2

var _view: Dictionary = {}
var _pools: Dictionary = {}   # kind -> Array[MeshInstance3D]
var _used: Dictionary = {}    # kind -> nombre utilisé à cette image
var _skin_nodes: Dictionary = {}   # bot -> MeshInstance3D
var _tint_layer: CanvasLayer
var _tint: ColorRect
var _roll := 0.0              # roulis appliqué (degrés)
var _cam_blend := 0.0         # 0 : vue normale ; 1 : vue imposée
var _cam_mode := ""
var _sun_base := Vector3.INF  # rotation du soleil avant la règle de l'horloge


func _init() -> void:
	name = "WtfScene"
	_tint_layer = CanvasLayer.new()
	_tint_layer.layer = 0     # sous le HUD, au-dessus de la vue 3D
	_tint = ColorRect.new()
	_tint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tint.set_anchors_preset(Control.PRESET_FULL_RECT)
	_tint.color = Color(0, 0, 0, 0)
	_tint.visible = false
	_tint_layer.add_child(_tint)
	add_child(_tint_layer)


func is_active() -> bool:
	return bool(_view.get("active", false))


## Bond du vélo sur la Lune (m), à ajouter à la position de l'avatar.
func hop_m() -> float:
	return float(_view.get("hop_m", 0.0))


## Une fois par image. `route` : route_data.gd ; `s_route` : distance du cycliste ; `bot_anchor` : Callable
## (id -> Vector3 ou null) des bots affichés ; `sun` : lumière du soleil (règle de l'horloge).
func step(view: Dictionary, route, s_route: float, bot_anchor: Callable, sun: DirectionalLight3D) -> void:
	_view = view
	_used.clear()
	var active := is_active()
	visible = active
	var tint: Color = view.get("tint", Color(0, 0, 0, 0))
	_tint.color = tint
	_tint.visible = active and tint.a > 0.0
	if active and route != null:
		for p in view.get("props", []):
			_place(p, route, s_route)
	for kind in _pools:
		var pool: Array = _pools[kind]
		for i in range(int(_used.get(kind, 0)), pool.size()):
			pool[i].visible = false
	_skins(view.get("skins", {}) if active else {}, str(view.get("attack", "")), bot_anchor)
	_sun(float(view.get("sun_hour", -1.0)) if active else -1.0, sun)


func _place(p: Dictionary, route, s_route: float) -> void:
	var kind := str(p["kind"])
	var node := _take(kind)
	if node == null:
		return
	var s: float = route.wrap_s(s_route + float(p["ds"]))
	var heading := deg_to_rad(float(route.sample_heading_deg(s)))
	var right := Vector3(cos(heading), 0.0, sin(heading))
	node.global_position = route.sample_point(s) + right * float(p["lateral"]) + Vector3.UP * float(p["up"])
	node.rotation = Vector3(0.0, -heading, 0.0)
	var spin := float(p["spin"])
	match kind:
		"cheese", "ball":
			node.rotate_object_local(Vector3.RIGHT, spin)
		"cow", "fish", "tornado":
			node.rotate_object_local(Vector3.UP, spin)
	node.scale = Vector3.ONE * maxf(float(p["scale"]), 0.01)
	node.visible = true


func _take(kind: String) -> MeshInstance3D:
	var pool: Array = _pools.get(kind, [])
	var i := int(_used.get(kind, 0))
	if i >= pool.size():
		var node := _make(kind)
		if node == null:
			return null
		add_child(node)
		pool.append(node)
		_pools[kind] = pool
	_used[kind] = i + 1
	return pool[i]


## Forme et couleur de chaque sorte d'objet (charte cartoon des maquettes).
static func _make(kind: String) -> MeshInstance3D:
	var mesh: Mesh
	var color := Color.WHITE
	match kind:
		"chunk":
			mesh = _box(Vector3(4.0, 0.6, WtfSceneModel.CHUNK_M * 0.95))
			color = Color(0.35, 0.35, 0.38)
		"cheese":
			var c := CylinderMesh.new()
			c.top_radius = WtfSceneModel.CHEESE_RADIUS_M
			c.bottom_radius = WtfSceneModel.CHEESE_RADIUS_M
			c.height = 1.0
			mesh = c
			color = WtfHudModel.YELLOW
		"cow":
			mesh = _box(Vector3(0.6, 0.7, 1.2))
			color = Color(0.95, 0.95, 0.95)
		"tornado":
			var c := CylinderMesh.new()
			c.top_radius = 9.0
			c.bottom_radius = 1.5
			c.height = 18.0
			mesh = c
			color = Color(0.55, 0.55, 0.62, 0.45)
		"ball":
			var s := SphereMesh.new()
			s.radius = WtfSceneModel.KATA_BALL_M   # × scale = taille de la boule (posée au sol, sans s'y enfoncer)
			s.height = 2.0 * WtfSceneModel.KATA_BALL_M
			mesh = s
			color = WtfHudModel.PINK
		"fish":
			var s := SphereMesh.new()
			s.radius = 0.25
			s.height = 0.9
			mesh = s
			color = WtfHudModel.CYAN
		"plate":
			var c := CylinderMesh.new()
			c.top_radius = 1.0
			c.bottom_radius = 0.8
			c.height = 0.08
			mesh = c
			color = Color.WHITE
		"fork":
			mesh = _box(Vector3(0.08, 0.04, 1.0))
			color = Color(0.8, 0.82, 0.86)
		"cup":
			var c := CylinderMesh.new()
			c.top_radius = 0.4
			c.bottom_radius = 0.32
			c.height = 0.8
			mesh = c
			color = WtfHudModel.ORANGE
		"chef":
			var c := CapsuleMesh.new()
			c.radius = 0.35
			c.height = 1.8
			mesh = c
			color = Color.WHITE
		_:
			if kind.begins_with("dish_"):
				var s := SphereMesh.new()
				s.radius = 0.3
				s.height = 0.4
				mesh = s
				color = {"dish_spaghetti": WtfHudModel.YELLOW, "dish_jelly": WtfHudModel.GREEN,
					"dish_musette": WtfHudModel.PURPLE, "dish_souffle": Color(1.0, 0.9, 0.6),
					"dish_chili": Color(0.9, 0.1, 0.1)}.get(kind, WtfHudModel.PINK)
			elif kind.begins_with("kata_"):
				mesh = _box(Vector3(1.0, 1.0, 1.0))
				color = {"kata_apple": Color(0.9, 0.15, 0.15), "kata_sign": WtfHudModel.YELLOW,
					"kata_cow": Color.WHITE, "kata_car": WtfHudModel.CYAN, "kata_house": WtfHudModel.ORANGE,
					"kata_church": WtfHudModel.PURPLE}.get(kind, WtfHudModel.GREEN)
			else:
				return null
	var node := MeshInstance3D.new()
	node.name = "Wtf_" + kind
	node.mesh = mesh
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_PER_VERTEX
	if color.a < 1.0:
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	node.material_override = mat
	return node


static func _box(size: Vector3) -> BoxMesh:
	var b := BoxMesh.new()
	b.size = size
	return b


## Costumes des bots (règle du peloton) : une forme colorée au-dessus de chaque bot, rouge vif pour la mamie
## qui attaque.
func _skins(skins: Dictionary, attack: String, bot_anchor: Callable) -> void:
	for id in _skin_nodes:
		_skin_nodes[id].visible = false
	if skins.is_empty() or not bot_anchor.is_valid():
		return
	for id in skins:
		var at = bot_anchor.call(str(id))
		if not (at is Vector3):
			continue
		if not _skin_nodes.has(id):
			var node := _skin_mesh(str(skins[id]))
			add_child(node)
			_skin_nodes[id] = node
		var n: MeshInstance3D = _skin_nodes[id]
		n.global_position = at + Vector3.UP * SKIN_HEIGHT_M
		(n.material_override as StandardMaterial3D).emission_enabled = str(id) == attack
		n.visible = true


static func _skin_mesh(skin: String) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = "WtfSkin_" + skin
	var color := WtfHudModel.PINK
	match skin:
		"tractor":
			node.mesh = _box(Vector3(1.4, 1.2, 2.2))
			color = WtfHudModel.GREEN
		"bathtub":
			node.mesh = _box(Vector3(0.9, 0.5, 1.8))
			color = Color.WHITE
		"whale":
			var s := SphereMesh.new()
			s.radius = 1.6
			s.height = 2.4
			node.mesh = s
			color = WtfHudModel.CYAN
		_:   # mamie en vélo hollandais : un chapeau fleuri
			var c := CylinderMesh.new()
			c.top_radius = 0.2
			c.bottom_radius = 0.4
			c.height = 0.3
			node.mesh = c
			color = WtfHudModel.PURPLE
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.emission = Color(1.0, 0.2, 0.2)
	mat.emission_energy_multiplier = 2.0
	node.material_override = mat
	return node


## Soleil réglé par l'horloge (règle « la cadence pilote le monde ») ; rendu tel quel sans la règle.
func _sun(hour: float, sun: DirectionalLight3D) -> void:
	if sun == null:
		return
	if hour < 0.0:
		if _sun_base != Vector3.INF:
			sun.rotation = _sun_base
			_sun_base = Vector3.INF
		return
	if _sun_base == Vector3.INF:
		_sun_base = sun.rotation
	var elev := WtfSceneModel.sun_elevation_deg(hour)
	sun.rotation = Vector3(deg_to_rad(-maxf(elev, 2.0)), deg_to_rad(fposmod(hour, 24.0) * 15.0), 0.0)


## Après la caméra de la séance : roulis du monde à l'envers et vues imposées (pigeon, escargot, roue, vélo
## minuscule), toujours amenés en BLEND_S. `pos` : point de la route sous le cycliste, `heading` en radians.
func apply_camera(camera: Camera3D, pos: Vector3, heading: float, delta: float) -> void:
	var want_roll := float(_view.get("roll_deg", 0.0)) if is_active() else 0.0
	_roll = move_toward(_roll, want_roll, 180.0 * delta / BLEND_S)
	var mode := str(_view.get("camera", "")) if is_active() else ""
	if mode != "":
		_cam_mode = mode
	_cam_blend = move_toward(_cam_blend, 1.0 if mode != "" else 0.0, delta / BLEND_S)
	if _cam_blend > 0.0 and _cam_mode != "":
		var goal := camera_goal(_cam_mode, pos, heading, Time.get_ticks_msec() / 1000.0)
		camera.global_transform = camera.global_transform.interpolate_with(goal, smoothstep(0.0, 1.0, _cam_blend))
	elif _cam_blend <= 0.0:
		_cam_mode = ""
	if absf(_roll) > 0.01:
		camera.rotate_object_local(Vector3.FORWARD, deg_to_rad(_roll))


## Pose de la vue imposée : pigeon (au-dessus et derrière, qui plane), escargot (au ras du bord de la route,
## devant), roue (contre la roue avant), vélo minuscule (à hauteur de fourmi).
static func camera_goal(mode: String, pos: Vector3, heading: float, t: float) -> Transform3D:
	var fwd := Vector3(sin(heading), 0.0, -cos(heading))
	var right := Vector3(cos(heading), 0.0, sin(heading))
	var eye := pos
	var look := pos + Vector3.UP
	match mode:
		"pigeon":
			eye = pos - fwd * 6.0 + Vector3.UP * (11.0 + 0.6 * sin(t * 2.0)) + right * 2.0 * sin(t * 0.7)
		"snail":
			eye = pos + fwd * 7.0 + right * 2.6 + Vector3.UP * 0.12
			look = pos + Vector3.UP * 0.9
		"wheel":
			eye = pos + fwd * 0.55 + right * 0.18 + Vector3.UP * 0.4
			look = eye + fwd * 10.0
		"tiny":
			eye = pos - fwd * 1.2 + Vector3.UP * 0.25
			look = pos + fwd * 6.0 + Vector3.UP * 0.2
	return Transform3D(Basis.looking_at(look - eye, Vector3.UP), eye)


## Vrai pendant une vue imposée (pigeon, escargot, roue, vélo minuscule), transition comprise.
func forced_camera() -> bool:
	return _cam_blend > 0.0 and _cam_mode != ""


## Pour les tests et le banc : ce qui est affiché.
func test_info() -> Dictionary:
	var shown := {}
	for kind in _pools:
		var c := 0
		for n in _pools[kind]:
			if n.visible:
				c += 1
		if c > 0:
			shown[kind] = c
	return {"active": is_active(), "props": shown, "tint": _tint.visible, "roll_deg": _roll,
		"camera": _cam_mode if _cam_blend > 0.0 else "", "skins": _skin_nodes.values().filter(func(n): return n.visible).size()}
