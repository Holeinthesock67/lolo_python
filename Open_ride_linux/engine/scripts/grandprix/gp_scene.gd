extends Node3D

## Objets du « Grand Prix des objets » en 3D (série GP, lot GP7), d'après les maquettes GP6 validées le
## 7 novembre 2026 (charte cartoon CT9 : aplats sans ombre, matériaux non éclairés) :
## - boîtes de ravitaillement (caisse papier à bandes `warm`, bord encre) : un MultiMesh de six instances au
##   plus (deux rangées de trois), qui tournent et flottent doucement ;
## - bidons posés, musettes lancées, musettes guidées (anneau de visée `hot`) et nuages d'orage : une réserve
##   de POOL instances par sorte, créée une fois à la construction, aucune création en course ;
## - effets sur les coureurs (le cycliste et les bots), une réserve par coureur : étoiles qui tournent au-dessus
##   d'un coureur qui glisse, nuage et averse, halo de la super-forme, voiture d'équipe devant le coureur
##   remorqué, rafales du vent contraire, traits du coup de fouet. `low` : sprites seulement, sans particules ;
##   `medium` : averse limitée ; `high` : averse et étincelles complètes (gp_scene_model.gd PARTICLES) ;
## - onomatopées au-dessus du coureur touché (« ZIOUF ! », « SPLASH ! », « BOING ! »), quatre au plus.
## Ne décide rien : main.gd appelle step() une fois par image avec la trame, la route, la place du cycliste et
## celle des bots (bots_view.anchor_of). Rien n'est montré hors du mode. Ombres coupées partout.
## Pas de class_name : preload("res://scripts/grandprix/gp_scene.gd").

const Model := preload("res://scripts/grandprix/gp_scene_model.gd")
const Items := preload("res://scripts/grandprix/gp_items.gd")

const MAX_RIDERS := 12
const BOX_M := 0.6
const BOX_HEIGHT_M := 0.9
const BOX_SPIN := 1.2                 # rad/s
const OBJ_HEIGHT_M := {"bottle": 0.12, "musette": 0.6, "homing": 0.8, "storm": 4.5}
const RIDER_TOP_M := 1.9              # au-dessus du casque
const CAR_AHEAD_M := 5.0
const WORD_RISE_M := 0.8
const WARM_FRAMES := 3
const WARM_DIST_M := 2.0
const WARM_SCALE := 0.001

var quality := "low"
var _model = Model.new()
var _route = null
var _boxes: MultiMeshInstance3D
var _pools := {}                      # sorte -> [Node3D]
var _rigs: Array = []                 # [{root, looks: {look: Node3D}, rain: CPUParticles3D, sparks: CPUParticles3D}]
var _labels: Array = []               # Label3D des onomatopées
var _mats := {}
var _active := false
var _warm_left := -1                  # -1 : jamais préchauffé
var _shown := {"boxes": 0, "objects": 0, "looks": 0, "words": 0}


func _init() -> void:
	name = "GrandPrixScene"
	visible = false
	_build()


func set_route(route) -> void:
	_route = route


func set_quality(q: String) -> void:
	quality = q
	for rig in _rigs:
		var rain: CPUParticles3D = rig["rain"]
		rain.amount = maxi(Model.particles(q, "rain"), 1)
		var sparks: CPUParticles3D = rig["sparks"]
		sparks.amount = maxi(Model.particles(q, "halo"), 1)


func reset() -> void:
	_model.reset()


## Message `gp_hit` du core ; vrai s'il est nouveau (onomatopée posée).
func on_hit(msg: Dictionary, now_s: float) -> bool:
	return _model.on_hit(msg, now_s)


## Une fois par image. `gp` : objet `gp` de la trame (null hors du mode) ; `riders` : [{id, pos (Vector3 au
## sol, ou null), heading (rad), fx}] du cycliste et des bots ; `camera` : pour le préchauffage.
func step(gp, riders: Array, now_s: float, camera: Camera3D) -> void:
	_active = gp is Dictionary and _route != null
	visible = _active
	if not _active:
		return
	if _warm_left < 0:
		_warm_left = WARM_FRAMES
	_step_boxes(gp, now_s)
	_step_objects(gp, now_s)
	_step_riders(riders, now_s)
	if _warm_left > 0:
		_warm(camera)


## Pour les tests graphiques et le banc : ce qui est montré.
func test_info() -> Dictionary:
	return {"active": _active, "quality": quality} | _shown


# --- construction ------------------------------------------------------------------------------------

