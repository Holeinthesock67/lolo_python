shader_type spatial;
// Feuillage en lambert sans reflet spéculaire (étude du rendu du 6 novembre : même image, moins de calcul)
render_mode cull_back, diffuse_lambert, specular_disabled;

// Balancement des arbres et des touffes d'herbe au vent (Lot P5).
// Le vent vient du modèle P4 (wind_model.gd) par quatre paramètres globaux, mis à jour une fois par
// image par TreeRenderer.apply_wind() : aucune boucle sur les tuiles ni donnée ajoutée au MultiMesh.
// Déplacement horizontal = dir × force × (hauteur relative)² × amplitude, oscillant autour d'une
// légère inclinaison ; le décalage de phase vient de la position de l'instance. Les rafales augmentent
// l'amplitude et la fréquence. Vent nul : sommets inchangés.
// La copie du LOD 1 (panneaux croisés) est faite par tree_renderer.gd en remplaçant cull_back par
// cull_disabled, avec une amplitude réduite.
// Habillage (lot Y8 étape 2) : l'alpha de la couleur du sommet porte la matière (tree_species.gd, codes
// MAT_*) : écorces crevassée, lisse, de bouleau, en plaques, de palmier, côtes de cactus, puis feuillus,
// aiguilles et palmes. Motifs procéduraux en coordonnées de l'objet (mètres), sans texture, avec la couche
// commune surface_detail.gdshaderinc, sans faux relief (mesure du 28 octobre : la perturbation de la normale
// par dérivées d'écran sur les houppiers coûtait trop en medium sur la GTX 1060). Alpha de 0,7 ou plus
// (herbe, anciens maillages) : couleur unie comme avant.

#include "res://shaders/surface_detail.gdshaderinc"
#include "res://shaders/couleur_srgb.gdshaderinc"

global uniform vec3 wind_dir;
global uniform float wind_strength;
global uniform float wind_gust;
global uniform float wind_phase;
// Saisons (lot P18, season_model.gd) : valeurs par défaut de project.godot = été, rendu inchangé.
global uniform vec3 season_leaf_tint;
global uniform float season_autumn;
global uniform float season_bare;
global uniform float season_blossom;
global uniform vec3 season_grass_tint;
global uniform float season_grass_dry;

uniform float sway_amplitude_m = 0.45;   // déplacement de la cime par vent de 60 km/h, en mètres
uniform float sway_height_m = 5.4;       // hauteur du modèle (cime)
uniform float sway_frequency_hz = 0.35;  // oscillation par vent calme ; × 1,6 en pleine rafale
uniform float roughness_value = 0.85;
// Vent propre au matériau (touffes d'herbe : vent apparent) quand use_local_wind est vrai.
uniform bool use_local_wind = false;
uniform vec3 local_wind_dir = vec3(0.0);
uniform float local_wind_strength = 0.0;
// Fondu avec la distance (touffes d'herbe, Lot Y11 H4) : au-delà de thin_start_m, une part croissante des
// instances est repliée (tirage par la position), puis toutes le sont à fade_end_m. 0 : pas de fondu.
uniform float thin_start_m = 0.0;
uniform float fade_end_m = 0.0;
// Tirage du fondu lu dans INSTANCE_CUSTOM.x (touffes d'herbe, lot « herbe au loin ») plutôt que haché depuis la
// position : le script choisit alors côté CPU les touffes de la gerbe lointaine avec le même tirage.
uniform bool pick_from_custom = false;
// Niveau de détail par instance (lot « herbe au loin ») : instance montrée de lod_begin_m à lod_end_m mètres de
// la caméra principale (0 : sans borne), repliée en taille sur lod_blend_m mètres de part et d'autre, pour que
// le modèle proche et le modèle lointain se relaient sans saut. Distance à la caméra principale
// (MAIN_CAM_INV_VIEW_MATRIX) : la passe d'ombre replie les mêmes instances que l'image.
uniform float lod_begin_m = 0.0;
uniform float lod_end_m = 0.0;
uniform float lod_blend_m = 4.0;
// Faces arrière (copie cull_disabled) : garde la normale du sommet au lieu de la retourner, pour des brins
// éclairés des deux côtés comme le sol (touffes d'herbe, Lot Y11 H4).
uniform bool normals_up_both_sides = false;
// Teinte du feuillage, neutre par défaut ; réglée par les saisons (P18, version 2.0).
uniform vec3 foliage_tint : source_color = vec3(1.0);
// Herbe : pied plus sombre, pointe plus claire (0 = aucun dégradé ; arbres : toujours 0)
uniform float root_darken : hint_range(0.0, 1.0) = 0.0;
// Saisons (lot P18) : espèce à feuilles caduques (feuillage d'automne, dénudée l'hiver), herbe (jaunie),
// verger (en fleurs au printemps). Posés par tree_renderer.gd, grass_tufts.gd et ground_details.gd.
uniform bool deciduous = false;
uniform bool grass = false;
uniform bool orchard = false;
// Panneaux croisés de loin : un feuillu nu garde une couronne de rameaux gris-brun (feuillage non replié).
uniform bool bare_as_twigs = false;
const vec3 SEASON_DRY_GRASS = vec3(0.62, 0.6, 0.32);

