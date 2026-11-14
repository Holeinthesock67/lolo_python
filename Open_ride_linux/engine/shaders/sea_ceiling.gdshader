shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque, shadows_disabled;

// Surface de la mer vue d'en dessous (lot SM1, atmosphere_view.gd) : grand carré au niveau de la mer qui suit la
// caméra sous l'eau ; vagues claires qui ondulent sur l'eau sombre, effacées par le brouillard de l'eau au loin.
// `strength` (0 à 1) : part du fond marin sous la caméra ; à 0 le carré est caché par atmosphere_view.gd.

global uniform float anim_time;
uniform vec3 deep_color : source_color = vec3(0.10, 0.45, 0.55);
uniform vec3 bright_color : source_color = vec3(0.80, 0.97, 1.0);
uniform float strength = 1.0;

varying vec3 v_world;

void vertex() {
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = v_world.xz;
	float t = anim_time;
	// Rides fines (quelques mètres) et douces : une surface d'eau, pas un plafond de nuages blancs (14/11)
	float r = sin(p.x * 0.53 + t * 0.9) + sin(p.y * 0.47 - t * 0.7)
		+ sin((p.x + p.y) * 0.37 + t * 1.1) + sin((p.x - p.y) * 0.71 - t * 0.5);
	float crest = smoothstep(0.7, 1.0, 1.0 - abs(r * 0.25));
	float glow = 0.15 + 0.45 * crest;
	ALBEDO = mix(deep_color, bright_color, glow * strength);
}
