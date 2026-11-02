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
const INK_3D := Color(0.08, 0.08, 0.1)
const ROAD_GREY := Color(0.42, 0.42, 0.45)
const ASPHALT := Color(0.25, 0.25, 0.28)
const EARTH := Color(0.45, 0.32, 0.2)

static var _cache: Dictionary = {}   # maillages fusionnés partagés (vache, chef)

var _view: Dictionary = {}
var _pools: Dictionary = {}   # kind -> Array[MeshInstance3D]
var _used: Dictionary = {}    # kind -> nombre utilisé à cette image
var _skin_nodes: Dictionary = {}   # bot -> MeshInstance3D
var _tint_layer: CanvasLayer
var _tint: ColorRect
var _roll := 0.0              # roulis appliqué (degrés)
var _cam_blend := 0.0         # 0 : vue normale ; 1 : vue imposée
var _cam_mode := ""
var _rider_scale := 1.0
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


## Taille du cycliste (vélo minuscule), amenée en BLEND_S comme les vues imposées.
func rider_scale() -> float:
	return _rider_scale


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


## Forme et couleur de chaque sorte d'objet (charte cartoon des maquettes). Les objets à plusieurs pièces
## (vache, chef sur son vélo, vaisselle) sont fusionnés en un seul maillage à couleurs par sommet : un appel
## de dessin par objet, quel que soit le nombre de pièces.
static func _make(kind: String) -> MeshInstance3D:
	var mesh: Mesh
	var color := Color.WHITE
	match kind:
		"chunk":
			mesh = _merge([
				[_box(Vector3(4.0, 0.6, WtfSceneModel.CHUNK_M * 0.95)), Vector3.ZERO, ROAD_GREY],
				[_box(Vector3(4.05, 0.05, WtfSceneModel.CHUNK_M * 0.95)), Vector3(0.0, 0.31, 0.0), ASPHALT],
				[_box(Vector3(0.15, 0.06, WtfSceneModel.CHUNK_M * 0.6)), Vector3(0.0, 0.33, 0.0), Color.WHITE],
				[_box(Vector3(3.6, 1.2, WtfSceneModel.CHUNK_M * 0.8)), Vector3(0.0, -0.85, 0.0), EARTH]])
		"void":
			# Gouffre : bande sombre posée sur la route derrière le front, bords de terre.
			var half := WtfSceneModel.VOID_LENGTH_M * 0.5
			mesh = _merge([
				[_box(Vector3(7.0, 0.05, WtfSceneModel.VOID_LENGTH_M)), Vector3(0.0, 0.03, half), Color(0.04, 0.03, 0.05)],
				[_box(Vector3(7.2, 0.3, 0.5)), Vector3(0.0, 0.0, 0.25), EARTH]])
		"cheese":
			var c := CylinderMesh.new()
			c.top_radius = WtfSceneModel.CHEESE_RADIUS_M
			c.bottom_radius = WtfSceneModel.CHEESE_RADIUS_M
			c.height = 1.2
			var r := WtfSceneModel.CHEESE_RADIUS_M
			var label := CylinderMesh.new()
			label.top_radius = r * 0.45
			label.bottom_radius = r * 0.45
			label.height = 1.24
			var rind := CylinderMesh.new()
			rind.top_radius = r * 1.02
			rind.bottom_radius = r * 1.02
			rind.height = 1.0
			mesh = _merge([[c, Basis(Vector3.FORWARD, PI / 2.0), WtfHudModel.YELLOW],
				[rind, Basis(Vector3.FORWARD, PI / 2.0), Color(0.9, 0.55, 0.1)],
				[label, Basis(Vector3.FORWARD, PI / 2.0), Color(0.85, 0.12, 0.12)],
				[_ball(0.25), Vector3(0.5, r * 0.4, r * 0.3), Color(0.85, 0.7, 0.1)],
				[_ball(0.2), Vector3(-0.5, -r * 0.3, r * 0.5), Color(0.85, 0.7, 0.1)],
				[_ball(0.3), Vector3(0.5, -r * 0.5, -r * 0.2), Color(0.85, 0.7, 0.1)]])
		"cow":
			mesh = _cow_mesh()
		"tornado":
			var c := CylinderMesh.new()
			c.top_radius = 9.0
			c.bottom_radius = 1.5
			c.height = 18.0
			c.cap_top = false
			c.cap_bottom = false
			mesh = c
			color = Color(0.32, 0.32, 0.4, 0.55)
		"ball":
			var s := SphereMesh.new()
			s.radius = WtfSceneModel.KATA_BALL_M   # × scale = taille de la boule (posée au sol, sans s'y enfoncer)
			s.height = 2.0 * WtfSceneModel.KATA_BALL_M
			mesh = s
			color = WtfHudModel.PINK
		"fish":
			mesh = _merge([[_ball(0.25, 0.9), Basis(Vector3.RIGHT, PI / 2.0), WtfHudModel.CYAN],
				[_box(Vector3(0.05, 0.4, 0.3)), Vector3(0.0, 0.0, 0.55), WtfHudModel.ORANGE],
				[_ball(0.06), Vector3(0.12, 0.08, -0.3), INK_3D]])
		"plate":
			var c := CylinderMesh.new()
			c.top_radius = 2.6
			c.bottom_radius = 2.0
			c.height = 0.25
			var rim := CylinderMesh.new()
			rim.top_radius = 1.9
			rim.bottom_radius = 1.9
			rim.height = 0.05
			mesh = _merge([[c, Vector3(0.0, 0.13, 0.0), Color.WHITE], [rim, Vector3(0.0, 0.27, 0.0), WtfHudModel.CYAN]])
		"fork":
			var parts := [[_box(Vector3(0.35, 0.12, 4.0)), Vector3(0.0, 0.06, 1.0), Color(0.82, 0.84, 0.9)],
				[_box(Vector3(1.0, 0.12, 0.6)), Vector3(0.0, 0.06, -1.2), Color(0.82, 0.84, 0.9)]]
			for i in 4:
				parts.append([_box(Vector3(0.12, 0.12, 1.4)), Vector3(-0.42 + i * 0.28, 0.06, -2.2), Color(0.82, 0.84, 0.9)])
			mesh = _merge(parts)
		"cup":
			var c := CylinderMesh.new()
			c.top_radius = 1.0
			c.bottom_radius = 0.8
			c.height = 1.8
			var handle := TorusMesh.new()
			handle.inner_radius = 0.35
			handle.outer_radius = 0.6
			var coffee := CylinderMesh.new()
			coffee.top_radius = 0.92
			coffee.bottom_radius = 0.92
			coffee.height = 0.05
			mesh = _merge([[c, Vector3(0.0, 0.9, 0.0), WtfHudModel.ORANGE],
				[handle, Transform3D(Basis(Vector3.FORWARD, PI / 2.0), Vector3(1.05, 1.0, 0.0)), WtfHudModel.ORANGE],
				[coffee, Vector3(0.0, 1.62, 0.0), Color(0.35, 0.2, 0.1)]])
		"chef":
			mesh = _chef_mesh()
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
				if kind == "kata_cow":
					mesh = _cow_mesh()
			else:
				return null
	var node := MeshInstance3D.new()
	node.name = "Wtf_" + kind
	node.mesh = mesh
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_PER_VERTEX
	if mesh is ArrayMesh and (mesh as ArrayMesh).surface_get_format(0) & Mesh.ARRAY_FORMAT_COLOR:
		mat.vertex_color_use_as_albedo = true
	if color.a < 1.0:
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	node.material_override = mat
	return node


