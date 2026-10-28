shader_type canvas_item;

// Piratage, salle manquée, défaite (lot R17) : bandes décalées et séparation des couleurs, à poser sur un
// ColorRect plein écran. `intensity` de 0 (rien) à 1. Le motif change au plus 3 fois par seconde.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float intensity : hint_range(0.0, 1.0) = 0.0;
uniform float bands = 24.0;

float rnd(float n) {
	return fract(sin(n * 91.345) * 47453.5453);
}

void fragment() {
	float step_id = floor(TIME * 3.0);
	float band = floor(SCREEN_UV.y * bands);
	float r = rnd(band + step_id * 17.0);
	float on_band = step(1.0 - 0.5 * intensity, r);
	float shift = (rnd(band * 3.1 + step_id) - 0.5) * 0.12 * intensity * on_band;
	float split = 0.006 * intensity * on_band;
	vec2 uv = SCREEN_UV + vec2(shift, 0.0);
	float cr = texture(screen_tex, uv + vec2(split, 0.0)).r;
	float cg = texture(screen_tex, uv).g;
	float cb = texture(screen_tex, uv - vec2(split, 0.0)).b;
	COLOR = vec4(cr, cg, cb, 1.0);
}
