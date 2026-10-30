extends Node3D

## Vue du HUD diégétique du Cyber-Rogue (lot R11) : hologramme au-dessus de la roue arrière (vitesse engagée,
## watts en % de FTP, cadence, posture, jauges de W'bal et de l'ennemi, écart au Firewall), deux arcs au sol
## (bouclier à gauche, adrénaline à droite) et, en surimpression, le bandeau « Salle manquée » avec le
## grésillement rouge. Ne calcule rien : elle dessine les valeurs de rogue_hud_model.gd. Primitives Godot
## seulement, couleurs de la charte R17 (neon_palette.gd).

const Palette := preload("res://scripts/rogue/neon_palette.gd")
const Materials := preload("res://scripts/rogue/neon_materials.gd")

const HOLO_UP_M := 1.6              # bas de l'hologramme, au-dessus de la roue
const HOLO_BACK_M := 0.9
const GAUGES_GAP_M := 0.08           # écart entre le bas de l'hologramme et le haut des jauges
const ARC_RADIUS_M := 1.5
const ARC_WIDTH_M := 0.12
const ARC_SEGMENTS := 24
const ARC_REBUILD_STEP := 0.02       # l'arc n'est reconstruit que si la jauge bouge d'au moins 2 %
const BANNER_S := 3.0
const GLITCH_S := 0.5
const BANNER_TEXT := "Salle manquée −10 or"

var preset := "low"
var adapted := false
var holo: Label3D
var gauges: Label3D
var shield_arc: MeshInstance3D
var adrenaline_arc: MeshInstance3D
var banner: Label
var glitch_rect: ColorRect
var banner_left_s := 0.0
var glitch_left_s := 0.0
var _layer: CanvasLayer
var _shield_drawn := -1.0
var _adrenaline_drawn := -1.0


func _ready() -> void:
	# L'hologramme pousse vers le haut depuis HOLO_UP_M, les jauges vers le bas : deux blocs qui ne se
	# recouvrent jamais, quelle que soit la longueur des textes (constat du banc visuel X41).
	holo = _label(56, 0.009)
	holo.name = "Hologram"
	holo.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	add_child(holo)
	gauges = _label(36, 0.007)
	gauges.name = "Gauges"
	gauges.vertical_alignment = VERTICAL_ALIGNMENT_TOP
	add_child(gauges)
	shield_arc = MeshInstance3D.new()
	shield_arc.name = "ShieldArc"
	add_child(shield_arc)
	adrenaline_arc = MeshInstance3D.new()
	adrenaline_arc.name = "AdrenalineArc"
	add_child(adrenaline_arc)
	_layer = CanvasLayer.new()
	_layer.layer = 5
	add_child(_layer)
	glitch_rect = ColorRect.new()
	glitch_rect.color = Palette.color("danger", adapted)
	glitch_rect.color.a = 0.0
	glitch_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	glitch_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_layer.add_child(glitch_rect)
	banner = Label.new()
	banner.text = BANNER_TEXT
	banner.visible = false
	banner.add_theme_font_size_override("font_size", 36)
	banner.add_theme_color_override("font_color", Palette.color("danger", adapted))
	banner.set_anchors_preset(Control.PRESET_CENTER_TOP)
	banner.position = Vector2(0.0, 80.0)
	banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_layer.add_child(banner)
	set_style(preset, adapted)


func _label(size: int, pixel: float) -> Label3D:
	var l := Label3D.new()
	l.font_size = size
	l.pixel_size = pixel
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.outline_size = 12
	l.outline_modulate = Palette.color("void", false)
	return l


func set_style(new_preset: String, new_adapted: bool) -> void:
	preset = new_preset
	adapted = new_adapted
	if shield_arc == null:
		return
	shield_arc.material_override = Materials.edge("parry", 2.0, preset, adapted)
	adrenaline_arc.material_override = Materials.edge("energy", 2.0, preset, adapted)
	_shield_drawn = -1.0
	_adrenaline_drawn = -1.0


