extends VBoxContainer

## Collection de cartes au menu (série BC, lot BC5) : album par familles, carte agrandie, première
## ouverture, selon les maquettes validées du lot BC3. Ne décide rien : dessine la fiche `collection` de
## menu_flow.gd (collection_view_model.gd : album(), card_view(), first_view()). Placée par menu_view.gd
## au-dessus de la liste des éléments (cachée sur l'album : les vignettes sont les éléments).
## Visuels : engine/assets/collection/<visual>.png (lot BC4), lus à l'exécution ; un visuel absent est
## remplacé par un disque et un pictogramme. Couleurs et tailles du thème commun (ui_theme.gd).
## Pas de class_name : charger par preload("res://scripts/collection_view.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const UiIcons := preload("res://scripts/ui_icons.gd")

const VISUALS_DIR := "res://assets/collection/"
const THUMB := 84             # vignette de l'album
const THUMB_GAP := 14
const BIG := 220              # visuel de la carte agrandie
const CARD_W := 300
const CARD_H := 380
const FIRST_VISUAL := 120     # visuels de la première ouverture
const FIRST_OVERLAP := -15    # ils se chevauchent un peu
const RING_W := 4.0
const ANNOUNCE_VISUAL := 96   # visuel de l'annonce au bilan (lot BC6), à gauche du bilan
const ANNOUNCE_TEXT_W := 260
const RARITY_COLORS := {"commune": UiTheme.RARITY_COMMUNE, "rare": UiTheme.RARITY_RARE,
	"epique": UiTheme.RARITY_EPIQUE, "legendaire": UiTheme.RARITY_LEGENDAIRE}

## Clic sur une vignette de l'album (identifiant d'élément du menu, « c:<id> »).
signal item_clicked(item_id: String)

static var _textures := {}
var _shown_key := ""


func _init() -> void:
	name = "CollectionView"
	visible = false
	add_theme_constant_override("separation", UiTheme.GAP)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


## Visuel `name` (null s'il manque : le dessin le remplace).
static func texture(visual: String) -> Texture2D:
	if visual == "":
		return null
	if not _textures.has(visual):
		var path := ProjectSettings.globalize_path(VISUALS_DIR + visual + ".png")
		var img: Image = Image.load_from_file(path) if FileAccess.file_exists(path) else null
		_textures[visual] = ImageTexture.create_from_image(img) if img != null else null
	return _textures[visual]


static func rarity_color(rarity: String) -> Color:
	return RARITY_COLORS.get(rarity, UiTheme.LINE)


## Affiche la fiche (album, carte ou première ouverture) ; {} : cachée. Rien n'est reconstruit tant que la
## fiche ne change pas (le menu est rafraîchi à chaque trame).
func update_display(view: Dictionary) -> void:
	visible = not view.is_empty()
	var key := JSON.stringify(view)
	if key == _shown_key:
		return
	_shown_key = key
	for c in get_children():
		remove_child(c)
		c.queue_free()
	match str(view.get("kind", "")):
		"album":
			_build_album(view)
		"card":
			_build_card(view)
		"first":
			_build_first(view)
		"announce":
			_build_announce(view)


## Textes affichés, séparés par « | », vignette choisie entre crochets (tests).
func view_text() -> String:
	var parts: Array[String] = []
	_collect_text(self, parts)
	return " | ".join(parts)


func _collect_text(node: Node, parts: Array[String]) -> void:
	for c in node.get_children():
		if c is Label and (c as Label).text != "":
			parts.append((c as Label).text)
		elif c.has_meta("item_id"):
			var id := str(c.get_meta("item_id"))
			parts.append(("[%s]" % id) if c.get_meta("focused", false) else id)
		_collect_text(c, parts)


## Vignettes affichées (tests, banc des menus) : identifiant, focus et rectangle (repère du canevas).
func test_rows() -> Array:
	var out: Array = []
	_collect_rows(self, out)
	return out


func _collect_rows(node: Node, out: Array) -> void:
	for c in node.get_children():
		if c.has_meta("item_id"):
			out.append({"id": str(c.get_meta("item_id")), "text": str(c.get_meta("item_id")),
				"focused": bool(c.get_meta("focused", false)), "rect": (c as Control).get_global_rect()})
		_collect_rows(c, out)


## Rectangle (repère du canevas) de la vignette `item_id` ; vide si elle n'est pas affichée.
func item_rect(item_id: String) -> Rect2:
	var found := _find(self, item_id)
	return found.get_global_rect() if found != null else Rect2()


func _find(node: Node, item_id: String) -> Control:
	for c in node.get_children():
		if c.has_meta("item_id") and str(c.get_meta("item_id")) == item_id:
			return c
		var deeper := _find(c, item_id)
		if deeper != null:
			return deeper
	return null


