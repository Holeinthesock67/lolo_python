# Lot R12 – Engine : ennemis et boss géométriques, effets d'impact

## 1. Objectif

Donner un corps aux cinq archétypes et au boss : formes géométriques simples, animées selon l'état reçu du core (PV, attaques, piratage), et des effets d'impact sobres. Peu d'assets : maillages procéduraux ou primitives Godot, shaders et particules. Lot interne : contrôle visuel.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_R17_direction_artistique.md` (charte, jetons de couleur, matériaux, catalogue des objets et des effets : à suivre partout), `docs/2.0/GDD_CYBER_ROGUE.md` §1.3 et §2.5, `docs/lots/LOT_R10_scene_neon_ruban.md`, `LOT_T1_contrat_1_4.md` §4.3 (partie R du contrat 1.4).
2. Code : `engine/scripts/rogue/` (après R10 et R11), `engine/scripts/quality_presets.gd`.

## 3. Prérequis

R10 et R17 livrés.

## 4. Travail demandé

| Archétype | Forme | Animation |
| --- | --- | --- |
| Diesel | Train blindé de 3 voitures (boîtes biseautées), souffle de particules à l'arrière | Avance devant le joueur ; éclairs quand une charge de tunnel est prête |
| Puncheur | Moto lumineuse (deux anneaux et un fuselage), laisse un mur d'énergie | Accélère avant chaque bosse ; la zone bleue s'allume 2 s avant |
| Grimpeur | Drone pyramidal qui soulève la route | Monte d'un palier à chaque changement de pente ; rochers d'armure qui se fissurent |
| Sprinteur | Chasseur furtif en losange | Disparaît et réapparaît pendant les salves du Firewall |
| Saboteur | Essaim de cubes corrompus (instanciation multiple) | Grésille pendant un piratage ; se disperse à la purge |
| Boss | Chimère : assemblage des cinq formes, une par phase en avant | Phase 1 : verrous lumineux ; phase 2 : ondes de choc circulaires ; phase 3 : rouge écarlate |

- Position : l'ennemi se tient 30 à 60 m devant le joueur ; il recule quand ses PV baissent, s'enfuit (s'éloigne et s'éteint) quand la salle finit sans victoire.
- Impacts : éclat de particules et flash de 0,1 s ; coup critique plus gros ; tout se coupe avec le préréglage `low` si le budget d'images n'est pas tenu.
- Le modèle de pose (position, état, effets à déclencher, sans affichage) est un script séparé testé sans écran.
- Noms : aucune marque ni œuvre existante (risque 7 du plan).

## 5. Fichiers concernés

- **Créés :** `engine/scripts/rogue/enemy_model.gd`, `engine/scripts/rogue/enemy_views.gd`, `engine/tests/unit/test_enemy_model.gd`.
- **Modifiés :** `engine/scenes/rogue.tscn`, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests sans écran du modèle : position selon les PV, fuite en fin de salle perdue, phase du boss.
2. Budget : sur la GTX 1060 en `low`, salle du Saboteur (le plus d'instances) à 60 images/s ou plus.
3. Contrôle visuel du propriétaire.

## 8. Hors périmètre

- Sons des ennemis au-delà des impacts (après la recette R14).
