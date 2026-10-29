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
## Bandeau de l'écran de séance (banner.gd) : alerte (core perdu, erreur) en rouge, information (rappel
## des boutons, consigne, niveau gagné) sur le fond des panneaux du HUD avec un liseré de sélection.
const BANNER_ALERT := Color(0.6, 0.1, 0.05, 0.85)
const BANNER_INFO_BORDER := Color(0.094, 0.941, 1.000, 0.6)
const KEYCAP := Color(0.102, 0.137, 0.314)        # fond des touches du bandeau
const KEYCAP_EDGE := Color(0.227, 0.278, 0.502)
## Voile sur la scène 3D derrière le menu : plus dense à gauche (liste), plus léger à droite.
const VEIL_LEFT := Color(0.020, 0.024, 0.059, 0.94)
const VEIL_RIGHT := Color(0.043, 0.063, 0.188, 0.80)

# --- Couleurs des données du HUD, des courbes et du globe (étape 4) ----------------------------
## Une couleur par rôle de donnée ; les vues du HUD, des courbes et du globe écrivent `UiTheme.NOM`,
## jamais de `Color(` en dur. `DATA` liste le tout (test_menu_style.gd).
# Pente, vent, maillots, bonus et jauges du HUD
const GRADE_DESCENT := Color(0.25, 0.6, 0.9, 0.85)
const GRADE_FLAT := Color(0.25, 0.75, 0.3, 0.85)
const GRADE_CLIMB := Color(0.95, 0.75, 0.2, 0.85)
const GRADE_STEEP := Color(0.95, 0.45, 0.1, 0.85)
const GRADE_WALL := Color(0.85, 0.15, 0.15, 0.85)
# Texte des classes de pente (valeur du HUD, carrefours) : teintes des barres éclaircies et opaques,
# au moins 4,5:1 sur un panneau au-dessus d'un ciel clair (lot X22) ; encore éclaircies le 28/10 quand
# les panneaux sont passés à 60 % d'opacité.
const GRADE_TEXT_DESCENT := Color(0.70, 0.88, 1.00)
const GRADE_TEXT_FLAT := Color(0.62, 0.95, 0.66)
const GRADE_TEXT_CLIMB := Color(1.00, 0.89, 0.48)
const GRADE_TEXT_STEEP := Color(1.00, 0.77, 0.54)
const GRADE_TEXT_WALL := Color(1.00, 0.77, 0.75)
const WIND_GOOD := Color(0.15, 0.62, 0.25, 0.95)
const WIND_BAD := Color(0.8, 0.18, 0.12, 0.95)
const WIND_NEUTRAL := Color(0.45, 0.48, 0.52, 0.95)
const PALE := Color(0.85, 0.9, 0.95)
const WIND_BAR_OFF := Color(0.85, 0.9, 0.95, 0.18)
const DRAFT := Color(0.15, 0.42, 0.75, 0.95)
const SEGMENT_GOOD := Color(0.35, 0.9, 0.45)
const SEGMENT_BAD := Color(0.95, 0.4, 0.35)
const SEGMENT_NEUTRAL := Color(0.92, 0.94, 0.96)
const BONUS := Color(0.62, 0.32, 0.92, 0.95)
const JERSEY_SPRINT := Color(0.2, 0.75, 0.3)
const JERSEY_KOM := Color(0.97, 0.97, 0.97)
const KOM_DOT := Color(0.85, 0.1, 0.1)
const WBAL := Color(0.35, 0.8, 0.95)
const TRACK := Color(1, 1, 1, 0.15)
const TRACK_SOFT := Color(1, 1, 1, 0.1)
const TRACK_FAINT := Color(1, 1, 1, 0.12)
const HUD_DIM := Color(0.75, 0.8, 0.85)
const PANEL_BG := Color(0.05, 0.07, 0.1, 0.6)   # panneaux du HUD : 10 % plus transparents que 0,7 (28/10)
## Fond des graphiques (courbes de la séance, histogramme ERG, profil d'altitude) : léger, pour voir la
## route derrière ; les traits et les textes posés dessus portent leur propre contour (OUTLINE).
const CHART_BG := Color(0.04, 0.06, 0.08, 0.3)
const SHADOW_LINE := Color(0, 0, 0, 0.6)
const OUTLINE := Color(0, 0, 0, 0.8)
# Zones de Coggan (Z1 à Z7, seuils de erg_view.gd) et bloc sans zone connue (FTP inconnue, case vide)
const ZONE_1 := Color(0.55, 0.57, 0.6)
const ZONE_2 := Color(0.25, 0.55, 0.95)
const ZONE_3 := Color(0.3, 0.75, 0.35)
const ZONE_4 := Color(0.95, 0.8, 0.2)
const ZONE_5 := Color(0.95, 0.5, 0.15)
const ZONE_6 := Color(0.9, 0.2, 0.15)
const ZONE_7 := Color(0.65, 0.25, 0.8)
const NEUTRAL_BLOCK := Color(0.4, 0.42, 0.45)
# Courbes de la séance (puissance, fréquence cardiaque, cadence)
const POWER := Color(1, 1, 1)
const HEART_RATE := Color(0.95, 0.25, 0.25)
const CADENCE := Color(0.55, 0.8, 1)
const GRID := Color(1, 1, 1, 0.16)
const CHART_TEXT := Color(0.8, 0.84, 0.88)
# Carrefour (junction_view.gd)
const PICK := Color(1, 0.85, 0.25)
const JUNCTION_DEFAULT := Color(0.75, 0.85, 1)
const JUNCTION_ARROW := Color(0.95, 0.97, 1)
const ATTRIBUTION := Color(1, 1, 1, 0.55)
const JUNCTION_TILE := Color(1, 1, 1, 0.06)
const JUNCTION_DIM := Color(1, 1, 1, 0.4)
# Globe et menu Monde ouvert (world_menu_view.gd)
const GLOBE_BG := Color(0.03, 0.05, 0.09, 0.96)
const GLOBE_TEXT := Color(0.92, 0.95, 1)
const GLOBE_DIM := Color(0.62, 0.7, 0.8)
const COAST := Color(0.85, 0.92, 1, 0.55)
const BORDER := Color(0.85, 0.92, 1, 0.18)
const REGION := Color(0.3, 0.85, 0.45)
const PINNED := Color(1, 0.55, 0.15)
const ROAD_P := Color(1, 0.75, 0.3)
const ROAD_S := Color(0.95, 0.85, 0.5)
const ROAD_M := Color(0.6, 0.68, 0.78)
const ROAD_C := Color(0.35, 0.85, 0.55)
const ROAD_K := Color(0.75, 0.6, 0.45)
const GLOBE_SEA := Color(0.1, 0.25, 0.5)
const GLOBE_PANEL := Color(0.07, 0.1, 0.15)
# Traits des repères (curseurs, marqueurs, flèches teintées par `modulate`) et leur liseré
const INK := Color(1, 1, 1)
const INK_EDGE := Color(0, 0, 0)
# Adversaires (bots_view_model.gd) : puissance constante, fantôme, profil T12, inconnu
const BOT_CONSTANT := Color(1.00, 0.68, 0.30)
const BOT_GHOST := Color(0.60, 0.75, 1.00)
const BOT_PROFILE := Color(0.95, 0.85, 0.30)
const BOT_OTHER := Color(0.75, 0.75, 0.75)
const DATA := {
	"grade_descent": GRADE_DESCENT,
	"grade_flat": GRADE_FLAT,
	"grade_climb": GRADE_CLIMB,
	"grade_steep": GRADE_STEEP,
	"grade_wall": GRADE_WALL,
	"grade_text_descent": GRADE_TEXT_DESCENT,
	"grade_text_flat": GRADE_TEXT_FLAT,
	"grade_text_climb": GRADE_TEXT_CLIMB,
	"grade_text_steep": GRADE_TEXT_STEEP,
	"grade_text_wall": GRADE_TEXT_WALL,
	"wind_good": WIND_GOOD,
	"wind_bad": WIND_BAD,
	"wind_neutral": WIND_NEUTRAL,
	"pale": PALE,
	"wind_bar_off": WIND_BAR_OFF,
	"draft": DRAFT,
	"segment_good": SEGMENT_GOOD,
	"segment_bad": SEGMENT_BAD,
	"segment_neutral": SEGMENT_NEUTRAL,
	"bonus": BONUS,
	"jersey_sprint": JERSEY_SPRINT,
	"jersey_kom": JERSEY_KOM,
	"kom_dot": KOM_DOT,
	"wbal": WBAL,
	"track": TRACK,
	"track_soft": TRACK_SOFT,
	"track_faint": TRACK_FAINT,
	"hud_dim": HUD_DIM,
	"panel_bg": PANEL_BG,
	"chart_bg": CHART_BG,
	"shadow_line": SHADOW_LINE,
	"outline": OUTLINE,
	"zone_1": ZONE_1,
	"zone_2": ZONE_2,
	"zone_3": ZONE_3,
	"zone_4": ZONE_4,
	"zone_5": ZONE_5,
	"zone_6": ZONE_6,
	"zone_7": ZONE_7,
	"neutral_block": NEUTRAL_BLOCK,
	"power": POWER,
	"heart_rate": HEART_RATE,
	"cadence": CADENCE,
	"grid": GRID,
	"chart_text": CHART_TEXT,
	"pick": PICK,
	"junction_default": JUNCTION_DEFAULT,
	"junction_arrow": JUNCTION_ARROW,
	"attribution": ATTRIBUTION,
	"junction_tile": JUNCTION_TILE,
	"junction_dim": JUNCTION_DIM,
	"globe_bg": GLOBE_BG,
	"globe_text": GLOBE_TEXT,
	"globe_dim": GLOBE_DIM,
	"coast": COAST,
	"border": BORDER,
	"region": REGION,
	"pinned": PINNED,
	"road_p": ROAD_P,
	"road_s": ROAD_S,
	"road_m": ROAD_M,
	"road_c": ROAD_C,
	"road_k": ROAD_K,
	"globe_sea": GLOBE_SEA,
	"globe_panel": GLOBE_PANEL,
	"ink": INK,
	"ink_edge": INK_EDGE,
	"bot_constant": BOT_CONSTANT,
	"bot_ghost": BOT_GHOST,
	"bot_profile": BOT_PROFILE,
	"bot_other": BOT_OTHER,
}

# --- Tailles de police --------------------------------------------------------------------------
const TITLE_SIZE := 40
const ITEM_SIZE := 28
const DETAIL_SIZE := 22
const CARD_SIZE := 22
const HELP_SIZE := 21
const CHIP_SIZE := 18
const SMALL_SIZE := 16
const VALUE_SIZE := 28         # chiffre clé d'une tuile de la carte de détail

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
const SUMMARY_CARD_W := 700   # carte du bilan de fin de séance (chiffres sur deux colonnes)
const ICON := 28              # pictogramme d'une entrée
const LINE_W := 2.2           # trait des pictogrammes
const BAR_W := 180            # curseur d'un réglage en % dans une rangée
const BAR_H := 10
const CHART_H := 72           # profil d'altitude ou blocs d'entraînement dans la carte


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


## Tuile d'un chiffre clé dans la carte de détail (distance, dénivelé, durée…).
static func tile_style() -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = Color(VOID, 0.55)
	s.border_color = LINE
	s.set_border_width_all(1)
	s.set_corner_radius_all(RADIUS)
	s.content_margin_left = 14
	s.content_margin_right = 14
	s.content_margin_top = 8
	s.content_margin_bottom = 8
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
