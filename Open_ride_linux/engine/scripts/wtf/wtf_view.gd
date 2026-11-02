extends Control

## Habillage du mode « What the fuck » dans le HUD (série WTF, lot WTF7), d'après les maquettes validées
## le 30 octobre : style cartoon (aplats, bord encre épais, ombre portée décalée).
## - bandeau du gag centré sous le panneau central du HUD : nom, temps restant, points ;
## - carte du gag à gauche, sous l'indicateur du vent : titre, valeur, jauge, note (cachée quand le gag n'en a
##   pas) ; hors du centre de l'image pour laisser voir le gag (essai PC 7cn du 31 octobre) ;
## - invite d'un bouton (« Z : NON MERCI, CHEF ! ») juste sous le bandeau, le temps de la révélation (au
##   milieu de l'écran, elle cachait le cycliste et le chef en tandem) ;
## - Katamari et horloge à gauche, sous la carte du gag ; les cartes s'empilent sans trou. Pendant un gag
##   à carte, Katamari et horloge se réduisent à une seule ligne pour que la pile ne descende pas sur la route
##   (pile bornée à STACK_MAX_FRAC de la hauteur de l'écran de base 1280 × 720, vérifiée par le test).
## Ne décide rien : affiche la sortie de wtf_hud_model.gd (update_view). Enfant du HUD : caché avec lui
## quand un menu plein écran est ouvert. Pas de class_name : preload("res://scripts/wtf/wtf_view.gd").

const WtfHudModel := preload("res://scripts/wtf/wtf_hud_model.gd")

const INK := WtfHudModel.INK
const BORDER := 4
const RADIUS := 18
const SHADOW := 5
const BANNER_TOP := 125.0     # sous le panneau central du HUD (TOP_MARGIN 20 + CENTER_H 89 + marge)
const BANNER_W := 560.0
const SIDE_LEFT := 20.0
const SIDE_TOP := 330.0       # sous le vent et l'abri du panneau de gauche
const SIDE_GAP := 12.0
const SIDE_W := 243.0         # largeur du panneau de gauche (hud_view.gd COLUMN_W)
const TITLE_SIZE := 26
const TEXT_SIZE := 16
const VALUE_SIZE := 22
const NOTE_SIZE := 13
const BAR_H := 10
const PROMPT_TOP := BANNER_TOP + 64.0
const STACK_MAX_FRAC := 0.75

var _view: Dictionary = {}
var _stack_bottom := 0.0
var _banner: PanelContainer
var _banner_text: Label
var _banner_time: Label
var _banner_points: Label
var _card: PanelContainer
var _card_title: Label
var _card_value: Label
var _card_bar: ProgressBar
var _card_note: Label
var _prompt: PanelContainer
var _prompt_text: Label
var _kata: PanelContainer
var _kata_title: Label
var _kata_line: Label
var _kata_bar: ProgressBar
var _clock: PanelContainer
var _clock_text: Label


func _init() -> void:
	name = "WtfView"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build()


func _build() -> void:
	_banner = _panel(WtfHudModel.YELLOW)
	_banner.anchor_left = 0.5
	_banner.anchor_right = 0.5
	_banner.offset_left = -BANNER_W / 2.0
	_banner.offset_right = BANNER_W / 2.0
	_banner.offset_top = BANNER_TOP
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	_banner.add_child(row)
	_banner_text = _label(TITLE_SIZE, INK)
	_banner_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_banner_text.clip_text = true
	_banner_time = _label(TEXT_SIZE, INK)
	_banner_points = _label(TEXT_SIZE, INK)
	for l in [_banner_text, _banner_time, _banner_points]:
		row.add_child(l)

	_card = _panel(Color.WHITE)
	_card.offset_left = SIDE_LEFT
	_card.offset_right = SIDE_LEFT + SIDE_W
	_card.offset_top = SIDE_TOP
	var col := _vbox(_card)
	_card_title = _label(TEXT_SIZE, INK)
	_card_value = _label(VALUE_SIZE, INK)
	_card_bar = _bar(WtfHudModel.PINK)
	_card_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_card_note = _label(NOTE_SIZE, INK)
	_card_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for c in [_card_title, _card_value, _card_bar, _card_note]:
		col.add_child(c)

	_prompt = _panel(WtfHudModel.PINK)
	_prompt.anchor_left = 0.5
	_prompt.anchor_right = 0.5
	_prompt.offset_left = -BANNER_W / 2.0
	_prompt.offset_right = BANNER_W / 2.0
	_prompt.offset_top = PROMPT_TOP
	_prompt_text = _label(TEXT_SIZE + 4, Color.WHITE)
	_prompt_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_prompt.add_child(_prompt_text)

	_kata = _panel(Color.WHITE)
	_kata.offset_left = SIDE_LEFT
	_kata.offset_right = SIDE_LEFT + SIDE_W
	var kcol := _vbox(_kata)
	_kata_title = _label(TEXT_SIZE, INK)
	_kata_line = _label(NOTE_SIZE, INK)
	_kata_line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_kata_bar = _bar(WtfHudModel.GREEN)
	for c in [_kata_title, _kata_line, _kata_bar]:
		kcol.add_child(c)

	_clock = _panel(WtfHudModel.CYAN)
	_clock.offset_left = SIDE_LEFT
	_clock.offset_right = SIDE_LEFT + SIDE_W
	_clock_text = _label(TEXT_SIZE, INK)
	_clock.add_child(_clock_text)

	for p in [_banner, _card, _prompt, _kata, _clock]:
		add_child(p)


