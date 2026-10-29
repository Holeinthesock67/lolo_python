extends SceneTree

## Vitrine de la pente à l'écran (lot Y15) : la même montée de 8 % et la même descente de 8 %, vues avant (relief
## réel, regard qui suit toute la pente, champ de vision fixe) et après (relief ×2 par défaut, regard qui ne suit que
## la moitié de la pente, champ de vision qui respire avec elle), dans les quatre vues de caméra du lot V12. Sans core ni parcours compilé : route, terrain (shader du
## terrain), poteaux et arbres simples posés d'aplomb pour juger les verticales, brume du préréglage medium.
## Mêmes fonctions que la scène principale : route_data.gd (`relief_k`), road_builder.gd, terrain_tiles.gd,
## camera_follow.gd (`pitch_deg`) et camera_views.gd (`goal`, `fov_deg`).
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_pente.gd -- --out DOSSIER [--k 2.0]
##
## Écrit DOSSIER/<avant|apres>_<montee|descente>_<vue>.png et DOSSIER/vitrine_pente.csv (état ; endroit ; vue ;
## pente réelle ; k ; tangage ; champ de vision ; triangles). Les images par seconde se mesurent sur le PC cible
## (perf_probe.py), pas ici : le rendu logiciel de Xvfb ne dit rien de la GTX 1060.

