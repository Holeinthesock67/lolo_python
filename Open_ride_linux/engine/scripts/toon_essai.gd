extends RefCounted

## Essais de rendu du style dessin animé (lot CS0) : contours d'écran et aplats du prototype du 23 novembre,
## branchés dans le jeu par OPENRIDE_RENDER_DIAG pour en mesurer le coût sur le PC cible (engine/tests/cout_rendu.py,
## variantes `cs_…`). Sans variable, rien n'est créé : aucun nœud, aucun shader chargé, image inchangée.
##
##   contours            trait sombre sur les ruptures de profondeur et de normale (shaders/toon_essai.gdshader)
##   contours_px=F       épaisseur du trait en pixels (1,25 sans réglage)
##   contours_m=M        distance où le trait a disparu (350 m sans réglage)
##   paliers=N           luminosité de l'image en N niveaux (5 au prototype) ; lit l'image entière
##
## Le quad lit les tampons de profondeur et de normales de l'écran. Au cloud (Vulkan logiciel), ils sont vides
## quand le MSAA est actif : les variantes du banc mesurent le trait avec le MSAA du préréglage et avec le SMAA
## à sa place (`msaa=0,screen_aa=smaa`), les captures disent s'il est dessiné.
## Pas de class_name : charger par preload("res://scripts/toon_essai.gd").

const RenderDiag := preload("res://scripts/render_diag.gd")

const SHADER_PATH := "res://shaders/toon_essai.gdshader"
const NODE_NAME := "ToonEssai"
const DEFAULT_THICKNESS_PX := 1.25
const DEFAULT_FADE_M := 350.0
## Dessiné avant les autres objets transparents (eau, particules, halos des lampes), qui restent par-dessus.
const RENDER_PRIORITY := -128


## Essai demandé : {outlines, thickness_px, fade_m, levels} ; dictionnaire vide sans essai.
static func wanted() -> Dictionary:
	var outlines := RenderDiag.has("contours")
	var levels := maxf(0.0, RenderDiag.number("paliers", 0.0))
	if not outlines and levels < 0.5:
		return {}
	return {"outlines": outlines, "levels": levels,
		"thickness_px": clampf(RenderDiag.number("contours_px", DEFAULT_THICKNESS_PX), 0.5, 6.0),
		"fade_m": clampf(RenderDiag.number("contours_m", DEFAULT_FADE_M), 20.0, 5000.0)}


## Pose le quad de l'essai sous la caméra (une seule fois) ; renvoie le nœud, ou null sans essai.
static func attach(camera: Camera3D) -> MeshInstance3D:
	var w := wanted()
	if w.is_empty() or camera == null:
		return null
	var old := camera.get_node_or_null(NODE_NAME)
	if old != null:
		return old as MeshInstance3D
	var quad := MeshInstance3D.new()
	quad.name = NODE_NAME
	var mesh := QuadMesh.new()
	mesh.size = Vector2(2.0, 2.0)
	quad.mesh = mesh
	quad.extra_cull_margin = 16384.0
	quad.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := ShaderMaterial.new()
	mat.shader = load(SHADER_PATH)
	mat.render_priority = RENDER_PRIORITY
	mat.set_shader_parameter("outlines", bool(w["outlines"]))
	mat.set_shader_parameter("levels", float(w["levels"]))
	mat.set_shader_parameter("thickness", float(w["thickness_px"]))
	mat.set_shader_parameter("fade_m", float(w["fade_m"]))
	quad.material_override = mat
	camera.add_child(quad)
	quad.position = Vector3(0.0, 0.0, -1.0)
	return quad
