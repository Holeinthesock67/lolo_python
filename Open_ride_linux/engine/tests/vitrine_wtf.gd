extends SceneTree

## Vitrine des gags en 3D du mode « What the fuck » (série WTF) sans core : l'avatar sur une route droite, vu
## comme en séance (vue de suivi), et chaque gag forcé (wtf_scene_model.gd puis wtf_scene.gd, caméra imposée
## et roulis compris), pour chaque préréglage demandé. Sert à juger les formes avant le banc du PC.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver vulkan --rendering-method forward_plus \
##     --audio-driver Dummy --script res://tests/vitrine_wtf.gd -- --out DOSSIER [--quality low,medium,high]
##
## Le HUD du mode (wtf_view.gd : bandeau, consigne « À toi », légende du premier passage) est dessiné par-dessus,
## comme en séance ; `--hud 0` le retire. Écrit DOSSIER/wtf_<gag>_<préréglage>.png. Les temps du GPU se mesurent sur le PC (sim_bench.py).

const AvatarModel := preload("res://scripts/avatar_model.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const WtfScene := preload("res://scripts/wtf/wtf_scene.gd")
const WtfSceneModel := preload("res://scripts/wtf/wtf_scene_model.gd")
const WtfHudModel := preload("res://scripts/wtf/wtf_hud_model.gd")
const WtfView := preload("res://scripts/wtf/wtf_view.gd")

const SIZE := Vector2i(1280, 720)
const SETTLE_FRAMES := 20
const DEMO := {"height": "M", "build": "medium", "skin": 3, "hair": 2, "hair_color": 1, "kit_primary": 4,
	"kit_secondary": 9, "number": 27}
## Gags : objet `wtf` de la trame `state` (contrat 1.5).
const GAGS := {
	"lune": {"event": {"id": "gravity", "planet": "moon", "hop_m": 2.5}},
	"jupiter": {"event": {"id": "gravity", "planet": "jupiter", "hop_m": 0.0}},
	"envers": {"event": {"id": "upside_down"}},
	"effondrement": {"event": {"id": "collapse", "left_s": 42.0, "gap_m": 130.0}},
	"effondrement_proche": {"event": {"id": "collapse", "left_s": 20.0, "gap_m": 8.0}},
	"fromage": {"event": {"id": "cheese", "gap_m": 60.0, "squashed": false}},
	"tornade": {"event": {"id": "storm", "cows": 24}},
	"cuisine": {"event": {"id": "tiny"}},
	"pigeon": {"event": {"id": "camera", "view": "pigeon"}},
	"escargot": {"event": {"id": "camera", "view": "snail"}},
	"roue": {"event": {"id": "camera", "view": "wheel"}},
	"chef": {"event": {"id": "chef", "phase": "reveal", "dish": "spaghetti", "phase_left_s": 4.0}},
	"chef_gelee": {"event": {"id": "chef", "phase": "reveal", "dish": "jelly", "phase_left_s": 4.0}},
	"chef_musette": {"event": {"id": "chef", "phase": "reveal", "dish": "musette", "phase_left_s": 4.0}},
	"chef_souffle": {"event": {"id": "chef", "phase": "reveal", "dish": "souffle", "phase_left_s": 4.0}},
	"chef_piment": {"event": {"id": "chef", "phase": "reveal", "dish": "chili", "phase_left_s": 4.0}},
	"katamari": {"kata": {"size": 2.0, "count": 12, "last": "sign", "next": [[7.0, "apple"], [13.0, "sign"], [22.0, "car"]]}},
	"katamari_gros": {"kata": {"size": 3.0, "count": 40, "last": "car", "next": [[9.0, "cow"], [20.0, "house"], [42.0, "church"]]}},
	"poissons": {"clock_h": 14.0, "fish": true},
	"objets_katamari": {"kata": {"size": 1.0, "count": 0}},   # vue faite à la main : OBJECTS_VIEW
}
## Les six objets du Katamari au sol, sans la boule qui les cache, à leur taille de jeu (KATA_SCALES), de part
## et d'autre de la route : [sorte, devant (m), à droite (m)].
const OBJECTS := [["apple", 6.0, 2.6], ["sign", 7.5, -2.2], ["cow", 11.0, 2.8], ["car", 15.0, -3.2],
	["house", 26.0, 6.0], ["church", 40.0, -9.0]]


## Route droite à plat vers −Z (interface de route_data.gd utilisée par wtf_scene.gd).
class StraightRoute:
	extends RefCounted
	func wrap_s(s: float) -> float:
		return s
	func sample_heading_deg(_s: float) -> float:
		return 0.0
	func sample_point(s: float) -> Vector3:
		return Vector3(0.0, 0.0, -s)


var _out_dir := "user://vitrine_wtf"
var _presets: Array = ["medium"]
var _only: Array = []
var _hud := true


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--quality":
			_presets = Array(args[i + 1].split(","))
		elif args[i] == "--gags":
			_only = Array(args[i + 1].split(","))
		elif args[i] == "--hud":
			_hud = args[i + 1] != "0"
	call_deferred("_run")


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var route := StraightRoute.new()
	for preset in _presets:
		for gag in GAGS:
			if not _only.is_empty() and not _only.has(gag):
				continue
			var vp := _build_world(preset)
			var sun: DirectionalLight3D = vp.get_node("Sun")
			var cam: Camera3D = vp.get_node("Camera")
			var avatar = AvatarView.new()
			vp.add_child(avatar)
			avatar.set_visible_for_view("follow")
			avatar.configure(AvatarModel.parse_settings(DEMO), 0)
			avatar.apply_pose(0.6, false)
			var scene = WtfScene.new()
			vp.add_child(scene)
			var wtf: Dictionary = (GAGS[gag] as Dictionary).duplicate(true)
			wtf["points"] = 120
			var hud = null
			if _hud:
				hud = WtfView.new()
				vp.add_child(hud)
			var pos := Vector3(RoadBuilder.RIDER_LATERAL_M, 0.0, 0.0)
			for f in range(SETTLE_FRAMES):
				var t := 10.0 + f * 0.05
				var v := WtfSceneModel.view(wtf, t, preset)
				if gag == "objets_katamari":
					v["props"] = OBJECTS.map(func(o): return {"kind": "kata_" + o[0], "ds": o[1], "lateral": o[2], "up": 0.0,
						"scale": float(WtfSceneModel.KATA_SCALES[o[0]]), "spin": 0.0})
				scene.step(v, route, 0.0, Callable(), sun)
				if hud != null:
					hud.update_view(WtfHudModel.view(wtf), t)
				cam.fov = 60.0
				cam.look_at_from_position(pos + Vector3(0.0, 1.9, 4.2), pos + Vector3(0.4, 1.0, -8.0))
				scene.apply_camera(cam, pos, 0.0, 0.1)
				if scene.has_method("rider_offset"):
					avatar.position = pos + scene.rider_offset()
				else:
					avatar.position = pos + Vector3.UP * scene.hop_m()
				if scene.has_method("rider_scale"):
					avatar.scale = Vector3.ONE * scene.rider_scale()
				await process_frame
			var path := _out_dir.path_join("wtf_%s_%s.png" % [gag, preset])
			vp.get_texture().get_image().save_png(path)
			print("[vitrine_wtf] %s : %s" % [path, str(scene.test_info())])
			vp.queue_free()
			await process_frame
	quit(0)


## Ciel procédural, soleil du thème par défaut, sol au shader du terrain, route droite (comme vitrine_bots.gd).
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
	sun.name = "Sun"
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
