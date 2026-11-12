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
## Préchauffage (2 novembre) : banc PC du 2 novembre, premier tirage de la tornade 776 ms et du fromage 310 ms
## (premier dessin de leurs matériaux), tirages suivants ~50 ms. Un exemplaire de ces objets est dessiné,
## minuscule et 2 m devant la caméra, pendant WARM_FRAMES images. main.gd l'appelle sur l'écran d'attente du
## départ d'une séance WTF (banc du 2 novembre : fait à RUNNING, il gelait l'image ~2 s en roulant) ; step()
## le fait encore au premier état actif s'il n'a pas eu lieu (départ immédiat).
## Seulement les objets dont un banc a mesuré l'à-coup (règle du préchauffage) : en préchauffer 17 gelait
## l'écran d'attente 2 à 8 s (banc du 2 novembre), pour des gags qui ne coûtaient rien.
const WARM_KINDS := ["cheese", "cow", "tornado"]
const WARM_SKINS := []
const WARM_DIST_M := 2.0
const WARM_SCALE := 0.0005
const WARM_FRAMES := 3

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
var _warm_nodes: Array = []   # exemplaires du préchauffage, sous la caméra
var _warm_left := 0           # images restantes avant de les retirer
var _warmed := false          # préchauffage déjà fait pour cette instance


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
	if active and not _warmed and is_inside_tree():
		warm_up(get_viewport().get_camera_3d())
	else:
		tick_warm()
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


## Dessine un exemplaire des objets de WARM_KINDS sous `camera` (hors de vue) pour que le premier tirage d'un
## gag ne compile plus ses matériaux en pleine image. Renvoie le nombre d'exemplaires (0 sans caméra).
func warm_up(camera: Camera3D) -> int:
	_warmed = true
	if camera == null:
		return 0
	_drop_warm()
	var nodes: Array = []
	for kind in WARM_KINDS:
		nodes.append(_make(kind))
	for skin in WARM_SKINS:
		for lit in [false, true]:
			var sk := _skin_mesh(skin)
			(sk.material_override as StandardMaterial3D).emission_enabled = lit
			sk.name = str(sk.name) + ("_attaque" if lit else "")
			nodes.append(sk)
	for n in nodes:
		if n == null:
			continue
		n.name = "WtfWarm_" + str(n.name)
		n.position = Vector3(0.0, 0.0, -WARM_DIST_M)
		n.scale = Vector3.ONE * WARM_SCALE
		camera.add_child(n)
		_warm_nodes.append(n)
	_warm_left = WARM_FRAMES
	return _warm_nodes.size()


func warmed() -> bool:
	return _warmed


func warm_count() -> int:
	return _warm_nodes.size()


## Une image de plus pour le préchauffage ; retiré après WARM_FRAMES images.
func tick_warm() -> void:
	if _warm_left > 0:
		_warm_left -= 1
		if _warm_left == 0:
			_drop_warm()


func _drop_warm() -> void:
	for n in _warm_nodes:
		if is_instance_valid(n):
			n.queue_free()
	_warm_nodes.clear()
	_warm_left = 0


