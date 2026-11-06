# Plan de la série VD : modèle « Vélodrome »

Demande du propriétaire du 5 novembre 2026 : « J'aimerais ajouter un modèle vélodrome au 4.0 ». Lecture retenue : un nouveau type de parcours, une piste ovale fermée à virages relevés, sans route ni terrain, utilisable en séance libre, en ERG et dans des épreuves de piste. Plan validé par le propriétaire le 6 novembre 2026 (décisions au §10). Toute maquette est soumise au propriétaire avant le code d'affichage, et tout essai de performance se fait en `low`, `medium` **et** `high`, captures à l'appui.

Sources lues : `docs/contracts/world_format_v1.md` (§4 couche route, `type = loop`), `core/src/openride_core/route.py` (Catmull-Rom, `wrap`), `demo_world.py` (parcours synthétiques écrits par le core), `surface_physics.py` (facteur de Crr par surface), `draft.py` et `lane_m` (AS2), `bots.py`, `engine/scripts/road_builder.gd` (coupe plate de 6 m perpendiculaire au cap), `camera_follow.gd` et `bots_view.gd` (écart à l'axe), `crowd_renderer.gd`, `docs/4.0/PLAN_SERIE_GP.md`, `docs/2.0/PLAN_SERIE_DS.md`, `docs/lots/00_INDEX.md`.

---

## 1. En bref

1. **Un type de parcours, pas un mode à part** : le vélodrome est un `.world` en boucle (`type = loop`) que le core génère lui-même, sans GPX ni compilateur, comme le parcours de démonstration. Il apparaît dans la liste des parcours (filtre « Vélodrome ») et se roule avec tout ce qui existe déjà : séance libre, ERG, plans, bots, fantôme, abri.
2. **Une seule piste : 250 m couverte en bois**, virages relevés à 42° et lignes droites à 12°, 7 m de large plus la côte d'azur (§3). Décision du propriétaire du 6 novembre : « On fera une piste de 250 m. En bois avec virages relevés. »
3. **Le relèvement ne touche pas le trainer** : sur une piste, la pente le long de la trajectoire est nulle. La pente envoyée reste 0 % ; seuls la surface (bois, Crr plus faible), l'air sans vent et l'abri se ressentent. Le relèvement est **visuel** (ruban incliné, caméra et coureurs qui penchent) et **géométrique** (rouler plus haut allonge le tour, §4.2).
4. **Toutes les épreuves de piste dès la première livraison** (§5, décision du propriétaire du 6 novembre) : poursuite individuelle, kilomètre et 500 m départ arrêté, 200 m lancé, scratch, course aux points, tempo, élimination (règles de DS reprises), keirin (derny, véhicule et abri d'AS6), omnium et record de l'heure, plus les trois épreuves par équipes (vitesse par équipes, poursuite par équipes, américaine), ajoutées par le propriétaire le 6 novembre.
5. **Un décor unique, une salle couverte** (décision du propriétaire du 6 novembre : « On fera un unique décor. On considère un circuit intérieur. ») : un bâtiment léger : salle, tribunes, public, éclairage ; pas de terrain, de végétation, de biome ni de ciel lointain. Le vélodrome couvert doit coûter **nettement moins** que la route (§7) : c'est le parcours le plus léger du jeu.
6. **Version : 4.0**, après le peloton PL1 (bots en piste) et AS2 (voies). Seul le générateur de piste (VD2) et la physique (VD3) sont des modules purs du core, faisables plus tôt si le propriétaire le veut.

## 2. Ce qui change et ce qui reste

| Élément | Sur le vélodrome | Pourquoi |
| --- | --- | --- |
| Pente envoyée (SIM) | 0 % partout | Une piste est plane le long de la trajectoire ; le relèvement est perpendiculaire au sens de marche |
| Difficulté (Q1) | Sans effet visible (elle multiplie une pente nulle) | Inchangée, pas d'exception |
| Surface | `wood` (bois), nouveau facteur de Crr (§4.1) | Une piste en bois roule mieux qu'une route |
| Vent (P) | Coupé | Pas de vent dans une salle |
| Abri (AS1 à AS5) | Identique, avec les voies de la piste (§4.3) | C'est le cœur des épreuves de piste |
| ERG, plans, séance .zwo | Identiques | Le vélodrome est un parcours comme un autre |
| Bonus T6/TT, objets GP | Coupés dans les épreuves, gardés en séance libre | Records honnêtes |
| Segments, sprints, montées (T) | Remplacés par les tours : temps au tour, meilleur tour, 200 m lancé | Il n'y a ni montée ni sprint de route |
| Records | Par piste et par épreuve (fichier existant des records, clé de parcours `velodrome-250` etc.) | Pas de mélange avec la route |
| Journal, FIT | Identiques ; le FIT marque chaque tour (`lap`) | Lisible dans GoldenCheetah |
| Braquets | Braquets virtuels gardés ; option « Braquet fixe » (un seul rapport, sans changement) | Réaliste sans rien imposer |

## 3. La piste

### 3.1 Géométrie de référence (250 m)

| Grandeur | Valeur proposée |
| --- | --- |
| Longueur à la ligne de mesure | 250,00 m (exactement, à ± 0,05 m) |
| Largeur de piste | 7,0 m, plus une côte d'azur de 1,0 m (bande bleue à l'intérieur, non relevée) et une zone de sécurité de 4 m |
| Rayon des virages (à la ligne de mesure) | environ 23 m |
| Lignes droites | environ 2 × 40 m |
| Raccordements | Clothoïdes (courbure qui varie linéairement), environ 2 × 18 m par virage, pour un relèvement et une courbure continus |
| Relèvement | 12° dans les lignes droites, 42° au sommet des virages, variation douce dans les raccordements |
| Lignes peintes | Ligne de mesure noire à 0,20 m du bord intérieur, ligne des sprinteurs rouge à 0,85 m, ligne des stayers bleue à 2,45 m ; ligne d'arrivée, ligne des 200 m, lignes de poursuite au milieu des deux lignes droites |

Les chiffres sont ceux des pistes de 250 m courantes ; le générateur résout les longueurs exactes (droites et clothoïdes) pour tomber sur 250,00 m.

### 3.2 Repères physiques utiles

- **Vitesse d'équilibre du virage** (aucune force de côté) : v = √(g · R · tan θ) ≈ √(9,81 × 23 × 0,90) ≈ 14,4 m/s, soit **52 km/h**. En dessous, un vrai coureur appuie vers l'intérieur ; au-dessus, vers l'extérieur.
- **Vitesse minimale dans le virage** avant de glisser (adhérence 0,8) : √(g · R · tan(θ − arctan 0,8)) ≈ **13 km/h**. Sous environ 15 km/h dans un virage, le coureur redescend tout seul vers la côte d'azur (§4.3), comme dans la réalité.

### 3.3 Une seule piste

Décision du propriétaire du 6 novembre : une seule piste, `velodrome-250` (250 m, bois, 42° / 12°, couverte). Le générateur garde la forme en paramètres (longueur, rayon, relèvement), sans autre piste listée : une autre longueur (333 m, 400 m) resterait une ligne de table si elle était demandée un jour, pas du code.

## 4. Physique

### 4.1 Surface et air (lot VD3)

- Deux surfaces nouvelles dans `surface_physics.py`, au même endroit que `compacted`, `gravel` et `dirt` : `wood` (Crr × 0,6 environ, Crr de l'ordre de 0,0025 avec un boyau de piste), au même titre que les autres surfaces. Le supplément de pente équivalent existant (`grade_offset_pct`) devient **négatif** sur le bois : la résistance baisse un peu, sous la même borne et avec les mêmes rampes que l'abri et le vent.
- Air : densité de la salle (`[velodrome] temperature_c`, 24 °C par défaut). Pas de nouveau calcul : `RiderPhysics` reçoit la densité comme aujourd'hui.

### 4.2 Hauteur sur la piste et distance

- L'écart latéral `lane_m` d'AS2 devient, sur le vélodrome, la **distance mesurée sur la piste depuis la ligne de mesure, vers le haut**. La position 3D est calculée en remontant la pente du relèvement (hauteur = écart × sin θ, retrait horizontal = écart × cos θ).
- La distance comptée reste celle de la ligne de mesure (un tour = 250 m), mais le coureur parcourt plus : dans les virages, son rayon vaut R + écart × cos θ. Le core fait avancer `s` de v × R / (R + écart × cos θ) dans les virages. Rouler 1 m plus haut coûte environ 5 m par tour : c'est ce qui rend la corde intérieure intéressante et les dépassements coûteux, sans aucune règle spéciale.

### 4.3 Placement

- Placement automatique d'AS2 repris : le coureur reste à la corde (ligne des sprinteurs) et monte pour doubler.
- Sous 15 km/h dans un virage, descente automatique vers la côte d'azur.
- Départ arrêté (kilomètre, 500 m, poursuite) : la séance part de 0 km/h ; la mise en action dépend de la résistance à basse vitesse (lot RC4), essai vélo dédié dans VD12.

## 5. Épreuves (lot VD6)

| Épreuve | Format proposé | Adversaires | Repris de |
| --- | --- | --- | --- |
| Séance libre / ERG | Tours illimités, temps au tour | Bots et fantôme facultatifs | Classique |
| Poursuite individuelle | 3 ou 4 km, départ arrêté sur la ligne de poursuite, contre le fantôme ou un bot parti de l'autre côté | 1 | Fantôme, `replay.py` |
| Kilomètre / 500 m | Départ arrêté, seul contre la montre | 0 (fantôme facultatif) | Records |
| 200 m lancé | 2 tours et demi d'élan, temps chronométré sur les 200 derniers mètres | 0 | Records |
| Scratch | 10 à 60 tours, premier à l'arrivée | 3 à 11 bots | Peloton PL1 |
| Course aux points | Sprint tous les 10 tours (5, 3, 2, 1 points, double au dernier), 20 points par tour pris | 3 à 11 bots | Maillots T14 (barème) |
| Élimination | Le dernier sort tous les 2 tours | 3 à 11 bots | Règles et code de DS (`survivor.py`) |
| Record de l'heure | 60 min, distance totale, tableau des tours | 0 | Records |
| Vitesse par équipes | 3 coureurs, 3 tours départ arrêté ; chacun mène un tour puis s'écarte ; le joueur choisit sa place (1, 2 ou 3) ; contre une autre équipe de bots partie de l'autre côté | 2 coéquipiers + 3 adversaires | Poursuite, abri AS1 |
| Poursuite par équipes | 4 coureurs, 4 km départ arrêté ; relais tous les demi-tours ou tours (réglable), le relayeur remonte et se replace en dernière position ; temps pris sur le 3e coureur | 3 coéquipiers + 4 adversaires | Poursuite, abri AS1 à AS4 |
| Américaine | Équipes de 2, course aux points ; le joueur et son coéquipier bot se relaient environ tous les tours et demi ; pendant son repos, le joueur roule en haut de la piste à allure libre (le bot court), puis reprend la course au relais (lancer simulé : la vitesse du coureur relancé est celle du relayé) | 1 coéquipier + 6 à 10 adversaires (3 à 5 équipes) | Course aux points |
| Keirin | Derny jusqu'à 3 tours de l'arrivée, puis sprint | 3 à 6 bots | Véhicule et abri d'AS6 |
| Tempo | 10 tours au moins ; à partir du 5e tour, 1 point au premier de chaque tour, 20 points par tour pris | 3 à 11 bots | Course aux points |
| Omnium | Enchaînement scratch, tempo, élimination, course aux points, classement aux points | 3 à 11 bots | Épreuves ci-dessus |

Chaque épreuve est un module pur du paquet `track/` du core (une règle, un fichier), comme `survivor.py` et `wtf/mode.py`. Les épreuves sont en **SIM** ; la séance libre accepte aussi l'ERG. Pause (Y) : tout est figé, épreuve comprise.

## 6. Bots (lot VD7)

- Peloton PL1 (environ 12 bots) en piste : voies par hauteur sur la piste, relais dans la ligne des stayers, attaques depuis le haut du virage (gain d'élan simulé par la règle de distance du §4.2, sans tricher sur la physique).
- Élimination : stratégie de DS (rester devant à l'approche du sprint). Course aux points : effort réparti sur les sprints. Poursuite : bot à allure constante calée sur un temps cible.
- Aucune règle physique propre aux bots : mêmes équations que le joueur.

## 7. Contrat, rendu et performances

### 7.1 Contrat (lot VD1, décision du propriétaire)

- **Format `.world`, mineur libre suivant** (ajout compatible) : colonne facultative `bank_deg` dans `route.json` (relèvement en degrés, positif quand l'extérieur du virage est plus haut ; absente = 0, toutes les routes actuelles inchangées) ; valeur `wood` pour la surface ; couche facultative `venue.json` (`kind = velodrome`, `track_width_m`, `apron_width_m`, lignes peintes en distance depuis le bord intérieur, tribunes, toit).
- **IPC, première révision libre à la fusion de VD1** (1.6 est prise par PL1) : objet facultatif `track` dans `state` (épreuve, tour, tours restants, cloche, points, classement, éliminé) et options d'épreuve passées par les commandes génériques `list_mode_options` et `set_mode_option` proposées par la série GP (pas de commandes propres au vélodrome). Pire trame contrôlée par l'outil X25 (budget de 4 096 octets).

### 7.2 Rendu (lots VD4 et VD5)

- **Ruban relevé** : `road_builder.gd` lit `bank_deg` et fait tourner la coupe autour de la ligne de mesure ; une seule coupe générique, la route classique étant le cas `bank_deg = 0` (pas de second constructeur). Lignes peintes par la texture, une coupe tous les 1 m dans les virages.
- **Caméra, avatar et bots** penchent avec le relèvement et la vitesse (`camera_follow.gd`, `bots_view.gd`) ; la caméra garde l'horizon de la salle lisible (inclinaison de la vue limitée à la moitié du relèvement, réglable).
- **Bâtiment** : salle procédurale (murs, toit à arcs, rampes d'éclairage émissives), tribunes en gradins, public par instances (`crowd_renderer.gd`), pelouse centrale avec bancs et home trainers d'échauffement. Un seul décor, intérieur, sans thème ni variante (décision du 6 novembre) : pas de ciel, de météo, de jour et nuit ni de saison sur le vélodrome.
- **Désactivé sur le vélodrome** : terrain, végétation, biome, bâtiments OSM, eau, circulation, cyclistes du décor, faune.

### 7.3 Performances (budgets GPU : low 6 ms, medium 12 ms, high 14 ms)

- **Critère 1** : sous le budget de chaque préréglage, au pire cas (départ du scratch avec 11 bots, tribunes pleines), en `low`, `medium` **et** `high`, au banc simulé (`sim_bench.py`, nouveau scénario `velodrome`) sur le PC cible.
- **Critère 2 (vélodrome couvert)** : au plus **70 % du budget** dans chaque préréglage (environ 4,2, 8,4 et 9,8 ms), puisqu'il n'y a ni terrain ni végétation. Un dépassement de ce seuil est expliqué avant la fusion.
- **Lumières** : une lumière directionnelle et l'ambiance de la salle ; les rampes sont émissives (pas une lumière par projecteur). Ombres : coureurs seulement, `low` sans ombres, `medium` ombres proches, `high` ombres douces.
- **Public** : `low` 1 000 spectateurs au plus en sprites, `medium` 3 000, `high` 6 000 animés par shader, tout par `MultiMesh`, aucune création pendant l'épreuve.
- **Reflets du bois** : rugosité seulement en `low` ; `medium` et `high` gardent les réglages SSIL et SSR des préréglages, sans réglage propre.
- Garde-fou des à-coups (`perf_targets.json`) et endurance de 30 min ; captures `low`, `medium`, `high` validées par le propriétaire avant fusion de VD4, VD5 et VD9.

## 8. Menus (lot VD10)

- Liste des parcours : filtre « Vélodrome » et fiches des pistes (longueur, surface, couvert ou non) ; pas de nouvelle entrée à l'accueil.
- Écran Prêt du vélodrome : choix de l'épreuve, puis de ses options (tours, distance, nombre de bots, adversaire de poursuite) ; « Séance libre » par défaut.
- Plan des boutons inchangé (spécification générale §7.1) : A court change de hauteur sur la piste (monter / redescendre à la corde) comme il change de voie ailleurs, A long rend la main au placement automatique.

## 9. Lots

| Lot | Titre | Dépend de | Taille |
| --- | --- | --- | --- |
| [VD0](../lots/LOT_VD0_decisions.md) | Décisions du propriétaire (pistes, épreuves, version) | — | Petite |
| [VD1](../lots/LOT_VD1_contrat.md) | Contrat : `bank_deg`, surface `wood`, couche `venue`, objet `track` de l'IPC | VD0 | Petite |
| [VD2](../lots/LOT_VD2_generateur_piste.md) | Core : générateur de pistes (droites, clothoïdes, virages, relèvement) | VD1 | Moyenne |
| [VD3](../lots/LOT_VD3_physique_piste.md) | Core : surface, air, hauteur sur la piste et distance | VD1, AS2 | Moyenne |
| [VD4](../lots/LOT_VD4_ruban_releve.md) | Engine : ruban relevé, lignes peintes, caméra et coureurs qui penchent | VD2 | Moyenne |
| [VD5](../lots/LOT_VD5_batiment_tribunes.md) | Engine : salle, tribunes, public, éclairage | VD2 | Grande |
| [VD6](../lots/LOT_VD6_epreuves.md) | Core : toutes les épreuves de piste (paquet `track/`) | VD3, DS1, AS6 | Grande |
| [VD7](../lots/LOT_VD7_bots_piste.md) | Bots en piste (peloton PL1) | VD3, VD6, PL1 | Moyenne |
| [VD8](../lots/LOT_VD8_maquettes.md) | Maquettes du HUD de piste, du tableau d'affichage et du bilan | VD6 | Petite |
| [VD9](../lots/LOT_VD9_hud_sons.md) | Engine : HUD de piste, tableau d'affichage, cloche, pistolet, public | VD6, VD8 | Moyenne |
| [VD10](../lots/LOT_VD10_menu.md) | Menu : filtre des pistes, écran Prêt et options d'épreuve | VD6 | Petite |
| [VD11](../lots/LOT_VD11_bancs.md) | Bancs GPU `low`, `medium`, `high` et captures | VD4, VD5, VD7, VD9 | Petite |
| [VD12](../lots/LOT_VD12_recette.md) | Recette sur le vélo (étapes de 10 min) | VD10, VD11 | Petite |

Ordre : VD0 ──► VD1 ──► VD2, VD3 ;  VD2 ──► VD4, VD5 ;  VD3, DS1, AS6 ──► VD6 ──► VD8, VD10 ;  VD3, VD6, PL1 ──► VD7 ;  VD6, VD8 ──► VD9 ;  VD4, VD5, VD7, VD9 ──► VD11 ;  VD10, VD11 ──► VD12.

Délégables : VD2, VD3, VD6 (modules purs du core, testables sans engine ni matériel) ; VD4, VD5, VD9 à rendre au propriétaire avec captures ; VD1 et VD0 décisions ; VD12 recette du propriétaire. Fichiers partagés : `route.py` et `route_data.gd` (VD1 lecture de `bank_deg`, seul) ; `surface_physics.py` (VD3 seul) ; `session.py` et `settings.py` (VD3, puis VD6) ; `bots.py` (VD7, après PL1) ; `road_builder.gd` (VD4 seul) ; `camera_follow.gd` et `bots_view.gd` (VD4) ; `crowd_renderer.gd` et `world_streamer.gd` (VD5) ; `hud_view.gd` et `summary_view.gd` (VD9) ; `menu_flow.gd` et `catalog.py` (VD10).

## 10. Décisions du propriétaire (6 novembre 2026, toutes les questions tranchées)

1. **Taille** : **tranché le 6 novembre**, une seule piste de 250 m.
2. **Virages** : **tranché le 6 novembre**, relevés (42° au sommet, 12° dans les droites).
3. **Surface** : **tranché le 6 novembre**, bois (piste couverte).
4. **Épreuves de la première livraison** : **tranché le 6 novembre**, toutes les épreuves du §5 (séance libre, poursuite, kilomètre et 500 m, 200 m lancé, scratch, course aux points, tempo, élimination, keirin, omnium, record de l'heure) et les trois épreuves par équipes (vitesse par équipes, poursuite par équipes, américaine). **Exclues (décision du 6 novembre)** : toutes les épreuves qui demandent du surplace, dont la vitesse individuelle en duel.
5. **Braquet fixe** : **tranché le 6 novembre**, option « Braquet fixe » proposée dans les réglages du vélodrome (un seul rapport, sans changement de vitesse), coupée par défaut.
6. **Version** : **tranché le 6 novembre**, 4.0. VD2 et VD3 peuvent être faits plus tôt sans rien changer au jeu, puisqu'aucune piste n'est listée avant VD10.