## Vache cartoon (face vers −Z) : corps blanc à taches noires, tête, museau rose, cornes, pattes, queue.
static func _cow_mesh() -> ArrayMesh:
	if _cache.has("cow"):
		return _cache["cow"]
	var parts := [[_box(Vector3(0.7, 0.6, 1.2)), Vector3(0.0, 0.75, 0.0), Color.WHITE],
		[_box(Vector3(0.72, 0.3, 0.35)), Vector3(0.0, 0.85, 0.2), INK_3D],
		[_box(Vector3(0.4, 0.32, 0.3)), Vector3(0.16, 0.7, -0.3), INK_3D],
		[_box(Vector3(0.42, 0.42, 0.42)), Vector3(0.0, 0.95, -0.75), Color.WHITE],
		[_box(Vector3(0.38, 0.2, 0.15)), Vector3(0.0, 0.85, -1.0), Color(1.0, 0.6, 0.7)],
		[_box(Vector3(0.06, 0.18, 0.06)), Vector3(-0.16, 1.24, -0.75), Color(1.0, 0.95, 0.8)],
		[_box(Vector3(0.06, 0.18, 0.06)), Vector3(0.16, 1.24, -0.75), Color(1.0, 0.95, 0.8)],
		[_box(Vector3(0.05, 0.4, 0.05)), Transform3D(Basis(Vector3.RIGHT, 0.6), Vector3(0.0, 0.85, 0.7)), INK_3D]]
	for x in [-0.25, 0.25]:
		for z in [-0.45, 0.45]:
			parts.append([_box(Vector3(0.14, 0.45, 0.14)), Vector3(x, 0.225, z), Color.WHITE])
			parts.append([_box(Vector3(0.15, 0.08, 0.15)), Vector3(x, 0.04, z), INK_3D])
	_cache["cow"] = _merge(parts)
	return _cache["cow"]