// Position du sommet dans l'objet (avant le vent : les motifs suivent l'arbre) et décalage propre à l'arbre.
varying vec3 v_obj;
varying vec3 v_shift;
varying float v_pick;   // tirage propre à l'arbre (palette d'automne)
varying float v_bare;   // 1 : arbre nu cet hiver

void vertex() {
	vec3 dir = use_local_wind ? local_wind_dir : wind_dir;
	float strength = use_local_wind ? local_wind_strength : wind_strength;
	float h = clamp(VERTEX.y / sway_height_m, 0.0, 1.0);
	vec3 origin = MODEL_MATRIX[3].xyz;
	float offset = fract(sin(dot(origin.xz, vec2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
	v_obj = VERTEX;
	// Décalage continu (ajouté à la position, jamais haché dans fragment()) : chaque arbre a ses motifs
	v_shift = vec3(offset * 7.3, offset * 1.7, offset * 5.1);
	v_pick = fract(offset * 5.37);
	// Hiver (lot P18) : feuillage d'une part des feuillus replié en un point (aucun pixel, aucune défausse).
	v_bare = 0.0;
	if (deciduous && season_bare > 0.0 && fract(offset * 3.71) < season_bare) {
		v_bare = 1.0;
		int leaf_code = int(floor(COLOR.a * 16.0 + 0.5));
		if ((leaf_code == 8 || leaf_code == 9) && !bare_as_twigs) {
			VERTEX = vec3(0.0);
		}
	}
	float freq = sway_frequency_hz * (1.0 + 0.6 * wind_gust);
	float swing = 0.55 + 0.45 * sin(wind_phase * freq * 6.2831853 + offset);
	float amp = sway_amplitude_m * strength * (1.0 + 0.8 * wind_gust) * h * h * swing;
	vec3 local_disp = inverse(mat3(MODEL_MATRIX)) * (dir * amp);
	VERTEX += vec3(local_disp.x, 0.0, local_disp.z);
	if (fade_end_m > 0.0 || lod_begin_m > 0.0 || lod_end_m > 0.0) {
		float d = distance(origin, MAIN_CAM_INV_VIEW_MATRIX[3].xyz);
		float size = 1.0;
		if (fade_end_m > 0.0) {
			float keep = 1.0 - smoothstep(thin_start_m, fade_end_m, d);
			float pick = pick_from_custom ? INSTANCE_CUSTOM.x : fract(offset * 7.31);
			// Une instance gardée rétrécit doucement quand elle approche de son seuil, au lieu de disparaître d'un coup
			size = clamp((keep - pick) * 8.0, 0.0, 1.0);
		}
		if (lod_end_m > 0.0) {
			size *= clamp((lod_end_m + lod_blend_m - d) / lod_blend_m, 0.0, 1.0);
		}
		if (lod_begin_m > 0.0) {
			size *= clamp((d - lod_begin_m + lod_blend_m) / lod_blend_m, 0.0, 1.0);
		}
		VERTEX *= size;
	}
}

// Bruit de valeur 3D (deux tranches 2D de sd_noise), de 0 à 1
float n3(vec3 p) {
	float k = floor(p.z);
	float t = fract(p.z);
	t = t * t * (3.0 - 2.0 * t);
	return mix(sd_noise(p.xy + k * vec2(17.13, 31.71)), sd_noise(p.xy + (k + 1.0) * vec2(17.13, 31.71)), t);
}

// Lignes de niveau d'un bruit : 0 sur la ligne, 1 entre deux (crevasses, joints de plaques)
float contour(float f, float count, float width) {
	float r = fract(f * count);
	return smoothstep(0.0, width, r) * smoothstep(1.0, 1.0 - width, r);
}

void fragment() {
	if (normals_up_both_sides && !FRONT_FACING) {
		NORMAL = -NORMAL;
	}
	int code = int(floor(COLOR.a * 16.0 + 0.5));
	vec3 col = COLOR.rgb * srgb(foliage_tint);   // teinte en sRGB, convertie à l'écriture
	if (deciduous && (code == 8 || code == 9)) {
		// Automne : jaune, orange ou roux selon l'arbre, à la luminosité de la feuille ; puis teinte de la saison
		vec3 hue = v_pick < 0.4 ? vec3(0.95, 0.74, 0.18) : (v_pick < 0.75 ? vec3(0.92, 0.45, 0.12) : vec3(0.62, 0.24, 0.10));
		float lum = dot(col, vec3(0.3, 0.59, 0.11));
		col = mix(col, hue * lum * 2.4, season_autumn * (0.7 + 0.3 * v_pick));
		col *= season_leaf_tint;
		if (bare_as_twigs && v_bare > 0.5) {
			// Rameaux nus vus de loin : gris-brun, plus sombres au cœur
			col = vec3(0.30, 0.26, 0.23) * (0.8 + 0.5 * v_pick);
			code = 7;   // motif des tiges, sans reflets de feuilles
		}
	}
	if (grass) {
		col = mix(col, col * 0.55 + SEASON_DRY_GRASS * 0.45, season_grass_dry) * season_grass_tint;
	}
	float rough = roughness_value;
	float through = 0.0;   // part de lumière qui traverse les feuilles
	vec3 p = v_obj + v_shift;
	float near = sd_visible(vec2(p.x + p.z, p.y), 0.08);
	float mid_vis = sd_visible(vec2(p.x + p.z, p.y), 0.3);
	if (code >= 1 && code <= 10) {
		if (code == 1) {
			// Écorce crevassée (chêne, épicéa, olivier…) : crevasses verticales, lignes de niveau d'un bruit étiré
			float f = n3(p * vec3(5.0, 0.7, 5.0));
			float ridge = contour(f, 3.0, 0.35);
			col *= mix(0.42, 1.1, ridge) * (0.9 + 0.2 * n3(p * 4.0));
			rough = 0.95;
		} else if (code == 2) {
			// Écorce lisse (hêtre, baobab) : marbrures et plaques de lichen
			float m = n3(p * vec3(3.0, 1.0, 3.0));
			col *= 0.88 + 0.22 * m;
			col = mix(col, col * vec3(0.95, 1.05, 0.85) + 0.05, smoothstep(0.62, 0.72, n3(p * 1.7 + 4.0)) * 0.6);
		} else if (code == 3) {
			// Bouleau : blanc, lenticelles sombres horizontales, pied noirci
			float l = n3(p * vec3(3.5, 28.0, 3.5));
			float dark = smoothstep(0.64, 0.7, l) * near;
			col = mix(col, vec3(0.08, 0.07, 0.06), dark);
			col = mix(col, vec3(0.12, 0.1, 0.08), (1.0 - smoothstep(0.3, 1.4, v_obj.y + 0.4 * n3(p * 3.0))) * 0.85);
			rough = 0.7;
		} else if (code == 4) {
			// Écorce en plaques (pins, mélèze) : plaques rousses séparées de joints sombres
			float f = n3(p * vec3(3.2, 1.2, 3.2));
			float plate = contour(f, 4.0, 0.18);
			col *= mix(0.35, 1.15, plate) * (0.85 + 0.3 * n3(p * vec3(6.0, 2.0, 6.0)));
			rough = 0.95;
		} else if (code == 5) {
			// Stipe de palmier : anneaux des anciennes palmes
			float r = fract(v_obj.y * 3.2 + 0.3 * n3(p * 2.0));
			float ring = smoothstep(0.0, 0.3, r) * (1.0 - smoothstep(0.75, 1.0, r));
			col *= mix(0.55, 1.05, ring);
		} else if (code == 6) {
			// Cactus : côtes verticales (12 par tour) et aréoles claires
			float rib = 0.5 + 0.5 * cos(atan(v_obj.z, v_obj.x) * 12.0);
			col *= 0.72 + 0.4 * rib;
			float spot = smoothstep(0.8, 0.86, n3(p * vec3(14.0, 10.0, 14.0))) * rib * near;
			col = mix(col, vec3(0.85, 0.82, 0.7), spot * 0.7);
			rough = 0.6;
		} else if (code == 7) {
			// Ceps et tiges : fibres longitudinales
			col *= 0.8 + 0.35 * n3(p * vec3(12.0, 1.5, 12.0));
		} else {
			// Feuillage : touffes (mètre) et feuilles (décimètre), dessous et intérieur plus sombres
			float clump = n3(p * 1.4);
			float leaf = mix(0.5, n3(p * (code == 9 ? 11.0 : 7.0)), near);
			// Bouquets de feuilles (30 cm) et trouées sombres entre eux
			float twig = mix(0.5, n3(p * 3.5 + 11.0), mid_vis);
			float m = clump * 0.45 + twig * 0.35 + leaf * 0.2;
			m -= smoothstep(0.3, 0.2, twig) * 0.2 * mid_vis;
			if (code == 9) {
				// Aiguilles : étages de branches et teinte plus froide
				float tier = fract(v_obj.y * 0.9 + clump * 0.6);
				m = m * 0.7 + 0.3 * smoothstep(0.0, 0.5, tier);
				col *= vec3(0.95, 1.0, 1.05);
			} else if (code == 10) {
				// Palmes et frondes : folioles en lanières
				m = m * 0.4 + 0.6 * mix(0.5, 0.5 + 0.5 * sin((p.x + p.z) * 14.0), mid_vis);
			}
			col *= mix(0.55, 1.3, clamp(m, 0.0, 1.0));
			// Reflets jaunes des feuilles au soleil
			col = mix(col, col * vec3(1.18, 1.12, 0.7), smoothstep(0.62, 0.9, leaf) * 0.45);
			if (orchard && code == 8 && season_blossom > 0.0) {
				// Vergers en fleurs : bouquets blancs et roses sur le feuillage
				float bloom = smoothstep(0.58, 0.68, n3(p * 6.0 + 23.0)) * season_blossom;
				col = mix(col, mix(vec3(1.0, 0.96, 0.97), vec3(0.98, 0.78, 0.86), v_pick), bloom);
			}
			through = code == 9 ? 0.25 : 0.5;
			rough = 0.8;
		}
	}
	if (through > 0.0) {
		// Houppier vu comme un volume : normale tirée vers le haut (dessous moins noir), lumière à travers
		vec3 up_view = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
		NORMAL = normalize(mix(NORMAL, up_view, 0.35));
		BACKLIGHT = lineaire(col) * through;
		// Lumière du ciel diffusée par les feuilles : un houppier à l'ombre reste vert, pas noir
		EMISSION = lineaire(col) * through * 0.15;
	}
	if (root_darken > 0.0) {
		float hh = clamp(v_obj.y / sway_height_m, 0.0, 1.0);
		col *= mix(1.0 - root_darken, 1.0 + root_darken * 0.25, hh);
	}
	ALBEDO = lineaire(col);
	ROUGHNESS = rough;
}