func _build() -> void:
	_mats["paper"] = _flat(Items.PAPER)
	_mats["ink"] = _flat(Items.INK)
	_mats["warm"] = _flat(Items.WARM)
	_mats["hot"] = _flat(Items.HOT)
	_mats["spark"] = _flat(Items.SPARK)
	_mats["fresh"] = _flat(Items.FRESH)
	_mats["draft"] = _flat(Color(Items.DRAFT, 0.7), true)
	_mats["cloud"] = _flat(Color(0.55, 0.55, 0.62))
	_mats["canvas"] = _flat(Color(0.86, 0.76, 0.56))
	_mats["crate"] = _textured(_crate_image())
	_mats["star"] = _sprite(_star_image())
	_mats["halo"] = _sprite(_ring_image())
	_mats["rain"] = _sprite(_rain_image())
	_mats["drop"] = _flat(Color(0.55, 0.75, 1.0, 0.8), true)
	_mats["spark_dot"] = _flat(Items.SPARK, true)

	_boxes = MultiMeshInstance3D.new()
	_boxes.name = "GpBoxes"
	_boxes.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	var box := BoxMesh.new()
	box.size = Vector3.ONE * BOX_M
	box.material = _mats["crate"]
	mm.mesh = box
	mm.instance_count = Model.MAX_ROWS * Model.LANE_CENTRES_M.size()
	mm.visible_instance_count = 0
	_boxes.multimesh = mm
	add_child(_boxes)

	for kind in Model.SHOT_KINDS:
		var list: Array = []
		for i in range(Model.POOL):
			var n := _make_object(kind)
			n.visible = false
			add_child(n)
			list.append(n)
		_pools[kind] = list

	for i in range(MAX_RIDERS):
		_rigs.append(_make_rig(i))

	for i in range(Model.MAX_WORDS):
		var l := Label3D.new()
		l.name = "GpWord%d" % i
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.font_size = 96
		l.pixel_size = 0.004
		l.outline_size = 24
		l.modulate = Items.WARM
		l.outline_modulate = Items.INK
		l.no_depth_test = true
		l.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		l.visible = false
		add_child(l)
		_labels.append(l)
	set_quality(quality)


func _make_object(kind: String) -> Node3D:
	var root := Node3D.new()
	root.name = "Gp_" + kind
	match kind:
		"bottle":   # bidon couché au sol : corps `warm`, bouchon encre, flaque claire
			var body := _mesh(root, _cylinder(0.08, 0.24), "warm", Vector3.ZERO)
			body.rotation = Vector3(0.0, 0.0, PI / 2.0)
			var cap := _mesh(root, _cylinder(0.035, 0.06), "ink", Vector3(0.15, 0.0, 0.0))
			cap.rotation = Vector3(0.0, 0.0, PI / 2.0)
			_mesh(root, _cylinder(0.45, 0.01), "draft", Vector3(0.0, -0.11, 0.0))
		"musette", "homing":   # musette en toile, bandoulière encre ; guidée : anneau de visée `hot`
			_mesh(root, _box(Vector3(0.36, 0.28, 0.1)), "canvas", Vector3.ZERO)
			var strap := _mesh(root, _torus(0.14, 0.17), "ink", Vector3(0.0, 0.16, 0.0))
			strap.rotation = Vector3(PI / 2.0, 0.0, 0.0)
			if kind == "homing":
				var ring := _mesh(root, _torus(0.3, 0.36), "hot", Vector3(0.0, 0.0, 0.0))
				ring.rotation = Vector3(PI / 2.0, 0.0, 0.0)
		"storm":   # nuage gris et éclair encre
			for k in [[Vector3(-0.7, 0.0, 0.0), 0.7], [Vector3(0.0, 0.25, 0.0), 0.9], [Vector3(0.75, 0.0, 0.0), 0.65]]:
				_mesh(root, _sphere(k[1]), "cloud", k[0])
			_mesh(root, _box(Vector3(0.12, 0.7, 0.12)), "spark", Vector3(0.0, -0.9, 0.0))
	return root