func _exit_tree() -> void:
	_drop_warm()


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
		"cheese", "ball", "chunk":
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
			# Plaque de route arrachée (lot WTF9) : bitume, bande blanche du bord, couche de gravier puis motte
			# de terre et cailloux dessous, pour qu'on lise « un morceau de route qui tombe » et pas un pavé.
			var l := WtfSceneModel.CHUNK_M * 0.9
			var parts := [[_box(Vector3(4.0, 0.12, l)), Vector3(0.0, 0.0, 0.0), ASPHALT],
				[_box(Vector3(0.18, 0.02, l * 0.9)), Vector3(1.6, 0.07, 0.0), Color.WHITE],
				[_box(Vector3(0.15, 0.02, l * 0.4)), Vector3(0.0, 0.07, 0.0), Color.WHITE],
				[_box(Vector3(3.8, 0.3, l * 0.95)), Vector3(0.0, -0.21, 0.0), Color(0.62, 0.58, 0.52)],
				[_ball(1.7, 1.6), Vector3(0.0, -0.9, 0.0), EARTH]]
			for r in [[0.45, -1.2, -1.3, -1.6], [0.35, 1.0, -1.4, 1.2], [0.3, 0.3, -1.6, 2.1], [0.4, -0.6, -1.5, 0.4]]:
				parts.append([_ball(r[0]), Vector3(r[1], r[2], r[3]), Color(0.5, 0.48, 0.45)])
			mesh = _merge(parts)
		"void":
			# Gouffre derrière le front : fond noir, parois de terre et de roche visibles, lèvre de bitume
			# déchiquetée côté cycliste (dents), fissures sur la route encore debout devant le front.
			var half := WtfSceneModel.VOID_LENGTH_M * 0.5
			var parts := [
				[_box(Vector3(7.0, 0.05, WtfSceneModel.VOID_LENGTH_M)), Vector3(0.0, 0.03, half), Color(0.03, 0.02, 0.04)],
				[_box(Vector3(6.6, 0.06, WtfSceneModel.VOID_LENGTH_M)), Vector3(0.0, 0.04, half + 1.5), Color(0.0, 0.0, 0.0)],
				[_box(Vector3(0.6, 0.12, WtfSceneModel.VOID_LENGTH_M)), Vector3(-3.4, 0.06, half), EARTH],
				[_box(Vector3(0.6, 0.12, WtfSceneModel.VOID_LENGTH_M)), Vector3(3.4, 0.06, half), EARTH],
				[_box(Vector3(7.0, 0.07, 1.2)), Vector3(0.0, 0.05, 0.6), Color(0.3, 0.2, 0.12)]]
			for i in 9:
				# Dents de bitume en lèvre du trou, une sur deux plus longue.
				var w := 0.75
				parts.append([_box(Vector3(w * 0.8, 0.08, 0.5 + 0.5 * (i % 2))), Transform3D(Basis(Vector3.UP, 0.35 * (i % 3 - 1)),
					Vector3(-3.0 + i * w, 0.07, 0.15)), ASPHALT])
			for c in [[-1.6, -1.5, 0.4], [0.4, -2.6, -0.3], [1.9, -1.2, 0.5], [-0.6, -3.6, 0.2], [1.1, -4.4, -0.4]]:
				# Fissures noires en zigzag sur la route devant le front (−Z : vers le cycliste).
				parts.append([_box(Vector3(0.09, 0.03, 1.6)), Transform3D(Basis(Vector3.UP, c[2]), Vector3(c[0], 0.05, c[1])), INK_3D])
			mesh = _merge(parts)
		"cheese":
			# Meule (axe vers la droite) : pâte jaune, croûte orangée sur la tranche, trous ronds peints à plat
			# sur les deux faces (disques plus sombres, à peine en saillie).
			var r := WtfSceneModel.CHEESE_RADIUS_M
			var c := CylinderMesh.new()
			c.top_radius = r
			c.bottom_radius = r
			c.height = 1.2
			var rind := CylinderMesh.new()
			rind.top_radius = r * 1.02
			rind.bottom_radius = r * 1.02
			rind.height = 1.0
			var axis := Basis(Vector3.FORWARD, PI / 2.0)
			var parts := [[c, axis, WtfHudModel.YELLOW], [rind, axis, Color(0.9, 0.55, 0.1)]]
			for side in [-1.0, 1.0]:
				for h in [[0.35, 0.8, 0.5], [0.22, -0.9, 0.7], [0.28, -0.3, -1.0], [0.18, 1.0, -0.6], [0.14, 0.2, -0.1]]:
					var hole := CylinderMesh.new()
					hole.top_radius = h[0]
					hole.bottom_radius = h[0]
					hole.height = 0.02
					hole.radial_segments = 16
					parts.append([hole, Transform3D(axis, Vector3(side * 0.605, h[1], h[2])), Color(0.82, 0.62, 0.05)])
			mesh = _merge(parts)
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
			mesh = _kata_ball_mesh()
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
				mesh = _dish_mesh(kind.trim_prefix("dish_"))
				if mesh == null:
					return null
			elif kind.begins_with("kata_"):
				mesh = _kata_mesh(kind.trim_prefix("kata_"))
				if mesh == null:
					return null
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
		mat.vertex_color_is_srgb = true   # couleurs de sommet sRGB (couleur_srgb.gdshaderinc)
	if color.a < 1.0:
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	node.material_override = mat
	return node


