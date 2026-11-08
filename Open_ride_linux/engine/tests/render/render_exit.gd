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
const PipelineSettle := preload("res://scripts/pipeline_settle.gd")


static func pipeline_compilations() -> int:
	return PipelineSettle.pipeline_compilations()


## Attend la fin des compilations de pipelines (voir l'en-tête, engine/scripts/pipeline_settle.gd) ; affiche le
## nombre relevé et l'attente.
static func settle(tree: SceneTree) -> void:
	var got: Array = await PipelineSettle.settle(tree, SETTLE_FRAMES, SETTLE_S, SETTLE_MAX_S)
	print("compilations de pipelines : %d, attente %d ms" % [got[0], got[1]])
