extends RefCounted

## Surface du ruban de route (lot U22, option « gravel », Format .world v1 §4 et §9 `surfaces`).
## - Surface effective selon `[gravel] mode` (IPC 1.6, `hello_ack.config.gravel`, ou `--gravel=`) : `off`
##   bitume partout ; `auto` colonne `surface` du parcours ; `compacted`, `gravel` ou `dirt` : toute la route
##   dans cette surface (décision U-Q8) ;
## - portion non revêtue : couleur et largeur de `surfaces` du thème (largeurs par défaut 4 m `compacted`,
##   3,5 m `gravel`, 3 m `dirt`), bords irréguliers par un bruit déterministe de ± 0,25 m (pas de 3 m),
##   raccord en biseau de 5 m avec le bitume (part non revêtue moyenne sur 5 m centrés) ;
## - `paved` partout (option coupée, ou `auto` sans colonne) : `active()` faux, le ruban d'avant U22.
## - aspect de la chaussée par biome (lot SM2, thème `biomes.<id>.road.color`) : là où ces biomes pèsent, le bitume
##   prend leur couleur, sans marquage (piste de sable du fond marin) ; largeur, physique, son et cyclistes du décor
##   inchangés ; une portion réellement non revêtue (option gravel) garde sa surface. `look` = {weights_at, looks}.
## Pas de class_name : charger par preload("res://scripts/road_surface.gd").

const MODES := ["off", "auto", "compacted", "gravel", "dirt"]
const UNPAVED := ["compacted", "gravel", "dirt"]
const DEFAULT_WIDTH_M := {"compacted": 4.0, "gravel": 3.5, "dirt": 3.0}
## Couleurs sRGB, converties en linéaire par road_markings.gdshader (Forward+) ; gris-brun, retour du propriétaire 03/11.
const DEFAULT_COLOR := {"compacted": Color(0.60, 0.54, 0.42), "gravel": Color(0.54, 0.48, 0.38),
	"dirt": Color(0.54, 0.44, 0.31)}
const BEVEL_M := 5.0
const BEVEL_SAMPLES := 11
const EDGE_NOISE_M := 0.25
const EDGE_STEP_M := 3.0


static func effective(route_surface: String, mode: String) -> String:
	if mode == "off" or not (mode in MODES):
		return "paved"
	if mode == "auto":
		return route_surface if route_surface in UNPAVED else "paved"
	return mode


## Couleur et largeur de chaque surface non revêtue : `surfaces` du thème, sinon les valeurs par défaut.
static func surfaces_of(theme: Dictionary) -> Dictionary:
	var raw = theme.get("surfaces", {})
	var out := {}
	for id in UNPAVED:
		var entry = raw.get(id, {}) if typeof(raw) == TYPE_DICTIONARY else {}
		if typeof(entry) != TYPE_DICTIONARY:
			entry = {}
		var color: Color = DEFAULT_COLOR[id]
		if typeof(entry.get("color", null)) == TYPE_STRING and Color.html_is_valid(entry["color"]):
			color = Color.html(entry["color"])
		var width := float(entry.get("width_m", DEFAULT_WIDTH_M[id])) if typeof(entry.get("width_m", null)) in [TYPE_INT, TYPE_FLOAT] else float(DEFAULT_WIDTH_M[id])
		out[id] = {"color": color, "width_m": clampf(width, 1.0, 8.0)}
	return out


## Couleur de la chaussée de chaque biome qui en donne une (`biomes.<id>.road.color` du thème, lot SM2).
static func biome_looks(theme: Dictionary) -> Dictionary:
	var out := {}
	var biomes = theme.get("biomes", {})
	if typeof(biomes) != TYPE_DICTIONARY:
		return out
	for b in biomes:
		var entry = biomes[b]
		var road = entry.get("road", null) if typeof(entry) == TYPE_DICTIONARY else null
		if typeof(road) == TYPE_DICTIONARY and typeof(road.get("color", null)) == TYPE_STRING \
				and Color.html_is_valid(road["color"]):
			out[str(b)] = Color.html(road["color"])
	return out


## Part et couleur de l'aspect par biome en un point, d'après les poids des biomes (somme 1) : {weight, color}.
static func look_from_weights(weights: Dictionary, looks: Dictionary) -> Dictionary:
	var w := 0.0
	var c := Color(0, 0, 0)
	for b in weights:
		if looks.has(b):
			var wb := float(weights[b])
			w += wb
			c += (looks[b] as Color) * wb
	if w <= 0.0:
		return {"weight": 0.0, "color": Color.WHITE}
	return {"weight": clampf(w, 0.0, 1.0), "color": Color(c.r / w, c.g / w, c.b / w)}