## Boule du Katamari (lot WTF9) : noyau sable couvert d'objets collés (pommes, panneaux, voiturette, vache,
## maisonnette, bâtons), pour qu'on y lise « une boule qui ramasse tout » et non une sphère unie. Rayon
## KATA_BALL_M à la taille 1 ; les objets dépassent de ~25 %.
static func _kata_ball_mesh() -> ArrayMesh:
	if _cache.has("ball"):
		return _cache["ball"]
	var r := WtfSceneModel.KATA_BALL_M
	var core := SphereMesh.new()
	core.radius = r
	core.height = 2.0 * r
	core.radial_segments = 20
	core.rings = 10
	var parts := [[core, Vector3.ZERO, Color(0.86, 0.78, 0.6)]]
	# Directions réparties sur la sphère (spirale de Fibonacci), un objet par direction.
	var stuck := []
	for i in 32:
		stuck.append(["apple", "sign", "car", "stick", "cow", "apple", "house", "stick"][i % 8])
	var n := stuck.size()
	for i in n:
		var y := 1.0 - 2.0 * (i + 0.5) / n
		var rad := sqrt(1.0 - y * y)
		var a := i * 2.39996
		var dir := Vector3(cos(a) * rad, y, sin(a) * rad)
		var basis := Basis(Quaternion(Vector3.UP, dir))
		var at := dir * r * 0.95
		for piece in _mini(str(stuck[i]), r * 0.28):
			var xf: Transform3D = Transform3D(basis, at) * piece[1]
			parts.append([piece[0], xf, piece[2]])
	_cache["ball"] = _merge(parts)
	return _cache["ball"]


## Petits objets collés sur la boule : pièces [maillage, transformation locale (Y vers l'extérieur), couleur].
static func _mini(kind: String, k: float) -> Array:
	match kind:
		"apple":
			return [[_ball(k * 0.5), Transform3D(Basis(), Vector3(0, k * 0.35, 0)), Color(0.9, 0.12, 0.12)],
				[_box(Vector3(k * 0.08, k * 0.3, k * 0.08)), Transform3D(Basis(), Vector3(0, k * 0.9, 0)), Color(0.4, 0.25, 0.1)]]
		"sign":
			return [[_box(Vector3(k * 0.1, k * 1.2, k * 0.1)), Transform3D(Basis(), Vector3(0, k * 0.6, 0)), Color(0.75, 0.75, 0.78)],
				[_box(Vector3(k * 0.8, k * 0.8, k * 0.08)), Transform3D(Basis(Vector3.FORWARD, PI / 4.0), Vector3(0, k * 1.3, 0)), WtfHudModel.YELLOW]]
		"car":
			return [[_box(Vector3(k * 1.2, k * 0.4, k * 0.6)), Transform3D(Basis(), Vector3(0, k * 0.3, 0)), WtfHudModel.CYAN],
				[_box(Vector3(k * 0.6, k * 0.3, k * 0.55)), Transform3D(Basis(), Vector3(0, k * 0.6, 0)), Color(0.75, 0.9, 1.0)]]
		"cow":
			return [[_box(Vector3(k * 1.0, k * 0.55, k * 0.5)), Transform3D(Basis(), Vector3(0, k * 0.35, 0)), Color.WHITE],
				[_box(Vector3(k * 0.4, k * 0.3, k * 0.52)), Transform3D(Basis(), Vector3(k * 0.1, k * 0.45, 0)), INK_3D]]
		"house":
			var roof := PrismMesh.new()
			roof.size = Vector3(k * 0.9, k * 0.4, k * 0.8)
			return [[_box(Vector3(k * 0.7, k * 0.6, k * 0.7)), Transform3D(Basis(), Vector3(0, k * 0.3, 0)), Color(1.0, 0.95, 0.85)],
				[roof, Transform3D(Basis(), Vector3(0, k * 0.8, 0)), Color(0.8, 0.25, 0.15)]]
		_:   # bâton / crayon
			return [[_box(Vector3(k * 0.12, k * 1.4, k * 0.12)), Transform3D(Basis(Vector3.RIGHT, 0.3), Vector3(0, k * 0.6, 0)), WtfHudModel.GREEN]]


