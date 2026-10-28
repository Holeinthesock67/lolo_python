extends CanvasLayer

## Écran de couloir du Cyber-Rogue (lot R13) : trois cartes puis deux portes en surimpression de la scène. Le
## core gère les boutons ; l'engine ne fait qu'afficher la sélection `loot_focus` (0 à 2 : les cartes, 3 : porte
## de gauche, 4 : porte de droite) et le coût de relance. Mêmes styles que les menus (ui_theme.gd), couleurs de la
## charte R17. Reçoit `corridor` de rogue_hud_model.gd (vide hors couloir : l'écran se cache).

const UiTheme := preload("res://scripts/ui_theme.gd")

const ARCHETYPE_NAMES := {"diesel": "Diesel", "puncheur": "Puncheur", "grimpeur": "Grimpeur",
	"sprinteur": "Sprinteur", "saboteur": "Saboteur", "boss": "Boss"}
## Jeton de couleur du type de carte (catalogue R17 : card_*), repris par ui_theme.
const KIND_COLORS := {"terraformer": UiTheme.GOLD, "gear": UiTheme.FOCUS, "module": Color(0.18, 0.48, 1.0),
	"active": Color(1.0, 0.54, 0.12), "relic": UiTheme.TEXT}
const CARD_COUNT := 3

var root: VBoxContainer
var cards: Array = []              # PanelContainer
var doors: Array = []              # PanelContainer
var reroll: Label
var _key := ""


func _ready() -> void:
	layer = 6
	visible = false
	root = VBoxContainer.new()
	root.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	root.offset_top = -300.0
	root.offset_left = UiTheme.MARGIN
	root.offset_right = -UiTheme.MARGIN
	root.offset_bottom = -UiTheme.GAP
	root.add_theme_constant_override("separation", UiTheme.GAP)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	var card_row := HBoxContainer.new()
	card_row.add_theme_constant_override("separation", UiTheme.GAP)
	root.add_child(card_row)
	for _i in CARD_COUNT:
		var p := PanelContainer.new()
		p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		card_row.add_child(p)
		cards.append(p)
	var door_row := HBoxContainer.new()
	door_row.add_theme_constant_override("separation", UiTheme.GAP)
	root.add_child(door_row)
	for _i in 2:
		var p := PanelContainer.new()
		p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		door_row.add_child(p)
		doors.append(p)
	reroll = UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM)
	root.add_child(reroll)


static func card_color(kind: String) -> Color:
	return KIND_COLORS.get(kind, UiTheme.TEXT)


static func archetype_name(archetype: String) -> String:
	return ARCHETYPE_NAMES.get(archetype, archetype)


## Texte d'une porte : côté et archétype de la salle derrière.
static func door_text(door: Dictionary) -> String:
	var side := "← Porte de gauche" if str(door.get("side", "")) == "left" else "Porte de droite →"
	return "%s : %s" % [side, archetype_name(str(door.get("archetype", "")))]


## `corridor` : {cards, doors, focus, reroll_cost, can_reroll} ou {} hors couloir.
func apply(corridor: Dictionary) -> void:
	if root == null:
		return
	visible = not corridor.is_empty()
	if not visible:
		_key = ""
		return
	var key := str(corridor.hash())
	if key == _key:
		return
	_key = key
	var focus := int(corridor.get("focus", -1))
	var card_list: Array = corridor.get("cards", [])
	for i in CARD_COUNT:
		_fill(cards[i], card_list[i] if i < card_list.size() else {}, i == focus, true)
	var door_list: Array = corridor.get("doors", [])
	for i in 2:
		_fill(doors[i], door_list[i] if i < door_list.size() else {}, 3 + i == focus, false)
	var cost := int(corridor.get("reroll_cost", 0))
	reroll.text = "Relancer les cartes : %d or%s" % [cost, "" if bool(corridor.get("can_reroll", true)) else " (or insuffisant)"]


func _fill(panel: PanelContainer, data: Dictionary, focused: bool, is_card: bool) -> void:
	for c in panel.get_children():
		c.queue_free()
	var style := UiTheme.card_style()
	if focused:
		style.border_color = UiTheme.FOCUS
		style.set_border_width_all(3)
	panel.add_theme_stylebox_override("panel", style)
	var box := VBoxContainer.new()
	panel.add_child(box)
	if is_card:
		var tint := card_color(str(data.get("kind", "")))
		var title := UiTheme.label(UiTheme.ITEM_SIZE, tint, str(data.get("name", "")))
		box.add_child(title)
		var body := UiTheme.label(UiTheme.CARD_SIZE, UiTheme.TEXT, str(data.get("text", "")))
		body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(body)
	else:
		box.add_child(UiTheme.label(UiTheme.ITEM_SIZE, UiTheme.TEXT, door_text(data)))
