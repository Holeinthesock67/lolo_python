extends SceneTree

## Glissières d'un parcours compilé (lot JP8), comme si tout le parcours était dans un biome de
## GUARDRAIL_BIOMES : morceaux (début, fin, côté) et liste --at-m des milieux pour les planches des bancs.
## Lancement : godot --headless --path engine --script res://tests/liste_glissieres.gd -- --world DOSSIER.world [--max N]

const RouteData := preload("res://scripts/route_data.gd")
const RoadsideModel := preload("res://scripts/roadside_model.gd")


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var world := ""
	var max_n := 6
	for i in range(args.size()):
		if args[i] == "--world" and i + 1 < args.size():
			world = args[i + 1]
		elif args[i] == "--max" and i + 1 < args.size():
			max_n = int(args[i + 1])
	var route = RouteData.new()
	if world.is_empty() or not route.load_world_dir(world):
		printerr("Parcours illisible : ", world)
		quit(1)
		return
	var everywhere := func(_x: float, _z: float) -> String: return RoadsideModel.GUARDRAIL_BIOMES[0]
	var runs: Array = RoadsideModel.guardrails(route, everywhere)
	var mids := []
	for r in runs:
		var mid := 0.5 * (float(r["s"]) + float(r["s_end"]))
		print("glissière %s de %.0f à %.0f m" % ["à gauche" if int(r["side"]) < 0 else "à droite", float(r["s"]), float(r["s_end"])])
		mids.append(mid)
	print("%d morceaux sur %.0f m" % [runs.size(), float(route.length_m)])
	# Milieux répartis sur le parcours, au plus max_n, 30 m avant (la glissière devant la caméra)
	var at := []
	if not mids.is_empty():
		var stride := maxf(1.0, float(mids.size()) / float(max_n))
		var i := 0.0
		while int(i) < mids.size() and at.size() < max_n:
			at.append(str(int(maxf(0.0, mids[int(i)] - 30.0))))
			i += stride
	print("--at-m ", ",".join(at))
	quit(0)
