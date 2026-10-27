extends RefCounted

## Thème commun des menus (lot « présentation des menus », étape 1) : jetons de couleur, de taille et
## d'espacement, et fabriques des styles partagés. Charte : version sobre des jetons néon du lot R17
## (fond `void`, texte `neutral`, sélection `player`, records `gold`, erreur `danger`). Une couleur = un
## rôle : aucune vue de menu n'écrit de couleur en dur, elle prend ici le jeton de son rôle.
## Tailles en unités de la fenêtre de base 1280 × 720 (mise à l'échelle canvas_items) : rien sous 16 px,
## lisible à 2 m d'un écran de salon. Pas de texture ni de police ajoutée : police par défaut de Godot.
## Pas de class_name : charger par preload("res://scripts/ui_theme.gd").

# --- Couleurs -----------------------------------------------------------------------------------
const VOID := Color(0.020, 0.024, 0.059)          # fond du menu
const NIGHT := Color(0.043, 0.063, 0.188)         # bandeau des boutons
const SURFACE := Color(0.063, 0.090, 0.227)       # cartes, pastilles
const LINE := Color(0.141, 0.188, 0.369)          # filets, bords
const TEXT := Color(0.910, 0.941, 1.000)          # texte (neutral R17)
const DIM := Color(0.557, 0.604, 0.753)           # texte secondaire
const DISABLED := Color(0.365, 0.408, 0.549)      # élément désactivé
const FOCUS := Color(0.094, 0.941, 1.000)         # sélection (player R17)
const GOLD := Color(1.000, 0.824, 0.235)          # records, valeur clé
const OK := Color(0.271, 0.878, 0.541)            # appareil prêt
const WARN := Color(1.000, 0.702, 0.278)          # appareil en recherche, batterie basse
const DANGER := Color(1.000, 0.180, 0.298)        # erreur, appareil perdu
const KEYCAP := Color(0.102, 0.137, 0.314)        # fond des touches du bandeau
const KEYCAP_EDGE := Color(0.227, 0.278, 0.502)
## Voile sur la scène 3D derrière le menu : plus dense à gauche (liste), plus léger à droite.
const VEIL_LEFT := Color(0.020, 0.024, 0.059, 0.94)
const VEIL_RIGHT := Color(0.043, 0.063, 0.188, 0.80)

# --- Tailles de police --------------------------------------------------------------------------
const TITLE_SIZE := 40
const ITEM_SIZE := 28
const DETAIL_SIZE := 22
const CARD_SIZE := 22
const HELP_SIZE := 21
const CHIP_SIZE := 18
const SMALL_SIZE := 16

# --- Espacements --------------------------------------------------------------------------------
const MARGIN := 64            # marge gauche et droite de l'écran
const TOP := 36               # haut du titre
const HEADER_H := 84          # titre et ligne d'état, filet compris
const GAP := 16               # écart entre blocs
const ROW_H := 46             # hauteur d'une entrée de liste
const ROW_GAP := 4
const RADIUS := 10
const HELP_H := 64            # bandeau des boutons
const CHIPS_H := 38           # rangée des pastilles d'appareils
const CARD_W := 520           # carte de détail à droite
const ICON := 28              # pictogramme d'une entrée
const LINE_W := 2.2           # trait des pictogrammes


## Style d'une entrée de liste ; `focused` : fond et bord de la sélection, lueur autour.
static func row_style(focused: bool) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.set_corner_radius_all(RADIUS)
	s.content_margin_left = 18
	s.content_margin_right = 18
	s.set_border_width_all(2)
	if focused:
		s.bg_color = Color(FOCUS, 0.14)
		s.border_color = FOCUS
		s.shadow_color = Color(FOCUS, 0.30)
		s.shadow_size = 8
	else:
		s.bg_color = Color(0, 0, 0, 0)
		s.border_color = Color(0, 0, 0, 0)
	return s


## Carte de détail (fiche du parcours, bilan).
static func card_style() -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = Color(SURFACE, 0.88)
	s.border_color = LINE
	s.set_border_width_all(1)
	s.set_corner_radius_all(14)
	s.set_content_margin_all(22)
	return s


## Pastille d'appareil (bord de la couleur du niveau quand `edge` n'est pas transparent).
static func chip_style(edge := Color(0, 0, 0, 0)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = Color(SURFACE, 0.85)
	s.border_color = edge if edge.a > 0.0 else LINE
	s.set_border_width_all(1)
	s.set_corner_radius_all(19)
	s.content_margin_left = 12
	s.content_margin_right = 14
	return s


## Touche du bandeau des boutons ; `accent` : bord et lettre en couleur de sélection (A, valider).
static func keycap_style(accent: bool) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = KEYCAP
	s.border_color = FOCUS if accent else KEYCAP_EDGE
	s.set_border_width_all(2)
	s.set_corner_radius_all(9)
	s.content_margin_left = 10
	s.content_margin_right = 10
	return s


## Fond du bandeau des boutons.
static func help_style() -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = Color(NIGHT, 0.96)
	s.border_color = LINE
	s.border_width_top = 1
	s.content_margin_left = MARGIN
	s.content_margin_right = MARGIN
	return s


## Étiquette à la taille et à la couleur données.
static func label(size: int, color := TEXT, text := "") -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.text = text
	return l
