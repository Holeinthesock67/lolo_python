extends SceneTree

## Vitrine des toits fermés (fil « Fermer les toits des maisons », retour d'essai du 21/11) : rangée d'immeubles
## de bois peint (style du Grand Nord) et maisons à contours non rectangulaires, comme les empreintes OSM, vues
## de la rue en contre-plongée. Avant la correction, le haut d'un pignon perdait sa coupe au faîtage et restait
## plat : le ciel se voyait entre le mur et le toit. Même maillage que la scène principale (building_mesh.gd).
##
##   xvfb-run -a $GODOT --path engine --rendering-driver vulkan --rendering-method forward_plus \
##     --audio-driver Dummy --script res://tests/vitrine_toits_fermes.gd -- --out DOSSIER [--tag apres] [--preset medium]
##
## Écrit DOSSIER/<tag>_<vue>.png et DOSSIER/<tag>_toits.csv (bâtiment ; défauts relevés par tests/roof_seal.gd).

const BuildingMesh := preload("res://scripts/building_mesh.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const RoofSeal := preload("res://tests/roof_seal.gd")

const SIZE := Vector2i(1280, 720)
const SETTLE_FRAMES := 20
## Bâtiments : identifiant, contour (x, z), hauteur, style, type OSM, toit de la couche
const BUILDINGS := [
	["immeuble_1", [[0, 0], [16, 1.2], [15.2, 12.5], [-0.8, 11.0]], 12.0, "bois_peint", "apartments", "gabled"],
	["immeuble_2", [[-15.5, -1.0], [0, 0], [-0.8, 11.0], [-16.0, 10.2]], 11.0, "bois_peint", "apartments", "gabled"],
	["immeuble_3", [[-30.0, -2.4], [-15.5, -1.0], [-16.0, 10.2], [-30.5, 9.0]], 10.0, "bois_peint", "apartments", "gabled"],
	["maison_1", [[24, -2], [36, 0.5], [34.5, 9.5], [23, 8]], 7.0, "tuile_plate", "house", "flat"],
	["maison_2", [[42, -3], [52, -1], [50, 8], [41, 6.5]], 6.5, "ardoise", "house", "flat"],
	["eglise", [[-60, -6], [-36, -3], [-37.5, 9], [-61, 6.5]], 12.0, "tuile_plate", "church", "flat"],
]
## Décalage des empreintes et des caméras : les bâtiments du monde sont loin de l'origine (le défaut venait de
## l'arrondi des plans du toit en flottants 32 bits)
const OFFSET := Vector3(3817.5, 0.0, -2264.25)
const VIEWS := {
	"rue": [Vector3(6.0, 1.7, -20.0), Vector3(2.0, 9.0, 4.0)],
	"pignon": [Vector3(30.0, 1.7, -9.0), Vector3(14.0, 10.0, 6.0)],
	"maisons": [Vector3(38.0, 1.7, -16.0), Vector3(38.0, 6.0, 3.0)],
	"eglise": [Vector3(-34.0, 1.7, -22.0), Vector3(-48.0, 10.0, 2.0)],
}

var _out_dir := "user://vitrine_toits_fermes"
var _preset := "medium"
var _tag := "apres"


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--preset":
			_preset = args[i + 1]
		elif args[i] == "--tag":
			_tag = args[i + 1]
	call_deferred("_run")


func _items() -> Array:
	var items := []
	for b in BUILDINGS:
		var ring := []
		for p in b[1]:
			ring.append([p[0] + OFFSET.x, p[1] + OFFSET.z])
		items.append({"id": b[0], "outer": ring, "holes": [], "base_y": 0.0, "height_m": b[2], "roof": b[5],
			"style": b[3], "hint": {"building": b[4], "colour": null}})
	return items


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var theme: Dictionary = ThemeLoader.new().load_named("default")["theme"]
	var csv := FileAccess.open(_out_dir.path_join("%s_toits.csv" % _tag), FileAccess.WRITE)
	csv.store_line("bâtiment;défauts")
	for item in _items():
		var one := BuildingMesh.build([item], theme, 0.0)
		csv.store_line("%s;%s" % [item["id"], " | ".join(RoofSeal.defects(one))])
	csv.close()
	var vp := _build_world(_items(), theme)
	var cam: Camera3D = vp.get_node("Camera")
	for view in VIEWS:
		cam.look_at_from_position(VIEWS[view][0] + OFFSET, VIEWS[view][1] + OFFSET, Vector3.UP)
		for _f in range(SETTLE_FRAMES):
			await process_frame
		vp.get_texture().get_image().save_png(_out_dir.path_join("%s_%s.png" % [_tag, view]))
	vp.queue_free()
	for _f in range(4):
		await process_frame
	print("vitrine_toits_fermes : captures dans ", ProjectSettings.globalize_path(_out_dir))
	quit(0)


func _build_world(items: Array, theme: Dictionary) -> SubViewport:
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
	plane.size = Vector2(400.0, 400.0)
	ground.mesh = plane
	ground.position = OFFSET
	var gmat := StandardMaterial3D.new()
	gmat.albedo_color = Color(0.36, 0.45, 0.28)
	ground.material_override = gmat
	vp.add_child(ground)

	var m := BuildingMesh.build(items, theme, 0.5)
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
	var bmat := BuildingMesh.make_material()
	BuildingMesh.apply_preset(bmat, _preset)
	var bi := MeshInstance3D.new()
	bi.mesh = mesh
	bi.material_override = bmat
	vp.add_child(bi)

	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.fov = 70.0
	cam.far = 2000.0
	vp.add_child(cam)
	return vp
