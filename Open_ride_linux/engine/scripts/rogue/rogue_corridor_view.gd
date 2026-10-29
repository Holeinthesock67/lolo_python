extends CanvasLayer

## Écran de couloir du Cyber-Rogue (lot R13) : trois cartes puis deux portes en surimpression de la scène. Le
## core gère les boutons ; l'engine ne fait qu'afficher la sélection `loot_focus` (0 à 2 : les cartes, 3 : porte
## de gauche, 4 : porte de droite) et le coût de relance. Mêmes styles que les menus (ui_theme.gd), couleurs de la
## charte R17 (neon_catalog.gd : cartes `card_*`, ennemis de chaque archétype pour les portes). Reçoit `corridor`
## de rogue_hud_model.gd (vide hors couloir : l'écran se cache).
## Les portes sont des portails cintrés (DoorPortal) à la couleur de l'archétype de la salle derrière, avec son nom
## et ce qui attend le joueur. Le bloc est calé en bas de l'écran et grandit vers le haut : rien n'est coupé, même
## en 1024 × 600 (retouche du 29/10, portes coupées en 720p).

const UiTheme := preload("res://scripts/ui_theme.gd")
const NeonPalette := preload("res://scripts/rogue/neon_palette.gd")
const NeonCatalog := preload("res://scripts/rogue/neon_catalog.gd")

const ARCHETYPE_NAMES := {"diesel": "Diesel", "puncheur": "Puncheur", "grimpeur": "Grimpeur",
	"sprinteur": "Sprinteur", "saboteur": "Saboteur", "boss": "Boss"}
## Ce qui attend le joueur derrière la porte (profils des salles, lot R3).
const ARCHETYPE_HINTS := {"diesel": "Rampe longue et régulière", "puncheur": "Bosses courtes et raides",
	"grimpeur": "Paliers de montée", "sprinteur": "Plat, salves du Firewall",
	"saboteur": "Pente changeante, piratages", "boss": "Tout à la fois"}
## Objet du catalogue R17 dont la porte prend la couleur : l'ennemi de l'archétype.
const ARCHETYPE_OBJECTS := {"diesel": "enemy_diesel", "puncheur": "enemy_puncher", "grimpeur": "enemy_climber",
	"sprinteur": "enemy_sprinter", "saboteur": "enemy_saboteur", "boss": "boss_chimera"}
const CARD_COUNT := 3
const DOOR_SIZE := Vector2(320.0, 150.0)

var root: VBoxContainer
var cards: Array = []              # PanelContainer
var doors: Array = []              # DoorPortal
var reroll: Label
var _key := ""


## Portail cintré : arc surbaissé posé sur deux montants, chambranle intérieur, clé de voûte, seuil lumineux.
## Fond teinté de la couleur, bord plus épais et halo quand la porte est sélectionnée.
class DoorPortal extends PanelContainer:
	var tint := Color(1, 1, 1)
	var focused := false

	func _init() -> void:
		var empty := StyleBoxEmpty.new()
		empty.content_margin_left = 28
		empty.content_margin_right = 28
		empty.content_margin_top = 52
		empty.content_margin_bottom = 16
		add_theme_stylebox_override("panel", empty)
		custom_minimum_size = DOOR_SIZE

	## Contour du portail dans un rectangle `r` : montants droits, arc surbaissé en haut.
	static func outline(r: Rect2, seg: int = 24) -> PackedVector2Array:
		var pts := PackedVector2Array()
		var rise := minf(r.size.y * 0.32, r.size.x * 0.18)
		var top := r.position.y + rise
		pts.append(Vector2(r.position.x, r.end.y))
		pts.append(Vector2(r.position.x, top))
		# Arc de cercle passant par les deux coins hauts et le sommet
		var half := r.size.x * 0.5
		var radius := (half * half + rise * rise) / (2.0 * rise)
		var c := Vector2(r.position.x + half, top - rise + radius)
		var a0 := atan2(top - c.y, r.position.x - c.x)
		var a1 := atan2(top - c.y, r.end.x - c.x)
		for i in range(1, seg):
			var a := lerpf(a0, a1 + TAU if a1 < a0 else a1, float(i) / seg)
			pts.append(c + Vector2(cos(a), sin(a)) * radius)
		pts.append(Vector2(r.end.x, top))
		pts.append(Vector2(r.end.x, r.end.y))
		return pts

	func _draw() -> void:
		var r := Rect2(Vector2(4, 4), size - Vector2(8, 8))
		var pts := outline(r)
		draw_colored_polygon(pts, Color(UiTheme.SURFACE, 0.88))
		draw_colored_polygon(pts, Color(tint, 0.16 if focused else 0.07))
		# Seuil lumineux
		var mid := r.position.x + r.size.x * 0.5
		draw_line(Vector2(r.position.x + 10.0, r.end.y - 4.0), Vector2(r.end.x - 10.0, r.end.y - 4.0), Color(tint, 0.7), 3.0)
		# Montants intérieurs (chambranle)
		var inner := outline(r.grow(-9.0))
		inner.append(inner[0])
		draw_polyline(inner, Color(tint, 0.25), 1.5, true)
		var closed := pts.duplicate()
		closed.append(pts[0])
		if focused:
			draw_polyline(closed, Color(tint, 0.25), 10.0, true)
		draw_polyline(closed, tint if focused else Color(tint, 0.75), 4.0 if focused else 2.0, true)
		# Clé de voûte : petit losange au sommet de l'arc
		var k := Vector2(mid, r.position.y)
		draw_colored_polygon(PackedVector2Array([k + Vector2(0, -6), k + Vector2(7, 2), k + Vector2(0, 10), k + Vector2(-7, 2)]), tint)