const RouteDataScript := preload("res://scripts/route_data.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const CameraFollow := preload("res://scripts/camera_follow.gd")
const CameraViews := preload("res://scripts/camera_views.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")

const SIZE := Vector2i(1280, 720)
const BASE_FOV := 65.0          # champ de vision de scenes/main.tscn
const SETTLE_FRAMES := 20
const ALT0 := 300.0
const LENGTH_M := 2400.0
## Endroits capturés : milieu de la montée et milieu de la descente (pente réelle constante de ±8 %).
const SPOTS := {"montee": 700.0, "descente": 1700.0}


var _out_dir := "user://vitrine_pente"
var _k_after := EngineArgs.DEFAULT_VISUAL_GRADE


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--k":
			_k_after = float(args[i + 1])
	call_deferred("_run")


## Altitude réelle du profil : plat, montée de 8 % (300 → 1100 m), replat, descente de 8 % (1300 → 2100 m), plat.
static func _alt(s: float) -> float:
	var a := ALT0
	a += 0.08 * clampf(s - 300.0, 0.0, 800.0)
	a -= 0.08 * clampf(s - 1300.0, 0.0, 800.0)
	return a


static func _make_route(k: float):
	var d := {"version": "1.0", "ds_m": 10.0, "n": 0, "length_m": 0.0, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var n := int(LENGTH_M / 10.0) + 1
	for i in range(n):
		var s := i * 10.0
		d["lat"].append(48.9)
		d["lon"].append(7.1)
		d["alt_m"].append(_alt(s))
		d["x"].append(0.0)
		d["z"].append(-s)
		d["grade_pct"].append((_alt(s + 5.0) - _alt(s - 5.0)) / 10.0 * 100.0)
		d["heading_deg"].append(0.0)
	d["n"] = n
	d["length_m"] = (n - 1) * 10.0
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	route.relief_k = k
	return route


## Hauteur réelle du terrain : la route dans un vallon (talus à 12 % puis collines), comme un col de moyenne montagne.
static func _ground(x: float, z: float) -> float:
	var s := clampf(-z, 0.0, LENGTH_M)
	var d := absf(x)
	var h := _alt(s) - 0.08
	h += maxf(d - 9.0, 0.0) * 0.12
	h += 30.0 * sin(x / 95.0 + 0.6) * cos(z / 140.0) * smoothstep(40.0, 160.0, d)
	return h


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var csv := FileAccess.open(_out_dir.path_join("vitrine_pente.csv"), FileAccess.WRITE)
	csv.store_line("état;endroit;vue;pente_réelle_pct;k;pente_affichée_deg;regard_deg;champ_deg;triangles")
	for state in [["avant", 1.0, false], ["apres", _k_after, true]]:
		var route = _make_route(float(state[1]))
		var vp := _build_world(route)
		var cam: Camera3D = vp.get_node("Camera")
		var rider: Node3D = vp.get_node("Rider")
		var views = CameraViews.new()
		for spot in SPOTS:
			var s: float = SPOTS[spot]
			var follow = CameraFollow.new()
			var pitch := 0.0
			for _i in range(240):   # lissage établi (0,5 s de constante de temps)
				pitch = follow.pitch_deg(route, s, 8.0, 1.0 / 60.0)
			var pos: Vector3 = route.sample_point(s)
			rider.transform = Transform3D(Basis.from_euler(Vector3(deg_to_rad(pitch), 0.0, 0.0)), pos)
			for view in CameraViews.VIEWS:
				views.set_view(view)
				views.snap()
				cam.global_transform = views.step(0.0, views.goal(pos, 0.0, pitch)) if state[2] else _goal_before(view, pos, pitch)
				cam.fov = CameraViews.fov_deg(BASE_FOV, pitch) if state[2] else BASE_FOV
				rider.visible = view != "subjective"
				for _f in range(SETTLE_FRAMES):
					await process_frame
				var img := vp.get_texture().get_image()
				img.save_png(_out_dir.path_join("%s_%s_%s.png" % [state[0], spot, view]))
				var tris := RenderingServer.viewport_get_render_info(vp.get_viewport_rid(),
					RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
				var look := CameraViews.camera_pitch_deg(pitch) if state[2] else pitch
				var line := "%s;%s;%s;%.1f;%.1f;%.2f;%.2f;%.1f;%d" % [state[0], spot, view, route.sample_grade(s), route.relief_k,
					pitch, look, cam.fov, tris]
				csv.store_line(line)
				print("[vitrine_pente] ", line)
		vp.queue_free()
		await process_frame
	csv.close()
	quit(0)


## Ciel, brume, soleil, terrain (shader du terrain avec relief_k), route, poteaux, arbres et un cycliste schématique.
func _build_world(route) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = SIZE
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.fog_enabled = true
	env.fog_light_color = Color(0.72, 0.78, 0.86)
	env.fog_density = 0.00035
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(-(ThemeRenderParams.sky_params({})["sun_direction"] as Vector3), Vector3.UP)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 150.0
	vp.add_child(sun)
	TreeRenderer.apply_wind({"dir": Vector3(1.0, 0.0, 0.0), "strength": 0.2, "gust": 0.0, "phase": 0.0})

	var mat := TerrainMaterial.create_material()
	mat.set_shader_parameter("relief_k", route.relief_k)
	mat.set_shader_parameter("relief_origin_m", route.alt_m[0])
	for ix in range(-2, 2):
		for iz in range(-3, 1):
			var heights := PackedFloat32Array()
			heights.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
			var o := TerrainTiles.tile_origin("near", ix, iz)
			for j in range(TerrainTiles.SAMPLES):
				for i in range(TerrainTiles.SAMPLES):
					heights[j * TerrainTiles.SAMPLES + i] = _ground(o.x + i * 10.0, o.z + j * 10.0)
			var tile := MeshInstance3D.new()
			tile.mesh = _mesh(TerrainTiles.build_arrays(heights, "near", {}, route.relief_k, route.alt_m[0]))
			tile.position = o
			tile.material_override = mat
			vp.add_child(tile)

	var road_mat := RoadBuilder.make_markings_material(RoadBuilder.ROAD_COLOR, RoadBuilder.ROAD_WIDTH_M)
	for k in range(RoadBuilder.chunk_count(route)):
		var road := MeshInstance3D.new()
		road.mesh = _mesh(RoadBuilder.build_chunk_arrays(route, k))
		road.material_override = road_mat
		vp.add_child(road)

	# Poteaux de bord de route tous les 25 m et arbres d'aplomb sur les talus (repères verticaux).
	var post := CylinderMesh.new()
	post.top_radius = 0.06
	post.bottom_radius = 0.06
	post.height = 1.2
	var post_mat := StandardMaterial3D.new()
	post_mat.albedo_color = Color(0.93, 0.93, 0.9)
	var crown := CylinderMesh.new()
	crown.top_radius = 0.0
	crown.bottom_radius = 2.2
	crown.height = 7.0
	var crown_mat := StandardMaterial3D.new()
	crown_mat.albedo_color = Color(0.16, 0.32, 0.17)
	var s := 0.0
	while s <= LENGTH_M:
		for side in [-1.0, 1.0]:
			var p: Vector3 = route.sample_point(s) + Vector3(side * 4.6, 0.6, 0.0)
			var m := MeshInstance3D.new()
			m.mesh = post
			m.material_override = post_mat
			m.position = p
			vp.add_child(m)
			var tx: float = side * (16.0 + fmod(s * 0.37, 9.0))
			var tz := -s - 7.0
			var t := MeshInstance3D.new()
			t.mesh = crown
			t.material_override = crown_mat
			t.position = Vector3(tx, route.display_y(_ground(tx, tz)) + 3.8, tz)
			vp.add_child(t)
		s += 25.0

	var rider := Node3D.new()
	rider.name = "Rider"
	var body := MeshInstance3D.new()
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.25
	capsule.height = 1.5
	body.mesh = capsule
	body.position = Vector3(0.0, 1.0, 0.0)
	var body_mat := StandardMaterial3D.new()
	body_mat.albedo_color = Color(0.85, 0.2, 0.15)
	body.material_override = body_mat
	rider.add_child(body)
	vp.add_child(rider)

	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.far = 6000.0
	vp.add_child(cam)
	cam.make_current()
	return vp


## Pose des vues avant le lot Y15 (camera_views.gd du lot V12) : le regard suivait toute l'inclinaison de la route.
static func _goal_before(view: String, pos: Vector3, pitch_deg: float) -> Transform3D:
	var p := deg_to_rad(pitch_deg)
	if view == "subjective":
		return Transform3D(Basis.from_euler(Vector3(p, 0.0, 0.0)), pos + Vector3(0.0, CameraViews.EYE_HEIGHT_M, 0.0))
	var fwd := Vector3(0.0, sin(p), -cos(p))
	var target_base := pos + Vector3(0.0, CameraViews.TARGET_HEIGHT_M, 0.0)
	var eye: Vector3
	var target: Vector3
	match view:
		"follow_far":
			eye = pos - fwd * CameraViews.FAR_BACK_M + Vector3(0.0, CameraViews.FAR_HEIGHT_M, 0.0)
			target = target_base + fwd * CameraViews.FAR_AHEAD_M
		"side":
			eye = pos + Vector3(CameraViews.SIDE_OFFSET_M, CameraViews.SIDE_HEIGHT_M, 0.0)
			target = target_base + fwd * CameraViews.SIDE_AHEAD_M
		_:
			eye = pos - fwd * CameraViews.NEAR_BACK_M + Vector3(0.0, CameraViews.NEAR_HEIGHT_M, 0.0)
			target = target_base + fwd * CameraViews.NEAR_AHEAD_M
	return Transform3D(Basis.looking_at(target - eye, Vector3.UP), eye)


static func _mesh(arrays: Array) -> ArrayMesh:
	var m := ArrayMesh.new()
	if not arrays.is_empty():
		m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return m
