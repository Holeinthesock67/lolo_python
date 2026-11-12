extends SceneTree

## Vitrine des bâtiments sur une pente : maisons posées comme par le compilateur (`base_y` = terrain le plus bas
## sous l'empreinte, format .world §6) sur un versant de 14 %, vues de l'amont (fenêtres au ras de l'herbe avant
## la correction) et de l'aval (socle). « avant » : maillage sans `ground_max_y` ; « apres » : `ground_max_y`
## lu le long des façades comme dans osm_streamer.gd (`ground_max_along`), rez-de-chaussée relevé.
## Mêmes fonctions que la scène principale : terrain_tiles.gd, terrain_material.gd, building_mesh.gd.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver vulkan --rendering-method forward_plus \
##     --audio-driver Dummy --script res://tests/vitrine_batiments_pente.gd -- --out DOSSIER [--preset medium]
##
## Écrit DOSSIER/<avant|apres>_<amont|aval|biais>.png et DOSSIER/vitrine_batiments_pente.csv (état ; maison ;
## base_y ; terrain le plus haut ; relèvement).

const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const BuildingMesh := preload("res://scripts/building_mesh.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

const SIZE := Vector2i(1280, 720)
const SETTLE_FRAMES := 20
const SLOPE := 0.14
## Maisons : x0, z0, largeur, profondeur, hauteur, style (variantes de building_styles.gd)
const HOUSES := [
	[-30.0, -60.0, 11.0, 9.0, 6.0, "tuile_plate"],
	[-12.0, -58.0, 12.0, 10.0, 7.0, "ardoise"],
	[6.0, -60.0, 10.0, 8.0, 6.0, "chalet"],
	[22.0, -57.0, 14.0, 11.0, 9.0, "tuile_ronde"],
]
## Caméras : position, cible
const VIEWS := {
	"amont": [Vector3(-4.0, 0.0, -88.0), Vector3(-4.0, 0.0, -62.0)],
	"aval": [Vector3(-4.0, 0.0, -32.0), Vector3(-4.0, 0.0, -60.0)],
	"biais": [Vector3(-46.0, 0.0, -84.0), Vector3(-24.0, 0.0, -62.0)],
}

var _out_dir := "user://vitrine_batiments_pente"
var _preset := "medium"


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--preset":
			_preset = args[i + 1]
	call_deferred("_run")


## Versant : le terrain monte vers −z (14 %), légère ondulation en x.
static func _ground(x: float, z: float) -> float:
	return 200.0 + SLOPE * -z + 0.6 * sin(x / 23.0)


## Terrain le plus bas sous l'empreinte, comme le compilateur (grille de 1 m, contour compris).
static func _base_y(ring: Array) -> float:
	var lo := INF
	var x0: float = ring[0][0]
	var z0: float = ring[0][1]
	var x1: float = ring[2][0]
	var z1: float = ring[2][1]
	var x := minf(x0, x1)
	while x <= maxf(x0, x1) + 1e-6:
		var z := minf(z0, z1)
		while z <= maxf(z0, z1) + 1e-6:
			lo = minf(lo, _ground(x, z))
			z += 1.0
		x += 1.0
	return snappedf(lo, 0.01)


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var theme: Dictionary = ThemeLoader.new().load_named("default")["theme"]
	var csv := FileAccess.open(_out_dir.path_join("vitrine_batiments_pente.csv"), FileAccess.WRITE)
	csv.store_line("état;maison;base_y;terrain_haut;relèvement_m")
	for state in ["avant", "apres"]:
		var items := []
		for i in range(HOUSES.size()):
			var h: Array = HOUSES[i]
			var ring := [[h[0], h[1]], [h[0] + h[2], h[1]], [h[0] + h[2], h[1] - h[3]], [h[0], h[1] - h[3]]]
			var b := {"id": "pente_%d" % i, "outer": ring, "holes": [], "base_y": _base_y(ring), "height_m": h[4],
				"roof": "flat", "style": h[5], "hint": {"building": "house", "colour": null}}
			var top = OsmStreamer.ground_max_along(ring, _ground)
			if state == "apres":
				b["ground_max_y"] = top
			csv.store_line("%s;%d;%.2f;%.2f;%.2f" % [state, i, b["base_y"], float(top),
				BuildingMesh.floor_lift(b["base_y"], b.get("ground_max_y", null))])
			items.append(b)
		var vp := _build_world(items, theme)
		var cam: Camera3D = vp.get_node("Camera")
		for view in VIEWS:
			var p: Vector3 = VIEWS[view][0]
			var t: Vector3 = VIEWS[view][1]
			p.y = _ground(p.x, p.z) + 1.7
			t.y = _ground(t.x, t.z) + 1.5
			cam.look_at_from_position(p, t, Vector3.UP)
			for _f in range(SETTLE_FRAMES):
				await process_frame
			vp.get_texture().get_image().save_png(_out_dir.path_join("%s_%s.png" % [state, view]))
		vp.queue_free()
		for _f in range(4):
			await process_frame
	csv.close()
	print("vitrine_batiments_pente : captures dans ", ProjectSettings.globalize_path(_out_dir))
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

	var mat := TerrainMaterial.create_material()
	for ix in range(-1, 1):
		for iz in range(-1, 1):
			var heights := PackedFloat32Array()
			heights.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
			var o := TerrainTiles.tile_origin("near", ix, iz)
			for j in range(TerrainTiles.SAMPLES):
				for i in range(TerrainTiles.SAMPLES):
					heights[j * TerrainTiles.SAMPLES + i] = _ground(o.x + i * 10.0, o.z + j * 10.0)
			var tile := MeshInstance3D.new()
			tile.mesh = _mesh(TerrainTiles.build_arrays(heights, "near", {}, 1.0, 200.0))
			tile.position = o
			tile.material_override = mat
			vp.add_child(tile)

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
	var bmat := BuildingMesh.make_material()
	BuildingMesh.apply_preset(bmat, _preset)
	var bi := MeshInstance3D.new()
	bi.mesh = mesh
	bi.material_override = bmat
	vp.add_child(bi)

	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.fov = 65.0
	cam.far = 2000.0
	vp.add_child(cam)
	return vp


static func _mesh(arrays: Array) -> ArrayMesh:
	var mesh := ArrayMesh.new()
	if not arrays.is_empty():
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh
