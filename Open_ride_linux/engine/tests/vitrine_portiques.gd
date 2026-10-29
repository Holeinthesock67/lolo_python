extends SceneTree

## Vitrine des portiques du parcours (segment_markers.gd) : départ et arrivée du parcours, départ et fin d'un
## sprint, pied et sommet d'une montée, arche de bonus, vus depuis la selle à 16 m, sans core ni parcours
## réel, pour comparer avant et après une retouche (captures PNG, triangles, appels de dessin et nœuds par vue).
## Route droite de démonstration de 600 m : sprint de 100 à 250 m, montée de 350 à 500 m, arche à 550 m.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_portiques.gd -- --out DOSSIER \
##     [--quality medium] [--size 1920x1080,1024x600] [--views depart,sprint_depart]
##
## Écrit DOSSIER/<vue>_<préréglage>_<largeur>x<hauteur>.png et DOSSIER/vitrine_portiques.csv (vue ; préréglage ;
## taille ; triangles ; appels de dessin ; nœuds des marques). Les temps du processeur graphique se mesurent
## sur le PC cible (perf_probe.py), pas ici.

const SegmentMarkers := preload("res://scripts/segment_markers.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")

const ROAD_WIDTH_M := 6.0
const SETTLE_FRAMES := 20
const LENGTH_M := 600.0
const SEGMENTS := [
	{"id": "sprint1", "name": "Sprint de la vitrine", "type": "sprint", "s_start": 100.0, "s_end": 250.0,
		"length_m": 150.0, "avg_grade_pct": 0.5, "gain_m": 0.8, "category": null},
	{"id": "climb1", "name": "Côte de la vitrine", "type": "climb", "s_start": 350.0, "s_end": 500.0,
		"length_m": 150.0, "avg_grade_pct": 6.0, "gain_m": 9.0, "category": "3"},
]
## Vue : position de la marque visée (m) ; caméra 16 m avant, à 1,4 m, sur la voie de droite.
const VIEWS := {"depart": 0.0, "sprint_depart": 100.0, "sprint_arrivee": 250.0, "montee": 350.0, "sommet": 500.0,
	"bonus": 550.0, "arrivee": 600.0}


## Route droite le long de -z (cap 0, comme route_data.gd) : seules les méthodes lues par segment_markers.gd.
class StraightRoute:
	var length_m := LENGTH_M
	var segments: Array = SEGMENTS
	func is_loop() -> bool:
		return false
	func sample(s: float) -> Dictionary:
		return {"x": 0.0, "y": 0.0, "z": -s, "heading_deg": 0.0, "alt_m": 200.0 + maxf(0.0, minf(s, 500.0) - 350.0) * 0.06}


var _out_dir := "user://vitrine_portiques"
var _presets := ["medium"]
var _sizes: Array = [Vector2i(1920, 1080), Vector2i(1024, 600)]
var _views: Array = VIEWS.keys()


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--quality":
			_presets = Array(args[i + 1].split(","))
		elif args[i] == "--views":
			_views = Array(args[i + 1].split(","))
		elif args[i] == "--size":
			_sizes = []
			for wh in args[i + 1].split(","):
				_sizes.append(Vector2i(int(wh.get_slice("x", 0)), int(wh.get_slice("x", 1))))
	call_deferred("_run")


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var csv := FileAccess.open(_out_dir.path_join("vitrine_portiques.csv"), FileAccess.WRITE)
	csv.store_line("vue;préréglage;taille;triangles;appels_dessin;noeuds_marques")
	for preset in _presets:
		for size in _sizes:
			var vp := _build_world(preset, size)
			var markers = vp.get_node("Markers")
			var cam: Camera3D = vp.get_node("Camera")
			for view in _views:
				var s: float = VIEWS[view]
				markers.update(s - 16.0, true)
				cam.look_at_from_position(Vector3(1.0, 1.4, -(s - 16.0)), Vector3(0.0, 2.6, -s))
				for f in range(SETTLE_FRAMES):
					await process_frame
				var path := _out_dir.path_join("%s_%s_%dx%d.png" % [view, preset, size.x, size.y])
				vp.get_texture().get_image().save_png(path)
				var rid := vp.get_viewport_rid()
				var tris := RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,
					RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
				var draws := RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,
					RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
				var nodes: int = markers.active_node_count()
				csv.store_line("%s;%s;%dx%d;%d;%d;%d" % [view, preset, size.x, size.y, tris, draws, nodes])
				print("[vitrine] %s : %d triangles, %d appels de dessin, %d nœuds" % [path, tris, draws, nodes])
			vp.queue_free()
			await process_frame
	csv.close()
	quit(0)


## Ciel, soleil, sol au shader du terrain, route et marques, comme vitrine_rendu.gd.
func _build_world(preset: String, size: Vector2i) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = size
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
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(300.0, 800.0)
	plane.subdivide_width = 30
	plane.subdivide_depth = 80
	ground.mesh = plane
	ground.position = Vector3(0.0, -0.02, -300.0)
	ground.material_override = TerrainMaterial.create_material()
	vp.add_child(ground)
	var road := MeshInstance3D.new()
	road.mesh = _road_mesh()
	road.material_override = RoadBuilder.make_markings_material(RoadBuilder.ROAD_COLOR, ROAD_WIDTH_M)
	vp.add_child(road)
	var markers = SegmentMarkers.new()
	markers.name = "Markers"
	vp.add_child(markers)
	markers.set_route(StraightRoute.new(), 550.0, ROAD_WIDTH_M)
	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.current = true
	cam.fov = 70.0
	vp.add_child(cam)
	RenderQuality.apply_preset(preset, cam, sun, env, vp)
	RenderQuality.apply_fog(env, preset, false)
	return vp


## Ruban de route droit de -50 à 650 m avec les UV d'E1 (u en travers, bas-côtés compris ; v = s / V_REPEAT_M).
func _road_mesh() -> ArrayMesh:
	var half := ROAD_WIDTH_M * 0.5 + RoadBuilder.SHOULDER_WIDTH_M
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var step := 2.0
	for j in range(350):
		var s0 := -50.0 + j * step
		var s1 := s0 + step
		var quad := [[-half, s0, 0.0], [half, s1, 1.0], [half, s0, 1.0], [-half, s0, 0.0], [-half, s1, 0.0], [half, s1, 1.0]]
		for q in quad:
			st.set_normal(Vector3.UP)
			st.set_uv(Vector2(q[2], q[1] / RoadBuilder.V_REPEAT_M))
			st.add_vertex(Vector3(q[0], 0.0, -q[1]))
	st.generate_tangents()
	return st.commit()
