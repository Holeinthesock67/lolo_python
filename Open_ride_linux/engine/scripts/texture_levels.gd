extends RefCounted

## Niveau des textures du décor (lot P20) : quel côté de texture charger selon le préréglage de qualité, la
## mémoire vidéo estimée et le réglage `[render] texture_level`.
## - Un thème peut fournir plusieurs niveaux (`texture_levels` : liste `{name, max_px, dir}`, Format .world v1
##   §9) ; un chemin de texture est alors cherché dans le dossier du niveau retenu, puis dans ceux des niveaux
##   inférieurs, puis à la racine du thème ; sans `texture_levels`, les textures du thème sont réduites au
##   côté retenu au chargement (2 048, 1 024 ou 512 px) ;
## - côté voulu : `QualityPresets.texture_px` du préréglage, ou du préréglage imposé par `texture_level`
##   (`auto` : celui de la qualité) ; plafonné par le budget de mémoire vidéo du même préréglage
##   (`QualityPresets.texture_budget_bytes`) : niveau inférieur, puis couleurs unies ;
## - estimation : tailles décompressées (RGBA8), mipmaps comprises (× 4/3), majorée par le côté du niveau.
## Pas de class_name : charger par preload("res://scripts/texture_levels.gd").

const QualityPresets := preload("res://scripts/quality_presets.gd")

const AUTO := "auto"
## Côtés essayés pour un thème sans `texture_levels`, du plus grand au plus petit.
const DEFAULT_SIZES: Array[int] = [2048, 1024, 512]


## Mémoire vidéo estimée de `maps` cartes de `px` × `px` (RGBA8 décompressé, mipmaps comprises : × 4/3).
static func estimate_bytes(maps: int, px: int) -> int:
	return int(float(maps) * px * px * 4.0 * 4.0 / 3.0)


## Niveaux valides du thème, du plus grand au plus petit : [{name, max_px, dir}] ; [] sans `texture_levels`.
static func levels_of(theme: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var raw = theme.get("texture_levels", [])
	if typeof(raw) != TYPE_ARRAY:
		return out
	for l in raw:
		if typeof(l) != TYPE_DICTIONARY or typeof(l.get("dir", null)) != TYPE_STRING:
			continue
		var px = l.get("max_px", null)
		if (typeof(px) != TYPE_INT and typeof(px) != TYPE_FLOAT) or int(px) <= 0:
			continue
		out.append({"name": str(l.get("name", str(int(px)))), "max_px": int(px), "dir": str(l["dir"])})
	out.sort_custom(func(a, b): return a["max_px"] > b["max_px"])
	return out


## Préréglage qui fixe le côté et le budget : `forced` s'il en est un, sinon `preset`.
static func governing_preset(preset: String, forced: String) -> String:
	var f := forced.strip_edges()
	return f if f in QualityPresets.TEXTURE_PX else preset


## Niveau retenu pour `maps` cartes : {name, px, dir, bytes, reason, levels} ; px = 0 : couleurs unies.
## `levels` garde les niveaux du thème (ordre décroissant) pour le repli de `resolve`.
static func choose(theme: Dictionary, preset: String, forced: String, maps: int) -> Dictionary:
	var gov := governing_preset(preset, forced)
	var want := QualityPresets.texture_px(gov)
	var budget := QualityPresets.texture_budget_bytes(gov)
	var levels := levels_of(theme)
	var why := "imposé (%s)" % gov if gov != preset else "préréglage %s" % gov
	if maps == 0:
		return {"name": "", "px": 0, "dir": "", "bytes": 0, "reason": "aucune texture, %s" % why, "levels": levels}
	var candidates: Array[Dictionary] = []
	if levels.is_empty():
		for px in DEFAULT_SIZES:
			candidates.append({"name": "%d px" % px, "max_px": px, "dir": ""})
	else:
		candidates = levels
	var allowed := candidates.filter(func(c): return int(c["max_px"]) <= want)
	if allowed.is_empty():   # le plus petit niveau du pack dépasse le côté voulu : il reste le seul possible
		allowed = [candidates[-1]]
	for i in range(allowed.size()):
		var c: Dictionary = allowed[i]
		var bytes := estimate_bytes(maps, int(c["max_px"]))
		if bytes <= budget:
			return {"name": c["name"], "px": int(c["max_px"]), "dir": c["dir"], "bytes": bytes,
				"reason": why if i == 0 else "budget de %d Mo" % (budget >> 20), "levels": levels}
	return {"name": "", "px": 0, "dir": "", "bytes": 0, "levels": levels,
		"reason": "budget de %d Mo dépassé même au plus petit niveau" % (budget >> 20)}


## Chemin complet de la texture `rel` pour le niveau `choice` : dossier du niveau, puis des niveaux
## inférieurs, puis racine du thème ; "" si absente partout ou hors du dossier du thème.
static func resolve(theme_dir: String, rel: String, choice: Dictionary) -> String:
	var base := ProjectSettings.globalize_path(theme_dir).simplify_path()
	var dirs: Array[String] = []
	var px := int(choice.get("px", 0))
	for l in choice.get("levels", []):
		if int(l["max_px"]) <= px:
			dirs.append(str(l["dir"]))
	dirs.append("")
	for d in dirs:
		var full := base.path_join(d).path_join(rel).simplify_path()
		if not full.begins_with(base + "/"):
			return ""
		if FileAccess.file_exists(full):
			return full
	return ""


## Ligne de journal du niveau retenu (`what` : « décor », « sols des biomes »…).
static func log_line(what: String, choice: Dictionary, maps: int) -> String:
	var lvl := ("%s (%d px)" % [choice["name"], choice["px"]]) if int(choice["px"]) > 0 else "couleurs unies"
	return "[textures] %s : %d cartes, niveau %s, %.0f Mo estimés, %s" % [what, maps, lvl,
		int(choice["bytes"]) / 1048576.0, choice["reason"]]
