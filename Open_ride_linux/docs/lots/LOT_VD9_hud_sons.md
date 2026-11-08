# Lot VD9 – HUD et sons

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : HUD de piste, tableau d'affichage, cloche, pistolet de départ et ambiance du public | GDScript | VD6, VD8 | Moyenne | En PR (version 4.0) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Coder ce que les maquettes de VD8 ont validé.

## 2. À lire

Maquettes VD8 ; `engine/scripts/hud_view.gd`, `summary_view.gd`, `sound_player.gd`.

## 3. Travail demandé

- HUD d'épreuve lu dans l'objet `track` de `state`.
- Tableau d'affichage de la salle.
- Sons : cloche du dernier tour, pistolet, public qui monte au sprint (sons libres de droits, provenance notée).

## 4. Critères d'acceptation

1. Captures `low`, `medium`, `high` validées par le propriétaire avant fusion.
2. Lisibilité vérifiée par l'outil de galerie du HUD.

## 5. Fichiers touchés

- `hud_view.gd`, `summary_view.gd`, `sound_player.gd`, sons dans `engine/assets/`.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.

## 6. Livraison (7 novembre, demande du propriétaire : « Lance tout »)

D'après les maquettes VD8 validées le 7 novembre à 22 h 06.

- `engine/scripts/track/track_hud_model.gd` (sans nœud) : lit l'objet `track` de `state` et rend la vue :
  - bandeau de l'épreuve en haut au centre : nom (« Course aux points · 20 tours », « Omnium · Élimination (3 / 4) »), ligne d'information (prochain sprint et barème, derny, distance à la ligne d'élimination, relais, moyenne et projection de l'heure, dernier tour de la séance libre) ; doré avec deux cloches au dernier tour, rouge à l'élimination, bleu à l'américaine ;
  - bloc des tours à droite sous la vitesse : « 8 / 20 », tours restants ou « cloche », barre ; « ENCORE EN COURSE » à l'élimination ; tours et temps restant à l'heure ; tours et meilleur tour en séance libre ; distance restante aux contre-la-montre et poursuites ;
  - liste à gauche sous la puissance : points, positions, ordre de course de l'élimination (dernier en rouge, sortis grisés et barrés, le dernier sorti en premier), « derrière le derny », équipes de l'américaine, « ton équipe » des épreuves par équipes (seuls ses sortis) ; « Toi » ou « Ton équipe » sur fond or ;
  - en bas au centre : anneau de 250 m de la poursuite (lignes A et B, les deux coureurs) et écart (« −0,84 s » vert devant, « +1,20 s » rouge derrière), grand chrono des contre-la-montre (« élan » puis chrono au 200 m lancé), distance de l'heure ;
  - bloc du derny du keirin sous les tours (vitesse, tours avant qu'il s'écarte) ; bandeaux du milieu « DERNIER ! » (élimination, avec le coureur à remonter) et « AU REPOS EN HAUT » (américaine) ;
  - texte du tableau d'affichage de la salle (8 lignes au plus) ; lignes du bilan (`summary.track` : place, temps, distance de l'heure, tours, meilleur tour, record de la piste, vainqueur) et temps de chaque tour (`lap_rows`).
- `engine/scripts/track/track_view.gd` : l'affichage, dans le style des panneaux du HUD ; `main.gd` `_update_track` à chaque trame ; sur une piste la ligne d'état et le profil d'altitude (piste plate) laissent la place au bandeau et au bloc des tours (`hud_view.gd`), sauf le bandeau ERG de la séance libre ; l'encart des bots est remplacé par la liste.
- `velodrome_hall.gd` `set_scoreboard` : texte posé sur les quatre faces du tableau, taille des lettres selon les lignes.
- Sons synthétisés (aucun fichier, donc rien à créditer ; remplaçables par `~/OpenRide/Sounds/<nom>.ogg` comme les autres jingles) : `track_bell` (cinq coups de cloche du dernier tour), `track_gun` (claquement du départ, seulement si l'épreuve commence sous 1 s), `track_crowd` (rumeur du public au tour d'un sprint et au dernier tour), dans `event_sounds_model.gd`.
- Core : l'omnium transmet aussi `last`, `gap_last_s` et `alive` de l'élimination en cours (contrat 1.7 à jour, pire objet inchangé).
- Tests : `engine/tests/unit/test_track_hud.gd` (cas des maquettes, sons, tableau, bilan, vue) ; 2 258 trames de vraies épreuves du core (les 15) rejouées par le modèle et la vue sans erreur.

Écarts : la maquette du kilomètre montrait l'écart au record ; la trame n'a pas le record de la piste, le chrono montre la distance passée (à ajouter au contrat si le propriétaire le veut). Le tableau des tours et le mini-graphe du bilan sont réduits aux lignes du bilan (meilleur tour et son numéro) : `lap_rows` est prêt pour un tableau. La posture d'un bot fatigué ne change pas (voir VD7).
