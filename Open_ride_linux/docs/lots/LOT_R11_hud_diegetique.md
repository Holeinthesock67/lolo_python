# Lot R11 – Engine : HUD diégétique, arcs au sol, champ de vision et tremblement

## 1. Objectif

Afficher l'état du joueur dans la scène plutôt qu'en surimpression : hologramme au-dessus de la roue arrière (vitesse engagée, watts en % de FTP, cadence, posture), deux arcs au sol (bouclier et adrénaline), jauges de W'bal et de l'ennemi, écart au Firewall, et des effets de caméra (champ de vision, tremblement). Le modèle (calculs sans affichage) est délégable ; le rendu est interne.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_R17_direction_artistique.md` (charte, jetons de couleur, matériaux, catalogue des objets et des effets : à suivre partout), `docs/2.0/GDD_CYBER_ROGUE.md` §3.1, `docs/lots/LOT_T1_contrat_1_4.md` §4.3.
2. Code : `engine/scripts/hud_view_model.gd` et `hud_view.gd` (modèle et vue du HUD classique), `engine/scripts/camera_follow.gd`, `engine/scripts/sound_model.gd`.

## 3. Prérequis

T1 et R17 livrés ; R10 pour l'intégration dans la scène.

## 4. Travail demandé

### 4.1 Modèle `rogue_hud_model.gd` (sans affichage, délégable)

- Entrée : la trame `state` (objet `rogue` compris) et la FTP de `hello_ack`. Sortie : un dictionnaire de valeurs prêtes à afficher :
  - vitesse « 01 » à « 12 », watts en % de FTP (arrondi à 1 %), cadence, posture et sa couleur ;
  - arc gauche bleu (bouclier / `shield_max`), arc droit orange (adrénaline / 100), seuil de l'attaque Z (50) marqué ;
  - W'bal en % de W', rouge sous 25 % ;
  - PV de l'ennemi en %, écart au Firewall en mètres (rouge sous 30 m) ;
  - en couloir : 3 cartes, 2 portes, sélection, coût de relance ;
  - piratage : boutons bloqués ou pignon imposé, temps restant ;
  - événements de la trame à jouer en effet (`perfect_shift`, `hit`, `crit`, `parry`, `defeat`…), chacun une seule fois même si la trame se répète.
- Lissage : valeurs affichées lissées sur 0,3 s, sauf la vitesse engagée (immédiate).

### 4.2 Vue (interne)

- Hologramme à 1,2 m au-dessus de la roue arrière, dans l'axe du regard ; lisible à 180 bpm (gros chiffres, fort contraste).
- Arcs : deux demi-cercles au sol autour du vélo, rayon 1,5 m.
- Caméra : champ de vision de 75° au repos, jusqu'à 95° pendant un sprint (puissance ≥ 1,40 FTP) ou une attaque Z, retour en 1 s ; tremblement léger (amplitude 0,05 m, 0,2 s) aux impacts et aux Perfect Shifts, coupé si le réglage « réduire les mouvements » est actif (O4).
- Sons : bip de Perfect Shift, impact, parade, alarme de contact du Firewall (`sound_model.gd`) ; la liste complète des bruitages du mode, la musique et les volumes sont dans le lot R18.
- **Salle manquée** (`room_skipped`, décision R-Q2) : bandeau « Salle manquée −10 or » de 3 s, écran qui grésille en rouge 0,5 s et son d'échec distinct de celui de la défaite.

## 5. Fichiers concernés

- **Créés :** `engine/scripts/rogue/rogue_hud_model.gd`, `engine/scripts/rogue/rogue_hud_view.gd`, `engine/tests/unit/test_rogue_hud_model.gd`.
- **Modifiés :** `engine/scripts/camera_follow.gd` (champ de vision et tremblement, désactivés hors mode `ROGUE`), `engine/scripts/sound_model.gd` (sons du mode), `engine/scenes/rogue.tscn`, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests sans écran du modèle : toutes les sorties du §4.1 sur des trames d'exemple, dont une trame sans `rogue` (modèle vide, pas d'erreur).
2. Un événement répété dans trois trames n'est joué qu'une fois.
3. Mode classique : caméra et HUD inchangés (tests existants).
4. Contrôle visuel du propriétaire : lisibilité à l'effort sur la GTX 1060.

## 8. Hors périmètre

- Ennemis (R12), menu de départ et écran de fin (R13).