## Chef cuisinier sur son vélo (face vers −Z), roulant à côté du cycliste : roues, cadre, veste blanche,
## tête, toque haute, foulard rouge.
static func _chef_mesh() -> ArrayMesh:
	if _cache.has("chef"):
		return _cache["chef"]
	var wheel := TorusMesh.new()
	wheel.inner_radius = 0.3
	wheel.outer_radius = 0.36
	var on_side := Basis(Vector3.FORWARD, PI / 2.0)
	var body := CapsuleMesh.new()
	body.radius = 0.24
	body.height = 0.8
	var hat := CylinderMesh.new()
	hat.top_radius = 0.2
	hat.bottom_radius = 0.13
	hat.height = 0.42
	var frame := Color(0.85, 0.1, 0.1)
	_cache["chef"] = _merge([
		[wheel, Transform3D(on_side, Vector3(0.0, 0.36, -0.55)), INK_3D],
		[wheel, Transform3D(on_side, Vector3(0.0, 0.36, 0.55)), INK_3D],
		[_box(Vector3(0.05, 0.05, 1.0)), Vector3(0.0, 0.62, 0.0), frame],
		[_box(Vector3(0.05, 0.5, 0.05)), Transform3D(Basis(Vector3.RIGHT, 0.3), Vector3(0.0, 0.55, 0.2)), frame],
		[_box(Vector3(0.05, 0.5, 0.05)), Transform3D(Basis(Vector3.RIGHT, -0.3), Vector3(0.0, 0.62, -0.45)), frame],
		[_box(Vector3(0.5, 0.04, 0.04)), Vector3(0.0, 0.9, -0.55), INK_3D],
		[body, Transform3D(Basis(Vector3.RIGHT, -0.35), Vector3(0.0, 1.25, -0.05)), Color.WHITE],
		[_box(Vector3(0.1, 0.5, 0.1)), Transform3D(Basis(Vector3.RIGHT, -0.9), Vector3(-0.2, 1.25, -0.35)), Color.WHITE],
		[_box(Vector3(0.1, 0.5, 0.1)), Transform3D(Basis(Vector3.RIGHT, -0.9), Vector3(0.2, 1.25, -0.35)), Color.WHITE],
		[_box(Vector3(0.12, 0.55, 0.12)), Vector3(-0.12, 0.65, 0.05), INK_3D],
		[_box(Vector3(0.12, 0.55, 0.12)), Vector3(0.12, 0.65, 0.05), INK_3D],
		[_ball(0.17), Vector3(0.0, 1.78, -0.2), Color(0.96, 0.78, 0.62)],
		[_box(Vector3(0.3, 0.08, 0.06)), Vector3(0.0, 1.72, -0.36), INK_3D],
		[hat, Vector3(0.0, 2.08, -0.18), Color.WHITE],
		[_ball(0.26, 0.3), Vector3(0.0, 2.3, -0.18), Color.WHITE],
		[_box(Vector3(0.36, 0.1, 0.3)), Vector3(0.0, 1.58, -0.18), Color(0.9, 0.1, 0.1)]])
	return _cache["chef"]


## Pièces [maillage, position ou transformation ou base, couleur] fusionnées en une surface à couleurs par
## sommet.
static func _merge(parts: Array) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for part in parts:
		var xf := Transform3D.IDENTITY
		if part[1] is Vector3:
			xf.origin = part[1]
		elif part[1] is Basis:
			xf.basis = part[1]
		else:
			xf = part[1]
		var arrays: Array = (part[0] as Mesh).surface_get_arrays(0)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
		var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		var col: Color = part[2]
		var order := idx if not idx.is_empty() else PackedInt32Array(range(verts.size()))
		for i in order:
			st.set_color(col)
			st.set_normal((xf.basis * normals[i]).normalized())
			st.add_vertex(xf * verts[i])
	return st.commit()


static func _ball(radius: float, height := -1.0) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = radius
	s.height = 2.0 * radius if height < 0.0 else height
	s.radial_segments = 12
	s.rings = 6
	return s


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
	var want_scale := float(_view.get("rider_scale", 1.0)) if is_active() else 1.0
	_rider_scale = move_toward(_rider_scale, want_scale, delta / BLEND_S)
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
	# Bonds sur la Lune : la caméra suit la plus grande part du bond, le cycliste reste sous le bandeau du HUD.
	camera.global_position += Vector3.UP * hop_m() * WtfSceneModel.FOLLOW_HOP
	if absf(_roll) > 0.01:
		camera.rotate_object_local(Vector3.FORWARD, deg_to_rad(_roll))


## Pose de la vue imposée : pigeon (au-dessus et derrière, qui plane), escargot (au ras du bord de la route,
## devant), roue (contre la roue avant), vélo minuscule (à hauteur de fourmi, cycliste réduit), meule (de biais, depuis le bas-côté gauche), fuite (devant
## le cycliste, tournée vers la route qui s'effondre derrière lui).
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
			eye = pos - fwd * 1.8 + right * 0.15 + Vector3.UP * 0.5
			look = pos + fwd * 5.0 + Vector3.UP * 0.25
		"cheese":
			eye = pos + fwd * 3.0 - right * 6.0 + Vector3.UP * 2.4
			look = pos - fwd * 4.0 + Vector3.UP * 1.0
		"flee":
			eye = pos + fwd * 5.0 + right * 1.6 + Vector3.UP * 2.6
			look = pos - fwd * 10.0
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
