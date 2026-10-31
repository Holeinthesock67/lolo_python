extends RefCounted

## Écran « Réglages › Contenus » (lot O25 ; contrat IPC révision 1.5, message `contents`). Modèle sans
## nœud, relié par menu_flow.gd : une ligne par contenu (libellé à gauche, état à droite) et la carte de
## détail du contenu sous le focus (contenu, taille, téléchargement) ; A maintenu installe ce qui manque
## (`install_content`), sans rien écraser (sur un contenu installé : « Déjà installé ») ; un contenu
## qui télécharge passe d'abord par une confirmation (« Non » par défaut). La ligne d'état rappelle le compte rendu de la dernière installation.
## Quand une installation se termine, menu_flow.gd redemande les listes (parcours, entraînements, plans).

const SCREEN := "contents"
const STATE_TEXTS := {"missing": "à installer", "partial": "en partie installé", "installed": "installé",
	"installing": "installation…"}

## Dernier message `contents` : éléments {id, kind, label, detail, state, network, size_mb, progress_pct}.
var items: Array = []
var busy := ""
## Ligne d'état : compte rendu du core, refus (content_invalid, content_failed, busy) ou attente.
var message := ""
var received := false


## Message `contents` ; vrai quand une installation vient de se terminer (listes à redemander).
func on_contents(msg: Dictionary) -> bool:
	var raw = msg.get("items", [])
	items = raw if raw is Array else []
	var was_busy := busy
	busy = str(msg["busy"]) if msg.get("busy") != null else ""
	received = true
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
		text += ", %d Mo" % int(round(float(it["size_mb"])))
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
	return out


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
		return {"confirm": "Installer « %s » ? Téléchargement nécessaire" % str(it.get("label", id)), "action": act}
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
