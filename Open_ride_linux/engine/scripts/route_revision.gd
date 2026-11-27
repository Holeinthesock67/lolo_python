extends RefCounted

## Révision de la route du monde ouvert (revue de code EC2, constats E7-01 et E8-01) : ce qui a vraiment changé
## entre l'ancienne et la nouvelle route, pour ne refaire que le décor de ces tronçons. Pas de class_name : charger
## par preload("res://scripts/route_revision.gd").
##
## Pourquoi : à chaque révision (prolongement d'environ 1 km, choix d'une branche), herbe, détails du sol et lave
## étaient détruits puis repoussaient autour du cycliste. Une révision garde les parties de route d'avant le
## changement : le décor de ces tronçons est le même, seul celui des tronçons dont la route change est refait.

## Écart (m) au-delà duquel un point de la route a changé.
const SAME_TOL_M := 0.01
## Points comparés sur un tronçon (bouts compris).
const PROBES := 5


## Vrai si les deux routes passent par les mêmes points sur [s0, s1] (bouts compris) : décor de ce tronçon gardé.
## Faux si l'une des deux s'arrête avant s1 (route prolongée : la fin de l'ancienne était repliée sur son bout).
static func same_span(old_route, new_route, s0: float, s1: float) -> bool:
	if old_route == null or new_route == null:
		return false
	if is_same(old_route, new_route):
		return true
	if old_route.n < 2 or new_route.n < 2:
		return false
	if s1 > float(old_route.length_m) or s1 > float(new_route.length_m):
		return false
	for i in range(PROBES):
		var s := lerpf(maxf(s0, 0.0), s1, float(i) / float(PROBES - 1))
		var a: Vector3 = old_route.sample_point(s)
		var b: Vector3 = new_route.sample_point(s)
		if a.distance_to(b) > SAME_TOL_M:
			return false
	return true