func _make_rig(i: int) -> Dictionary:
	var root := Node3D.new()
	root.name = "GpRig%d" % i
	root.visible = false
	add_child(root)
	var looks := {}
	# Glissade : étoiles qui tournent au-dessus du casque
	var stars := Node3D.new()
	for k in range(4):
		var a := TAU * k / 4.0
		_quad(stars, 0.28, "star", Vector3(cos(a) * 0.35, 0.0, sin(a) * 0.35))
	stars.position.y = RIDER_TOP_M
	root.add_child(stars)
	looks["slip"] = stars
	# Averse : nuage au-dessus du coureur, rideau de pluie (sprite) en low, gouttes (particules) sinon
	var rain_root := Node3D.new()
	for k in [[Vector3(-0.5, 0.0, 0.0), 0.5], [Vector3(0.0, 0.18, 0.0), 0.65], [Vector3(0.5, 0.0, 0.0), 0.45]]:
		_mesh(rain_root, _sphere(k[1]), "cloud", k[0])
	rain_root.position.y = RIDER_TOP_M + 1.4
	var sheet := _quad(rain_root, 1.2, "rain", Vector3(0.0, -0.9, 0.0))
	sheet.name = "RainSheet"
	var rain := CPUParticles3D.new()
	rain.name = "Rain"
	rain.emitting = false
	rain.lifetime = 0.5
	rain.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	rain.emission_box_extents = Vector3(0.6, 0.05, 0.4)
	rain.direction = Vector3.DOWN
	rain.spread = 3.0
	rain.gravity = Vector3(0.0, -9.8, 0.0)
	rain.initial_velocity_min = 3.0
	rain.initial_velocity_max = 4.0
	var drop := BoxMesh.new()
	drop.size = Vector3(0.02, 0.14, 0.02)
	drop.material = _mats["drop"]
	rain.mesh = drop
	rain.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	rain_root.add_child(rain)
	root.add_child(rain_root)
	looks["rain"] = rain_root
	# Super-forme : halo (sprite) autour du coureur, étincelles en high
	var halo := Node3D.new()
	_quad(halo, 2.2, "halo", Vector3(0.0, 1.0, 0.0))
	var sparks := CPUParticles3D.new()
	sparks.name = "Sparks"
	sparks.emitting = false
	sparks.lifetime = 0.8
	sparks.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	sparks.emission_sphere_radius = 0.8
	sparks.gravity = Vector3(0.0, 1.0, 0.0)
	sparks.initial_velocity_min = 0.2
	sparks.initial_velocity_max = 0.6
	var dot := SphereMesh.new()
	dot.radius = 0.03
	dot.height = 0.06
	dot.radial_segments = 4
	dot.rings = 2
	dot.material = _mats["spark_dot"]
	sparks.mesh = dot
	sparks.position.y = 1.0
	sparks.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	halo.add_child(sparks)
	root.add_child(halo)
	looks["halo"] = halo
	# Voiture d'équipe devant le coureur remorqué : caisse blanche, vitres encre, deux vélos sur le toit
	var car := Node3D.new()
	_mesh(car, _box(Vector3(1.8, 0.7, 4.2)), "paper", Vector3(0.0, 0.55, 0.0))
	_mesh(car, _box(Vector3(1.6, 0.5, 2.2)), "ink", Vector3(0.0, 1.15, 0.3))
	for x in [-0.4, 0.4]:
		_mesh(car, _box(Vector3(0.04, 0.55, 1.6)), "fresh", Vector3(x, 1.7, 0.3))
	for w in [Vector3(-0.85, 0.3, -1.4), Vector3(0.85, 0.3, -1.4), Vector3(-0.85, 0.3, 1.4), Vector3(0.85, 0.3, 1.4)]:
		var wheel := _mesh(car, _cylinder(0.3, 0.2), "ink", w)
		wheel.rotation = Vector3(0.0, 0.0, PI / 2.0)
	root.add_child(car)
	looks["car"] = car
	# Rafales du vent contraire : trois traits `draft` devant le coureur
	var gust := Node3D.new()
	for k in range(3):
		_mesh(gust, _box(Vector3(0.03, 0.03, 1.2)), "draft", Vector3(-0.4 + 0.4 * k, 1.0 + 0.3 * (k % 2), -1.5 - 0.4 * k))
	root.add_child(gust)
	looks["gust"] = gust
	# Coup de fouet : traits jaunes derrière le coureur
	var kick := Node3D.new()
	for k in range(3):
		_mesh(kick, _box(Vector3(0.04, 0.04, 0.9)), "spark", Vector3(-0.3 + 0.3 * k, 0.6 + 0.35 * k, 1.2))
	root.add_child(kick)
	looks["kick"] = kick
	for l in looks.values():
		l.visible = false
	return {"root": root, "looks": looks, "rain": rain, "sparks": sparks, "sheet": sheet}


# --- mise à jour ------------------------------------------------------------------------------------

func _step_boxes(gp: Dictionary, now_s: float) -> void:
	var list := Model.boxes(gp)
	var mm := _boxes.multimesh
	for i in range(list.size()):
		var b: Dictionary = list[i]
		var t := _frame(float(b["s"]), float(b["lateral"]))
		var bob := 0.08 * sin(now_s * 2.0 + float(i))
		var basis := Basis(Vector3.UP, now_s * BOX_SPIN + float(i)) * Basis(Vector3.RIGHT, 0.35)
		mm.set_instance_transform(i, Transform3D(basis, t.origin + Vector3(0.0, BOX_HEIGHT_M + bob, 0.0)))
	mm.visible_instance_count = list.size()
	_shown["boxes"] = list.size()