# --- Album ---------------------------------------------------------------------------------------

func _build_album(view: Dictionary) -> void:
	for fam in view.get("families", []):
		var row := VBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(row)
		var head := HBoxContainer.new()
		head.add_theme_constant_override("separation", 10)
		head.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(head)
		head.add_child(UiTheme.label(UiTheme.DETAIL_SIZE, UiTheme.TEXT, str(fam.get("name", ""))))
		head.add_child(UiTheme.label(UiTheme.DETAIL_SIZE, UiTheme.DIM,
			"%d / %d" % [int(fam.get("earned", 0)), fam.get("cards", []).size()]))
		var thumbs := HBoxContainer.new()
		thumbs.add_theme_constant_override("separation", THUMB_GAP)
		thumbs.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(thumbs)
		for t in fam.get("cards", []):
			thumbs.add_child(_thumb(t))
	var more: Array[String] = []
	if int(view.get("above", 0)) > 0:
		more.append("▲ %d famille%s plus haut" % [int(view["above"]), "s" if int(view["above"]) > 1 else ""])
	if int(view.get("below", 0)) > 0:
		more.append("▼ %d famille%s plus bas" % [int(view["below"]), "s" if int(view["below"]) > 1 else ""])
	if not more.is_empty():
		add_child(UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, " · ".join(more)))


func _thumb(t: Dictionary) -> Control:
	var c := Control.new()
	c.custom_minimum_size = Vector2(THUMB, THUMB)
	c.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	c.mouse_filter = Control.MOUSE_FILTER_PASS   # clic droit et molette remontent au menu
	c.set_meta("item_id", str(t.get("id", "")))
	c.set_meta("focused", bool(t.get("focused", false)))
	var visual := str(t.get("visual", ""))
	var rarity := str(t.get("rarity", ""))
	var on := bool(t.get("earned", false))
	var is_new := bool(t.get("new", false))
	var focused := bool(t.get("focused", false))
	c.draw.connect(func() -> void:
		_draw_badge(c, Rect2(Vector2.ZERO, c.size), visual, rarity, on)
		var mid := c.size / 2.0
		if focused:
			c.draw_arc(mid, c.size.x / 2.0 + 6.0, 0.0, TAU, 64, UiTheme.FOCUS, 3.0, true)
		if is_new:
			c.draw_circle(Vector2(c.size.x - 8.0, 8.0), 7.0, UiTheme.CARD_NEW))
	c.gui_input.connect(func(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			c.accept_event()
			item_clicked.emit(str(c.get_meta("item_id"))))
	return c


## Visuel rond dans son anneau : couleur de la rareté si gagnée, silhouette sombre sinon.
static func _draw_badge(ci: CanvasItem, rect: Rect2, visual: String, rarity: String, on: bool) -> void:
	var mid := rect.get_center()
	var r := minf(rect.size.x, rect.size.y) / 2.0
	ci.draw_circle(mid, r, UiTheme.SURFACE)
	var tex := texture(visual)
	if tex != null:
		ci.draw_texture_rect(tex, rect, false, UiTheme.INK if on else UiTheme.CARD_LOCKED)
	else:
		var s := r * 0.9
		UiIcons.draw(ci, "trophy", Rect2(mid - Vector2(s, s) / 2.0, Vector2(s, s)),
			rarity_color(rarity) if on else UiTheme.DISABLED, UiTheme.LINE_W)
	ci.draw_arc(mid, r - RING_W / 2.0, 0.0, TAU, 64, rarity_color(rarity) if on else UiTheme.LINE, RING_W, true)


# --- Carte agrandie --------------------------------------------------------------------------------

func _build_card(view: Dictionary) -> void:
	var box := HBoxContainer.new()
	box.add_theme_constant_override("separation", UiTheme.GAP * 3)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(box)
	var on := bool(view.get("earned", false))
	var rarity := str(view.get("rarity", ""))
	var frame := PanelContainer.new()
	frame.custom_minimum_size = Vector2(CARD_W, CARD_H)
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style: StyleBoxFlat = UiTheme.card_style()
	style.border_color = rarity_color(rarity) if on else UiTheme.LINE
	style.set_border_width_all(6)
	style.set_corner_radius_all(20)
	frame.add_theme_stylebox_override("panel", style)
	box.add_child(frame)
	var inner := VBoxContainer.new()
	inner.add_theme_constant_override("separation", 8)
	inner.alignment = BoxContainer.ALIGNMENT_CENTER
	inner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(inner)
	var visual := str(view.get("visual", ""))
	var art := Control.new()
	art.custom_minimum_size = Vector2(BIG, BIG)
	art.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.draw.connect(func() -> void: _draw_badge(art, Rect2(Vector2.ZERO, art.size), visual, rarity, on))
	inner.add_child(art)
	var t := UiTheme.label(UiTheme.ITEM_SIZE, UiTheme.TEXT, str(view.get("title", "")))
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inner.add_child(t)
	var rn := UiTheme.label(UiTheme.DETAIL_SIZE, rarity_color(rarity) if on else UiTheme.DIM,
		str(view.get("rarity_name", "")))
	rn.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	inner.add_child(rn)
	var num := UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, str(view.get("number", "")))
	num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	inner.add_child(num)
	var info := VBoxContainer.new()
	info.add_theme_constant_override("separation", 12)
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(info)
	var amb := UiTheme.label(UiTheme.ITEM_SIZE, UiTheme.TEXT, "« %s »" % str(view.get("text", "")))
	amb.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	info.add_child(amb)
	for line in view.get("lines", []):
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 10)
		h.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if str(line[0]) != "":
			h.add_child(UiTheme.label(UiTheme.DETAIL_SIZE, UiTheme.DIM, str(line[0])))
		h.add_child(UiTheme.label(UiTheme.DETAIL_SIZE, UiTheme.TEXT, str(line[1])))
		info.add_child(h)
	var fill := float(view.get("bar", -1.0))
	if fill >= 0.0:
		var bar := Control.new()
		bar.custom_minimum_size = Vector2(UiTheme.CARD_W, 14)
		bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
		bar.draw.connect(func() -> void:
			bar.draw_rect(Rect2(Vector2.ZERO, bar.size), UiTheme.LINE)
			bar.draw_rect(Rect2(Vector2.ZERO, Vector2(bar.size.x * fill, bar.size.y)), UiTheme.FOCUS))
		info.add_child(bar)
	if str(view.get("note", "")) != "":
		var note := UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, str(view["note"]))
		note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		info.add_child(note)