## Objets semés sur la route pour le Katamari (lot WTF9), à leur taille 1 (KATA_SCALES les agrandit) : chaque
## objet a sa forme propre (pomme, panneau triangulaire, vache, voiture, maison, église), base au sol.
static func _kata_mesh(kind: String) -> Mesh:
	if _cache.has("kata_" + kind):
		return _cache["kata_" + kind]
	var parts := []
	match kind:
		"apple":
			parts = [[_ball(0.5, 0.9), Vector3(0, 0.45, 0), Color(0.9, 0.12, 0.12)],
				[_ball(0.18), Vector3(-0.15, 0.62, -0.3), Color(1.0, 0.55, 0.5)],
				[_box(Vector3(0.06, 0.3, 0.06)), Vector3(0, 1.0, 0), Color(0.4, 0.25, 0.1)],
				[_box(Vector3(0.3, 0.04, 0.15)), Transform3D(Basis(Vector3.FORWARD, 0.4), Vector3(0.15, 1.05, 0)), WtfHudModel.GREEN]]
		"sign":
			# Panneau « danger » : poteau gris, triangle blanc bordé de rouge, point d'exclamation.
			var tri := PrismMesh.new()
			tri.size = Vector3(1.0, 0.9, 0.06)
			var inner := PrismMesh.new()
			inner.size = Vector3(0.7, 0.62, 0.08)
			parts = [[_box(Vector3(0.08, 1.6, 0.08)), Vector3(0, 0.8, 0), Color(0.7, 0.7, 0.72)],
				[tri, Vector3(0, 1.95, 0), Color(0.85, 0.08, 0.08)],
				[inner, Vector3(0, 1.88, 0), Color.WHITE],
				[_box(Vector3(0.07, 0.24, 0.1)), Vector3(0, 1.93, 0), INK_3D],
				[_box(Vector3(0.07, 0.06, 0.1)), Vector3(0, 1.74, 0), INK_3D]]
		"cow":
			return _cow_mesh()
		"car":
			# Voiturette cartoon (face vers −Z) : caisse, cabine vitrée, roues noires, phares.
			parts = [[_box(Vector3(1.0, 0.45, 2.0)), Vector3(0, 0.45, 0), WtfHudModel.CYAN],
				[_box(Vector3(0.9, 0.4, 1.0)), Vector3(0, 0.88, 0.15), WtfHudModel.CYAN],
				[_box(Vector3(0.92, 0.3, 0.9)), Vector3(0, 0.9, 0.15), Color(0.75, 0.9, 1.0)],
				[_box(Vector3(0.2, 0.12, 0.05)), Vector3(-0.3, 0.5, -1.01), WtfHudModel.YELLOW],
				[_box(Vector3(0.2, 0.12, 0.05)), Vector3(0.3, 0.5, -1.01), WtfHudModel.YELLOW]]
			var wheel := CylinderMesh.new()
			wheel.top_radius = 0.24
			wheel.bottom_radius = 0.24
			wheel.height = 0.16
			for x in [-0.5, 0.5]:
				for z in [-0.6, 0.6]:
					parts.append([wheel, Transform3D(Basis(Vector3.FORWARD, PI / 2.0), Vector3(x, 0.24, z)), INK_3D])
		"house":
			# Maison : murs crème, toit rouge à deux pans, porte, fenêtres bleues, cheminée.
			var roof := PrismMesh.new()
			roof.size = Vector3(1.2, 0.6, 1.1)
			parts = [[_box(Vector3(1.0, 0.8, 1.0)), Vector3(0, 0.4, 0), Color(1.0, 0.94, 0.8)],
				[roof, Vector3(0, 1.1, 0), Color(0.82, 0.22, 0.14)],
				[_box(Vector3(0.22, 0.4, 0.04)), Vector3(0, 0.2, -0.51), Color(0.45, 0.25, 0.1)],
				[_box(Vector3(0.2, 0.2, 0.04)), Vector3(-0.3, 0.52, -0.51), Color(0.4, 0.7, 0.95)],
				[_box(Vector3(0.2, 0.2, 0.04)), Vector3(0.3, 0.52, -0.51), Color(0.4, 0.7, 0.95)],
				[_box(Vector3(0.14, 0.35, 0.14)), Vector3(0.3, 1.3, 0.2), Color(0.6, 0.3, 0.2)]]
		"church":
			# Église : nef claire au toit gris, clocher, flèche pointue, croix dorée, rosace, porte.
			var roof := PrismMesh.new()
			roof.size = Vector3(0.8, 0.4, 1.4)
			var spire := CylinderMesh.new()
			spire.top_radius = 0.0
			spire.bottom_radius = 0.28
			spire.height = 0.7
			spire.radial_segments = 4
			parts = [[_box(Vector3(0.7, 0.7, 1.4)), Vector3(0, 0.35, 0.2), Color(0.95, 0.92, 0.85)],
				[roof, Vector3(0, 0.9, 0.2), Color(0.45, 0.47, 0.55)],
				[_box(Vector3(0.4, 1.4, 0.4)), Vector3(0, 0.7, -0.6), Color(0.95, 0.92, 0.85)],
				[spire, Vector3(0, 1.75, -0.6), Color(0.45, 0.47, 0.55)],
				[_box(Vector3(0.04, 0.3, 0.04)), Vector3(0, 2.25, -0.6), WtfHudModel.YELLOW],
				[_box(Vector3(0.18, 0.04, 0.04)), Vector3(0, 2.3, -0.6), WtfHudModel.YELLOW],
				[_ball(0.1), Vector3(0, 1.1, -0.81), WtfHudModel.PURPLE],
				[_box(Vector3(0.18, 0.3, 0.04)), Vector3(0, 0.15, -0.81), Color(0.45, 0.25, 0.1)]]
		_:
			return null
	_cache["kata_" + kind] = _merge(parts)
	return _cache["kata_" + kind]


