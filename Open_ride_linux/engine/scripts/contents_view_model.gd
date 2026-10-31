extends RefCounted

## Écran « Réglages › Contenus » (lot O25 ; contrat IPC révision 1.5, message `contents`). Modèle sans
## nœud, relié par menu_flow.gd : une ligne par contenu (libellé à gauche, état à droite) et la carte de
## détail du contenu sous le focus (contenu, taille, téléchargement) ; A maintenu installe ce qui manque
## (`install_content`), sans rien écraser (sur un contenu installé : « Déjà installé ») ; un contenu
## qui télécharge passe d'abord par une confirmation (« Non » par défaut). La ligne d'état rappelle le compte rendu de la dernière installation.
## Quand une installation se termine, menu_flow.gd redemande les listes (parcours, entraînements, plans).
## Packs (lot O29) : pack « Cols célèbres » (téléchargement), archives de thèmes, de biomes ou de parcours
## trouvées dans Téléchargements, sur le Bureau ou dans ~/OpenRide/Import, thèmes installés (taille et
## dernière utilisation, information) ; une dernière ligne donne la place libre et celle des thèmes.

const SCREEN := "contents"
const STATE_TEXTS := {"missing": "à installer", "partial": "en partie installé", "installed": "installé",
	"installing": "installation…"}

## Dernier message `contents` : éléments {id, kind, label, detail, state, network, size_mb, progress_pct}.
var items: Array = []
var busy := ""
## Ligne d'état : compte rendu du core, refus (content_invalid, content_failed, busy) ou attente.
var message := ""
var received := false
## Place sur le disque (Mo) : libre, thèmes installés et leur plafond ; null quand le core ne la donne pas.
var disk_free_mb = null
var themes_mb = null
var themes_max_mb = null


## Message `contents` ; vrai quand une installation vient de se terminer (listes à redemander).
func on_contents(msg: Dictionary) -> bool:
	var raw = msg.get("items", [])
	items = raw if raw is Array else []
	var was_busy := busy
	busy = str(msg["busy"]) if msg.get("busy") != null else ""
	received = true
	disk_free_mb = msg.get("disk_free_mb")
	themes_mb = msg.get("themes_mb")
	themes_max_mb = msg.get("themes_max_mb")
	var text := str(msg.get("message", ""))
	if text != "" or busy != "":
		message = text
	return was_busy != "" and busy == ""


func on_error(code: String, text: String) -> bool:
	if code not in ["content_invalid", "content_failed", "busy"]:
		return false
	message = "Échec : " + text
	return true


func _find(id: String) -> Dictionary:
	for it in items:
		if it is Dictionary and str(it.get("id", "")) == id:
			return it
	return {}


static func state_text(it: Dictionary) -> String:
	var st := str(it.get("state", ""))
	var text := str(STATE_TEXTS.get(st, st))
	if st == "installing" and it.get("progress_pct") != null:
		text = "installation : %d %%" % int(it["progress_pct"])
	if it.get("size_mb") != null and st != "installing":
		text += ", " + size_text(float(it["size_mb"]))
	if bool(it.get("network", false)) and st in ["missing", "partial"]:
		text += ", téléchargement"
	return text


func menu_items() -> Array:
	var out: Array = []
	for it in items:
		if not (it is Dictionary):
			continue
		out.append({"id": "content:" + str(it.get("id", "")), "label": str(it.get("label", it.get("id", ""))),
			"enabled": busy == "", "detail": state_text(it)})
	if not received:
		out.append({"id": "wait", "label": "Recherche des contenus…", "enabled": false})
	elif out.is_empty():
		out.append({"id": "none", "label": "Aucun contenu proposé", "enabled": false})
	var disk := disk_text()
	if disk != "":
		out.append({"id": "disk", "label": disk, "enabled": false})
	return out


## « Place libre : 120 Go ; thèmes : 0,8 Go sur 5 Go » ("" sans les champs du lot O29).
func disk_text() -> String:
	var parts: Array[String] = []
	if disk_free_mb != null:
		parts.append("Place libre : " + size_text(float(disk_free_mb)))
	if themes_mb != null and themes_max_mb != null:
		parts.append("thèmes : %s sur %s" % [size_text(float(themes_mb)), size_text(float(themes_max_mb))])
	return " ; ".join(parts)


## Taille lisible en français : « 850 Mo », « 1,2 Go », « 120 Go ».
static func size_text(mb: float) -> String:
	if mb < 1000.0:
		return "%d Mo" % int(round(mb))
	var gb := mb / 1024.0
	if gb < 10.0:
		return ("%.1f Go" % gb).replace(".", ",")
	return "%d Go" % int(round(gb))


## Choix d'une ligne : {"action": "install_content", "id": …}, ou une confirmation si le contenu télécharge
## ({"confirm": titre, "action": …}) ; {} pour une ligne d'information.
func handle(item_id: String) -> Dictionary:
	if not item_id.begins_with("content:"):
		return {}
	var id := item_id.substr(8)
	var it := _find(id)
	if it.is_empty():
		return {}
	if str(it.get("state", "")) == "installed":
		message = "Déjà installé : rien à ajouter."
		return {}
	var act := {"action": "install_content", "id": id}
	message = "Installation demandée…"
	if bool(it.get("network", false)):
		message = ""
		return {"confirm": "%s : télécharger et installer ?" % str(it.get("label", id)), "action": act}
	return act


## Carte de détail du contenu sous le focus : état, taille, contenu, téléchargement ({} hors contenu).
func sheet(item_id: String) -> Dictionary:
	if not item_id.begins_with("content:"):
		return {}
	var it := _find(item_id.substr(8))
	if it.is_empty():
		return {}
	var lines: Array = []
	if str(it.get("detail", "")) != "":
		lines.append(str(it["detail"]))
	lines.append("Téléchargement nécessaire" if bool(it.get("network", false)) else "Rien n'est téléchargé")
	lines.append("Aucun fichier existant n'est remplacé")
	return {"title": "Contenu", "name": str(it.get("label", "")), "lines": lines}
