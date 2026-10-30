shader_type canvas_item;
// Brume de chaleur (lot U10) : l'image tremble dans une bande autour de l'horizon, comme l'air chaud
// au-dessus d'une route de désert. Posé sur un ColorRect plein écran par U17 ; `strength` vient de
// atmosphere_model.gd (`heat_haze`, 0 = nœud caché) et `horizon_y` de la caméra (0 en haut, 1 en bas).
// Temps global `anim_time` : la brume se fige avec le reste de la scène (pause, core muet).

global uniform float anim_time;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float strength : hint_range(0.0, 1.0) = 0.0;
uniform float horizon_y = 0.5;
uniform float band = 0.04;          // demi-hauteur de la bande, en part de l'écran
uniform float max_offset = 0.0009;  // déplacement maximal, en part de l'écran (1 à 2 pixels)

void fragment() {
	// Bande juste sous l'horizon (sol chaud au loin), presque rien au-dessus ; scintillement fin, surtout horizontal.
	float d = (SCREEN_UV.y - horizon_y) / band;
	float mask = exp(-d * d * (d < 0.0 ? 9.0 : 1.0)) * strength;
	float t = anim_time;
	float w1 = sin(SCREEN_UV.y * 900.0 + t * 7.0 + sin(SCREEN_UV.x * 60.0 + t * 1.3) * 3.0);
	float w2 = sin(SCREEN_UV.y * 1700.0 - t * 11.0 + SCREEN_UV.x * 40.0);
	vec2 offset = vec2(w1 * 0.7 + w2 * 0.3, w2 * 0.15) * max_offset * mask;
	COLOR = textureLod(screen_tex, SCREEN_UV + offset, 0.0);
}