## `view` : sortie de wtf_hud_model.gd view().
func update_view(view: Dictionary) -> void:
	_view = view
	visible = bool(view.get("visible", false))
	if not visible:
		return
	var b: Dictionary = view.get("banner", {})
	_banner.visible = not b.is_empty()
	if _banner.visible:
		_set_fill(_banner, b.get("color", WtfHudModel.YELLOW))
		_banner_text.text = str(b.get("text", ""))
		_banner_time.text = str(b.get("time", ""))
		_banner_points.text = str(b.get("points", ""))
	var c: Dictionary = view.get("card", {})
	_card.visible = not c.is_empty()
	if _card.visible:
		_card_title.text = str(c.get("title", ""))
		_card_value.text = str(c.get("value", ""))
		var bar := float(c.get("bar", -1.0))
		_card_bar.visible = bar >= 0.0
		_card_bar.value = clampf(bar, 0.0, 1.0)
		_card_note.text = str(c.get("note", ""))
		_card_note.visible = _card_note.text != ""
	var p: Dictionary = view.get("prompt", {})
	_prompt.visible = not p.is_empty()
	if _prompt.visible:
		_prompt_text.text = "%s : %s  (%s)" % [p.get("key", ""), p.get("text", ""), p.get("time", "")]
	var compact := _card.visible   # pendant un gag à carte : Katamari et horloge sur une ligne chacun
	var k: Dictionary = view.get("kata", {})
	_kata.visible = not k.is_empty()
	if _kata.visible:
		_kata_title.text = str(k.get("title", ""))
		_kata_line.text = str(k.get("line", ""))
		_kata_line.visible = not compact
		_kata_bar.visible = not compact
		_kata_bar.value = float(k.get("bar", 0.0))
	var h: Dictionary = view.get("clock", {})
	var clock_text := ""
	if not h.is_empty():
		var fish := bool(h.get("fish", false))
		clock_text = str(h.get("text", "")) + (("  · poissons !" if compact else "  · poissons volants !") if fish else "")
	# Gag à carte avec le Katamari : l'heure rejoint la ligne du Katamari, une carte de moins à gauche.
	var merged := compact and _kata.visible and clock_text != ""
	if merged:
		_kata_title.text += "  · " + clock_text
	_clock.visible = clock_text != "" and not merged
	_clock_text.text = clock_text
	var y := SIDE_TOP
	for panel in [_card, _kata, _clock]:
		if panel.visible:
			panel.offset_top = y
			y += panel.get_combined_minimum_size().y + SIDE_GAP
	_stack_bottom = y - SIDE_GAP


## Pour les tests graphiques et le banc des menus : textes affichés.
func test_info() -> Dictionary:
	return {"visible": visible, "banner": _banner_text.text if visible and _banner.visible else "",
		"card": _card_title.text if visible and _card.visible else "",
		"prompt": _prompt_text.text if visible and _prompt.visible else "",
		"kata": _kata_title.text if visible and _kata.visible else "",
		"clock": _clock_text.text if visible and _clock.visible else "",
		"card_top": _card.offset_top, "kata_top": _kata.offset_top, "clock_top": _clock.offset_top,
		"stack_bottom": _stack_bottom, "prompt_top": _prompt.offset_top, "kata_compact": not _kata_bar.visible}


static func _style(fill: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = fill
	s.border_color = INK
	s.set_border_width_all(BORDER)
	s.set_corner_radius_all(RADIUS)
	s.shadow_color = INK
	s.shadow_size = 1   # ombre nette décalée (style cartoon des maquettes)
	s.shadow_offset = Vector2(SHADOW, SHADOW)
	s.content_margin_left = 16
	s.content_margin_right = 16
	s.content_margin_top = 8
	s.content_margin_bottom = 8
	return s


func _panel(fill: Color) -> PanelContainer:
	var p := PanelContainer.new()
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_theme_stylebox_override("panel", _style(fill))
	p.visible = false
	return p


func _set_fill(p: PanelContainer, fill: Color) -> void:
	var s := p.get_theme_stylebox("panel") as StyleBoxFlat
	if s != null and s.bg_color != fill:
		s.bg_color = fill


static func _vbox(parent: Control) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	parent.add_child(v)
	return v


static func _label(size: int, color: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


static func _bar(fill: Color) -> ProgressBar:
	var b := ProgressBar.new()
	b.min_value = 0.0
	b.max_value = 1.0
	b.step = 0.0
	b.show_percentage = false
	b.custom_minimum_size = Vector2(0, BAR_H)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.9, 0.9, 0.92)
	bg.border_color = INK
	bg.set_border_width_all(2)
	bg.set_corner_radius_all(7)
	var fg := StyleBoxFlat.new()
	fg.bg_color = fill
	fg.border_color = INK
	fg.set_border_width_all(2)
	fg.set_corner_radius_all(7)
	b.add_theme_stylebox_override("background", bg)
	b.add_theme_stylebox_override("fill", fg)
	return b
