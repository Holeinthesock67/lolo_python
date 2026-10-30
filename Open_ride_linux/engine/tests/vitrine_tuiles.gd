extends SceneTree

## Vitrine de l'herbe loin de l'origine du monde : le vrai WorldStreamer sur un parcours avec couche terrain (démo
## `fake_world --demo --terrain`), herbe vue de près à côté de la route au départ, au milieu et à la fin du parcours,
## plus une vue de la route. Contrôle le défaut vu le 28 octobre (« les tuiles de l'herbe ne sont pas parfaitement
## jointives ») : le bruit de surface_detail.gdshaderinc perdait sa précision loin de l'origine et l'herbe devenait
## un damier de carrés flous. Mesure du détail fin : écart moyen entre pixels voisins dans le bas de l'image ; il doit
## rester au moins à DETAIL_MIN_RATIO de celui du départ (avant correction : 0,26 à 2,5 km, 0,08 à 4,9 km).
##
##   python -m openride_core.tools.fake_world --demo --terrain --out DOSSIER   (dans core/, PYTHONPATH=src)
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_tuiles.gd -- --world DOSSIER/demo.world --out SORTIE \
##     [--quality low] [--size 1280x720]
##
## Écrit SORTIE/<vue>_<préréglage>.png et SORTIE/vitrine_tuiles.csv (vue ; abscisse ; distance à l'origine ;
## détail fin ; rapport au départ). Code de sortie 1 si une vue d'herbe passe sous DETAIL_MIN_RATIO.

const RouteDataScript := preload("res://scripts/route_data.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const LivingWorld := preload("res://scripts/living_world.gd")

const GRASS_S: Array[float] = [0.0, 2500.0, 4900.0]
const DETAIL_MIN_RATIO := 0.6
const SETTLE_FRAMES := 8

var _world := ""
var _out_dir := "user://vitrine_tuiles"
var _preset := "low"
var _size := Vector2i(1280, 720)


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size()):
		match args[i]:
			"--world":
				_world = args[i + 1]
			"--out":
				_out_dir = args[i + 1]
			"--quality":
				_preset = args[i + 1]
			"--size":
				var wh: PackedStringArray = args[i + 1].split("x")
				_size = Vector2i(int(wh[0]), int(wh[1]))
	call_deferred("_run")


## Écart moyen (0 à 255) entre pixels voisins, en luminance, sur le bas de l'image (sol à moins de 5 m).
static func fine_detail(img: Image) -> float:
	var total := 0.0
	var count := 0
	var y0 := int(img.get_height() * 0.72)
	for y in range(y0, img.get_height() - 1):
		for x in range(0, img.get_width() - 1):
			var l := img.get_pixel(x, y).get_luminance()
			total += absf(img.get_pixel(x + 1, y).get_luminance() - l) + absf(img.get_pixel(x, y + 1).get_luminance() - l)
			count += 1
	return total / maxf(count, 1) * 255.0


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out_dir))
	var route = RouteDataScript.new()
	if not route.load_world_dir(_world):
		printerr("Parcours illisible : ", _world)
		quit(1)
		return
	var vp := SubViewport.new()
	vp.size = _size
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	# Ciel procédural (le ciel physique reste noir en rendu logiciel), soleil du thème par défaut comme main.gd
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(-(ThemeRenderParams.sky_params({})["sun_direction"] as Vector3), Vector3.UP)
	sun.shadow_enabled = true
	vp.add_child(sun)
	var cam := Camera3D.new()
	cam.current = true
	vp.add_child(cam)
	RenderQuality.apply_preset(_preset, cam, sun, env, vp)
	RenderQuality.apply_fog(env, _preset, true)
	var theme_res: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)
	var st = WorldStreamer.new()
	vp.add_child(st)
	var osm_st = OsmStreamer.new()
	st.add_child(osm_st)
	st.osm_streamer = osm_st
	st.set_theme(theme_res["theme"], ThemeLoader.DEFAULT_THEME_DIR)
	st.set_world(route, _world)
	# Touffes d'herbe branchées comme dans main.gd (living_world.gd) : elles doivent suivre le relief
	var lw = LivingWorld.new()
	vp.add_child(lw)
	lw.configure(_preset, true, theme_res["theme"], null, null, osm_st, null)
	lw.set_route(route)

	# Vues : [nom, abscisse, œil, point visé] ; herbe à 10 m à droite de la route, œil à 1,6 m, 2 m en arrière
	var views := []
	for s in GRASS_S:
		var p: Vector3 = route.sample_point(s)
		var h := deg_to_rad(route.sample_heading_deg(s))
		var fwd := Vector3(sin(h), 0.0, -cos(h))
		var g := p + Vector3(cos(h), 0.0, sin(h)) * 10.0
		views.append(["herbe_pres_%d" % int(s), s, g + Vector3(0.0, 1.6, 0.0) - fwd * 2.0, g + fwd * 4.0])
	# Vue de la caméra de séance (5 m derrière le cycliste, 2,2 m de haut) : capture du user du 28 octobre à 2,20 km
	for s_road in [2200.0]:
		var eye: Vector3 = route.sample_point(s_road - 5.0) + Vector3(0.0, 2.2, 0.0)
		views.append(["camera_%d" % int(s_road), s_road, eye, route.sample_point(s_road + 20.0) + Vector3(0.0, 0.3, 0.0)])

	var csv := FileAccess.open(_out_dir.path_join("vitrine_tuiles.csv"), FileAccess.WRITE)
	csv.store_line("vue;s_m;distance_origine_m;detail_fin;rapport_depart")
	var ref := -1.0
	var ok := true
	for v in views:
		cam.position = v[2]
		cam.look_at(v[3], Vector3.UP)
		st.update_window(float(v[1]), 0.0, cam.global_position)
		st.flush()
		for i in range(400):
			lw.grass.update(float(v[1]))
			if lw.grass.is_settled():
				break
		for i in SETTLE_FRAMES:
			await process_frame
		var img := vp.get_texture().get_image()
		img.save_png(_out_dir.path_join("%s_%s.png" % [v[0], _preset]))
		var dist := Vector2((v[2] as Vector3).x, (v[2] as Vector3).z).length()
		var detail := fine_detail(img)
		var ratio := 1.0
		if String(v[0]).begins_with("herbe_pres"):
			if ref < 0.0:
				ref = detail
			ratio = detail / maxf(ref, 1e-6)
			if ratio < DETAIL_MIN_RATIO:
				ok = false
		csv.store_line("%s;%.0f;%.0f;%.2f;%.2f" % [v[0], v[1], dist, detail, ratio])
		print("[vitrine_tuiles] %s : %.0f m de l'origine, détail fin %.2f (%.2f du départ)" % [v[0], dist, detail, ratio])
	csv.close()
	if not ok:
		printerr("[vitrine_tuiles] ÉCHEC : l'herbe perd son détail fin loin de l'origine (< %.0f %% du départ)" % (DETAIL_MIN_RATIO * 100.0))
	quit(0 if ok else 1)
