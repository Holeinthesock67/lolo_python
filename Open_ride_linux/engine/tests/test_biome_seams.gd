extends SceneTree

## Coutures du sol multi-biome en scène réelle (série U, outil d'auto-test) : le parcours de démo avec terrain
## (`python -m openride_core.tools.fake_world --demo --terrain`) reçoit une couche biome qui passe de la
## prairie tempérée au désert de sable d'ouest en est (poids continus dans le monde, tuiles proches et
## lointaines) ; world_streamer.gd charge les tuiles comme en séance (matériaux de biome_textures.gd).
## Vue de dessus sans éclairage du bord commun de deux tuiles proches, loin de la route :
## 1. pas de marche de couleur au bord (écart au bord au plus 3 fois l'écart moyen entre colonnes voisines,
##    et au plus 3 % en valeur absolue) ;
## 2. contrôle du test : une tuile volontairement fausse (tout en sable) à côté donne bien une marche.
## Lancement (Xvfb) : xvfb-run -a godot --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##   --audio-driver Dummy --script res://tests/test_biome_seams.gd -- <dossier demo.world>
## Code de sortie : 0 si tout passe, 1 sinon.

const RouteDataScript := preload("res://scripts/route_data.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

const WEST := "temperate_grassland"
const EAST := "sand_desert"
const BLEND_FROM_M := -1000.0   # fondu prairie → sable de x = -1 000 à 4 000 m
const BLEND_TO_M := 4000.0
const VIEW_M := 200.0
const PX := Vector2i(128, 64)
const MAX_RATIO := 3.0
const MAX_STEP := 0.03

var failures := 0
var checked := 0


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, what: String) -> void:
	checked += 1
	if ok:
		print("[OK] ", what)
	else:
		failures += 1
		printerr("[ÉCHEC] ", what)


## Part du sable au point (x, z) du monde, de 0 à 255 (continue d'une tuile à l'autre).
static func _east_weight(x: float) -> int:
	return int(round(255.0 * clampf((x - BLEND_FROM_M) / (BLEND_TO_M - BLEND_FROM_M), 0.0, 1.0)))


static func _tile_json(level: String, t: Vector2i, east_of: Callable) -> Dictionary:
	var size: float = TerrainTiles.LEVELS[level]["size"]
	var w := []
	var e := []
	for j in range(BiomeLayer.GRID):
		for i in range(BiomeLayer.GRID):
			var k: int = east_of.call(t.x * size + i * size / (BiomeLayer.GRID - 1))
			e.append(k)
			w.append(255 - k)
	return {"grid": BiomeLayer.GRID, "biomes": [WEST, EAST], "weights": [w, e], "variant": null}


## Copie du parcours de démo avec la couche biome ; renvoie son dossier.
func _make_world(src: String) -> String:
	var dst := ProjectSettings.globalize_path("user://test_biome_seams/demo.world")
	for sub in ["", "terrain/near", "terrain/far", "biome/near", "biome/far"]:
		DirAccess.make_dir_recursive_absolute(dst.path_join(sub))
	for sub in ["", "terrain/near", "terrain/far"]:
		for f in DirAccess.get_files_at(src.path_join(sub)):
			DirAccess.copy_absolute(src.path_join(sub).path_join(f), dst.path_join(sub).path_join(f))
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(src.path_join("manifest.json")))
	manifest["layers"]["biome"] = {"present": true, "version": "1.0", "default_biome": WEST}
	FileAccess.open(dst.path_join("manifest.json"), FileAccess.WRITE).store_string(JSON.stringify(manifest))
	for level in ["near", "far"]:
		for t in TerrainTiles.scan_index(dst, level):
			FileAccess.open(BiomeLayer.tile_path(dst, level, t.x, t.y), FileAccess.WRITE).store_string(
				JSON.stringify(_tile_json(level, t, _east_weight)))
	return dst


## Bord vertical commun à deux tuiles proches, le plus loin possible de la route : {x, z, left, right}.
func _pick_edge(route, dir: String) -> Dictionary:
	var tiles := {}
	for t in TerrainTiles.scan_index(dir, "near"):
		tiles[t] = true
	var best := {}
	var best_d := -1.0
	for t in tiles:
		if not tiles.has(Vector2i(t.x + 1, t.y)):
			continue
		var p := Vector2((t.x + 1) * 1000.0, t.y * 1000.0 + 500.0)
		var d := INF
		for i in range(route.n):
			d = minf(d, p.distance_to(Vector2(route.x[i], route.z[i])))
		if d > best_d:
			best_d = d
			best = {"x": p.x, "z": p.y, "left": t, "right": Vector2i(t.x + 1, t.y), "road_m": d}
	return best


func _nearest_s(route, p: Vector2) -> float:
	var best := 0
	for i in range(route.n):
		if p.distance_to(Vector2(route.x[i], route.z[i])) < p.distance_to(Vector2(route.x[best], route.z[best])):
			best = i
	return best * float(route.ds_m)