func _ready() -> void:
	layer = 6
	visible = false
	root = VBoxContainer.new()
	# Calé en bas, grandit vers le haut : le bloc tient dans l'écran quelle que soit la hauteur des cartes
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.offset_top = UiTheme.GAP
	root.offset_left = UiTheme.MARGIN
	root.offset_right = -UiTheme.MARGIN
	root.offset_bottom = -UiTheme.GAP
	root.alignment = BoxContainer.ALIGNMENT_END
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
	# Deux portes de part et d'autre du couloir, centrées, un passage entre elles
	var door_row := HBoxContainer.new()
	door_row.alignment = BoxContainer.ALIGNMENT_CENTER
	door_row.add_theme_constant_override("separation", int(DOOR_SIZE.x * 0.5))
	root.add_child(door_row)
	for _i in 2:
		var d := DoorPortal.new()
		door_row.add_child(d)
		doors.append(d)
	reroll = UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM)
	reroll.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	root.add_child(reroll)


## Couleur d'une carte : jeton de l'objet `card_<type>` du catalogue R17.
static func card_color(kind: String) -> Color:
	var obj: Dictionary = NeonCatalog.OBJECTS.get("card_" + kind, {})
	return NeonPalette.color(obj["token"]) if obj.has("token") else UiTheme.TEXT


## Couleur d'une porte : jeton de l'ennemi de l'archétype de la salle, sinon celui de `corridor_door`.
static func door_color(archetype: String) -> Color:
	var obj: String = ARCHETYPE_OBJECTS.get(archetype, "corridor_door")
	return NeonPalette.color(NeonCatalog.OBJECTS[obj]["token"])


static func archetype_name(archetype: String) -> String:
	return ARCHETYPE_NAMES.get(archetype, archetype)


static func side_text(door: Dictionary) -> String:
	return "← Porte de gauche" if str(door.get("side", "")) == "left" else "Porte de droite →"


## Texte d'une porte sur une ligne : côté et archétype de la salle derrière.
static func door_text(door: Dictionary) -> String:
	return "%s : %s" % [side_text(door), archetype_name(str(door.get("archetype", "")))]


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
		_fill_card(cards[i], card_list[i] if i < card_list.size() else {}, i == focus)
	var door_list: Array = corridor.get("doors", [])
	for i in 2:
		_fill_door(doors[i], door_list[i] if i < door_list.size() else {}, 3 + i == focus)
	var cost := int(corridor.get("reroll_cost", 0))
	reroll.text = "Relancer les cartes : %d or%s" % [cost, "" if bool(corridor.get("can_reroll", true)) else " (or insuffisant)"]


static func _clear(panel: Control) -> void:
	for c in panel.get_children():
		panel.remove_child(c)
		c.queue_free()


func _fill_card(panel: PanelContainer, data: Dictionary, focused: bool) -> void:
	_clear(panel)
	var style := UiTheme.card_style()
	if focused:
		style.border_color = UiTheme.FOCUS
		style.set_border_width_all(3)
	panel.add_theme_stylebox_override("panel", style)
	var box := VBoxContainer.new()
	panel.add_child(box)
	var tint := card_color(str(data.get("kind", "")))
	box.add_child(UiTheme.label(UiTheme.ITEM_SIZE, tint, str(data.get("name", ""))))
	var body := UiTheme.label(UiTheme.CARD_SIZE, UiTheme.TEXT, str(data.get("text", "")))
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(body)


func _fill_door(portal: DoorPortal, data: Dictionary, focused: bool) -> void:
	_clear(portal)
	var archetype := str(data.get("archetype", ""))
	portal.tint = door_color(archetype)
	portal.focused = focused
	portal.queue_redraw()
	var box := VBoxContainer.new()
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_theme_constant_override("separation", 2)
	portal.add_child(box)
	for spec in [[UiTheme.SMALL_SIZE, UiTheme.FOCUS if focused else UiTheme.DIM, side_text(data)],
			[UiTheme.ITEM_SIZE, portal.tint, archetype_name(archetype)],
			[UiTheme.SMALL_SIZE, UiTheme.TEXT, ARCHETYPE_HINTS.get(archetype, "")]]:
		var l := UiTheme.label(spec[0], spec[1], spec[2])
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		box.add_child(l)
