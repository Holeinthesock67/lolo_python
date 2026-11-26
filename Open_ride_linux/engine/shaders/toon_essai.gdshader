shader_type spatial;
// Essai de rendu du style dessin animé (lot CS0, OPENRIDE_RENDER_DIAG `contours` et `paliers=N`, toon_essai.gd) :
// quad plein écran posé devant la caméra. Contours : trait sombre là où la profondeur ou la normale des pixels
// voisins rompt, fondu au loin. Paliers : luminosité de l'image ramenée à N niveaux (aplats du prototype du
// 23 novembre). Sert à mesurer le coût sur le PC cible ; aucun réglage du joueur ne l'active. La version du
// jeu (lots CS3 et CS4) ne lira pas l'image entière : les paliers passeront dans les matériaux.
render_mode unshaded, fog_disabled, depth_test_disabled, depth_draw_never, cull_disabled, shadows_disabled;

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D normal_tex : hint_normal_roughness_texture, filter_nearest;
uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform float thickness = 1.25;      // épaisseur du trait en pixels
uniform float fade_m = 350.0;        // distance où le trait a disparu
uniform float levels = 0.0;          // 0 : pas de paliers (l'image n'est alors pas lue)
uniform bool outlines = true;
uniform vec3 line_color : source_color = vec3(0.06, 0.07, 0.10);

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

float linear_depth(vec2 uv, mat4 inv_projection) {
	float d = texture(depth_tex, uv).r;
	vec4 p = inv_projection * vec4(uv * 2.0 - 1.0, d, 1.0);
	return -p.z / p.w;
}

void fragment() {
	float edge = 0.0;
	if (outlines) {
		vec2 px = thickness / VIEWPORT_SIZE;
		vec2 o[4] = {vec2(px.x, 0.0), vec2(-px.x, 0.0), vec2(0.0, px.y), vec2(0.0, -px.y)};
		float dc = linear_depth(SCREEN_UV, INV_PROJECTION_MATRIX);
		vec3 nc = texture(normal_tex, SCREEN_UV).xyz * 2.0 - 1.0;
		float dsum = 0.0;
		float dmin = dc;
		float ndiff = 0.0;
		for (int i = 0; i < 4; i++) {
			float di = linear_depth(SCREEN_UV + o[i], INV_PROJECTION_MATRIX);
			dsum += di;
			dmin = min(dmin, di);
			vec3 ni = texture(normal_tex, SCREEN_UV + o[i]).xyz * 2.0 - 1.0;
			ndiff = max(ndiff, 1.0 - dot(nc, ni));
		}
		// Laplacien de la profondeur rapporté à la distance : pas de faux trait sur la route vue en rasant
		float e_depth = smoothstep(0.02, 0.06, abs(dsum - 4.0 * dc) / max(dmin, 0.1));
		float e_norm = smoothstep(0.35, 0.7, ndiff) * step(dc, 5000.0);
		edge = max(e_depth, e_norm) * (1.0 - smoothstep(fade_m * 0.4, fade_m, dmin));
	}
	vec3 col = line_color;
	float a = edge;
	if (levels > 0.5) {
		vec3 c = texture(screen_tex, SCREEN_UV).rgb;
		float v = sqrt(max(max(c.r, max(c.g, c.b)), 1e-4));
		float q = (floor(v * levels) + 0.5) / levels;
		c *= (q * q) / (v * v);
		col = mix(c, line_color, edge);
		a = 1.0;
	}
	ALBEDO = col;
	ALPHA = a;
}
