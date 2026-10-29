extends SceneTree

## Vitrine de rendu : route, herbe, personnages et animaux vus de près, sans core ni parcours, pour comparer avant et
## après une retouche graphique (captures PNG et compte de triangles et d'appels de dessin par vue).
## Mêmes scripts que la scène principale (grass_tufts.gd, crowd_renderer.gd, terrain.gdshader), posés
## sur une route droite de démonstration ; les modèles de foule et de passants sont remplacés par des
## listes fixes pour que deux captures soient comparables.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_rendu.gd -- --out DOSSIER [--quality low,medium,high]
##
## Le préréglage demandé est appliqué comme dans la scène principale (render_quality.gd : image, ombres,
## brouillard ; lot X32) ; avant, la vitrine n'en appliquait aucun et ne montrait pas les effets de Y13.
## Écrit DOSSIER/<vue>_<préréglage>.png et DOSSIER/vitrine.csv (vue ; préréglage ; qualité appliquée ;
## triangles ; appels de dessin ; objets). Les temps du processeur graphique se mesurent sur le PC cible (perf_probe.py),
## pas ici : le rendu logiciel de Xvfb ne dit rien de la GTX 1060.

const GrassTufts := preload("res://scripts/grass_tufts.gd")
const CrowdRenderer := preload("res://scripts/crowd_renderer.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const PeopleMesh := preload("res://scripts/people_mesh.gd")
const CrowdShader := preload("res://shaders/crowd.gdshader")
const FaunaRenderer := preload("res://scripts/fauna_renderer.gd")
const BuildingMesh := preload("res://scripts/building_mesh.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const TreeSpecies := preload("res://scripts/tree_species.gd")
const RoadsideProps := preload("res://scripts/roadside_props.gd")
const WindTurbines := preload("res://scripts/wind_turbines.gd")

const SIZE := Vector2i(1280, 720)
const ROAD_WIDTH_M := 6.0
const SETTLE_FRAMES := 30

## Vues : position de la caméra, point visé, champ vertical (degrés).
const VIEWS := {
	"route": [Vector3(0.8, 1.4, 0.0), Vector3(0.0, 0.0, -9.0), 70.0],
	"herbe": [Vector3(2.6, 1.4, 0.0), Vector3(5.0, 0.4, -14.0), 70.0],
	"herbe_loin": [Vector3(0.0, 1.4, 0.0), Vector3(0.0, 0.8, -60.0), 70.0],
	"foule": [Vector3(1.0, 1.5, -2.0), Vector3(4.6, 1.1, -10.0), 55.0],
	"cyclistes": [Vector3(-1.6, 1.5, -3.0), Vector3(1.0, 0.9, -9.5), 55.0],
	"cycliste_profil": [Vector3(-2.5, 1.0, -7.2), Vector3(1.2, 0.9, -7.2), 45.0],
	"passants": [Vector3(0.5, 1.5, -24.0), Vector3(5.0, 0.9, -31.0), 60.0],
	"animaux": [Vector3(-1.5, 1.6, -3.0), Vector3(-7.0, 0.8, -12.5), 55.0],
	"animaux_pres": [Vector3(-4.0, 1.2, -9.6), Vector3(-7.5, 0.9, -13.0), 50.0],
	"village": [Vector3(1.0, 1.6, -14.0), Vector3(-1.0, 4.0, -60.0), 70.0],
	"maisons": [Vector3(2.0, 1.6, -16.0), Vector3(14.0, 3.5, -28.0), 60.0],
	"facades_pres": [Vector3(-3.5, 1.6, -18.0), Vector3(-11.0, 3.0, -26.0), 55.0],
	"toits": [Vector3(3.0, 22.0, -6.0), Vector3(-2.0, 2.0, -48.0), 60.0],
	"styles": [Vector3(-104.0, 30.0, -82.0), Vector3(-104.0, 1.0, -134.0), 58.0],
	"arbres_temperes": [Vector3(147.0, 5.0, -86.0), Vector3(147.0, 8.0, -120.0), 60.0],
	"arbres_sud": [Vector3(153.0, 4.0, -128.0), Vector3(153.0, 4.5, -160.0), 60.0],
	"ecorces": [Vector3(129.0, 1.8, -112.0), Vector3(129.0, 2.4, -120.0), 55.0],
	"panneaux": [Vector3(58.5, 1.5, -15.5), Vector3(61.5, 1.3, -22.0), 50.0],
	"eolienne": [Vector3(-75.0, 2.0, -150.0), Vector3(-120.0, 55.0, -300.0), 60.0],
	"eolienne_pied": [Vector3(-113.0, 1.7, -287.0), Vector3(-120.0, 8.0, -300.0), 60.0],
}
## Objets du bord de route (roadside_props.gd, lot P14) : panneau de col, panneau d'approche, borne.
const PROPS := [
	[{"kind": "summit", "s": 0.0, "lines": ["COL DE TEST", "1 234 m"]}, Vector3(60.0, 0.0, -22.0)],
	[{"kind": "approach", "s": 0.0, "lines": ["SOMMET 2 km", "7 %"]}, Vector3(63.0, 0.0, -24.0)],
	[{"kind": "km", "s": 0.0, "lines": ["3"]}, Vector3(61.8, 0.0, -19.5)],
]
## Arbres de tree_species.gd (lot U7) et arbre d'avant la série U, en deux rangées loin de la route.
const TREES_TEMPERATE := ["oak", "birch", "pine", "beech", "spruce", "larch", "generic"]
const TREES_SOUTH := ["olive", "holm_oak", "cypress", "stone_pine", "palm", "acacia", "baobab", "cactus",
	"tree_fern", "reed", "dwarf_shrub", "vine_row"]
## Une maison et une grange par style d'architecture (variantes du contrat U1, building_styles.gd), en rangée
## loin de la route : les styles que prendront les biomes et les régions de la série U.
const STYLE_ROW := ["tuile_plate", "tuile_ronde", "ardoise", "pierre_seche", "toit_plat_blanc", "bois"]
## Bâtiments de la vitrine (forme de la couche `buildings` du .world) : type OSM, contour [x, z], hauteur des murs (m).
## Un échantillon des types courants des villages : maisons, ferme, église, immeuble, atelier, hangar, magasin.
const BUILDINGS := [
	["house", [[-9.0, -21.0], [-9.0, -29.0], [-19.0, -29.0], [-19.0, -21.0]], 6.0],
	["house", [[-9.5, -33.0], [-10.5, -41.0], [-18.5, -40.0], [-17.5, -32.0]], 6.5],
	["yes", [[-9.0, -46.0], [-9.0, -56.0], [-15.0, -56.0], [-15.0, -50.0], [-21.0, -50.0], [-21.0, -46.0]], 5.5],
	["church", [[-12.0, -64.0], [-12.0, -86.0], [-22.0, -86.0], [-22.0, -64.0]], 11.0],
	["shed", [[-21.5, -22.0], [-21.5, -26.0], [-24.5, -26.0], [-24.5, -22.0]], 2.6],
	["barn", [[10.0, -19.0], [10.0, -35.0], [22.0, -35.0], [22.0, -19.0]], 6.5],
	["apartments", [[9.0, -40.0], [9.0, -60.0], [21.0, -60.0], [21.0, -40.0]], 12.0],
	["retail", [[9.0, -66.0], [9.0, -80.0], [27.0, -80.0], [27.0, -66.0]], 5.0],
	["industrial", [[30.0, -40.0], [30.0, -80.0], [56.0, -80.0], [56.0, -40.0]], 8.0],
]

## Animaux (fauna_renderer.gd build_mesh et fauna.gdshader) : espèce, position, cap (radians), phase, tête levée.
const ANIMALS := [
	["cow", Vector3(-7.5, 0.0, -13.0), 1.75, 0.1, 1.0], ["cow", Vector3(-10.5, 0.0, -17.0), 2.6, 0.7, 0.0],
	["sheep", Vector3(-5.2, 0.0, -14.5), -0.4, 0.2, 1.0], ["sheep", Vector3(-6.0, 0.0, -16.0), 0.9, 0.5, 0.0],
	["sheep", Vector3(-4.4, 0.0, -16.8), 2.2, 0.8, 1.0], ["deer", Vector3(-12.0, 0.0, -11.5), 0.6, 0.3, 1.0],
	["bird", Vector3(-4.5, 2.4, -8.5), 1.2, 0.0, 0.0], ["bird", Vector3(-6.5, 3.0, -10.0), 0.9, 0.4, 0.0],
]


## Route droite le long de -z (cap 0, comme route_data.gd) : seules les méthodes lues par grass_tufts.gd.
class StraightRoute:
	var length_m := 2000.0
	func is_loop() -> bool:
		return false
	func sample(s: float) -> Dictionary:
		return {"x": 0.0, "y": 0.0, "z": -s, "heading_deg": 0.0}


## Spectateurs fixes (forme de crowd_model.gd) : deux rangs à droite de la route, un sur deux encourage.
class FixedCrowd:
	var spectators := []
	var states := {}
	var groups := []
	func _init() -> void:
		for i in range(14):
			var row := i % 2
			var pos := Vector3(4.2 + row * 0.8, 0.0, -7.0 - (i / 2) * 0.9 - row * 0.4)
			spectators.append({"s": -pos.z, "side": 1, "pos": pos, "yaw": -PI * 0.5, "color": i * 3,
				"flag": i % 5 == 2, "phase": fmod(i * 0.37, 1.0), "delay": 0.0, "group": 0})
			states[i] = {"cheer": i % 2 == 0}


## Passants fixes (forme de passersby_model.gd) : un exemple de chaque animation, un chien, un banc.
class FixedPassersby:
	var people := []
	var selection_serial := 1
	var dog_count := 1
	var bench_count := 1
	var _entries := []
	func _init() -> void:
		var cast := [["walker", "walk", false], ["jogger", "run", false], ["sitter", "sit", true],
			["gardener", "garden", false], ["kid", "hop", true], ["dog_walker", "walk", false], ["walker", "stand", true]]
		for i in range(cast.size()):
			var pos := Vector3(4.5 + (i % 2) * 1.6, 0.0, -27.0 - i * 1.3)
			var yaw := -PI * 0.5 if cast[i][2] else PI
			people.append({"role": cast[i][0], "color": i * 2 + 1, "phase": fmod(i * 0.29, 1.0), "yaw": yaw, "pos": pos})
			_entries.append({"i": i, "pos": pos, "yaw": yaw, "anim": cast[i][1], "wave": cast[i][2], "dirty": true,
				"dog": 0 if cast[i][0] == "dog_walker" else -1, "dog_pos": pos + Vector3(0.6, 0.0, 0.8),
				"dog_yaw": PI, "bench": 0 if cast[i][0] == "sitter" else -1})
	func visible(_cam: Vector3, _s: float, _t: float, budget: int) -> Array:
		return _entries.slice(0, mini(budget, _entries.size()))


var _out_dir := "user://vitrine"
var _presets := ["low", "medium", "high"]


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
	var csv := FileAccess.open(_out_dir.path_join("vitrine.csv"), FileAccess.WRITE)
	csv.store_line("vue;préréglage;qualite_appliquee;triangles;appels_dessin;objets")
	for preset in _presets:
		var vp := _build_world(preset)
		for view in VIEWS:
			var v: Array = VIEWS[view]
			var cam: Camera3D = vp.get_node("Camera")
			cam.fov = v[2]
			cam.look_at_from_position(v[0], v[1])
			for f in range(SETTLE_FRAMES):
				await process_frame
			var img := vp.get_texture().get_image()
			var path := _out_dir.path_join("%s_%s.png" % [view, preset])
			img.save_png(path)
			var rid := vp.get_viewport_rid()
			var tris := RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
			var draws := RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
			var objs := RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_OBJECTS_IN_FRAME)
			csv.store_line("%s;%s;%s;%d;%d;%d" % [view, preset, QualityPresets.applied_name(preset), tris, draws, objs])
			print("[vitrine] %s : %d triangles, %d appels de dessin, %d objets" % [path, tris, draws, objs])
		vp.queue_free()
		await process_frame
	csv.close()
	quit(0)


## Monde de la vitrine pour un préréglage : ciel, soleil, sol au shader du terrain, route, touffes,
## spectateurs et passants avec les budgets de `QualityPresets.living(preset)`.
func _build_world(preset: String) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = SIZE
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	# Ciel procédural (le ciel physique de scenes/main.tscn reste noir en rendu logiciel), lumière
	# ambiante du ciel et soleil du thème par défaut comme main.gd
	var sky_mat := ProceduralSkyMaterial.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = sky_mat
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(-(ThemeRenderParams.sky_params({})["sun_direction"] as Vector3), Vector3.UP)   # comme main.gd
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 150.0
	vp.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(400.0, 400.0)
	plane.subdivide_width = 40
	plane.subdivide_depth = 40
	ground.mesh = plane
	ground.position = Vector3(0.0, -0.02, -150.0)
	ground.material_override = TerrainMaterial.create_material()
	vp.add_child(ground)
	var road := MeshInstance3D.new()
	road.mesh = _road_mesh()
	road.material_override = RoadBuilder.make_markings_material(RoadBuilder.ROAD_COLOR, ROAD_WIDTH_M)
	vp.add_child(road)
	var living := QualityPresets.living(preset)
	var tufts = GrassTufts.new()
	vp.add_child(tufts)
	tufts.configure(int(living["grass_tufts"]), StraightRoute.new(), ROAD_WIDTH_M, 7)
	for i in range(200):
		tufts.update(0.0)
		if tufts.is_settled():
			break
	TreeRenderer.apply_wind({"dir": Vector3(1.0, 0.0, 0.0), "strength": 0.3, "gust": 0.0, "phase": 0.0})
	tufts.set_apparent_wind(Vector3(0.0, 0.0, 6.0))
	var crowd = CrowdRenderer.new()
	vp.add_child(crowd)
	crowd.set_preset(preset)
	crowd.setup(FixedCrowd.new())
	crowd.update(Vector3(1.0, 1.5, -2.0), 0.0, 0.0)
	var passersby = CrowdRenderer.new("passersby")
	vp.add_child(passersby)
	passersby.set_preset(preset)
	passersby.setup_passersby(FixedPassersby.new())
	passersby.update_passersby(Vector3(0.5, 1.5, -24.0), 24.0, 0.0)
	_add_cyclists(vp)
	_add_animals(vp)
	_add_buildings(vp, preset)
	_add_trees(vp, preset)
	_add_props(vp, preset)
	var turbines = WindTurbines.new()
	turbines.set_preset(preset)
	vp.add_child(turbines)
	turbines.set_points([{"kind": "wind_turbine", "id": "vitrine", "x": -120.0, "y": 0.0, "z": -300.0, "height_m": 100.0}])
	turbines.update({"dir": Vector3(0.0, 0.0, 1.0), "strength": 0.0}, Vector3(-75.0, 2.0, -150.0), 0.0)
	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.current = true
	vp.add_child(cam)
	RenderQuality.apply_preset(preset, cam, sun, env, vp)
	RenderQuality.apply_fog(env, preset, false)
	print("Qualité appliquée : %s (demandée %s, source vitrine)" % [QualityPresets.applied_name(preset), preset])
	return vp


## Ruban de route droit de 400 m avec les UV d'E1 (u en travers, bas-côtés compris ; v = s / V_REPEAT_M).
func _road_mesh() -> ArrayMesh:
	var half := ROAD_WIDTH_M * 0.5 + RoadBuilder.SHOULDER_WIDTH_M
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var step := 2.0
	for j in range(200):
		var s0 := j * step
		var s1 := s0 + step
		var quad := [[-half, s0, 0.0], [half, s1, 1.0], [half, s0, 1.0], [-half, s0, 0.0], [-half, s1, 0.0], [half, s1, 1.0]]
		for q in quad:
			st.set_normal(Vector3.UP)
			st.set_uv(Vector2(q[2], q[1] / RoadBuilder.V_REPEAT_M))
			st.add_vertex(Vector3(q[0], 0.0, -q[1]))
	st.generate_tangents()
	return st.commit()


## Cyclistes de people_mesh.gd (coureur casqué qui pédale et vélo), tels que les bots d'O7 les afficheraient :
## trois coureurs à la file sur la voie de droite, maillots aux couleurs des bots.
func _add_cyclists(vp: SubViewport) -> void:
	var mat := ShaderMaterial.new()
	mat.shader = CrowdShader
	PeopleMesh.apply_palettes(mat)
	var places := [[Vector3(1.2, 0.0, -7.0), Color(0.85, 0.15, 0.15), 0.9], [Vector3(1.0, 0.0, -9.6), Color(0.1, 0.4, 0.85), 0.85],
		[Vector3(1.5, 0.0, -12.5), Color(0.95, 0.8, 0.1), 0.95]]
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
			var anim := 7.0 if kind == "rider" else 8.0
			mm.set_instance_custom_data(i, Color(0.3 * i, places[i][2], anim, PeopleMesh.outfit(i * 2, i + 1, PeopleMesh.RIDER_OUTFIT_TROUSERS)))
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = mat
		vp.add_child(mmi)


## Bêtes et oiseaux posés à la main (ANIMALS), avec les maillages et le shader de fauna_renderer.gd ; oiseaux
## à l'échelle des rapaces, ailes battantes.
func _add_animals(vp: SubViewport) -> void:
	for sp in FaunaRenderer.SPECIES:
		var mat := FaunaRenderer.make_material(sp)
		var mine := ANIMALS.filter(func(a): return a[0] == sp)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = FaunaRenderer.build_mesh(sp)
		mm.instance_count = mine.size()
		for i in range(mine.size()):
			var a: Array = mine[i]
			var scale := FaunaRenderer.BIRD_SCALE["raptor"] if sp == "bird" else 1.0
			mm.set_instance_transform(i, Transform3D(Basis(Vector3.UP, a[2]).scaled(Vector3.ONE * scale), a[1]))
			mm.set_instance_custom_data(i, Color(a[3], a[4], 1.0 if sp == "bird" else 0.0, 0.0))
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = mat
		vp.add_child(mmi)


## Arbres en LOD 0 avec le matériau de la scène principale (tree_renderer.gd, balancement au vent compris).
func _add_trees(vp: SubViewport, preset: String) -> void:
	var rows := [[TREES_TEMPERATE, 120.0, -120.0, 9.0], [TREES_SOUTH, 120.0, -160.0, 6.0]]
	for row in rows:
		var kinds: Array = row[0]
		for i in range(kinds.size()):
			var kind: String = kinds[i]
			var mi := MeshInstance3D.new()
			var mat := TreeRenderer.sway_material(false)
			if kind == "generic":
				mi.mesh = TreeRenderer.build_lod0_mesh()
			else:
				var built := TreeSpecies.build(kind)
				mi.mesh = built["lod0"]
				mat.set_shader_parameter("sway_height_m", float(built["height"]))
			mi.material_override = mat
			mi.position = Vector3(float(row[1]) + i * float(row[3]), 0.0, float(row[2]))
			vp.add_child(mi)


## Panneaux et borne de PROPS avec les matériaux de la scène principale, face à la caméra de la vue `panneaux`.
func _add_props(vp: SubViewport, preset: String) -> void:
	var props = RoadsideProps.new()
	props.set_preset(preset)
	vp.add_child(props)
	for it in PROPS:
		var node: Node3D = props.build_prop(it[0])
		node.position = it[1]
		node.rotation.y = -0.35
		props.add_child(node)


## Village de BUILDINGS maillé par building_mesh.gd avec le matériau de la scène principale (osm_streamer.gd).
func _add_buildings(vp: SubViewport, preset: String) -> void:
	var items := []
	for i in range(BUILDINGS.size()):
		var b: Array = BUILDINGS[i]
		items.append({"id": "vitrine_%d" % i, "outer": b[1], "holes": [], "base_y": 0.0, "height_m": b[2],
			"roof": "flat", "hint": {"building": b[0], "colour": null}})
	for j in range(STYLE_ROW.size()):
		var x0 := -150.0 + j * 16.0
		items.append({"id": "style_maison_%d" % j, "outer": [[x0, -120.0], [x0 + 11.0, -120.0], [x0 + 11.0, -128.0], [x0, -128.0]],
			"holes": [], "base_y": 0.0, "height_m": 6.0, "roof": "flat", "style": STYLE_ROW[j],
			"hint": {"building": "house", "colour": null}})
		items.append({"id": "style_grange_%d" % j, "outer": [[x0, -134.0], [x0 + 12.0, -134.0], [x0 + 12.0, -146.0], [x0, -146.0]],
			"holes": [], "base_y": 0.0, "height_m": 5.0, "roof": "flat", "style": STYLE_ROW[j],
			"hint": {"building": "barn", "colour": null}})
	var theme: Dictionary = ThemeLoader.new().load_named("default")["theme"]
	var m := BuildingMesh.build(items, theme, 3.0)
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = m["vertices"]
	arr[Mesh.ARRAY_NORMAL] = m["normals"]
	arr[Mesh.ARRAY_COLOR] = m["colors"]
	arr[Mesh.ARRAY_TEX_UV] = m["uvs"]
	arr[Mesh.ARRAY_TEX_UV2] = m["uvs2"]
	arr[Mesh.ARRAY_INDEX] = m["indices"]
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	var mat := BuildingMesh.make_material()
	BuildingMesh.apply_preset(mat, preset)
	mi.material_override = mat
	vp.add_child(mi)
