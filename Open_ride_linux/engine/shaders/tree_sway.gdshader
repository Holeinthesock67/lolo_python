shader_type spatial;
render_mode cull_back;

// Balancement des arbres et des touffes d'herbe au vent (Lot P5).
// Le vent vient du modèle P4 (wind_model.gd) par quatre paramètres globaux, mis à jour une fois par
// image par TreeRenderer.apply_wind() : aucune boucle sur les tuiles ni donnée ajoutée au MultiMesh.
// Déplacement horizontal = dir × force × (hauteur relative)² × amplitude, oscillant autour d'une
// légère inclinaison ; le décalage de phase vient de la position de l'instance. Les rafales augmentent
// l'amplitude et la fréquence. Vent nul : sommets inchangés.
// La copie du LOD 1 (panneaux croisés) est faite par tree_renderer.gd en remplaçant cull_back par
// cull_disabled, avec une amplitude réduite.

global uniform vec3 wind_dir;
global uniform float wind_strength;
global uniform float wind_gust;
global uniform float wind_phase;

uniform float sway_amplitude_m = 0.45;   // déplacement de la cime par vent de 60 km/h, en mètres
uniform float sway_height_m = 5.4;       // hauteur du modèle (cime)
uniform float sway_frequency_hz = 0.35;  // oscillation par vent calme ; × 1,6 en pleine rafale
uniform float roughness_value = 0.85;
// Vent propre au matériau (touffes d'herbe : vent apparent) quand use_local_wind est vrai.
uniform bool use_local_wind = false;
uniform vec3 local_wind_dir = vec3(0.0);
uniform float local_wind_strength = 0.0;
// Teinte du feuillage, neutre par défaut ; réglée par les saisons (P18, version 2.0).
uniform vec3 foliage_tint : source_color = vec3(1.0);

void vertex() {
	vec3 dir = use_local_wind ? local_wind_dir : wind_dir;
	float strength = use_local_wind ? local_wind_strength : wind_strength;
	float h = clamp(VERTEX.y / sway_height_m, 0.0, 1.0);
	vec3 origin = MODEL_MATRIX[3].xyz;
	float offset = fract(sin(dot(origin.xz, vec2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
	float freq = sway_frequency_hz * (1.0 + 0.6 * wind_gust);
	float swing = 0.55 + 0.45 * sin(wind_phase * freq * 6.2831853 + offset);
	float amp = sway_amplitude_m * strength * (1.0 + 0.8 * wind_gust) * h * h * swing;
	vec3 local_disp = inverse(mat3(MODEL_MATRIX)) * (dir * amp);
	VERTEX += vec3(local_disp.x, 0.0, local_disp.z);
}

void fragment() {
	ALBEDO = COLOR.rgb * foliage_tint;
	ROUGHNESS = roughness_value;
}
