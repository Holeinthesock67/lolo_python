extends RefCounted

## Horloge des animations par sommet (personnages de crowd.gdshader, animaux de fauna.gdshader) : uniforme
## global `anim_time` (project.godot, [shader_globals]) à la place de TIME, pour que main.gd puisse figer
## ces animations avec le reste du décor quand le core ne répond plus (test graphique « image figée »).
## Sans appel à advance (vitrines, tests de rendu), l'horloge reste à 0 : poses fixes, captures reproductibles.
## Pas de class_name : charger par preload("res://scripts/anim_clock.gd").

const PARAM := "anim_time"

static var seconds := 0.0
## Scène figée des tests graphiques (message `_test` « freeze », lot X20) : l'horloge ne bouge plus.
static var frozen := false


## Avance l'horloge de `dt_s` secondes (sauf scène figée).
static func advance(dt_s: float) -> void:
	if frozen:
		return
	seconds += maxf(dt_s, 0.0)
	RenderingServer.global_shader_parameter_set(PARAM, seconds)


## Fige l'horloge à `t_s` secondes (scène figée des tests graphiques) ; NAN la libère.
static func freeze(t_s: float) -> void:
	frozen = not is_nan(t_s)
	if frozen:
		seconds = maxf(t_s, 0.0)
		RenderingServer.global_shader_parameter_set(PARAM, seconds)
