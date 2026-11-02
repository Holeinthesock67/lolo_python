extends RefCounted

## Saisie de texte au Click, au clavier ou à la souris (lot O31), partagée par le nom d'un profil (lot MJ8)
## et la recherche de lieu du monde ouvert (lot W11). Modèle sans nœud ; l'écran qui l'utilise affiche
## `grid_items()` en grille de GRID_COLUMNS colonnes et le texte en cours.
##
## Click : + et − passent à la case suivante ou précédente, maintenus ils sautent d'une ligne ; Z écrit la
## lettre de la case ; Y efface la dernière (texte vide : l'écran revient en arrière) ; A maintenu valide.
## Clavier : on tape le texte (`type_text`), Entrée valide, Retour arrière efface. Souris : un clic écrit la
## lettre, « Effacer » et « Valider » en fin de grille. Une lettre s'écrit en majuscule en début de mot.

const GRID_COLUMNS := 10
## Cases de la grille, dans l'ordre (les lettres s'écrivent en minuscules, une majuscule en début de mot).
const GRID := ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
	"K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
	"U", "V", "W", "X", "Y", "Z", "é", "è", "ê", "à",
	"ç", "ô", "ï", "ü", "-", " ", "0", "1", "2", "3",
	"4", "5", "6", "7", "8", "9"]
const ERASE := "erase"
const VALIDATE := "validate"
const CELL_PREFIX := "c:"

var text := ""
var max_length := 16
## Signes écrits en plus des cases (au clavier et en fin de grille), par exemple l'apostrophe d'un lieu.
var extra: Array = []
## Case en focus, pour un écran qui n'a pas de liste à lui (monde ouvert) ; les menus gardent leur focus.
var cell := 0


func _init(max_len := 16, extra_chars: Array = []) -> void:
	max_length = max_len
	extra = extra_chars


func cells() -> Array:
	return GRID + extra


func grid_items() -> Array:
	var out: Array = []
	var all := cells()
	for i in range(all.size()):
		var ch: String = all[i]
		out.append({"id": CELL_PREFIX + str(i), "label": "␣" if ch == " " else ch, "enabled": true, "detail": ""})
	out.append({"id": ERASE, "label": "Effacer", "enabled": true, "detail": ""})
	out.append({"id": VALIDATE, "label": "Valider", "enabled": true, "detail": ""})
	return out


## Lettre à écrire pour une case : majuscule en début de mot, sinon minuscule ; le reste tel quel.
func _char_for(ch: String) -> String:
	if ch.to_lower() == ch.to_upper():
		return ch
	var start := text == "" or text.ends_with(" ") or text.ends_with("-") or text.ends_with("'")
	return ch.to_upper() if start else ch.to_lower()


func type_char(ch: String) -> bool:
	if ch == "" or text.length() >= max_length:
		return false
	if ch == " " and (text == "" or text.ends_with(" ")):
		return false   # pas d'espace en tête ni deux de suite
	text += ch
	return true


func backspace() -> bool:
	if text == "":
		return false
	text = text.substr(0, text.length() - 1)
	return true


## Case activée (Z, ou clic) : « validate » pour Valider, « changed » si le texte a changé, sinon "".
func press_cell(item_id: String) -> String:
	if item_id == ERASE:
		return "changed" if backspace() else ""
	if item_id == VALIDATE:
		return "validate"
	if item_id.begins_with(CELL_PREFIX):
		var i := int(item_id.substr(CELL_PREFIX.length()))
		var all := cells()
		if i >= 0 and i < all.size() and type_char(_char_for(all[i])):
			return "changed"
	return ""


## Saisie au clavier : lettres (accents compris), chiffres, espace, tiret et signes `extra` ; le reste est ignoré.
func type_text(ch: String) -> bool:
	if ch.length() != 1:
		return false
	if ch.to_lower() != ch.to_upper() or ch.is_valid_int() or ch == " " or ch == "-" or ch in extra:
		type_char(ch)
		return true
	return false


## Déplace `cell` de `step` cases dans la grille et ses deux actions, sans boucler.
func move(step: int) -> void:
	cell = clampi(cell + step, 0, grid_items().size() - 1)


func cell_id() -> String:
	return str(grid_items()[cell]["id"])
