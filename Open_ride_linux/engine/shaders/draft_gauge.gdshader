shader_type spatial;
// Jauge d'abri au-dessus d'un bot (draft_gauge.gd) : arc de 140° tourné vers le haut, fond sombre et partie
// remplie de gauche à droite selon `fill` ; `glow` ajoute un halo doux autour de la partie remplie (high).
// Un seul quad toujours face à la caméra, sans lumière ni ombre ni brouillard.
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform float fill : hint_range(0.0, 1.0) = 0.0;
uniform float glow : hint_range(0.0, 1.0) = 0.0;
uniform vec4 track_color : source_color = vec4(0.08, 0.11, 0.16, 0.8);
uniform vec4 fill_color : source_color = vec4(0.25, 0.55, 0.9, 1.0);
uniform vec2 size_m = vec2(0.8, 0.5);

const float RADIUS = 0.3;
const float TRACK_HALF = 0.06;
const float FILL_HALF = 0.04;
const float START_DEG = 160.0;
const float SPAN_DEG = 140.0;

void vertex() {
	// Face à la caméra en gardant la position du nœud (billboard).
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

void fragment() {
	vec2 p = vec2((UV.x - 0.5) * size_m.x, (0.9 - UV.y) * size_m.y);
	float r = length(p);
	float a = degrees(atan(p.y, p.x));
	float t = (START_DEG - a) / SPAN_DEG;           // 0 à gauche, 1 à droite
	float aa = max(fwidth(r), 1e-4);
	float span = smoothstep(-0.01, 0.0, t) * (1.0 - smoothstep(1.0, 1.01, t)) * step(0.0, p.y + TRACK_HALF);
	float d = abs(r - RADIUS);
	float track = 1.0 - smoothstep(TRACK_HALF - aa, TRACK_HALF + aa, d);
	float filled = (1.0 - smoothstep(FILL_HALF - aa, FILL_HALF + aa, d)) * step(t, fill) * span;
	float halo = glow * exp(-max(d - FILL_HALF, 0.0) / 0.035) * step(t, fill) * span * 0.45;
	vec3 col = mix(track_color.rgb, fill_color.rgb, max(filled, halo * (1.0 - track)));
	ALBEDO = col;
	ALPHA = clamp(max(max(track * span * track_color.a, filled), halo), 0.0, 1.0);
}
