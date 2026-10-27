extends RefCounted

## Modèle sans affichage du carrefour à l'approche (lot W12, plan §2.3, contrat IPC 1.5 `state.open_world.next`).
##
## `update(next)` reçoit `open_world.next` (ou null) ; `view()` donne ce que le panneau affiche ;
## `press(sens)` donne la commande `choose_branch` d'une flèche du clavier (←, →) ou {} quand rien ne part.
## Pas de class_name (charger par preload).

const VISIBLE_FROM_M := 300.0    # le panneau apparaît à 300 m du carrefour et reste jusqu'à lui
const ARROW_STEP_DEG := 15.0
const ATTRIBUTION := "© OpenStreetMap, OpenMapTiles, Copernicus"
## Classes du contrat (§4 « Monde ouvert ») : p grande route, s et t routes, m petite route, c piste cyclable, k chemin revêtu.
const CLASS_LABELS := {"p": "grande route", "s": "route", "t": "route", "m": "petite route",
	"c": "piste cyclable", "k": "chemin revêtu"}
const UNKNOWN_CLASS := "route"

const HudViewModel := preload("res://scripts/hud_view_model.gd")

var _next: Dictionary = {}
## Branche demandée au clavier, tant que le core ne l'a pas confirmée dans `next.chosen` (une trame ou deux).
var _pending := -1
var _pending_id := ""


func update(next: Variant) -> void:
	_next = next if typeof(next) == TYPE_DICTIONARY else {}
	var id := str(_next.get("id", ""))
	if id != _pending_id or int(_next.get("chosen", -1)) == _pending:
		_pending = -1
		_pending_id = id


static func class_label(code: Variant) -> String:
	return str(CLASS_LABELS.get(str(code), UNKNOWN_CLASS))


static func round_arrow(angle_deg: float) -> int:
	return int(roundf(angle_deg / ARROW_STEP_DEG) * ARROW_STEP_DEG)


func is_visible() -> bool:
	if _next.is_empty():
		return false
	var d := float(_next.get("d_m", -1.0))
	return d >= 0.0 and d <= VISIBLE_FROM_M and _branches().size() > 0


func _branches() -> Array:
	var raw = _next.get("b", [])
	var out := []
	if typeof(raw) != TYPE_ARRAY:
		return out
	var index := 0
	for t in raw:
		if typeof(t) == TYPE_ARRAY and (t as Array).size() >= 3:
			out.append({"index": index, "angle": float(t[0]), "class": str(t[1]), "grade": float(t[2])})
		index += 1
	return out


## Branche affichée comme choisie : la demande du clavier en attente, sinon le choix du core, sinon le défaut.
func chosen_index() -> int:
	if _pending >= 0:
		return _pending
	return int(_next.get("chosen", _next.get("default", 0)))


func is_locked() -> bool:
	return bool(_next.get("locked", false))


## Branches triées de gauche à droite (angle croissant ; positif à droite).
func sorted_branches() -> Array:
	var items := _branches()
	items.sort_custom(func(a, b): return float(a["angle"]) < float(b["angle"]) or \
		(float(a["angle"]) == float(b["angle"]) and int(a["index"]) < int(b["index"])))
	return items


## Contenu du panneau : {visible, id, distance_m, locked, title, branches: [{index, arrow_deg, label, grade_pct,
## grade_class, is_default, is_chosen, greyed}]}.
func view() -> Dictionary:
	if not is_visible():
		return {"visible": false, "branches": []}
	var locked := is_locked()
	var default_index := int(_next.get("default", 0))
	var chosen := chosen_index()
	var cells := []
	for b in sorted_branches():
		var idx: int = b["index"]
		var grade := int(roundf(float(b["grade"])))
		cells.append({
			"index": idx,
			"arrow_deg": round_arrow(float(b["angle"])),
			"label": class_label(b["class"]),
			"grade_pct": grade,
			"grade_text": "%+d %%" % grade if grade != 0 else "0 %",
			"grade_class": HudViewModel.grade_class(float(grade)),
			"is_default": idx == default_index,
			"is_chosen": idx == chosen,
			"greyed": locked and idx != chosen,
		})
	var distance := int(roundf(float(_next.get("d_m", 0.0))))
	return {"visible": true, "id": str(_next.get("id", "")), "distance_m": distance, "locked": locked,
		"title": "Choix verrouillé" if locked else "Carrefour dans %d m" % distance, "branches": cells}


## Flèche du clavier : -1 gauche, +1 droite. Renvoie {junction_id, branch} (arguments de `choose_branch`) ou {}
## si le panneau est caché, le choix verrouillé ou la branche déjà la plus à gauche ou à droite.
func press(direction: int) -> Dictionary:
	if not is_visible() or is_locked() or direction == 0:
		return {}
	var items := sorted_branches()
	var current := chosen_index()
	var pos := -1
	for i in range(items.size()):
		if int(items[i]["index"]) == current:
			pos = i
	if pos < 0:
		return {}
	var target := pos + (1 if direction > 0 else -1)
	if target < 0 or target >= items.size():
		return {}
	var branch: int = items[target]["index"]
	_pending = branch
	_pending_id = str(_next.get("id", ""))
	return {"junction_id": _pending_id, "branch": branch}


# --- placement ---------------------------------------------------------------------------

const PANEL_HEIGHT := 128.0
const PANEL_MAX_WIDTH := 560.0
const SIDE_PANELS_M := 340.0       # largeur prise de chaque côté par les panneaux de mesures (20 + 300 + 20)
const BANNER_RESERVE := 56.0       # hauteur laissée au bandeau d'alerte sous le panneau central

## Rectangle du panneau : centré, sous le panneau central du HUD et la place du bandeau d'alerte,
## entre les deux colonnes de mesures ; ne descend pas sur le bandeau ERG ni sur le profil d'altitude.
static func layout_for(viewport: Vector2, center_bottom: float) -> Rect2:
	var width := clampf(viewport.x - 2.0 * SIDE_PANELS_M, 300.0, PANEL_MAX_WIDTH)
	var top := center_bottom + BANNER_RESERVE
	return Rect2((viewport.x - width) * 0.5, top, width, PANEL_HEIGHT)
