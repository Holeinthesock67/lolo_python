extends SceneTree

## Rendu hors écran de la mer animée du lot U9 (critère 3 du cahier) : mer vue de dessus à la teinte de sa
## couleur de biome (bleue ou verte, teinte moyenne à 10 % près), écume visible au bord d'une plage de test,
## absente au large ; plage drapée à la couleur du sable.

const RenderExit := preload("res://tests/render/render_exit.gd")

const SeaMesh := preload("res://scripts/sea_mesh.gd")
const SeaShader := preload("res://shaders/sea.gdshader")
const SeaFoamShader := preload("res://shaders/sea_foam.gdshader")
const BeachShader := preload("res://shaders/beach.gdshader")

const SIZE := 96
const SEA := Color("#2a8a9a")
const SAND := Color("#c2ae86")

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


func _instance(d: Dictionary, shader: Shader) -> MeshInstance3D:
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = d["vertices"]
	arr[Mesh.ARRAY_NORMAL] = d["normals"]
	arr[Mesh.ARRAY_COLOR] = d["colors"]
	if d.has("uvs"):
		arr[Mesh.ARRAY_TEX_UV] = d["uvs"]
	arr[Mesh.ARRAY_INDEX] = d["indices"]
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	var mat := ShaderMaterial.new()
	mat.shader = shader
	mi.material_override = mat
	return mi


## Moyenne des pixels entre les colonnes a et b (bornes comprises, dans n'importe quel ordre), sur la moitié
## centrale de l'image en hauteur.
func _mean(img: Image, a: int, b: int) -> Color:
	var acc := Color(0, 0, 0, 0)
	var n := 0
	for y in range(SIZE / 4, SIZE * 3 / 4):
		for x in range(mini(a, b), maxi(a, b) + 1):
			acc += img.get_pixel(x, y)
			n += 1
	return acc / maxf(n, 1)


func _run() -> void:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	vp.transparent_bg = true
	root.add_child(vp)
	# Côte nord-sud en x = 0 (la mer à l'ouest, x < 0), plage de 0 à 20 m, mer jusqu'à −60 m.
	var sea := {"id": "s", "kind": "sea", "level_y": 0.0, "holes": [],
		"outer": [[-60.0, -40.0], [0.0, -40.0], [0.0, 40.0], [-60.0, 40.0]]}
	vp.add_child(_instance(SeaMesh.build_sea([sea], func(_x: float, _z: float) -> Color: return SEA), SeaShader))
	vp.add_child(_instance(SeaMesh.build_foam([{"id": "c", "shore": "sand", "points": [[0.0, -40.0], [0.0, 40.0]]}], 0.0),
		SeaFoamShader))
	var beach := {"id": "b", "kind": "sand", "holes": [], "outer": [[0.0, -40.0], [20.0, -40.0], [20.0, 40.0], [0.0, 40.0]]}
	vp.add_child(_instance(SeaMesh.build_beaches([beach], func(_x: float, _z: float) -> float: return 0.3, SAND), BeachShader))
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 80.0
	vp.add_child(cam)
	cam.look_at_from_position(Vector3(-20.0, 60.0, 0.0), Vector3(-20.0, 0.0, 0.0), Vector3.FORWARD)
	cam.current = true
	for i in 6:
		await process_frame
	var img := vp.get_texture().get_image()
	var px := func(x: float) -> int:
		return clampi(int(cam.unproject_position(Vector3(x, 0.2, 0.0)).x), 0, SIZE - 1)
	var offshore := _mean(img, px.call(-58.0), px.call(-30.0))
	_check(offshore.b > offshore.r and offshore.g > offshore.r, "mer bleue ou verte au large (%s)" % str(offshore))
	var dh := absf(offshore.h - SEA.h)
	dh = minf(dh, 1.0 - dh)
	_check(dh <= 0.1, "teinte moyenne de la mer à 10 %% près de celle du biome (%.3f contre %.3f)" % [offshore.h, SEA.h])
	var foam := _mean(img, px.call(-1.6), px.call(-0.5))
	_check(foam.get_luminance() > offshore.get_luminance() + 0.2,
		"écume visible au bord de la plage (luminance %.2f contre %.2f au large)" % [foam.get_luminance(), offshore.get_luminance()])
	var mid := _mean(img, px.call(-25.0), px.call(-15.0))
	_check(absf(mid.get_luminance() - offshore.get_luminance()) < 0.05, "pas d'écume au large (%.2f)" % mid.get_luminance())
	var sand := _mean(img, px.call(8.0), px.call(18.0))
	_check(absf(sand.r - SAND.r) < 0.08 and absf(sand.g - SAND.g) < 0.08 and absf(sand.b - SAND.b) < 0.08,
		"plage à la couleur du sable (%s)" % str(sand))
	vp.queue_free()
	await process_frame
	await RenderExit.settle(self)   # sortie en ordre (render_exit.gd)
	print("test_sea_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