# --- Annonce au bilan (lot BC6) ------------------------------------------------------------------

func _build_announce(view: Dictionary) -> void:
	var rarity := str(view.get("rarity", ""))
	var frame := PanelContainer.new()
	frame.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style: StyleBoxFlat = UiTheme.card_style()
	style.border_color = rarity_color(rarity)
	style.set_border_width_all(3)
	frame.add_theme_stylebox_override("panel", style)
	add_child(frame)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", UiTheme.GAP)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(row)
	var visual := str(view.get("visual", ""))
	var art := Control.new()
	art.custom_minimum_size = Vector2(ANNOUNCE_VISUAL, ANNOUNCE_VISUAL)
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.draw.connect(func() -> void: _draw_badge(art, Rect2(Vector2.ZERO, art.size), visual, rarity, true))
	row.add_child(art)
	var texts := VBoxContainer.new()
	texts.alignment = BoxContainer.ALIGNMENT_CENTER
	texts.add_theme_constant_override("separation", 4)
	texts.mouse_filter = Control.MOUSE_FILTER_IGNORE
	texts.custom_minimum_size.x = ANNOUNCE_TEXT_W
	row.add_child(texts)
	texts.add_child(UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.CARD_NEW, "NOUVELLE CARTE"))
	var t := UiTheme.label(UiTheme.DETAIL_SIZE, UiTheme.TEXT, str(view.get("title", "")))
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	texts.add_child(t)
	texts.add_child(UiTheme.label(UiTheme.DETAIL_SIZE, rarity_color(rarity), str(view.get("rarity_name", ""))))
	if str(view.get("others", "")) != "":
		texts.add_child(UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, str(view["others"])))


# --- Première ouverture ----------------------------------------------------------------------------

func _build_first(view: Dictionary) -> void:
	var visuals := HBoxContainer.new()
	visuals.alignment = BoxContainer.ALIGNMENT_CENTER
	visuals.add_theme_constant_override("separation", FIRST_OVERLAP)
	visuals.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(visuals)
	for v in view.get("visuals", []):
		var art := Control.new()
		art.custom_minimum_size = Vector2(FIRST_VISUAL, FIRST_VISUAL)
		art.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var visual := str(v.get("visual", ""))
		var rarity := str(v.get("rarity", ""))
		art.draw.connect(func() -> void: _draw_badge(art, Rect2(Vector2.ZERO, art.size), visual, rarity, true))
		visuals.add_child(art)
	var h := UiTheme.label(UiTheme.TITLE_SIZE, UiTheme.TEXT, str(view.get("headline", "")))
	h.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(h)
	var t := UiTheme.label(UiTheme.DETAIL_SIZE, UiTheme.DIM, str(view.get("text", "")))
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(t)