func _step_objects(gp: Dictionary, now_s: float) -> void:
	var placed: Dictionary = _model.assign(Model.objects(gp))
	var count := 0
	for kind in Model.SHOT_KINDS:
		var nodes: Array = _pools[kind]
		var objs: Array = placed.get(kind, [])
		for i in range(nodes.size()):
			var n: Node3D = nodes[i]
			var o = objs[i] if i < objs.size() else null
			if o == null:
				n.visible = false
				continue
			var t := _frame(float(o["s"]), float(o["lateral"]))
			var h: float = OBJ_HEIGHT_M.get(kind, 0.3)
			n.global_transform = Transform3D(t.basis, t.origin + Vector3(0.0, h, 0.0))
			if kind == "musette" or kind == "homing":   # musette lancée : elle tourne en volant
				n.rotate_object_local(Vector3.RIGHT, fmod(now_s * 8.0, TAU))
			n.visible = true
			count += 1
	_shown["objects"] = count


func _step_riders(riders: Array, now_s: float) -> void:
	var looks_shown := 0
	for i in range(_rigs.size()):
		var rig: Dictionary = _rigs[i]
		var root: Node3D = rig["root"]
		var r = riders[i] if i < riders.size() else null
		var wanted: Array = Model.shown_looks(quality, Model.looks(r.get("fx", []))) if r is Dictionary and r.get("pos") is Vector3 else []
		root.visible = not wanted.is_empty()
		if root.visible:
			var heading := float(r.get("heading", 0.0))
			root.global_transform = Transform3D(Basis(Vector3.UP, -heading), r["pos"])
		for look in Model.LOOKS:
			var node: Node3D = rig["looks"][look]
			var on: bool = look in wanted
			node.visible = on
			if on:
				looks_shown += 1
		if root.visible:
			var slip: Node3D = rig["looks"]["slip"]
			slip.rotation.y = fmod(now_s * 4.0, TAU)
			var car: Node3D = rig["looks"]["car"]
			car.position = Vector3(0.0, 0.0, -CAR_AHEAD_M)
		var rain: CPUParticles3D = rig["rain"]
		var rain_on: bool = root.visible and "rain" in wanted and Model.particles(quality, "rain") > 0
		if rain.emitting != rain_on:
			rain.emitting = rain_on
		(rig["sheet"] as Node3D).visible = Model.particles(quality, "rain") == 0
		var sparks: CPUParticles3D = rig["sparks"]
		var sparks_on: bool = root.visible and "halo" in wanted and Model.particles(quality, "halo") > 0
		if sparks.emitting != sparks_on:
			sparks.emitting = sparks_on
	_shown["looks"] = looks_shown
	# Onomatopées au-dessus des coureurs touchés
	var pos_of := {}
	for r in riders:
		if r is Dictionary and r.get("pos") is Vector3:
			pos_of[str(r.get("id", ""))] = r["pos"]
	var words: Array = _model.words(now_s)
	var shown := 0
	for i in range(_labels.size()):
		var l: Label3D = _labels[i]
		var w = words[i] if i < words.size() else null
		if w == null or not pos_of.has(w["target"]):
			l.visible = false
			continue
		l.text = str(w["text"])
		l.global_position = pos_of[w["target"]] + Vector3(0.0, RIDER_TOP_M + 0.6 + WORD_RISE_M * float(w["age"]), 0.0)
		l.modulate.a = 1.0 - 0.6 * float(w["age"])
		l.visible = true
		shown += 1
	_shown["words"] = shown


## Préchauffage : un exemplaire de chaque objet et un coureur avec tous ses effets, minuscules devant la
## caméra pendant WARM_FRAMES images, pour que le premier dessin (matériaux, particules) se fasse au départ.
func _warm(camera: Camera3D) -> void:
	_warm_left -= 1
	if camera == null:
		return
	var front := camera.global_transform * Vector3(0.0, 0.0, -WARM_DIST_M)
	for kind in Model.SHOT_KINDS:
		var n: Node3D = _pools[kind][Model.POOL - 1]
		n.visible = _warm_left > 0
		n.global_transform = Transform3D(Basis().scaled(Vector3.ONE * WARM_SCALE), front)
	var rig: Dictionary = _rigs[MAX_RIDERS - 1]
	var root: Node3D = rig["root"]
	root.visible = _warm_left > 0
	root.global_transform = Transform3D(Basis().scaled(Vector3.ONE * WARM_SCALE), front)
	for look in Model.LOOKS:
		(rig["looks"][look] as Node3D).visible = _warm_left > 0


