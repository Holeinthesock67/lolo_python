extends SceneTree
const RoadBuilder := preload("res://scripts/road_builder.gd")
const RoadSurface := preload("res://scripts/road_surface.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const MarkingsShader := preload("res://shaders/road_markings.gdshader")
func _init() -> void:
	call_deferred("_run")
func _route():
	var d := {"version": "1.0", "ds_m": 10.0, "n": 101, "length_m": 1000.0, "type": "open", "lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": [], "surface": []}
	for k in range(101):
		d["lat"].append(45.0); d["lon"].append(6.0); d["alt_m"].append(300.0); d["x"].append(k * 10.0); d["z"].append(0.0)
		d["grade_pct"].append(0.0); d["heading_deg"].append(90.0); d["surface"].append("gravel")
	var r = RouteDataScript.new(); r.load_route_dict(d); return r
func _run() -> void:
	var theme = JSON.parse_string(FileAccess.get_file_as_string("res://themes/default/theme.json"))
	var surfaces := RoadSurface.surfaces_of(theme)
	var route = _route()
	var arrays := RoadBuilder.build_chunk_arrays(route, 0, RoadBuilder.ROAD_WIDTH_M, {"mode": "gravel", "surfaces": surfaces})
	var cols: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
	print("vertex color sample ", cols[cols.size()/2], " surface color ", surfaces["gravel"]["color"])
	var nrm: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	print("normal sample ", nrm[nrm.size()/2])
	var mesh := ArrayMesh.new(); mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mat := ShaderMaterial.new(); mat.shader = MarkingsShader
	for mode in ["unshaded", "lit"]:
		var vp := SubViewport.new(); vp.size = Vector2i(256, 256); vp.own_world_3d = true
		vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		if mode == "unshaded": vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
		root.add_child(vp)
		var mi := MeshInstance3D.new(); mi.mesh = mesh; mi.material_override = mat; vp.add_child(mi)
		var env := Environment.new(); env.background_mode = Environment.BG_SKY
		var sky := Sky.new(); sky.sky_material = ProceduralSkyMaterial.new(); env.sky = sky
		env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
		var we := WorldEnvironment.new(); we.environment = env; vp.add_child(we)
		var sun := DirectionalLight3D.new(); sun.rotation_degrees = Vector3(-50, 30, 0); vp.add_child(sun)
		var cam := Camera3D.new(); vp.add_child(cam)
		cam.look_at_from_position(Vector3(100, 301.6, 0), Vector3(115, 300, 0), Vector3.UP); cam.current = true
		for i in 6: await process_frame
		var img := vp.get_texture().get_image()
		print(mode, " centre chemin ", img.get_pixel(128, 200).to_html(false), " ", img.get_pixel(128, 230).to_html(false))
	quit(0)
