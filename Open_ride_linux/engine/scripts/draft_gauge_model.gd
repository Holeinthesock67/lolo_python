extends RefCounted

## Jauge d'abri au-dessus du bot qui abrite le cycliste (demande du propriétaire du 29 octobre, maquette C
## validée), sans aucun nœud. Pas de class_name : charger par preload("res://scripts/draft_gauge_model.gd").
##
## La jauge reprend ce que le core calcule (contrat IPC révision 1.3 §3) : `draft`, l'abri lissé que le
## cycliste ressent, et `draft_bot`, le bot qui le donne. Rien n'est recalculé ici : la jauge dit la même
## chose que la pastille « Abri 30 % » du HUD (wind_view_model.gd), même échelle (`draft / 0,55`, lot AS4) et même
## seuil (cachée sous 5 %). Seuls les bots `constant` abritent (draft.py) : ni le fantôme, ni les cyclistes
## du décor n'ont de jauge.
##
## `view(enabled, draft, draft_bot, quality)` rend `{visible, bot, fill, pct, text, glow}` :
## - `fill` de 0 à 1, continu (le core lisse déjà l'abri sur 1 s) ; `pct` arrondi à 5 % comme la pastille ;
## - `text` : « 30 % » sous l'arc en medium et high, vide en low (arc seul, maquette validée) ;
## - `glow` : halo doux autour de la partie remplie, en high seulement.
## Réglage `render.draft_gauge` (`off` / `on`), coupé par défaut.

const WindViewModel := preload("res://scripts/wind_view_model.gd")

const SETTING_KEY := "render.draft_gauge"
const MIN_PCT := 5


static func view(enabled: bool, draft: Variant, draft_bot: Variant, quality: String) -> Dictionary:
	var hidden := {"visible": false, "bot": "", "fill": 0.0, "pct": 0, "text": "", "glow": false}
	if not enabled or not (draft is float or draft is int) or not (draft_bot is String) or draft_bot == "":
		return hidden
	var fill := clampf(float(draft) / WindViewModel.DRAFT_MAX, 0.0, 1.0)
	var pct := roundi(fill * 20.0) * 5
	if pct < MIN_PCT:
		return hidden
	return {"visible": true, "bot": draft_bot, "fill": fill, "pct": pct,
		"text": "" if quality == "low" else "%d %%" % pct, "glow": quality == "high"}