## Repère de la route en `s`, décalé de `lateral` à droite de l'axe : origine au sol, -Z vers l'avant.
func _frame(s: float, lateral: float) -> Transform3D:
	var smp: Dictionary = _route.sample(s)
	var h := deg_to_rad(float(smp["heading_deg"]))
	var right := Vector3(cos(h), 0.0, sin(h))
	var pos := Vector3(float(smp["x"]), float(smp["y"]), float(smp["z"])) + right * lateral
	return Transform3D(Basis(Vector3.UP, -h), pos)


# --- matériaux et maillages --------------------------------------------------------------------------

static func _flat(c: Color, transparent := false) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = c
	if transparent:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return m


static func _textured(img: Image) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_texture = ImageTexture.create_from_image(img)
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	return m


static func _sprite(img: Image) -> StandardMaterial3D:
	var m := _textured(img)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


func _mesh(parent: Node3D, mesh: Mesh, mat: String, pos: Vector3) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = _mats[mat]
	mi.position = pos
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)
	return mi


func _quad(parent: Node3D, size_m: float, mat: String, pos: Vector3) -> MeshInstance3D:
	var q := QuadMesh.new()
	q.size = Vector2(size_m, size_m)
	return _mesh(parent, q, mat, pos)


static func _box(size: Vector3) -> BoxMesh:
	var b := BoxMesh.new()
	b.size = size
	return b


static func _cylinder(r: float, h: float) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = r
	c.bottom_radius = r
	c.height = h
	c.radial_segments = 12
	c.rings = 1
	return c


static func _sphere(r: float) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = r
	s.height = r * 2.0
	s.radial_segments = 12
	s.rings = 6
	return s


static func _torus(inner: float, outer: float) -> TorusMesh:
	var t := TorusMesh.new()
	t.inner_radius = inner
	t.outer_radius = outer
	t.rings = 16
	t.ring_segments = 6
	return t


## Face de la caisse : papier, bord encre, bande `warm` en croix (64 × 64).
static func _crate_image() -> Image:
	var n := 64
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	for y in range(n):
		for x in range(n):
			var c := Items.PAPER
			if x < 5 or y < 5 or x >= n - 5 or y >= n - 5:
				c = Items.INK
			elif absi(x - n / 2) < 6 or absi(y - n / 2) < 6:
				c = Items.WARM
			img.set_pixel(x, y, c)
	img.generate_mipmaps()
	return img


## Étoile jaune à bord encre (32 × 32).
static func _star_image() -> Image:
	var n := 32
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	var outer := PackedVector2Array()
	var inner := PackedVector2Array()
	for i in range(10):
		var a := -PI / 2.0 + PI * i / 5.0
		var r := 15.0 if i % 2 == 0 else 6.5
		outer.append(Vector2(16, 16) + Vector2(cos(a), sin(a)) * r)
		inner.append(Vector2(16, 16) + Vector2(cos(a), sin(a)) * (r - 2.5))
	for y in range(n):
		for x in range(n):
			var p := Vector2(x + 0.5, y + 0.5)
			var c := Color(0, 0, 0, 0)
			if Geometry2D.is_point_in_polygon(p, inner):
				c = Items.SPARK
			elif Geometry2D.is_point_in_polygon(p, outer):
				c = Items.INK
			img.set_pixel(x, y, c)
	img.generate_mipmaps()
	return img


## Anneau du halo de la super-forme : jaune, bords doux (64 × 64).
static func _ring_image() -> Image:
	var n := 64
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	for y in range(n):
		for x in range(n):
			var d := Vector2(x + 0.5 - n / 2.0, y + 0.5 - n / 2.0).length() / (n / 2.0)
			var a := clampf(1.0 - absf(d - 0.8) / 0.18, 0.0, 1.0)
			img.set_pixel(x, y, Color(Items.SPARK, a * 0.85))
	img.generate_mipmaps()
	return img


## Rideau de pluie du préréglage low : traits bleus obliques sur fond transparent (32 × 32).
static func _rain_image() -> Image:
	var n := 32
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	for k in range(6):
		var x0 := 2 + k * 5
		for y in range(n):
			if (y + k * 7) % 16 < 9:
				img.set_pixel(clampi(x0 + y / 8, 0, n - 1), y, Color(0.55, 0.75, 1.0, 0.85))
	img.generate_mipmaps()
	return img
