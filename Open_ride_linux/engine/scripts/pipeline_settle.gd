extends RefCounted

## Attente de la fin des compilations de pipelines en arrière-plan du serveur de rendu (Godot 4.7, Forward+).
## Sur la GTX 1060, Godot qui quitte pendant ces compilations ne se ferme jamais : tests de rendu (#712, r773,
## sortie en ordre de tests/render/render_exit.gd) et, essai du lot X58, fermeture du jeu par la souris.
## Fin : compteurs inchangés depuis `settle_s` secondes et `frames` images, attente bornée à `max_s` secondes.
## Pas de class_name : charger par preload("res://scripts/pipeline_settle.gd").

const PIPELINE_INFOS := [RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_CANVAS,
	RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_MESH, RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SURFACE,
	RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_DRAW,
	RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SPECIALIZATION]


static func pipeline_compilations() -> int:
	var total := 0
	for info in PIPELINE_INFOS:
		total += RenderingServer.get_rendering_info(info)
	return total


## Attend la fin des compilations (voir l'en-tête) ; renvoie [nombre relevé, attente en ms].
static func settle(tree: SceneTree, frames: int, settle_s: float, max_s: float) -> Array:
	var start := Time.get_ticks_msec()
	var last := pipeline_compilations()
	var since := start
	var still := 0
	while Time.get_ticks_msec() - start < max_s * 1000.0:
		await tree.process_frame
		var now := pipeline_compilations()
		if now != last:
			last = now
			since = Time.get_ticks_msec()
			still = 0
		else:
			still += 1
		if still >= frames and Time.get_ticks_msec() - since >= settle_s * 1000.0:
			break
	return [last, Time.get_ticks_msec() - start]