## Demi-cercle plat au sol rempli sur la fraction `frac` ; `side` vaut −1 (gauche) ou 1 (droite).
static func arc_mesh(frac: float, side: int) -> ArrayMesh:
	var mesh := ArrayMesh.new()
	frac = clampf(frac, 0.0, 1.0)
	if frac <= 0.0:
		return mesh
	var n := maxi(int(ceil(ARC_SEGMENTS * frac)), 1)
	var verts := PackedVector3Array()
	var idx := PackedInt32Array()
	for i in n + 1:
		var a := PI * 0.5 * frac * float(i) / float(n)   # 0 = devant, jusqu'à 90° vers l'arrière
		var dir := Vector3(sin(a) * side, 0.0, -cos(a))
		verts.append(dir * (ARC_RADIUS_M + ARC_WIDTH_M * 0.5))
		verts.append(dir * (ARC_RADIUS_M - ARC_WIDTH_M * 0.5))
	for i in n:
		var b := i * 2
		idx.append_array(PackedInt32Array([b, b + 1, b + 2, b + 1, b + 3, b + 2]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_INDEX] = idx
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


## Place le HUD autour du vélo (position monde de la roue arrière) et affiche les valeurs du modèle.
func apply(values: Dictionary, bike_pos: Vector3, delta: float) -> void:
	if holo == null:
		return
	visible = bool(values.get("active", false))
	if not visible:
		return
	position = bike_pos
	# Couloir : l'écran des cartes et des portes occupe le centre, l'hologramme et les jauges se retirent
	# (ils transparaissaient sous les cartes) ; les arcs au sol restent.
	var choosing: bool = not (values.get("corridor", {}) as Dictionary).is_empty()
	holo.visible = not choosing
	gauges.visible = not choosing
	holo.position = Vector3(0.0, HOLO_UP_M, HOLO_BACK_M)
	gauges.position = Vector3(0.0, HOLO_UP_M - GAUGES_GAP_M, HOLO_BACK_M)
	holo.text = "%s\n%s · %s rpm" % [values["gear_text"], values["power_pct_text"], values["cadence_text"]]
	holo.modulate = Palette.color(String(values["posture_token"]), adapted)
	var wbal := "W' %d %%" % int(roundf(values["wbal_pct"]))
	var fw := "FW %d m" % int(roundf(values["firewall_gap_m"]))
	var enemy := "  ·  Ennemi %d %%" % int(roundf(values["enemy_pct"])) if values["has_enemy"] else ""
	gauges.text = "%s  ·  %s%s" % [wbal, fw, enemy]
	var warn: bool = values["wbal_low"] or values["firewall_danger"]
	gauges.modulate = Palette.color("danger" if warn else "neutral", adapted)
	_set_arc(shield_arc, float(values["shield_frac"]), -1, true)
	_set_arc(adrenaline_arc, float(values["adrenaline_frac"]), 1, false)
	_tick(delta)


func _set_arc(node: MeshInstance3D, frac: float, side: int, is_shield: bool) -> void:
	var drawn := _shield_drawn if is_shield else _adrenaline_drawn
	var at_end := frac != drawn and (frac <= 0.0 or frac >= 1.0)
	if drawn >= 0.0 and absf(frac - drawn) < ARC_REBUILD_STEP and not at_end:
		return
	node.mesh = arc_mesh(frac, side)
	if is_shield:
		_shield_drawn = frac
	else:
		_adrenaline_drawn = frac


## Événements à montrer : « room_skipped » affiche le bandeau 3 s et grésille en rouge 0,5 s.
func show_events(events: Array) -> void:
	if banner == null:
		return
	if "room_skipped" in events:
		banner_left_s = BANNER_S
		glitch_left_s = GLITCH_S
		banner.visible = true


func _tick(delta: float) -> void:
	banner_left_s = maxf(banner_left_s - delta, 0.0)
	glitch_left_s = maxf(glitch_left_s - delta, 0.0)
	banner.visible = banner_left_s > 0.0
	# Un seul éclair rouge de 0,25 s dans la demi-seconde : bien sous le plafond de 3 éclairs par seconde.
	var lit := glitch_left_s > 0.0 and int(glitch_left_s * 4.0) % 2 == 1
	glitch_rect.color.a = 0.35 if lit else 0.0
