extends RefCounted

## Numéros des tronçons du décor posé le long de la route (herbe, détails de sol, lave) sur un parcours en
## boucle (revue de code, constats E7-02 et E8-02). Pas de class_name : charger par
## preload("res://scripts/loop_chunks.gd").
##
## Pourquoi : main.gd ramène la position de la caméra dans [0, L) sur une boucle. Le numéro du tronçon de la
## caméra retombait donc de L / CHUNK_M à 0 à chaque passage de la ligne : toute la fenêtre de tronçons était
## refaite, avec d'autres tirages (le placement est haché sur le numéro du tronçon). L'herbe s'effaçait et
## repoussait autour du cycliste, rochers, murets et lave changeaient de place devant lui.
##
## Deux numéros par tronçon :
## - `unwrap(k)` : numéro continu de la fenêtre, qui continue de croître (ou de décroître à rebours) au passage
##   de la ligne : la fenêtre glisse d'un tronçon comme ailleurs ;
## - `key(k)` : numéro du tronçon dans le tour (0 à count() − 1), seul utilisé pour le placement : un même
##   endroit de la boucle a toujours le même décor, d'un tour à l'autre et de part et d'autre de la ligne.
## Le dernier tronçon d'un tour est plus court quand L n'est pas un multiple de CHUNK_M : les places tirées
## au-delà de L sont laissées vides (`in_lap`), le tronçon 0 du tour suivant les couvre déjà.
## Parcours ouvert : les deux numéros sont le numéro d'origine, rien ne change.

var route = null
var chunk_m := 1.0
var _count := 0
var _lap := 0            # tronçons ajoutés par les tours déjà faits (multiple de _count)
var _last := 0
var _has_last := false


func _init(route_data = null, p_chunk_m: float = 1.0) -> void:
	route = route_data
	chunk_m = maxf(p_chunk_m, 1e-3)
	if route != null and route.is_loop() and float(route.length_m) > 0.0:
		_count = maxi(ceili(float(route.length_m) / chunk_m), 1)


## Vrai sur une boucle (numéros repliés).
func is_loop() -> bool:
	return _count > 0


## Tronçons d'un tour (0 hors boucle).
func count() -> int:
	return _count


## Numéro continu de la fenêtre pour le tronçon `k` de la caméra (position ramenée dans [0, L)) : un saut de
## plus d'un demi-tour d'une image à l'autre est un passage de la ligne, pas un déplacement.
func unwrap(k: int) -> int:
	if _count == 0:
		return k
	var u := k + _lap
	if _has_last and _count >= 2:
		var d := u - _last
		if d * 2 > _count:
			_lap -= _count
		elif d * 2 < -_count:
			_lap += _count
		u = k + _lap
	_last = u
	_has_last = true
	return u


## Numéro du tronçon `k` dans le tour (placement, tirages) ; `k` hors boucle.
func key(k: int) -> int:
	return posmod(k, _count) if _count > 0 else k


## Vrai si la position `s` (calculée depuis un numéro de `key`) est dans le tour : toujours hors boucle.
func in_lap(s: float) -> bool:
	return _count == 0 or (s >= 0.0 and s < float(route.length_m))
