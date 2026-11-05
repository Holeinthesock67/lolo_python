extends RefCounted

## Essais de rendu sur le PC (OPENRIDE_RENDER_DIAG) : liste séparée par des virgules de drapeaux (`sans_ombres`)
## et de réglages `clé=valeur` (`msaa=2`), lue une fois au démarrage. Sert à mesurer le coût de chaque effet au
## banc (engine/tests/cout_rendu.py) et à chercher l'effet qui dessine un défaut. Aucun réglage du joueur ne
## passe par là ; variable vide : rien ne change.
##
## Drapeaux et réglages (RenderQuality.apply_diagnostic sauf mention) :
##   sans_ombres, sans_ssao, sans_ssil, sans_brume, sans_glow, biais_ombres, ombres_2_cascades,
##   brume_ambiante (lumière ambiante injectée dans la brume volumétrique),
##   msaa=0|2|4, screen_aa=off|fxaa|smaa, ssao=low|medium|high, ssil=low|medium|high, atlas=2048|4096, ombres_m=M, filtre=hard|low|medium,
##   vegetation=F (densité des arbres, world_streamer), herbe=F (nombre de touffes, living_world),
##   sans_ombres_arbres, arbres_lod0_m=M, feuillage_simple (arbres et herbe en diffuse_lambert, specular_disabled),
##   arbres_loin_simple (même chose et sans vent pour les arbres du LOD 1) (tree_renderer),
##   anisotropy=2|4|8|16, halo_niveaux=N, halo_lineaire.
## Améliorations à faible coût (0 = rendu actuel) : soleil_brume=F (fog_sun_scatter du brouillard),
##   terrain_macro=F (variation de l'herbe à 600 m, terrain_material), herbe_degrade=F (pied sombre, pointe claire,
##   grass_tufts et ground_details).
## Réglage de l'image (RenderQuality.apply_diagnostic) : brume_ambiante=F (0 à 2, au lieu du drapeau = 1),
##   brume_densite=F (facteur sur la densité de la brume volumétrique, RenderQuality.volumetric_density), contraste=F, saturation=F,
##   agx_contraste=F, exposition=F (valeurs de LOOK remplacées).
## Pas de class_name : charger par preload("res://scripts/render_diag.gd").

static var _parsed := false
static var _flags := PackedStringArray()
static var _values := {}


static func parse(text: String) -> Dictionary:
	var flags := PackedStringArray()
	var values := {}
	for item in text.replace(" ", "").split(",", false):
		var kv := item.split("=", false, 1)
		if kv.size() == 2:
			values[kv[0]] = kv[1]
		else:
			flags.append(item)
	return {"flags": flags, "values": values}


static func _load() -> void:
	if _parsed:
		return
	_parsed = true
	var d := parse(OS.get_environment("OPENRIDE_RENDER_DIAG"))
	_flags = d["flags"]
	_values = d["values"]


static func has(flag: String) -> bool:
	_load()
	return flag in _flags


static func value(key: String, default: String = "") -> String:
	_load()
	return str(_values.get(key, default))


static func number(key: String, default: float) -> float:
	var v := value(key)
	return float(v) if v.is_valid_float() else default


static func text() -> String:
	_load()
	var parts := Array(_flags)
	for k in _values:
		parts.append("%s=%s" % [k, _values[k]])
	return ", ".join(parts)
