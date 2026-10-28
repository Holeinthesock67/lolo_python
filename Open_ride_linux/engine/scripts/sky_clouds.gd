extends RefCounted

## Ciel avec nuages qui défilent au vent (Lot P6). Pas de class_name : charger par
## preload("res://scripts/sky_clouds.gd"). Branché par P16 dans main.gd.
##
## - `build_material(params, quality, current, horizon)` : `params` vient de
##   ThemeRenderParams.cloud_params(theme), `quality` est le mode de nuages du préréglage
##   (QualityPresets.living(preset).clouds : "off", "flat" ou "layered"). En "off", ou avec une
##   couverture nulle, rend `current` (le matériau de ciel actuel) sans le changer ; sans `current`,
##   le ciel procédural actuel du moteur Compatibility. `horizon` est la couleur de l'horizon du ciel
##   nuageux : main.gd y passe la couleur du brouillard (`fog_light_color`), pour que le relief qui
##   disparaît dans le brouillard raccorde au ciel (le brouillard ne touche plus le ciel, render_quality.gd).
## - `update(material, wind_eval, dt_s)` une fois par image avec la sortie de wind_model.evaluate() :
##   cumule le défilement des nuages (vent × speed_factor). Sans effet sur un autre matériau.
## - Ombre des nuages sur le terrain (`high` seulement) : `terrain_shadow_params` donne les uniforms
##   `cloud_shadow_*` de terrain.gdshader, alignés sur le même bruit et le même défilement.

const SkyShader := preload("res://shaders/sky_clouds.gdshader")
const WindModel := preload("res://scripts/wind_model.gd")

## Couleurs du ciel procédural actuel (main.gd, moteur Compatibility).
const SKY_TOP := Color(0.38, 0.65, 0.98)
const SKY_HORIZON := Color(0.65, 0.75, 0.85)
const LAYERED_OCTAVES := 5
const FLAT_OCTAVES := 4
## Ombre des nuages : assombrissement maximal du terrain.
const SHADOW_STRENGTH := 0.35


## Ciel procédural actuel (le même que main.gd en moteur Compatibility).
static func current_sky_material() -> ProceduralSkyMaterial:
	var m := ProceduralSkyMaterial.new()
	m.sky_top_color = SKY_TOP
	m.sky_horizon_color = SKY_HORIZON
	return m


static func build_material(params: Dictionary, quality: String, current: Material = null,
		horizon: Color = SKY_HORIZON) -> Material:
	var mode := quality.strip_edges()
	var coverage := float(params.get("coverage", 0.0))
	if mode == "off" or mode == "" or coverage <= 0.0:
		return current if current != null else current_sky_material()
	var m := ShaderMaterial.new()
	m.shader = SkyShader
	m.set_shader_parameter("sky_top_color", SKY_TOP)
	m.set_shader_parameter("sky_horizon_color", horizon)
	m.set_shader_parameter("coverage", coverage)
	m.set_shader_parameter("cloud_color", params.get("color", Color(0.957, 0.969, 0.984)))
	m.set_shader_parameter("altitude_m", float(params.get("altitude_m", 2000.0)))
	m.set_shader_parameter("layered", mode == "layered")
	m.set_shader_parameter("octaves", LAYERED_OCTAVES if mode == "layered" else FLAT_OCTAVES)
	m.set_shader_parameter("cloud_offset", Vector2.ZERO)
	m.set_meta("speed_factor", float(params.get("speed_factor", 1.0)))
	return m


static func is_cloud_material(material: Material) -> bool:
	return material is ShaderMaterial and (material as ShaderMaterial).shader == SkyShader


## Défilement cumulé, en mètres (x, z) : les nuages vont vers où souffle le vent.
static func update(material: Material, wind_eval: Dictionary, dt_s: float = 1.0 / 60.0) -> void:
	if not is_cloud_material(material):
		return
	var m := material as ShaderMaterial
	var dir: Vector3 = wind_eval.get("dir", Vector3.ZERO)
	var speed := float(wind_eval.get("strength", 0.0)) * WindModel.MAX_SPEED_MPS * float(m.get_meta("speed_factor", 1.0))
	var off: Vector2 = m.get_shader_parameter("cloud_offset")
	# Le motif est vu par le dessous : un point du plan à (x, z) se lit à EYEDIR.xz × t + offset ;
	# pour qu'il avance vers +dir, l'offset recule.
	off -= Vector2(dir.x, dir.z) * speed * dt_s
	# Repli périodique (le bruit ne se répète pas, mais garde la précision des flottants)
	if off.length() > 1.0e6:
		off = Vector2.ZERO
	m.set_shader_parameter("cloud_offset", off)


## Scène figée des tests graphiques (lot X20) : nuages placés comme s'ils avaient avancé `t_s` secondes depuis 0
## sous le vent `wind_eval`, sans l'historique des images.
static func place(material: Material, wind_eval: Dictionary, t_s: float) -> void:
	if not is_cloud_material(material):
		return
	(material as ShaderMaterial).set_shader_parameter("cloud_offset", Vector2.ZERO)
	update(material, wind_eval, maxf(t_s, 0.0))


## Uniforms de l'ombre des nuages pour terrain.gdshader : désactivée sauf en "layered" (préréglage high).
static func terrain_shadow_params(sky_material: Material, quality: String) -> Dictionary:
	if quality != "layered" or not is_cloud_material(sky_material):
		return {"cloud_shadow_enabled": false}
	var m := sky_material as ShaderMaterial
	return {
		"cloud_shadow_enabled": true,
		"cloud_shadow_coverage": float(m.get_shader_parameter("coverage")),
		"cloud_shadow_offset": m.get_shader_parameter("cloud_offset"),
		"cloud_shadow_altitude_m": float(m.get_shader_parameter("altitude_m")),
		"cloud_shadow_strength": SHADOW_STRENGTH,
	}
