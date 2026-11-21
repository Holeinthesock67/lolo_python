extends "res://tests/vitrine_pente.gd"

## Vitrine de la voiture d'équipe du Grand Prix des objets (lot GP-voiture-modele) : même route et même décor
## que vitrine_pente.gd, la voiture `team_car` de vehicle_mesh.gd dessinée par traffic_renderer.gd (comme en
## course) et, à côté, la berline `car_a` qui la remplaçait ; le coureur remorqué roule 3 m derrière.
## Vues : de côté, trois quarts avant, de la caméra de poursuite (derrière le coureur) et de dessus (vélos du toit).
##
##   xvfb-run -a $GODOT --path engine --rendering-driver vulkan --rendering-method forward_plus \
##     --audio-driver Dummy --script res://tests/vitrine_voiture_equipe.gd -- --out DOSSIER
##
## Écrit DOSSIER/voiture_equipe_<vue>.png.

const TrafficModel := preload("res://scripts/traffic_model.gd")
const TrafficRenderer := preload("res://scripts/traffic_renderer.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")

## Véhicules posés : [sorte, décalage en s (m) du milieu de la voiture, écart à l'axe (m)].
const PLACED := [["team_car", 0.0, 1.2], ["car_a", 0.0, -1.6]]
const RIDER_BEHIND_M := 3.0 + 2.4 + 0.9
## Vues : [décalage de l'œil, point visé (décalage en s négatif vers l'avant, hauteur)].
const VIEWS := {
	"cote": [Vector3(8.5, 1.6, 0.0), Vector3(0.0, 1.0, 0.0)],
	"trois_quarts_avant": [Vector3(6.0, 2.2, -7.0), Vector3(0.0, 1.1, 0.0)],
	"poursuite": [Vector3(1.2, 3.2, 12.0), Vector3(0.0, 1.2, -2.0)],
	"dessus": [Vector3(3.5, 5.5, 3.5), Vector3(0.0, 1.6, 0.0)],
}


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var route = _make_route(_k_after)
	var vp := _build_world(route)
	var cam: Camera3D = vp.get_node("Camera")
	var rider: Node3D = vp.get_node("Rider")
	var tm = TrafficModel.new()
	tm.configure(route, {}, [], 3, 7)
	var view = TrafficRenderer.new()
	vp.add_child(view)
	view.setup(tm)
	var rc = RoadCyclistsModel.new()
	rc.route = route
	var s: float = 200.0
	tm.vehicles.clear()
	for i in range(PLACED.size()):
		var p: Array = PLACED[i]
		tm.vehicles.append({"id": "tc%d" % i, "kind": p[0], "s": s + float(p[1]), "dir": 1,
			"lateral": float(p[2]), "color": 0, "wheel": 0.0})
	view.update()
	rider.transform = rc.world_transform(s - RIDER_BEHIND_M, 1.2, 1)
	var pos: Vector3 = route.sample_point(s)
	for v in VIEWS:
		var eye: Vector3 = pos + VIEWS[v][0]
		var target: Vector3 = route.sample_point(s - float(VIEWS[v][1].z)) + Vector3(0.0, VIEWS[v][1].y, 0.0)
		cam.global_transform = Transform3D(Basis.looking_at(target - eye, Vector3.UP), eye)
		cam.fov = BASE_FOV
		for _f in range(SETTLE_FRAMES):
			await process_frame
		var img := vp.get_texture().get_image()
		var name := "voiture_equipe_%s.png" % v
		img.save_png(_out_dir.path_join(name))
		print("[vitrine_voiture_equipe] ", name)
	vp.queue_free()
	await process_frame
	quit(0)
