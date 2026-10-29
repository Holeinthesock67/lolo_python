extends SceneTree

## Vitrine de l'avatar du cycliste (lots V6, V7 et Y16) : l'avatar seul sur une route droite, vu de dos (vue
## de suivi), de profil, de trois quarts avant et de près, au niveau de détail intermédiaire et à côté des
## cyclistes du décor (people_mesh.gd) pour comparer les styles, puis quatre profils à des angles de
## pédalier successifs pour vérifier le sens du pédalage (vu de la droite du cycliste, le vélo avance vers la droite de l'image).
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_avatar.gd -- --out DOSSIER [--quality medium]
##
## Écrit DOSSIER/avatar_<vue>_<préréglage>.png et DOSSIER/vitrine_avatar.csv (vue ; préréglage ; triangles de
## l'image ; triangles de l'avatar ; appels de dessin). Les temps du processeur graphique se mesurent sur le PC
## cible (perf_probe.py), pas ici.

const AvatarModel := preload("res://scripts/avatar_model.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const PeopleMesh := preload("res://scripts/people_mesh.gd")
const CrowdShader := preload("res://shaders/crowd.gdshader")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")

const SIZE := Vector2i(1280, 720)
const SETTLE_FRAMES := 20
## Profil de démonstration de visual_check.py (hello_ack) : avatar réglé.
const DEMO := {"height": "M", "build": "medium", "skin": 3, "hair": 2, "hair_color": 1, "kit_primary": 4,
	"kit_secondary": 9, "number": 27}
## Vues : position de la caméra, point visé, champ vertical (degrés), niveau de détail, angle du pédalier.
const VIEWS := {
	"dos": [Vector3(0.0, 1.7, 3.0), Vector3(0.0, 0.95, 0.0), 60.0, 0, 0.6],
	"profil": [Vector3(3.2, 1.0, 0.0), Vector3(0.0, 0.85, 0.0), 45.0, 0, 0.6],
	"trois_quarts": [Vector3(-2.2, 1.4, -2.4), Vector3(0.0, 0.85, 0.0), 45.0, 0, 2.2],
	"pres": [Vector3(1.1, 1.45, -1.0), Vector3(0.0, 1.1, -0.15), 45.0, 0, 1.2],
	"intermediaire": [Vector3(2.5, 2.2, 8.0), Vector3(0.0, 0.9, 0.0), 30.0, 1, 0.6],
	"avec_decor": [Vector3(4.5, 1.6, 3.5), Vector3(0.0, 0.9, -1.8), 50.0, 0, 0.6],
	"pedalage_0": [Vector3(3.2, 0.7, 0.0), Vector3(0.0, 0.6, 0.0), 32.0, 0, 0.0],
	"pedalage_1": [Vector3(3.2, 0.7, 0.0), Vector3(0.0, 0.6, 0.0), 32.0, 0, PI * 0.25],
	"pedalage_2": [Vector3(3.2, 0.7, 0.0), Vector3(0.0, 0.6, 0.0), 32.0, 0, PI * 0.5],
	"pedalage_3": [Vector3(3.2, 0.7, 0.0), Vector3(0.0, 0.6, 0.0), 32.0, 0, PI * 0.75],
}

var _out_dir := "user://vitrine_avatar"
var _presets: Array = ["medium"]


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--quality":
			_presets = Array(args[i + 1].split(","))
	call_deferred("_run")


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var csv := FileAccess.open(_out_dir.path_join("vitrine_avatar.csv"), FileAccess.WRITE)
	csv.store_line("vue;préréglage;triangles_image;triangles_avatar;appels_dessin")
	for preset in _presets:
		var vp := _build_world(preset)
		var avatar = AvatarView.new()
		vp.add_child(avatar)
		avatar.set_visible_for_view("follow")
		for view in VIEWS:
			var v: Array = VIEWS[view]
			avatar.configure(AvatarModel.parse_settings(DEMO), int(v[3]))
			avatar.apply_pose(float(v[4]), false)
			avatar.set_speed(30.0, 0.0)
			var cam: Camera3D = vp.get_node("Camera")
			cam.fov = v[2]
			cam.look_at_from_position(v[0], v[1])
			for f in range(SETTLE_FRAMES):
				await process_frame
			var path := _out_dir.path_join("avatar_%s_%s.png" % [view, preset])
			vp.get_texture().get_image().save_png(path)
			var rid := vp.get_viewport_rid()
			var tris := RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
			var draws := RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
			var own: int = avatar.test_info()["triangles"]
			csv.store_line("%s;%s;%d;%d;%d" % [view, preset, tris, own, draws])
			print("[vitrine_avatar] %s : %d triangles (avatar %d), %d appels de dessin" % [path, tris, own, draws])
		vp.queue_free()
		await process_frame
	csv.close()
	quit(0)


## Ciel procédural, soleil du thème par défaut, sol au shader du terrain, route droite, deux cyclistes du
## décor devant l'avatar (même rendu que road_cyclists_renderer.gd).
func _build_world(preset: String) -> SubViewport:
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
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(-(ThemeRenderParams.sky_params({})["sun_direction"] as Vector3), Vector3.UP)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 60.0
	vp.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(200.0, 200.0)
	ground.mesh = plane
	ground.position = Vector3(0.0, -0.02, -60.0)
	ground.material_override = TerrainMaterial.create_material()
	vp.add_child(ground)
	var road := MeshInstance3D.new()
	var road_plane := PlaneMesh.new()
	road_plane.size = Vector2(7.0, 200.0)
	road.mesh = road_plane
	road.position = Vector3(1.5, 0.0, -60.0)
	road.material_override = RoadBuilder.make_markings_material(RoadBuilder.ROAD_COLOR, 6.0)
	vp.add_child(road)
	var mat := ShaderMaterial.new()
	mat.shader = CrowdShader
	PeopleMesh.apply_palettes(mat)
	var places := [[Vector3(1.4, 0.0, -2.2), Color(0.85, 0.15, 0.15)], [Vector3(-0.2, 0.0, -4.6), Color(0.1, 0.4, 0.85)]]
	for kind in ["rider", "bike"]:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		mm.mesh = PeopleMesh.build_person(false, true) if kind == "rider" else PeopleMesh.build_bike()
		mm.instance_count = places.size()
		for i in range(places.size()):
			mm.set_instance_transform(i, Transform3D(Basis(Vector3.UP, PI), places[i][0]))
			mm.set_instance_color(i, places[i][1] if kind == "rider" else places[i][1].darkened(0.3))
			mm.set_instance_custom_data(i, Color(0.3 * i, 0.9, 7.0 if kind == "rider" else 8.0,
				PeopleMesh.outfit(i * 2, i + 1, PeopleMesh.RIDER_OUTFIT_TROUSERS)))
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = mat
		vp.add_child(mmi)
	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.current = true
	vp.add_child(cam)
	RenderQuality.apply_preset(preset, cam, sun, env, vp)
	RenderQuality.apply_fog(env, preset, false)
	print("Qualité appliquée : %s (demandée %s, source vitrine)" % [QualityPresets.applied_name(preset), preset])
	return vp
