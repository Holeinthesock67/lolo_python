extends "res://tests/vitrine_pente.gd"

## Vitrine des véhicules et des cyclistes du décor dans la pente : même route et même décor que
## vitrine_pente.gd (montée et descente de 8 %, relief affiché ×k), avec une berline, un camion et un autocar
## de traffic_renderer.gd dans les deux sens et un cycliste du décor (people_mesh.gd n'est pas utile ici :
## une capsule suffit à juger le tangage). « avant » : véhicules à plat (cap seul, comme avant le correctif) ;
## « apres » : traffic_model.world_transform et road_cyclists_model.world_transform (tangage selon
## route_data.display_pitch).
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_vehicules_pente.gd -- --out DOSSIER [--k 2.0]
##
## Écrit DOSSIER/<avant|apres>_<montee|descente>_cote.png.

const TrafficModel := preload("res://scripts/traffic_model.gd")
const TrafficRenderer := preload("res://scripts/traffic_renderer.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")

## Véhicules posés autour de l'endroit capturé : [sorte, décalage en s (m), sens].
const PLACED := [["truck", -9.0, 1], ["car_a", 6.0, 1], ["bus", 2.0, -1]]
## Vue de côté (décalage de l'œil, hauteur visée) : le tangage se juge de profil.
const CAMERAS := {"cote": [Vector3(16.0, 2.5, 0.0), Vector3(0.0, 1.5, 0.0)]}


## Modèle d'affichage « avant le correctif » : même position et même cap, sans tangage.
class FlatModel:
	var inner
	var vehicles: Array:
		get:
			return inner.vehicles

	func world_transform(v: Dictionary) -> Transform3D:
		var t: Transform3D = inner.world_transform(v)
		var fwd := -t.basis.z
		return Transform3D(Basis(Vector3.UP, atan2(-fwd.x, -fwd.z)), t.origin)


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	for state in [["avant", false], ["apres", true]]:
		var route = _make_route(_k_after)
		var vp := _build_world(route)
		var cam: Camera3D = vp.get_node("Camera")
		var rider: Node3D = vp.get_node("Rider")
		var tm = TrafficModel.new()
		tm.configure(route, {}, [], 3, 7)
		var view = TrafficRenderer.new()
		vp.add_child(view)
		var flat := FlatModel.new()
		flat.inner = tm
		view.setup(tm if state[1] else flat)
		var rc = RoadCyclistsModel.new()
		rc.route = route
		for spot in SPOTS:
			var s: float = SPOTS[spot]
			tm.vehicles.clear()
			for i in range(PLACED.size()):
				var p: Array = PLACED[i]
				tm.vehicles.append({"id": "v%d" % i, "kind": p[0], "s": s + float(p[1]), "dir": p[2],
					"lateral": 1.6 * float(p[2]), "color": i, "wheel": 0.0})
			view.update()
			var xf: Transform3D = rc.world_transform(s - 3.0, 3.6, 1)
			if not state[1]:
				var f := xf.basis.z
				xf = Transform3D(Basis(Vector3.UP, atan2(f.x, f.z)), xf.origin)
			rider.transform = xf
			var pos: Vector3 = route.sample_point(s)
			for c in CAMERAS:
				var eye: Vector3 = pos + CAMERAS[c][0]
				var target: Vector3 = route.sample_point(s - float(CAMERAS[c][1].z)) + Vector3(0.0, CAMERAS[c][1].y, 0.0)
				cam.global_transform = Transform3D(Basis.looking_at(target - eye, Vector3.UP), eye)
				cam.fov = BASE_FOV
				for _f in range(SETTLE_FRAMES):
					await process_frame
				var img := vp.get_texture().get_image()
				var name := "%s_%s_%s.png" % [state[0], spot, c]
				img.save_png(_out_dir.path_join(name))
				print("[vitrine_vehicules_pente] ", name)
		vp.queue_free()
		await process_frame
	quit(0)
