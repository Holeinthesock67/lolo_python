extends SceneTree

## Vitrine des lumières de nuit (lot P35) : rue de village (maisons, commerces, immeuble), luminaires publics,
## lanterne de pierre, cycliste avec phare et feu arrière, à plusieurs heures du 13 novembre (48,9° N) :
## jour et nuit coupé (image d'aujourd'hui), midi, coucher, nuit. Mêmes fonctions que la scène principale :
## daylight_model.gd / atmosphere_view.gd (lumière de l'heure), night_lights.gd, building_mesh.gd,
## street_lights.gd, bike_lights.gd, avatar_view.gd, roadside_props.gd.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver vulkan --rendering-method forward_plus \
##     --audio-driver Dummy --script res://tests/vitrine_nuit.gd -- --out DOSSIER [--preset medium]
##
## Écrit DOSSIER/nuit_<preset>_<heure>_<vue>.png et DOSSIER/vitrine_nuit.csv (heure ; hauteur du soleil ;
## lumières ; luminance moyenne).

const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const BuildingMesh := preload("res://scripts/building_mesh.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const AtmosphereView := preload("res://scripts/atmosphere_view.gd")
const SkyCycle := preload("res://scripts/sky_cycle.gd")
const NightLights := preload("res://scripts/night_lights.gd")
const StreetLights := preload("res://scripts/street_lights.gd")
const BikeLights := preload("res://scripts/bike_lights.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const AvatarModel := preload("res://scripts/avatar_model.gd")
const RoadsideProps := preload("res://scripts/roadside_props.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

const SIZE := Vector2i(1280, 720)
const SETTLE_FRAMES := 24
const GROUND_Y := 200.0
const ROAD_W := 6.0
const LAT := 48.9
const DATE := {"year": 2026, "month": 11, "day": 13}
## Heures : nom, mode du réglage, heure solaire
const HOURS := [["coupe", "off", 12.0], ["midi", "theme", 12.0], ["coucher", "theme", 16.7], ["nuit", "theme", 21.0]]
## Maisons : x0 (bord côté route), z0, largeur (le long de la rue), profondeur, hauteur, style, type OSM
const HOUSES := [
	[6.0, -40.0, 11.0, 9.0, 6.5, "tuile_plate", "house"],
	[6.0, -56.0, 12.0, 10.0, 7.0, "ardoise", "retail"],
	[6.0, -74.0, 14.0, 11.0, 13.0, "tuile_plate", "apartments"],
	[6.0, -95.0, 10.0, 9.0, 6.0, "tuile_ronde", "house"],
	[-6.0, -44.0, 12.0, 10.0, 7.0, "tuile_plate", "house"],
	[-6.0, -62.0, 11.0, 9.0, 6.0, "ardoise", "house"],
	[-6.0, -80.0, 15.0, 10.0, 8.0, "tuile_plate", "retail"],
	[-6.0, -100.0, 10.0, 8.0, 6.0, "tuile_plate", "house"],
]
## Caméras : position (au-dessus du sol), cible
const VIEWS := {
	"rue": [Vector3(1.2, 2.2, -12.0), Vector3(1.0, 1.6, -60.0)],
	"subjective": [Vector3(1.5, 1.6, -18.3), Vector3(1.2, 1.2, -60.0)],
}
const RIDER_POS := Vector3(1.5, GROUND_Y, -18.0)

var _out_dir := "user://vitrine_nuit"
var _preset := "medium"


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--preset":
			_preset = args[i + 1]
	call_deferred("_run")


func _route():
	var n := 41
	var d := {"version": "1.0", "ds_m": 5.0, "n": n, "length_m": 5.0 * (n - 1), "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		d["lat"].append(LAT)
		d["lon"].append(7.0)
		d["alt_m"].append(GROUND_Y)
		d["x"].append(0.0)
		d["z"].append(-5.0 * i)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(0.0)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var theme: Dictionary = ThemeLoader.new().load_named("default")["theme"]
	var csv := FileAccess.open(_out_dir.path_join("vitrine_nuit.csv"), FileAccess.WRITE)
	csv.store_line("préréglage;heure;soleil_deg;lumières;vue;luminance")
	var vp := SubViewport.new()
	vp.size = SIZE
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = PhysicalSkyMaterial.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.glow_enabled = _preset != "low"
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 150.0
	vp.add_child(sun)
	var atmo = AtmosphereView.new()
	vp.add_child(atmo)
	atmo.setup(env, sun)
	atmo.set_world(theme, null, null, false)
	_build_world(vp, theme)
	var cam: Camera3D = vp.get_node("Camera")
	for h in HOURS:
		var out := SkyCycle.evaluate(str(h[1]), "off", theme, LAT, NAN, DATE, 0.0, {}, float(h[2]))
		var light: Dictionary = out["daylight"]
		var lit := bool(light.get("active", false))
		atmo.set_cycle(light if lit else {})
		NightLights.apply(NightLights.level(light), lit)
		for view in VIEWS:
			cam.look_at_from_position(VIEWS[view][0] + Vector3(0, GROUND_Y, 0), VIEWS[view][1] + Vector3(0, GROUND_Y, 0), Vector3.UP)
			var sl = vp.get_node("StreetLights")
			sl.update(cam.global_position, float(Time.get_ticks_msec()) + 1000.0)
			(vp.get_node("BikeLights") as Node3D).call("place", RIDER_POS, Vector3.ZERO)
			(vp.get_node("Avatar") as Node3D).call("apply_pose", 0.8, false)
			for _f in range(SETTLE_FRAMES):
				await process_frame
			var img := vp.get_texture().get_image()
			img.save_png(_out_dir.path_join("nuit_%s_%s_%s.png" % [_preset, h[0], view]))
			csv.store_line("%s;%s;%.1f;%.2f;%s;%.3f" % [_preset, h[0], float(light["sun_elevation_deg"]),
				NightLights.current, view, _luminance(img)])
	csv.close()
	NightLights.apply(0.0, false)
	print("vitrine_nuit : captures dans ", ProjectSettings.globalize_path(_out_dir))
	quit(0)


static func _luminance(img: Image) -> float:
	var small := img.duplicate() as Image
	small.resize(64, 36)
	var sum := 0.0
	for y in range(36):
		for x in range(64):
			sum += small.get_pixel(x, y).get_luminance()
	return sum / (64.0 * 36.0)


func _build_world(vp: SubViewport, theme: Dictionary) -> void:
	var mat := TerrainMaterial.create_material()
	for ix in range(-1, 1):
		for iz in range(-1, 1):
			var heights := PackedFloat32Array()
			heights.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
			heights.fill(GROUND_Y - 0.02)
			var tile := MeshInstance3D.new()
			tile.mesh = _mesh(TerrainTiles.build_arrays(heights, "near", {}, 1.0, GROUND_Y))
			tile.position = TerrainTiles.tile_origin("near", ix, iz)
			tile.material_override = mat
			vp.add_child(tile)
	# Chaussée : bande d'asphalte sombre
	var road := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(ROAD_W, 220.0)
	road.mesh = plane
	road.position = Vector3(0.0, GROUND_Y + 0.01, -100.0)
	var asphalt := StandardMaterial3D.new()
	asphalt.albedo_color = Color(0.16, 0.16, 0.17)
	asphalt.roughness = 0.9
	road.material_override = asphalt
	vp.add_child(road)
	# Maisons
	var items := []
	var buildings := []
	for i in range(HOUSES.size()):
		var h: Array = HOUSES[i]
		var sx := signf(h[0])
		var x0: float = h[0]
		var x1: float = h[0] + sx * h[3]
		var ring := [[x0, h[1]], [x0, h[1] - h[2]], [x1, h[1] - h[2]], [x1, h[1]]]
		if sx < 0.0:
			ring.reverse()
		items.append({"id": "rue_%d" % i, "outer": ring, "holes": [], "base_y": GROUND_Y, "height_m": h[4],
			"roof": "flat", "style": h[5], "hint": {"building": h[6], "colour": null}})
		var pts := PackedVector2Array()
		var rect := Rect2(Vector2(ring[0][0], ring[0][1]), Vector2.ZERO)
		for q in ring:
			pts.append(Vector2(q[0], q[1]))
			rect = rect.expand(Vector2(q[0], q[1]))
		buildings.append({"points": pts, "rect": rect})
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
	# Luminaires publics
	var sl = StreetLights.new()
	sl.name = "StreetLights"
	sl.road_width_m = ROAD_W
	vp.add_child(sl)
	sl.set_preset(_preset)
	sl.add_chunk(_route(), 0, buildings)
	# Lanterne de pierre au bord de la rue
	var props = RoadsideProps.new()
	vp.add_child(props)
	var lantern: Node3D = props.build_prop({"kind": "lantern", "s": 0.0, "side": 1, "text": "", "lines": []})
	lantern.position = Vector3(-4.5, GROUND_Y, -30.0)
	props.add_child(lantern)
	# Cycliste, phare et feu arrière
	var av = AvatarView.new()
	av.name = "Avatar"
	vp.add_child(av)
	av.configure(AvatarModel.DEFAULTS.duplicate(), 0)
	av.set_visible_for_view("follow_near")
	av.position = RIDER_POS
	var bl = BikeLights.new()
	vp.add_child(bl)
	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.fov = 65.0
	cam.far = 2000.0
	vp.add_child(cam)


static func _mesh(arrays: Array) -> ArrayMesh:
	var mesh := ArrayMesh.new()
	if not arrays.is_empty():
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh
