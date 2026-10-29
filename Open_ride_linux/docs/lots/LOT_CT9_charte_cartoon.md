# Lot CT9 – Charte graphique cartoon de la Course tactique et maquettes

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Décision du propriétaire du 29 octobre : effets **flashy et exagérés, façon cartoon**, même s'il faut créer de nouveaux effets. Ce lot fixe la charte du mode (comme R17 pour le Cyber-Rogue) et produit les maquettes que le propriétaire valide **avant tout code** de CT10 et CT11.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Cahier `LOT_R17_direction_artistique.md` (modèle) ; cahier `LOT_Y16_avatar_detaille.md` ; `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` ; maquettes de la jauge d'abri (choix C du 29 octobre).

## 3. Prérequis

CT1 fusionné.

## 4. Travail demandé

- **Palette** : 8 à 10 jetons de couleur saturés, contour noir épais (« ink »), ombrage en aplats (cel shading à 2 ou 3 tons).
- **Catalogue d'effets**, chacun avec sa version `low`, `medium` et `high` : vélo qui rougit et fume selon la W′ (bleu, orange, rouge), Burnout (fumée, étoiles qui tournent, ressort cassé), flux de l'abri (traits de vitesse entre les deux roues), catapulte chargée (ressort tendu, éclairs), impulsion (onde de choc, traits de vitesse plein écran mais transparents), Apex (étincelles, « POW » au point de corde), sangsue (petit aimant ou ventouse au-dessus du bot qui charge), capacités (icônes cartoon), flèches au sol géantes et rebondissantes avant une variante.
- **Règles de confort** (non négociables) : clignotement de 2 Hz au plus, pas de flash plein écran, chaque couleur doublée par une forme, effets plein écran sous 30 % d'opacité, réglage « Effets » (forts, normaux, discrets).
- **Maquettes** : images fixes de 6 scènes (peloton, attaque et Burnout, catapulte, virage et Apex, variante, HUD complet) en 1680×1050 et 1024×600, déposées dans `/mnt/project-files/captures/course-tactique-maquettes/` ; **validation du propriétaire avant CT10**.
- **Budget** : chaque effet estimé en coût GPU sur la GTX 1060 ; tout est procédural (shaders, particules), sans textures.

## 5. Fichiers concernés

- **Nouveaux :** `docs/5.0/CHARTE_CARTOON_CT9.md`, maquettes hors dépôt (dossier du projet).
- **Modifiés :** ce cahier, `00_INDEX.md`.
- **Interdits :** tout code de l'engine avant validation des maquettes.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Le propriétaire a validé les maquettes (date notée dans la charte).
2. Chaque effet a ses trois niveaux et une estimation de coût.
3. Les règles de confort sont vérifiables (fréquence, opacité, forme).

## 8. Hors périmètre

Code des effets (CT10) et du HUD (CT11).

## 9. Livraison (29 octobre 2026)

- Charte : `docs/5.0/CHARTE_CARTOON_CT9.md` (10 jetons, formes qui doublent chaque couleur, catalogue des effets en `low`, `medium` et `high` avec coût GPU estimé, réglage « Effets », règles de confort chiffrées).
- Maquettes : `/mnt/project-files/captures/course-tactique-maquettes/`, 6 scènes en 1680×1050 et 1024×600 dans les trois qualités (36 images), 7 planches (une par scène, une pour le réglage « Effets »), et le script qui les dessine (SVG rendu par Chromium, hors dépôt).
- **Écarts :** CT1 n'est pas encore fusionné ; la charte s'appuie sur les champs proposés au §6 du plan et ne demande aucun changement de contrat. Les coûts GPU sont des estimations, que CT10 mesure sur la GTX 1060 avec la sonde X13 en `low`, `medium` et `high`.
- **Pas encore fait :** la validation du propriétaire (critère 1), à noter en tête de la charte avant CT10.
