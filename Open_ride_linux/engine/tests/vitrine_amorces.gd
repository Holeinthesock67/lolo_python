extends SceneTree

## Vitrine des amorces de chaussée (demande du 1er novembre : « la route qui commence nulle part c'est étrange ») :
## départ et arrivée du parcours de démonstration avec terrain synthétique, vus comme au début de séance (caméra
## derrière et au-dessus du cycliste) et de plus loin, pour comparer avant et après. Mêmes fonctions que la scène
## principale : world_streamer.gd (route, terrain, arbres), segment_markers.gd (portiques).
##
##   PYTHONPATH=core/src python3 -m openride_core.tools.fake_world --demo --terrain --out ROUTES
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_amorces.gd -- --world ROUTES/demo.world --out DOSSIER \
##     [--quality medium] [--size 1024x600]
##
## Écrit DOSSIER/<vue>_<préréglage>_<largeur>x<hauteur>.png. Les temps du processeur graphique se mesurent sur le
## PC cible (perf_probe.py), pas ici.

const RouteDataScript := preload("res://scripts/route_data.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const SegmentMarkers := preload("res://scripts/segment_markers.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")

const SETTLE_FRAMES := 30
## Vue : [s visé, recul de la caméra (m le long de la route), hauteur de la caméra (m)] ; s < 0 : depuis l'arrivée.
const VIEWS := {
	"depart": [0.0, 8.0, 4.5],
	"depart_loin": [0.0, 40.0, 12.0],
	"arrivee": [-1.0, 20.0, 3.0],
}

var _world := ""
var _out_dir := "user://vitrine_amorces"
var _preset := "medium"
var _size := Vector2i(1024, 600)


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		match args[i]:
			"--world":
				_world = args[i + 1]
			"--out":
				_out_dir = args[i + 1]
			"--quality":
				_preset = args[i + 1]
			"--size":
				_size = Vector2i(int(args[i + 1].get_slice("x", 0)), int(args[i + 1].get_slice("x", 1)))
	call_deferred("_run")


func _run() -> void:
	var route = RouteDataScript.new()
	if _world == "" or not route.load_world_dir(_world):
		printerr("Parcours illisible : ", _world)
		quit(1)
		return
	DirAccess.make_dir_recursive_absolute(_out_dir)
	for view in VIEWS:
		var spec: Array = VIEWS[view]
		var s_target: float = route.length_m if float(spec[0]) < 0.0 else float(spec[0])
		var s_cam: float = s_target - float(spec[1])
		var vp := _build(route)
		var st = vp.get_node("Streamer")
		var markers = vp.get_node("Markers")
		var cam: Camera3D = vp.get_node("Camera")
		# Caméra en s < 0 : sur l'axe prolongé derrière le départ, au cap du départ.
		var p0: Vector3 = route.sample_point(maxf(s_cam, 0.0))
		var h := deg_to_rad(route.sample_heading_deg(maxf(s_cam, 0.0)))
		var fwd := Vector3(sin(h), 0.0, -cos(h))
		var cam_pos := p0 + fwd * minf(s_cam, 0.0) + Vector3.UP * float(spec[2])
		var look: Vector3 = route.sample_point(minf(s_target + 25.0, route.length_m))
		if s_target >= route.length_m:
			look = route.sample_point(route.length_m) + fwd * 60.0
		st.update_window(maxf(s_cam, 0.0), 0.0, cam_pos)
		st.flush()
		markers.update(maxf(s_cam, 0.0), true)
		cam.look_at_from_position(cam_pos, look + Vector3.UP * 1.0)
		for f in range(SETTLE_FRAMES):
			st.update_window(maxf(s_cam, 0.0), 0.0, cam_pos)
			st.flush()
			await process_frame
		var path := _out_dir.path_join("%s_%s_%dx%d.png" % [view, _preset, _size.x, _size.y])
		vp.get_texture().get_image().save_png(path)
		print("[vitrine] ", path)
		st.clear()
		vp.queue_free()
		await process_frame
	quit(0)


func _build(route) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = _size
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(-(ThemeRenderParams.sky_params({})["sun_direction"] as Vector3), Vector3.UP)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 150.0
	vp.add_child(sun)
	var st = WorldStreamer.new()
	st.name = "Streamer"
	vp.add_child(st)
	var trees = TreeRenderer.new()
	trees.name = "TreeRenderer"
	st.add_child(trees)
	st.tree_renderer = trees
	trees.set_preset(_preset)
	st.set_road_markings(true)
	st.set_world(route, _world)
	var markers = SegmentMarkers.new()
	markers.name = "Markers"
	vp.add_child(markers)
	markers.set_route(route, 1000.0, 6.0)
	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.current = true
	cam.fov = 65.0
	cam.far = 4000.0
	vp.add_child(cam)
	RenderQuality.apply_preset(_preset, cam, sun, env, vp)
	RenderQuality.apply_fog(env, _preset, false)
	return vp
