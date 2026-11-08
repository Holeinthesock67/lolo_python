extends RefCounted

## Sortie en ordre des tests de rendu (outil commun à tous les tests de tests/render/).
## Sur la GTX 1060 (Godot 4.7, Forward+, Xvfb), un test qui quitte pendant que Godot compile encore des
## pipelines en arrière-plan passe ses vérifications puis ne quitte jamais (tué au bout de UNIT_TIMEOUT par
## run_engine_tests.sh, code 124) : vu sur test_rogue_style_sheet_render au premier lancement, cache des shaders
## vide (#712), puis sur test_boat_render, test_props_render et test_sky_render (essai r773 du 8 novembre).
## Chaque test attend donc la fin des compilations avant de quitter : compteurs du serveur de rendu inchangés
## depuis SETTLE_S secondes et SETTLE_FRAMES images, attente bornée à SETTLE_MAX_S secondes.
## Pas de class_name : charger par preload("res://tests/render/render_exit.gd").

const SETTLE_FRAMES := 10
const SETTLE_S := 1.0
const SETTLE_MAX_S := 30.0
const PIPELINE_INFOS := [RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_CANVAS,
	RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_MESH, RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SURFACE,
	RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_DRAW,
	RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SPECIALIZATION]


static func pipeline_compilations() -> int:
	var total := 0
	for info in PIPELINE_INFOS:
		total += RenderingServer.get_rendering_info(info)
	return total


## Attend la fin des compilations de pipelines (voir l'en-tête) ; affiche le nombre relevé et l'attente.
static func settle(tree: SceneTree) -> void:
	var start := Time.get_ticks_msec()
	var last := pipeline_compilations()
	var since := start
	var frames := 0
	while Time.get_ticks_msec() - start < SETTLE_MAX_S * 1000.0:
		await tree.process_frame
		var now := pipeline_compilations()
		if now != last:
			last = now
			since = Time.get_ticks_msec()
			frames = 0
		else:
			frames += 1
		if frames >= SETTLE_FRAMES and Time.get_ticks_msec() - since >= SETTLE_S * 1000.0:
			break
	print("compilations de pipelines : %d, attente %d ms" % [last, Time.get_ticks_msec() - start])
