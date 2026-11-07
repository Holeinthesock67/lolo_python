# Lot GP6 – Maquettes des objets, des boîtes, du HUD et du bilan

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : maquettes des treize objets, des boîtes, du HUD, des avertissements et du bilan, charte cartoon CT9, validées par le propriétaire | Docs | GP1 | Petite | Maquettes validées par le propriétaire le 7 novembre 2026 (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Montrer au propriétaire, avant tout code d'affichage, le dessin de chaque objet, des boîtes de ravitaillement, du HUD (case d'objet, place, bande de course, choix de voie, avertissements) et du bilan.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §8.2 ; `docs/5.0/CHARTE_CARTOON_CT9.md` ; maquettes WTF4.

## 3. Travail demandé

- Planches en 1680×1050 et 1024×600, en `low`, `medium` et `high`.
- Objets dessinés pour OpenRide (bidon, musette, voiture d'équipe…), sans emprunt à un jeu existant.
- Pas de flash plein écran, clignotement de 2 Hz au plus, couleurs doublées d'une forme.

## 4. Critères d'acceptation

1. Le propriétaire valide les planches ; la date de validation est notée dans ce cahier avant le début de GP7 et GP8.

## 5. Maquettes soumises (7 novembre 2026)

**Statut : soumises au propriétaire le 7 novembre 2026 et validées telles quelles le 7 novembre 2026 à 23 h 10 (heure de Paris). GP7 et GP8 peuvent commencer, dans l'ordre de la série.**

Dossier du projet (hors dépôt, comme CT9) : `/mnt/project-files/captures/gp6-maquettes/`. Sept scènes, chacune en 1680×1050 et 1024×600, en `low`, `medium` et `high` (42 images dans `images/`), une planche par scène et une planche du réglage « Effets » de CT9 (forts, normaux, discrets) sur la scène 3. Images fixes dessinées en SVG et rendues par Chromium (`maquettes_gp6.js`, qui reprend les fonctions de `maquettes_ct9.js` dans `ct9_lib.js`) : ce ne sont pas des captures de l'engine, qui n'a encore aucun code du mode.

| Scène | Ce qu'elle montre |
| --- | --- |
| 1. Catalogue | Les treize objets avec leur nom, leur effet en une ligne et leur pastille de famille ; la légende des familles ; la boîte de ravitaillement |
| 2. Boîtes et roulette | Rangée de trois boîtes (une par voie), boîte prise en pointillés (elle se reforme en 2 s), rangée suivante au loin, roulette de 2 s dans la case d'objet, « HOP ! » du bot qui prend une boîte |
| 3. Attaque | Musette lancée sur la voie du joueur avec traits de vitesse, bidon au sol, glissade d'un bot (penché, traces, étoiles, « ZIOUF ! »), avertissement « Musette guidée derrière ! » avec flèche et contour de l'écran |
| 4. Orage et super-forme | Nuage d'orage et averse sur le premier (« SPLASH ! »), avertissement « Orage vers le premier », joueur en super-forme (contour pointillé, étoiles qui tournent, halo en `high`), bot frôlé qui glisse (« BOING ! ») |
| 5. Voiture d'équipe et vent contraire | Voiture d'équipe vue de dos (vélos sur le toit) qui remorque le joueur dans son abri (lignes `draft`, « TUT TUT ! »), rafales du vent contraire sur les coureurs de devant |
| 6. HUD complet | Puissance, cadence, cardio ; case d'objet et charges ; place, tour, écart ; bande de course avec l'objet tenu par chacun ; vitesse, pente, distance à l'arrivée ; trois traits de voie |
| 7. Bilan | Place, classement, objets lancés, reçus et esquivés, temps gagné ou perdu par objet (barre et flèche), rappel que puissance et vitesse sont réelles au journal et au FIT |

### 5.1 Choix proposés dans les maquettes

1. **Aucun nouveau jeton de couleur** : les objets reprennent les jetons de la charte CT9 et chaque famille a une forme de pastille, pour que la couleur ne soit jamais seule (règle 4 de CT9).

   | Famille | Jeton | Forme | Objets |
   | --- | --- | --- | --- |
   | Pour soi | `spark` | Rond | Coup de fouet, trois coups, super-forme, voiture d'équipe, furtif |
   | Attaque | `hot` | Triangle | Musette, trois musettes, musette guidée |
   | Piège derrière soi | `warm` | Carré | Bidon, trois bidons |
   | Contre la tête | `sling` | Losange | Nuage d'orage, vent contraire |
   | Défense | `fresh` | Écu | Sonnette |

2. **Dessins propres à OpenRide** : sachet de gel, bidon, musette en toile, sonnette, manche à air, voiture d'équipe avec vélos sur le toit, silhouette en pointillés ; la boîte est une caisse de ravitaillement (musette et bidon), sans point d'interrogation.
3. **Disposition du HUD** : la case d'objet prend le haut centre, la place et l'écart le haut droit, la bande de course la gauche sous la puissance ; vitesse, pente et distance à l'arrivée passent en bas à droite.
4. **Avertissements** : panneau papier au bord de l'écran, pastille de l'objet, flèche de la direction du danger, contour de 14 px aux bords de l'écran (chevrons en bas pour un danger qui vient de derrière), aucun flash plein écran.
5. **Onomatopées** en français, coupées en « Discrets » comme dans CT9 : « HOP ! », « ZIOUF ! », « BOING ! », « SPLASH ! », « TUT TUT ! ».
6. **Coureur touché** dans la bande de course : pastille `warm` avec une croix (forme distincte de l'étoile de la super-forme).

### 5.2 Ce que la validation tranche

En validant les planches, le propriétaire valide les dessins des treize objets et de la boîte, les familles du §5.1, la disposition du HUD, les avertissements et le bilan. Toute remarque sur une scène se reporte ici avant GP7 et GP8.