## Vrai si `look` ({weights_at: Callable (x, z) -> poids, looks: biome_looks}) peut changer la chaussée.
static func look_active(look: Dictionary) -> bool:
	return not (look.get("looks", {}) as Dictionary).is_empty() and (look.get("weights_at", Callable()) as Callable).is_valid()


## Vrai si le ruban change : option active et, en `auto`, une colonne `surface` avec au moins un point non revêtu.
static func active(route, mode: String) -> bool:
	if mode == "off" or not (mode in MODES):
		return false
	if mode != "auto":
		return true
	for v in route.surface:
		if v in UNPAVED:
			return true
	return false


## Bruit de valeur déterministe dans [−1, 1], interpolé tous les `EDGE_STEP_M` mètres.
static func edge_noise(s: float, side: int) -> float:
	var t := s / EDGE_STEP_M
	var i := floori(t)
	var f := t - i
	var a := _hash(i, side)
	var b := _hash(i + 1, side)
	var u := f * f * (3.0 - 2.0 * f)
	return lerpf(a, b, u)


static func _hash(i: int, side: int) -> float:
	var h := (i * 374761393 + side * 668265263) & 0x7fffffff
	h = ((h ^ (h >> 13)) * 1274126177) & 0x7fffffff
	return float(h % 2001) / 1000.0 - 1.0


## Coupe du ruban en s : {weight (0 bitume, 1 non revêtu), surface, color, left_m, right_m} ; `left_m` et
## `right_m` : demi-largeurs à gauche et à droite de l'axe, bruit des bords compris.
## Sans portion non revêtue, l'aspect par biome (`look`, lot SM2) : même largeur, couleur du biome, part = son poids.
static func section(route, s: float, mode: String, surfaces: Dictionary, road_width_m: float,
		look: Dictionary = {}) -> Dictionary:
	var count := {}
	var unpaved := 0
	for j in range(BEVEL_SAMPLES):
		var sv := s - BEVEL_M * 0.5 + BEVEL_M * j / (BEVEL_SAMPLES - 1)
		var e := effective(route.surface_at(sv), mode) if mode == "auto" else effective("paved", mode)
		if e != "paved":
			unpaved += 1
			count[e] = int(count.get(e, 0)) + 1
	var weight := float(unpaved) / BEVEL_SAMPLES
	var half := road_width_m * 0.5
	if unpaved == 0:
		if look_active(look):
			var smp: Dictionary = route.sample(s)
			var lk := look_from_weights((look["weights_at"] as Callable).call(float(smp["x"]), float(smp["z"])), look["looks"])
			if float(lk["weight"]) > 0.0:
				return {"weight": lk["weight"], "surface": "paved", "color": lk["color"], "left_m": half, "right_m": half,
					"verge": 1.0}
		return {"weight": 0.0, "surface": "paved", "color": Color.WHITE, "left_m": half, "right_m": half}
	var main := ""
	for id in UNPAVED:   # surface la plus présente dans le biseau, ordre fixe en cas d'égalité
		if int(count.get(id, 0)) > int(count.get(main, 0)):
			main = id
	var target: float = float(surfaces[main]["width_m"]) * 0.5
	var w := lerpf(half, target, weight)
	return {"weight": weight, "surface": main, "color": surfaces[main]["color"],
		"left_m": w + EDGE_NOISE_M * weight * edge_noise(s, 0), "right_m": w + EDGE_NOISE_M * weight * edge_noise(s, 1)}


## Demi-largeur sûre de la chaussée en `s` (cyclistes du décor sur le gravel, 7/11) : celle du bitume, ou sur une
## portion non revêtue celle de `section` sans ses bords irréguliers (le plus étroit des deux côtés possibles).
## Portage : core/src/openride_core/surface_physics.py `rideable_half_m`.
static func rideable_half(route, s: float, mode: String, surfaces: Dictionary, road_width_m: float) -> float:
	var half := road_width_m * 0.5
	if route == null or not active(route, mode):
		return half
	var sec := section(route, s, mode, surfaces, road_width_m)
	var weight := float(sec["weight"])
	if weight <= 0.0:
		return half
	var target := float(surfaces[str(sec["surface"])]["width_m"]) * 0.5
	return lerpf(half, target, weight) - EDGE_NOISE_M * weight