func _shot(vp: SubViewport, cam: Camera3D) -> Image:
	cam.current = true
	for i in 5:
		await process_frame
	return vp.get_texture().get_image()


## Écart relatif entre deux couleurs (plus grande composante).
func _rel(a: Color, b: Color) -> float:
	return maxf(maxf(absf(a.r - b.r), absf(a.g - b.g)), absf(a.b - b.b)) / maxf(maxf(maxf(b.r, b.g), b.b), 1e-3)


## Écart au bord (colonnes 63 et 64) et écart moyen entre colonnes voisines ailleurs, moyennés sur les lignes.
func _steps(img: Image) -> Vector2:
	var seam := 0.0
	var other := 0.0
	var n_other := 0
	for y in range(img.get_height()):
		seam += _rel(img.get_pixel(PX.x / 2 - 1, y), img.get_pixel(PX.x / 2, y))
		for x in range(8, PX.x - 8):
			if absi(x - PX.x / 2) <= 2:
				continue
			other += _rel(img.get_pixel(x - 1, y), img.get_pixel(x, y))
			n_other += 1
	return Vector2(seam / img.get_height(), other / maxf(n_other, 1.0))


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		printerr("Usage : -- <dossier demo.world avec terrain>")
		quit(1)
		return
	var dir := _make_world(args[0])
	var route = RouteDataScript.new()
	if not route.load_world_dir(dir):
		printerr("Parcours illisible : ", dir)
		quit(1)
		return
	var edge := _pick_edge(route, dir)
	_check(not edge.is_empty() and float(edge["road_m"]) > VIEW_M, "bord commun de tuiles proches à x = %.0f m, z = %.0f m, à %.0f m de la route" % [
		float(edge.get("x", NAN)), float(edge.get("z", NAN)), float(edge.get("road_m", NAN))])
	if edge.is_empty():
		quit(1)
		return

	var vp := SubViewport.new()
	vp.size = PX
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var streamer = WorldStreamer.new()
	streamer.quality_preset = "medium"
	vp.add_child(streamer)
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	streamer.set_theme(theme, ThemeLoader.DEFAULT_THEME_DIR)
	streamer.set_world(route, dir)
	var cam_pos := Vector3(edge["x"], 0.0, edge["z"])
	streamer.update_window(_nearest_s(route, Vector2(edge["x"], edge["z"])), 0.0, cam_pos)
	streamer.flush()
	var keys: Array = streamer.loaded_keys()
	var left_key := "near:%d:%d" % [edge["left"].x, edge["left"].y]
	var right_key := "near:%d:%d" % [edge["right"].x, edge["right"].y]
	_check(streamer.biome_textures != null and keys.has(left_key) and keys.has(right_key),
		"tuiles %s et %s chargées par world_streamer avec les sols des biomes" % [left_key, right_key])
	if not (keys.has(left_key) and keys.has(right_key)):
		quit(1)
		return
	for mat_material in [streamer.instance(left_key).mesh.surface_get_material(0), streamer.instance(right_key).mesh.surface_get_material(0)]:
		(mat_material as ShaderMaterial).set_shader_parameter("detail_strength", 0.0)

	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.keep_aspect = Camera3D.KEEP_WIDTH
	cam.size = VIEW_M
	cam.far = 5000.0
	vp.add_child(cam)
	cam.position = Vector3(edge["x"], 3000.0, edge["z"])
	cam.rotation = Vector3(-PI / 2.0, 0.0, 0.0)

	# 1. Couture réelle
	var st := _steps(await _shot(vp, cam))
	_check(st.x <= maxf(MAX_RATIO * st.y, 0.002) and st.x <= MAX_STEP,
		"bord des tuiles : écart moyen %.2f %% au bord, %.2f %% entre colonnes voisines (au plus %.0f fois, et %.0f %%)" % [
		100.0 * st.x, 100.0 * st.y, MAX_RATIO, 100.0 * MAX_STEP])

	# 2. Contrôle : tuile de droite toute en sable, le bord doit sauter
	streamer.biome_model.layer.put_tile("near", edge["right"].x, edge["right"].y,
		BiomeLayer.parse_tile(_tile_json("near", edge["right"], func(_x): return 255), PackedStringArray()))
	var wrong: ShaderMaterial = streamer.biome_textures.tile_material("near", edge["right"].x, edge["right"].y)
	wrong.set_shader_parameter("detail_strength", 0.0)
	streamer.instance(right_key).mesh.surface_set_material(0, wrong)
	var bad := _steps(await _shot(vp, cam))
	_check(bad.x > MAX_RATIO * bad.y and bad.x > MAX_STEP, "contrôle : tuile fausse détectée (écart au bord %.1f %%)" % (100.0 * bad.x))

	print("test_biome_seams : %d vérifications, %d échecs" % [checked, failures])
	quit(1 if failures > 0 else 0)