## Plats du chef (lot WTF9), posés sur une assiette blanche : spaghetti (nid jaune, boulettes, sauce), gelée
## verte tremblotante, accordéon du bal musette, soufflé doré dans son ramequin, piment rouge.
static func _dish_mesh(dish: String) -> Mesh:
	if _cache.has("dish_" + dish):
		return _cache["dish_" + dish]
	var plate := CylinderMesh.new()
	plate.top_radius = 0.32
	plate.bottom_radius = 0.24
	plate.height = 0.04
	var parts := [[plate, Vector3(0, 0.0, 0), Color.WHITE]]
	match dish:
		"spaghetti":
			for i in 4:
				var t := TorusMesh.new()
				t.inner_radius = 0.1 - i * 0.02
				t.outer_radius = 0.16 - i * 0.02
				parts.append([t, Vector3(0, 0.04 + i * 0.035, 0), WtfHudModel.YELLOW])
			parts.append([_ball(0.06), Vector3(0, 0.17, 0), Color(0.85, 0.15, 0.1)])
			parts.append([_ball(0.045), Vector3(0.09, 0.08, 0.05), Color(0.45, 0.22, 0.12)])
			parts.append([_ball(0.045), Vector3(-0.08, 0.08, -0.06), Color(0.45, 0.22, 0.12)])
		"jelly":
			var g := CylinderMesh.new()
			g.top_radius = 0.12
			g.bottom_radius = 0.2
			g.height = 0.22
			parts.append([g, Vector3(0, 0.13, 0), WtfHudModel.GREEN])
			parts.append([_ball(0.04), Vector3(0, 0.27, 0), Color(0.9, 0.1, 0.2)])
		"musette":
			# Accordéon : deux caissons rouges, soufflet plissé, touches blanches.
			parts.append([_box(Vector3(0.1, 0.24, 0.16)), Vector3(-0.17, 0.14, 0), Color(0.85, 0.1, 0.15)])
			parts.append([_box(Vector3(0.1, 0.24, 0.16)), Vector3(0.17, 0.14, 0), Color(0.85, 0.1, 0.15)])
			for i in 5:
				parts.append([_box(Vector3(0.035, 0.22, 0.15)), Vector3(-0.09 + i * 0.045, 0.14, 0),
					INK_3D if i % 2 == 0 else Color(0.95, 0.95, 0.95)])
			parts.append([_box(Vector3(0.02, 0.2, 0.1)), Vector3(-0.225, 0.14, 0), Color.WHITE])
		"souffle":
			var ram := CylinderMesh.new()
			ram.top_radius = 0.15
			ram.bottom_radius = 0.14
			ram.height = 0.14
			parts.append([ram, Vector3(0, 0.09, 0), Color.WHITE])
			parts.append([_ball(0.17, 0.2), Vector3(0, 0.2, 0), Color(0.95, 0.75, 0.35)])
		"chili":
			var body := CapsuleMesh.new()
			body.radius = 0.06
			body.height = 0.4
			parts.append([body, Transform3D(Basis(Vector3.FORWARD, PI / 2.0 - 0.3), Vector3(0, 0.08, 0)), Color(0.9, 0.08, 0.05)])
			parts.append([_box(Vector3(0.1, 0.03, 0.03)), Vector3(0.22, 0.15, 0), WtfHudModel.GREEN])
		_:
			return null
	_cache["dish_" + dish] = _merge(parts)
	return _cache["dish_" + dish]


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
