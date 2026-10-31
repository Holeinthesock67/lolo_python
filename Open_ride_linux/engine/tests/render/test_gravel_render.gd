extends SceneTree

## Rendu hors écran du ruban non revêtu (lot U22, option « gravel ») : ruban de road_builder.gd en `auto` sur une
## route bitumée jusqu'à 60 m puis en terre, shader des marquages (shaders/road_markings.gdshader), couleurs de
## `surfaces` du thème par défaut. Rendu sans éclairage : la couleur lue est l'albédo.
## Critère 4 du cahier : teinte moyenne de la portion `dirt` à moins de 10 % de `surfaces.dirt` ; plus : aucune
## peinture sur la terre, bas-côté au-delà des 3 m de chaussée, bitume et ligne médiane inchangés avant 60 m.

const RoadBuilder := preload("res://scripts/road_builder.gd")
const RoadSurface := preload("res://scripts/road_surface.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const MarkingsShader := preload("res://shaders/road_markings.gdshader")

const SIZE := 256
const ORTHO_M := 16.0
const TOL := 0.06

var _failures := 0
var _checked := 0


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite vers l'est (s = x, droite = +z), bitume jusqu'à 60 m, terre ensuite.
func _make_route():
	var d := {"version": "1.0", "ds_m": 10.0, "n": 0, "length_m": 0.0, "type": "open", "lat": [], "lon": [],
		"alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": [], "surface": []}
	for k in range(101):
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(300.0)
		d["x"].append(k * 10.0)
		d["z"].append(0.0)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(90.0)
		d["surface"].append("paved" if k < 6 else "dirt")
	d["n"] = 101
	d["length_m"] = 1000.0
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _rel_err(a: Color, b: Color) -> float:
	var la := Vector3(a.r, a.g, a.b)
	var lb := Vector3(b.r, b.g, b.b)
	return (la - lb).length() / lb.length()


func _run() -> void:
	var theme = JSON.parse_string(FileAccess.get_file_as_string("res://themes/default/theme.json"))
	var surfaces := RoadSurface.surfaces_of(theme if theme is Dictionary else {})
	var route = _make_route()
	var arrays := RoadBuilder.build_chunk_arrays(route, 0, RoadBuilder.ROAD_WIDTH_M, {"mode": "auto", "surfaces": surfaces})
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mat := ShaderMaterial.new()
	mat.shader = MarkingsShader
	mat.set_shader_parameter("wear", 0.0)
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	vp.add_child(mi)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = ORTHO_M
	vp.add_child(cam)
	var y0: float = route.sample_point(0.0).y
	var shots := {}
	for cx in [20.0, 100.0]:
		cam.look_at_from_position(Vector3(cx, y0 + 50.0, 0.0), Vector3(cx, y0, 0.0), Vector3(0, 0, -1))
		cam.current = true
		for i in 5:
			await process_frame
		shots[cx] = vp.get_texture().get_image()
	var px := func(cx: float, s: float, lat: float) -> Color:
		var img: Image = shots[cx]
		cam.look_at_from_position(Vector3(cx, y0 + 50.0, 0.0), Vector3(cx, y0, 0.0), Vector3(0, 0, -1))
		var p := cam.unproject_position(Vector3(s, y0, lat))
		return img.get_pixel(clampi(int(p.x), 0, SIZE - 1), clampi(int(p.y), 0, SIZE - 1))
	# Teinte moyenne de la terre : 9 × 7 points sur 8 m de long et 2,4 m de large
	var dirt: Color = surfaces["dirt"]["color"]
	var acc := Vector3.ZERO
	var count := 0
	for i in range(9):
		for j in range(7):
			var c: Color = px.call(100.0, 96.0 + i, -1.2 + j * 0.4)
			acc += Vector3(c.r, c.g, c.b)
			count += 1
	acc /= count
	var mean := Color(acc.x, acc.y, acc.z)
	var err := _rel_err(mean, dirt)
	_check(err < 0.10, "terre : teinte moyenne %s, à %.1f %% de surfaces.dirt %s" % [mean.to_html(false), err * 100.0, dirt.to_html(false)])
	var line := Color(0.95, 0.95, 0.95)
	var no_paint := true
	for s in [92.0, 93.5, 105.5, 106.5]:     # traits de la ligne médiane (motif de 13 m) s'il y en avait
		var c: Color = px.call(100.0, s, 0.0)
		no_paint = no_paint and c.r < 0.8
	_check(no_paint, "aucune peinture sur la terre")
	var shoulder: Color = px.call(100.0, 100.0, 1.9)
	_check(_rel_err(shoulder, dirt) > 0.15, "au-delà de 1,5 m + bruit : bas-côté (%s), plus de terre" % shoulder.to_html(false))
	var road := Color(0.29, 0.29, 0.30)
	var asphalt: Color = px.call(20.0, 21.0, 1.0)
	var center: Color = px.call(20.0, 14.5, 0.0)
	var edge: Color = px.call(20.0, 21.0, 3.0 - 0.2 - 0.075)
	_check(_rel_err(asphalt, road) < 0.25 and center.r > 0.8 and edge.r > 0.8,
		"bitume avant 60 m : chaussée, ligne médiane et bande de rive inchangées")
	vp.queue_free()
	await process_frame
	print("test_gravel_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
