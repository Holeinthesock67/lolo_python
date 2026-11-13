shader_type spatial;
render_mode unshaded, fog_disabled, blend_mix, depth_draw_never, cull_disabled, shadows_disabled;

// Lune du ciel de nuit (lot P35) : disque tourné vers la caméra, phase dessinée (part éclairée `illum`, de 0
// nouvelle lune à 1 pleine lune, côté éclairé à droite), lumière cendrée sur la part sombre, halo léger.
// `opacity` : apparition avec la nuit (étoiles de daylight_model.gd).

uniform float illum : hint_range(0, 1) = 1.0;
uniform float opacity : hint_range(0, 1) = 1.0;
const vec3 MOON = vec3(0.95, 0.93, 0.86);

void vertex() {
	// Toujours face à la caméra
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}

void fragment() {
	vec2 p = (UV - 0.5) * 2.0 * 1.6;           // disque de rayon 1, halo jusqu'à 1,6
	float r = length(p);
	float disk = smoothstep(1.0, 0.94, r);
	float edge = (1.0 - 2.0 * illum) * sqrt(max(0.0, 1.0 - p.y * p.y));
	float lit = smoothstep(edge - 0.06, edge + 0.06, p.x);
	// Mers lunaires : quelques taches plus sombres
	float mare = 1.0 - 0.14 * smoothstep(0.3, 0.0, length(p - vec2(-0.25, 0.3)))
		- 0.1 * smoothstep(0.4, 0.0, length(p - vec2(0.3, -0.2)));
	vec3 col = MOON * mix(0.16, 1.0, lit) * mare;
	float halo = smoothstep(1.6, 1.0, r) * (0.06 + 0.16 * illum);
	ALBEDO = col * disk + MOON * halo * (1.0 - disk);
	ALPHA = clamp(disk * mix(0.55, 1.0, lit) + halo, 0.0, 1.0) * opacity;
}
