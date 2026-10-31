extends RefCounted

## Saisie du QWKcode de GoldenCheetah au clavier dans le menu ERG (lot O21, choix « Les deux » du
## propriétaire du 30 octobre), sans nœud. Une ligne par segment, écrite à la fin de la dernière ligne :
## une touche imprimable ajoute son caractère, Entrée commence une ligne, Retour arrière efface (et
## remonte d'une ligne sur une ligne vide). Le core relit le texte (`create_workout_qwk`, parse_qwk) :
## l'engine n'analyse rien, il borne seulement la taille pour tenir dans un datagramme (contrat §2).
## Pas de class_name : charger par preload("res://scripts/qwk_editor.gd").

const SCREEN := "workout_qwk"
const TITLE := "Saisir du QWKcode"
const SAVE_ID := "save"
const CLEAR_ID := "clear"
const MAX_LINES := 40
const MAX_LINE_CHARS := 60
## Même borne que le core (workout_menu.MAX_QWK_TEXT_BYTES).
const MAX_TEXT_BYTES := 3000
const CARET := "▌"

var lines: Array[String] = [""]


func clear() -> void:
	lines = [""]


func is_empty() -> bool:
	return text().strip_edges() == ""


## Texte envoyé au core : les lignes jointes, sans lignes vides en fin.
func text() -> String:
	return "\n".join(PackedStringArray(lines)).strip_edges(false, true)


## Ajoute un caractère imprimable à la dernière ligne ; faux si refusé (ligne ou texte plein).
func type_char(ch: String) -> bool:
	if ch.length() != 1 or ch.unicode_at(0) < 32:
		return false
	var last: String = lines[-1]
	if last.length() >= MAX_LINE_CHARS or (text() + ch).to_utf8_buffer().size() > MAX_TEXT_BYTES:
		return false
	lines[-1] = last + ch
	return true


## Entrée : nouvelle ligne (pas deux lignes vides de suite, 40 lignes au plus).
func new_line() -> bool:
	if lines[-1].strip_edges() == "" or lines.size() >= MAX_LINES:
		return false
	lines.append("")
	return true


## Retour arrière : dernier caractère, ou ligne vide retirée (curseur en fin de la ligne précédente).
func backspace() -> bool:
	var last: String = lines[-1]
	if last != "":
		lines[-1] = last.left(last.length() - 1)
		return true
	if lines.size() > 1:
		lines.remove_at(lines.size() - 1)
		return true
	return false


## Nombre de segments écrits (lignes non vides hors commentaires), pour la ligne « Enregistrer ».
func segment_count() -> int:
	var n := 0
	for l in lines:
		var s := l.strip_edges()
		if s != "" and not s.begins_with("#"):
			n += 1
	return n


## Éléments de l'écran : une ligne du texte par élément (la dernière avec le curseur), puis
## « Enregistrer et choisir » et « Tout effacer ».
func menu_items() -> Array:
	var out: Array = []
	for i in range(lines.size()):
		var label: String = lines[i] + (CARET if i == lines.size() - 1 else "")
		out.append({"id": "line:%d" % i, "label": label, "enabled": true, "detail": ""})
	var n := segment_count()
	out.append({"id": SAVE_ID, "label": "Enregistrer et choisir", "enabled": n > 0,
		"detail": "%d segment%s" % [n, "s" if n > 1 else ""]})
	out.append({"id": CLEAR_ID, "label": "Tout effacer", "enabled": not is_empty(), "detail": ""})
	return out


## Identifiant de la ligne en cours d'écriture (focus après une touche).
func last_line_id() -> String:
	return "line:%d" % (lines.size() - 1)
