extends SceneTree

## Vitrine des bots sur la route (lot Y18) : l'avatar du joueur et des bots (bots_view.gd) sur une route
## droite, vus comme en séance (vue de suivi), de côté, de près, de loin, avec un fantôme et avec les maillots
## de la séance, pour chaque préréglage demandé. La même vitrine lancée sur une version d'avant le lot Y18
## donne les captures « avant » (bots_view.gd sans set_quality : appel sauté).
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_bots.gd -- --out DOSSIER [--quality low,medium,high]
##
## Écrit DOSSIER/bots_<vue>_<préréglage>.png et DOSSIER/vitrine_bots.csv (vue ; préréglage ; triangles de
## l'image ; appels de dessin ; bots affichés ; bots par niveau de détail 0/1/2). Les temps du processeur
## graphique se mesurent sur le PC cible (perf_probe.py, sim_bench.py), pas ici.

const AvatarModel := preload("res://scripts/avatar_model.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const BotsView := preload("res://scripts/bots_view.gd")
const BotsViewModel := preload("res://scripts/bots_view_model.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")

const SIZE := Vector2i(1280, 720)
const SETTLE_FRAMES := 20
const DEMO := {"height": "M", "build": "medium", "skin": 3, "hair": 2, "hair_color": 1, "kit_primary": 4,
	"kit_secondary": 9, "number": 27}
## Vues : position de la caméra, point visé, champ vertical (degrés), bots [id, kind, écart devant le joueur
## en mètres, maillot].
const GROUP := [["b1", "constant", 4.0, null], ["b2", "constant", 8.5, null], ["b3", "constant", 13.0, null],
	["b4", "constant", 22.0, null], ["ghost", "ghost", 6.0, null]]
const VIEWS := {
	"suivi": [Vector3(1.2, 1.9, 4.2), Vector3(1.6, 1.0, -8.0), 60.0, GROUP],
	"cote": [Vector3(-3.5, 1.3, -9.0), Vector3(2.0, 0.9, -9.0), 55.0, GROUP],
	"pres": [Vector3(0.6, 1.5, -1.6), Vector3(2.1, 1.0, -4.0), 50.0, [["b1", "constant", 4.0, null]]],
	"loin": [Vector3(1.2, 1.9, 4.2), Vector3(1.8, 1.0, -40.0), 50.0,
		[["b1", "constant", 30.0, null], ["b2", "constant", 48.0, null], ["b3", "constant", 75.0, null], ["b4", "constant", 120.0, null]]],
	"maillots": [Vector3(-1.2, 1.7, -1.0), Vector3(2.1, 1.0, -7.5), 50.0,
		[["b1", "constant", 5.0, "kom"], ["b2", "constant", 9.0, "sprint"]]],
}


## Route droite à plat vers −Z (cap 0°, interface de route_data.gd utilisée par bots_view.gd).
class StraightRoute:
	func wrap_s(s: float) -> float:
		return s

	func sample(s: float) -> Dictionary:
		return {"x": 0.0, "y": 0.0, "z": -s, "heading_deg": 0.0, "grade_pct": 0.0}

	func sample_point(s: float) -> Vector3:
		return Vector3(0.0, 0.0, -s)


var _out_dir := "user://vitrine_bots"
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
	var csv := FileAccess.open(_out_dir.path_join("vitrine_bots.csv"), FileAccess.WRITE)
	csv.store_line("vue;préréglage;triangles_image;appels_dessin;bots;lod0;lod1;lod2")
	var route := StraightRoute.new()
	for preset in _presets:
		for view in VIEWS:
			var vp := _build_world(preset)
			var avatar = AvatarView.new()
			vp.add_child(avatar)
			avatar.set_visible_for_view("follow")
			avatar.configure(AvatarModel.parse_settings(DEMO), 0)
			avatar.position = Vector3(RoadBuilder.RIDER_LATERAL_M, 0.0, 0.0)
			avatar.apply_pose(0.6, false)
			var bots = BotsView.new()
			if bots.has_method("set_quality"):
				bots.set_quality(preset)
			vp.add_child(bots)
			var v: Array = VIEWS[view]
			var cam: Camera3D = vp.get_node("Camera")
			cam.fov = v[2]
			cam.look_at_from_position(v[0], v[1])
			var items := []
			for b in v[3]:
				var kind: String = b[1]
				items.append({"id": b[0], "name": "Fantôme" if kind == "ghost" else "Bot %s" % b[0], "kind": kind,
					"s": float(b[2]), "gap_m": float(b[2]), "visible": true, "show_name": float(b[2]) < BotsViewModel.NAME_M,
					"color": BotsViewModel.color_of(kind), "jersey": b[3]})
			for f in range(SETTLE_FRAMES):
				bots.update_view(items, route)
				await process_frame
			var path := _out_dir.path_join("bots_%s_%s.png" % [view, preset])
			vp.get_texture().get_image().save_png(path)
			var rid := vp.get_viewport_rid()
			var tris := RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
			var draws := RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
			var info: Dictionary = bots.test_info(cam)
			var lods: Array = info.get("lods", [0, 0, 0])
			csv.store_line("%s;%s;%d;%d;%d;%d;%d;%d" % [view, preset, tris, draws, int(info["shown"]), lods[0], lods[1], lods[2]])
			print("[vitrine_bots] %s : %d triangles, %d appels de dessin, %d bots (niveaux %s)" % [path, tris, draws, int(info["shown"]), str(lods)])
			vp.queue_free()
			await process_frame
	csv.close()
	quit(0)


## Ciel procédural, soleil du thème par défaut, sol au shader du terrain, route droite (comme vitrine_avatar.gd).
func _build_world(preset: String) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = SIZE
	vp.own_world_3d = true
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
	vp.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(400.0, 400.0)
	ground.mesh = plane
	ground.position = Vector3(0.0, -0.02, -150.0)
	ground.material_override = TerrainMaterial.create_material()
	vp.add_child(ground)
	var road := MeshInstance3D.new()
	var road_plane := PlaneMesh.new()
	road_plane.size = Vector2(RoadBuilder.ROAD_WIDTH_M, 400.0)
	road.mesh = road_plane
	road.position = Vector3(0.0, 0.0, -150.0)
	road.material_override = RoadBuilder.make_markings_material(RoadBuilder.ROAD_COLOR, RoadBuilder.ROAD_WIDTH_M)
	vp.add_child(road)
	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.current = true
	vp.add_child(cam)
	RenderQuality.apply_preset(preset, cam, sun, env, vp)
	RenderQuality.apply_fog(env, preset, false)
	return vp
