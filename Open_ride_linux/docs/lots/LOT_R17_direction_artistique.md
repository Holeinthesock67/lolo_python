# Lot R17 – Direction artistique du mode Cyber-Rogue : charte néon, matériaux, shaders et catalogue des objets graphiques

## 1. Objectif

Demande du propriétaire du 27 octobre : ne pas oublier le graphisme du Cyber-Rogue, avec des objets graphiques de style néon vectoriel (lignes lumineuses sur fond sombre, motos et murs de lumière). Les lots R10 à R13 disaient **où** dessiner (ruban, ennemis, HUD, menus) mais pas **à quoi tout cela ressemble** : ni palette commune, ni matériaux partagés, ni portes, ni cartes, ni vélo du joueur, ni post-traitement chiffré, ni liste complète des effets.

Ce lot fixe la charte et livre la boîte à outils graphique commune, **avant** R10 à R12, qui l'utilisent. Il ne change aucune règle de jeu ni aucune décision déjà prise (boutons, couleurs de pente de R10, effets de R11).

Principe : **tout est généré par le code** (maillages procéduraux, primitives Godot, shaders, particules GPU). Aucune texture ni aucun modèle dans le dépôt (invariant A9 de la spécification générale). Aucun nom d'œuvre ni de marque existante dans les fichiers, nœuds, ressources ou textes (risque 7 du plan).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/GDD_CYBER_ROGUE.md` §1.3, §2.5 et §3.1 (avec leurs corrections), `docs/2.0/PLAN_SERIE_R.md`, `docs/SPECIFICATION_GENERALE.md` §3 (A9) et §7.2 (vues de caméra).
2. `docs/lots/LOT_R10_scene_neon_ruban.md`, `LOT_R11_hud_diegetique.md`, `LOT_R12_ennemis_boss.md`, `LOT_R13_menu_cyber_rogue.md`.
3. Code : `engine/scripts/quality_presets.gd`, `render_quality.gd` (lot L4), `theme_render_params.gd`, `engine/tests/run_visual_tests.sh` et `engine/tests/visual_check.py` (captures d'écran comparées).

## 3. Prérequis

T1 livré (noms des marqueurs et des événements). Aucun autre : ce lot se fait avant R10.

## 4. Travail demandé

### 4.1 Charte (dans ce cahier, recopiée en tête de `neon_palette.gd`)

**Palette.** Des jetons nommés, jamais de couleur écrite en dur ailleurs :

| Jeton | Valeur de départ | Usage |
| --- | --- | --- |
| `void` | #05060F | Fond, vide sous la piste |
| `night` | #0B1030 | Horizon, brume lointaine |
| `grid` | #1E6BFF, intensité 0,35 | Grille au sol |
| `player` | #18F0FF | Vélo du joueur, sa traînée, arc du bouclier |
| `energy` | #FF8A1E | Adrénaline, cibles d'attaque, coups |
| `parry` | #2E7BFF | Zones de parade, aspiration |
| `gold` | #FFD23C | Arches de Perfect Shift, or, coffres |
| `danger` | #FF2E4C | Firewall, défaite, salle manquée, phase 3 du boss |
| `glitch` | #C23CFF | Saboteur, piratage |
| `neutral` | #E8F0FF | Textes et chiffres du HUD |

Les cinq couleurs de pente de R10 (bleu, cyan, jaune, orange, magenta) restent celles de R10 et deviennent elles aussi des jetons.

**Formes.** Lignes et arêtes lumineuses sur volumes sombres : chaque objet est un volume presque noir (`void` éclairci de 10 %) dont les arêtes portent une ligne émissive de la couleur de son rôle. Pas de dégradé photo, pas de texture.

**Lisibilité.** Une couleur = un rôle, dans toute la scène et le HUD. Le joueur est toujours la seule source cyan ; le danger est toujours rouge.

**Mouvement.** Les objets du décor bougent lentement (pulsation de 0,5 à 1 Hz) ; seuls les événements de jeu clignotent vite, et jamais plus de 3 fois par seconde (§4.6).

### 4.2 Matériaux et shaders partagés

| Fichier | Contenu |
| --- | --- |
| `engine/scripts/rogue/neon_palette.gd` | Jetons du §4.1, intensités par préréglage de qualité, variante « couleurs adaptées » (§4.6) |
| `engine/scripts/rogue/neon_materials.gd` | Fabrique de matériaux : `edge(color, width)`, `glass(color, alpha)`, `hologram(color)`, `wall(color)` ; mise en cache, un seul matériau par jeton et par sorte |
| `engine/scripts/rogue/neon_edge.gdshader` | Arêtes lumineuses par coordonnées barycentriques ou distance au bord de l'UV, épaisseur constante à l'écran |
| `engine/scripts/rogue/neon_grid.gdshader` | Grille infinie au sol, lignes antialiasées, fondu avec la distance, défilement selon la vitesse du joueur |
| `engine/scripts/rogue/hologram.gdshader` | Lignes de balayage fines, scintillement léger, transparence (HUD de R11, cartes, portes) |
| `engine/scripts/rogue/glitch.gdshader` | Décalage de bandes et séparation des couleurs, intensité de 0 à 1 (piratage, salle manquée, défaite) |
| `engine/scripts/rogue/energy_wall.gdshader` | Mur de lumière translucide et ondulant (Firewall, traînées, mur du Puncheur) |
| `engine/scripts/rogue/rogue_environment.gd` | Réglages de l'`Environment` Godot : fond `void`, brume `night`, glow (seuil, intensité, bloom) et correction de couleur par préréglage |

### 4.3 Environnement et post-traitement

| Préréglage | Glow | Bloom | Brume | Particules | Aberration chromatique |
| --- | --- | --- | --- | --- | --- |
| `low` | 3 niveaux, intensité 0,8 | 0,05 | Linéaire, 400 m | 25 % | Non |
| `medium` | 5 niveaux, intensité 1,0 | 0,10 | Linéaire, 600 m | 60 % | Non |
| `high` | 7 niveaux, intensité 1,1 | 0,15 | Exponentielle, 900 m | 100 % | Légère, seulement pendant les effets de glitch |

- Horizon : un soleil couchant en bandes horizontales (`gold` vers `danger`, disque découpé par des lignes), des montagnes en fil de fer (`grid`), le tout sur un ciel `night` sans texture. Couper le soleil en `low` si le budget n'est pas tenu.
- Pas de lumière dynamique hors du joueur : tout l'éclairage vient des matériaux émissifs et du glow.

### 4.4 Catalogue des objets graphiques

| Objet | Description | Lot qui l'intègre |
| --- | --- | --- |
| Vélo du joueur | Silhouette de vélo en arêtes `player` (cadre, deux roues pleines lumineuses, rayons qui tournent avec la cadence), cycliste stylisé en volumes sombres à arêtes ; visible dans les vues de suivi, masqué en vue subjective (§7.2 de la spécification générale) | R10 |
| Traînée du joueur | Ruban de lumière `player` derrière la roue arrière, longueur proportionnelle à la vitesse (5 à 30 m), qui s'épaissit pendant un sprint | R10 |
| Ruban de piste | Ruban de R10, bords en arêtes de la couleur de pente, surface sombre avec la grille par-dessus, flèches lumineuses tous les 50 m | R10 |
| Arche de Perfect Shift | Arche `gold` en deux montants et une barre, qui s'allume pendant la fenêtre puis éclate en particules au succès | R10 |
| Cible d'attaque [Z] | Losange `energy` flottant au-dessus de la piste, qui tourne ; se brise en éclats au coup | R10 |
| Zone de parade [Z] | Bande de sol `parry` en chevrons qui défilent vers le joueur | R10 |
| Balise de purge | Anneau `glitch` vertical qui pulse, se referme au succès | R10 |
| Tunnel de cadence | Anneaux `player` espacés de 10 m, qui s'allument tant que la cadence est dans la plage | R10 |
| Rocher d'armure | Polyèdre sombre à arêtes `energy`, fissures lumineuses à chaque point d'armure perdu | R10, R12 |
| Pavé de boost | Rectangle `gold` au sol, flèches qui accélèrent | R10 |
| Firewall | Mur `danger` sur toute la largeur de la piste, ondulation d'`energy_wall`, grésillement plus fort à moins de 30 m, flash au contact | R10 |
| Ennemis et boss | Formes de R12, toutes en volumes sombres à arêtes de leur couleur (Diesel `energy`, Puncheur `parry` avec mur de lumière derrière lui, Grimpeur `gold`, Sprinteur `neutral`, Saboteur `glitch`, Chimère qui change de couleur à chaque phase puis `danger`) | R12 |
| Portes du couloir | Deux portails rectangulaires à gauche et à droite de la piste, cadre lumineux de la couleur de l'archétype, symbole de l'archétype en fil de fer au centre, porte sélectionnée plus lumineuse et animée | R13 |
| Cartes | Panneaux holographiques flottants (shader `hologram`), cadre de la couleur du type (terraformeur `gold`, pignon `player`, module `parry`, carte active `energy`, relique `neutral`), pictogramme vectoriel tracé par le code, texte court ; carte sélectionnée avancée et plus lumineuse | R13 |
| Coffres de fin | Cubes `gold` qui s'ouvrent en éventail de lignes | R13 |
| HUD de run | Hologramme et arcs de R11 en jetons de la charte ; chiffres en police à chasse fixe, contour sombre pour rester lisible sur le glow | R11 |
| Écrans de menu du mode | Départ, prêt, pause et bilan du mode avec le fond `void`, la grille qui défile et les cadres holographiques | R13 |

### 4.5 Catalogue des effets

| Événement | Effet visuel | Durée |
| --- | --- | --- |
| `perfect_shift` | Éclat de l'arche, onde `gold` au sol, tremblement de R11 | 0,4 s |
| `hit`, `crit` | Éclats `energy` sur l'ennemi, flash de 0,1 s ; plus gros et plus nombreux pour `crit` | 0,3 s |
| `parry` | Onde de choc `parry` qui se brise devant le vélo | 0,4 s |
| `parry_miss` | Onde qui traverse le vélo, bords de l'écran `danger` | 0,5 s |
| `firewall_contact` | Grésillement `glitch` léger et bords `danger` tant que le contact dure | continu |
| Piratage | Bandes `glitch` sur la vitesse affichée, cubes du Saboteur autour du vélo | durée du piratage |
| `room_won` | L'ennemi se désagrège en lignes qui montent, pluie d'or | 1,5 s |
| `room_fled` | L'ennemi s'éloigne et s'éteint | 1,5 s |
| `room_skipped` | Effet de R11 (bandeau, grésillement rouge 0,5 s), rendu avec `glitch.gdshader` | 3 s |
| `defeat` | Écran qui se désature, grand grésillement `danger`, piste qui se fragmente puis se recompose pendant la récupération | 2 s |
| Phases du boss | Changement de couleur de la Chimère, piste qui se teinte, phase 3 tout en `danger` | 1 s |

### 4.6 Confort et accessibilité

- **Clignotements :** jamais plus de 3 éclairs par seconde, jamais de grand flash plein écran blanc ou rouge (règle de prudence pour les personnes photosensibles) ; le réglage « réduire les mouvements » (O4) coupe aussi le tremblement, l'aberration chromatique et les grands grésillements.
- **Couleurs adaptées :** variante de palette où le danger et l'énergie se distinguent aussi par la forme (motifs hachurés, pictogrammes), pour les personnes daltoniennes ; réglage booléen lu par `neon_palette.gd`.
- **Lisibilité à l'effort :** les chiffres du HUD gardent un contraste d'au moins 7:1 sur leur fond, glow compris.

### 4.7 Images d'ambiance (facultatif)

Le propriétaire peut faire générer par une IA d'images (par exemple Gemini) des planches d'ambiance pour valider la charte avant R10. Ces images restent **hors du dépôt** (dossier local sous `~/OpenRide/`), servent seulement de référence et ne sont jamais chargées par le jeu. Leurs consignes de génération ne citent aucune œuvre ni marque.

### 4.8 Scène de démonstration

- `engine/scenes/rogue_style_sheet.tscn` : une planche qui montre côte à côte chaque objet du §4.4, chaque effet du §4.5 rejouable à la touche, et les trois préréglages. C'est l'outil de validation de la charte, avant la vraie scène de R10.

## 5. Fichiers concernés

- **Créés :** `engine/scripts/rogue/neon_palette.gd`, `neon_materials.gd`, `rogue_environment.gd`, les cinq shaders du §4.2, `engine/scenes/rogue_style_sheet.tscn`, `engine/tests/unit/test_neon_palette.gd`, `engine/tests/unit/test_neon_materials.gd`.
- **Modifiés :** `engine/tests/run_visual_tests.sh` (captures de la planche dans les trois préréglages), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, toute texture ou tout modèle importé.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests sans écran : chaque jeton du §4.1 existe, la variante « couleurs adaptées » change danger et énergie ; la fabrique renvoie le même matériau pour le même jeton (cache) ; aucun fichier `.png`, `.jpg`, `.glb` ou `.obj` ajouté au dépôt.
2. Contraste des chiffres du HUD d'au moins 7:1 (calcul du test sur les jetons).
3. Aucun effet du §4.5 ne clignote plus de 3 fois par seconde (test sur les courbes d'animation).
4. Captures de la planche dans les trois préréglages produites par `run_visual_tests.sh`.
5. Sur la GTX 1060 en `low`, la planche complète tourne à 60 images/s ou plus ; contrôle visuel et accord du propriétaire sur la charte (couleurs, formes, effets) avant le début de R10.

## 8. Hors périmètre

- Placement des objets dans la scène de jeu (R10 à R13), sons (R11).
- Avatar et équipement de la série V hors du mode Cyber-Rogue.
