extends RefCounted

## Horloge des animations par sommet (personnages de crowd.gdshader, animaux de fauna.gdshader) : uniforme
## global `anim_time` (project.godot, [shader_globals]) à la place de TIME, pour que main.gd puisse figer
## ces animations avec le reste du décor quand le core ne répond plus (test graphique « image figée »).
## Sans appel à advance (vitrines, tests de rendu), l'horloge reste à 0 : poses fixes, captures reproductibles.
## Pas de class_name : charger par preload("res://scripts/anim_clock.gd").

const PARAM := "anim_time"

static var seconds := 0.0


## Avance l'horloge de `dt_s` secondes.
static func advance(dt_s: float) -> void:
	seconds += maxf(dt_s, 0.0)
	RenderingServer.global_shader_parameter_set(PARAM, seconds)
