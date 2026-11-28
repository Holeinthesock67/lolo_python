extends SceneTree

## Rendu hors écran du trou du terrain dans les tunnels (lot EA5) : le shader du terrain compilé ne dessine pas
## ce qui est dans le volume d'un tunnel enregistré (tunnel_cut.gd, tunnel_cut.gdshaderinc), et seulement là.
## Scène : flanc de colline à 25 % qui monte vers le nord depuis la route (100 m au portail sud), tunnel de 40 m vers
## le nord (tunnel_mesh.gd) ; caméra orthogonale devant le portail sud, à 2 m au-dessus de la route, qui regarde vers
## le nord ; rendu sans éclairage. Sans le trou, le flanc ferme l'entrée (herbe sur la route).
## Lancé par run_engine_tests.sh sous Xvfb (Forward+ sur Vulkan).

const RenderExit := preload("res://tests/render/render_exit.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const TunnelMesh := preload("res://scripts/tunnel_mesh.gd")
const TunnelCut := preload("res://scripts/tunnel_cut.gd")

const SIZE := 64
const SLOPE := 0.25

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


func _tunnel_item() -> Dictionary:
	var pts := []
	for i in range(5):
		pts.append([0.0, -10.0 * i, 100.0])
	return {"id": "t0", "kind": "tunnel", "half_width_m": 3.0, "points": pts}


## Image vue du sud (SIZE pixels pour 32 m), centrée sur (0, 102, 15).
func _shot(cut: bool = true) -> Image:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(80.0, 120.0)
	plane.subdivide_width = 16
	plane.subdivide_depth = 24
	ground.mesh = plane
	var mat := TerrainMaterial.create_material({})
	mat.shader = TunnelCut.shader_for(mat.shader, cut)   # variante TUNNEL_CUT des tuiles qui touchent un tunnel
	mat.set_shader_parameter("detail_strength", 0.0)
	ground.material_override = mat
	ground.position = Vector3(0.0, 100.0 + SLOPE * 20.0, -20.0)
	ground.rotation = Vector3(atan(SLOPE), 0.0, 0.0)      # y = 100 − 0,25 z
	vp.add_child(ground)
	var built := TunnelMesh.build([_tunnel_item()])
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	var shell: Dictionary = built["shell"]
	arr[Mesh.ARRAY_VERTEX] = shell["vertices"]
	arr[Mesh.ARRAY_NORMAL] = shell["normals"]
	arr[Mesh.ARRAY_COLOR] = shell["colors"]
	arr[Mesh.ARRAY_INDEX] = shell["indices"]
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var tube := MeshInstance3D.new()
	tube.mesh = mesh
	tube.material_override = TunnelMesh.make_material()
	vp.add_child(tube)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 32.0
	cam.near = 0.05
	cam.far = 300.0
	vp.add_child(cam)
	cam.position = Vector3(0.0, 102.0, 15.0)
	cam.current = true
	TunnelCut.update(cam.position)
	for i in 6:
		await process_frame
	var img := vp.get_texture().get_image()
	vp.queue_free()
	await process_frame
	return img


func _greenish(c: Color) -> bool:
	return c.g > c.r + 0.04 and c.g > c.b + 0.04


func _run() -> void:
	var cut: PackedFloat32Array = TunnelMesh.build([_tunnel_item()])["cut"]
	TunnelCut.clear()
	TunnelCut.set_chunk(0, cut)
	var img: Image = await _shot()
	var opening := img.get_pixel(SIZE / 2, SIZE / 2)           # dans l'ouverture du portail, 2 m au-dessus de la route
	var side := img.get_pixel(SIZE / 2 + 24, SIZE / 2)          # flanc de la colline, 12 m à droite de l'axe
	var above := img.get_pixel(SIZE / 2, SIZE / 2 - 16)         # 8 m plus haut : colline au-dessus de la tête
	_check(not _greenish(opening), "entrée du tunnel ouverte : pas d'herbe dans le portail (#%s)" % opening.to_html(false))
	_check(_greenish(side), "flanc de la colline hors du tunnel dessiné (#%s)" % side.to_html(false))
	_check(_greenish(above), "colline au-dessus du tunnel gardée (#%s)" % above.to_html(false))
	# Shader de base (tuile loin de tout tunnel) : pas de trou, même tunnel enregistré
	var plain: Image = await _shot(false)
	var shut := plain.get_pixel(SIZE / 2, SIZE / 2)
	_check(_greenish(shut), "shader de base sans le trou : le flanc reste dessiné (#%s)" % shut.to_html(false))
	# Sans tunnel enregistré : le flanc ferme l'entrée (règle d'avant)
	TunnelCut.clear()
	var none: Image = await _shot()
	var closed := none.get_pixel(SIZE / 2, SIZE / 2)
	_check(_greenish(closed), "sans tunnel enregistré, le flanc ferme l'entrée (#%s)" % closed.to_html(false))
	await RenderExit.settle(self)   # sortie en ordre (render_exit.gd)
	print("test_tunnel_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
