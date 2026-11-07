extends "res://tests/vitrine_pente.gd"

## Vitrine des cyclistes du décor sur le gravel (recette vélo du 7 novembre : cyclistes « dans la terre », roue
## avant dans la roue arrière de celui de devant, rabattement brusque). Même route, même terrain que
## vitrine_pente.gd, sur la portion plate de la fin, ruban en gravier de 3,5 m (option gravel « gravier », largeurs
## du thème par défaut) ; cyclistes de road_cyclists_model.gd dessinés par road_cyclists_renderer.gd (mêmes
## avatars qu'en jeu), demi-largeur roulable de road_surface.gd (`rideable_half`, celle du jeu).
## Scènes : « file » (trois de front rattrapés sur le chemin : en file, roues séparées), « en_face » (deux de
## front qui arrivent : en file sur leur droite), « rabattement_1 » à « _3 » (un groupe qui a doublé se rabat, à
## 0,4 s d'intervalle : trajectoire courbe, vélo tourné dans le sens où il va). Deux vues : « suivi » (derrière le
## cycliste, rouge) et « dessus » (à la verticale, pour juger le chemin et l'écart des roues).
##
##   xvfb-run -a $GODOT --path engine --rendering-driver vulkan --rendering-method forward_plus \
##     --audio-driver Dummy --script res://tests/vitrine_cyclistes_gravel.gd -- --out DOSSIER [--quality medium]
##
## Écrit DOSSIER/<scène>_<vue>_<qualité>.png et DOSSIER/vitrine_cyclistes_gravel.csv (scène ; qualité ; id ;
## rel_m ; écart à l'axe ; demi-largeur roulable ; lacet en degrés ; écart d'axe à axe avec celui de devant).

const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const RoadCyclistsRenderer := preload("res://scripts/road_cyclists_renderer.gd")
const RoadSurface := preload("res://scripts/road_surface.gd")

const S0 := 2200.0          # portion plate après la descente
const DT := 1.0 / 30.0
const SHOT_FRAMES := 45     # images d'affichage avant la capture (avatars construits en fil de travail)
const VIEWS := {"suivi": [Vector3(-0.4, 3.0, 9.0), Vector3(0.6, 0.8, -16.0)],
	"dessus": [Vector3(0.0, 17.0, -15.0), Vector3(0.0, 0.0, -15.3)]}

var _quality := "medium"


func _init() -> void:
	super._init()
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--quality":
			_quality = args[i + 1]
	if _out_dir == "user://vitrine_pente":
		_out_dir = "user://vitrine_cyclistes_gravel"


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var csv := FileAccess.open(_out_dir.path_join("vitrine_cyclistes_gravel.csv"), FileAccess.WRITE)
	csv.store_line("scène;qualité;id;rel_m;écart_axe_m;demi_largeur_m;lacet_deg;axe_a_axe_m")
	var route = _make_route(1.0)
	var surfaces := RoadSurface.surfaces_of({"surfaces": {"gravel": {"width_m": 3.5}}})
	var gravel := {"mode": "gravel", "surfaces": surfaces}
	var vp := _build_world(route, gravel)
	var cam: Camera3D = vp.get_node("Camera")
	var rider: Node3D = vp.get_node("Rider")
	var half_at := func(s: float) -> float: return RoadSurface.rideable_half(route, s, "gravel", surfaces, RoadBuilder.ROAD_WIDTH_M)
	for scene in ["file", "en_face", "rabattement"]:
		var m = RoadCyclistsModel.new()
		m.configure(route, [], [], 16, 7, RoadBuilder.ROAD_WIDTH_M, null, half_at)
		var view = RoadCyclistsRenderer.new()
		vp.add_child(view)
		view.setup(m)
		view.set_quality(_quality)
		var s := S0
		var v := 5.0
		var shots := []          # [nom, images à simuler avant]
		match scene:
			"file":
				m.update(s, v, 0.0)
				m.place_for_test(s, v, "ahead", 9.0, 3, true)
				shots = [["file", 180]]
			"en_face":
				m.update(s, v, 0.0)
				m.place_for_test(s, v, "oncoming", 26.0, 2, true)
				shots = [["en_face", 1]]
			"rabattement":
				v = 6.0
				m.update(s, v, 0.0)
				m.place_for_test(s, v, "overtake", -6.0, 2, false)
				# jusqu'au début du rabattement (le dernier à MERGE_AHEAD_M devant), puis trois images à 0,4 s
				var guard := 0
				while guard < 30 * 60:
					m.update(s, v, DT)
					s += v * DT
					guard += 1
					if not m.groups.is_empty() and str(m.groups[0]["side"]) == "right" and float(m.groups[0]["s"]) > s + 10.0:
						break
				shots = [["rabattement_1", 6], ["rabattement_2", 12], ["rabattement_3", 12]]
		for shot in shots:
			for _i in range(int(shot[1])):
				m.update(s, v, DT)
				s += v * DT
			var pos: Vector3 = route.sample_point(s)
			rider.transform = m.world_transform(s, RoadBuilder.RIDER_LATERAL_M, 1)
			_log(csv, str(shot[0]), m, s, half_at)
			# Vue de dessus centrée sur les cyclistes (route vers −z)
			var mid := 0.0
			for r in m.riders():
				mid += (float(r["s"]) - s) / float(m.riders().size())
			for vn in VIEWS:
				var eye: Vector3 = pos + VIEWS[vn][0]
				var target: Vector3 = pos + VIEWS[vn][1]
				if vn == "dessus":
					eye = pos + Vector3(0.0, 14.0, -mid)
					target = pos + Vector3(0.0, 0.0, -mid - 0.3)
				var up := Vector3.FORWARD if vn == "dessus" else Vector3.UP
				cam.global_transform = Transform3D(Basis.looking_at(target - eye, up), eye)
				cam.fov = BASE_FOV
				for _f in range(SHOT_FRAMES):
					view.update(0.0, true, s)
					await process_frame
				var img := vp.get_texture().get_image()
				var name := "%s_%s_%s.png" % [shot[0], vn, _quality]
				img.save_png(_out_dir.path_join(name))
				print("[vitrine_cyclistes_gravel] ", name)
		view.queue_free()
		await process_frame
	csv.close()
	vp.queue_free()
	await process_frame
	quit(0)


func _log(csv: FileAccess, scene: String, m, rider_s: float, half_at: Callable) -> void:
	for g in m.groups:
		var prev := NAN
		for r in m.riders():
			if not is_same(r["group"], g):
				continue
			var gap := absf(float(r["s"]) - prev) if not is_nan(prev) else NAN
			prev = float(r["s"])
			var line := "%s;%s;%s;%.2f;%.2f;%.2f;%.1f;%.2f" % [scene, _quality, str(r["id"]), float(r["s"]) - rider_s,
				float(r["lateral"]), float(half_at.call(float(r["s"]))), rad_to_deg(float(r["yaw"])), gap]
			csv.store_line(line)
			print("[vitrine_cyclistes_gravel] ", line)
