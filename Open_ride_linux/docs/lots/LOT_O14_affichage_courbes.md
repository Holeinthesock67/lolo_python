# Lot O14 – Courbes de la séance à l'écran (puissance, cible, FC, cadence)

## 1. Objectif

Afficher pendant la séance le graphique du lot O13, « comme GoldenCheetah » : profil des watts cibles et courbes de puissance, de fréquence cardiaque et de cadence. Il doit rester lisible à 2 m sans masquer la route.

**Lot interne :** il modifie la scène principale et se recette à l'œil sur une vraie séance.

## 2. À lire

`docs/lots/LOT_O13_modele_courbes.md`, `docs/lots/LOT_N7_affichage_erg.md` (bandeau et histogramme), `docs/lots/LOT_E3_ciel_arbres_hud.md` (HUD final) ; code : `workout_chart_model.gd`, `erg_view.gd` (N7), `hud_view.gd`, `main.gd`.

## 3. Prérequis

O13 et N7 fusionnés (N6 pour la touche ou le geste qui change l'affichage).

## 4. Travail demandé

- Panneau en bas de l'écran, semi-transparent, dans le style du HUD d'E3 : en ERG, il **remplace** l'histogramme de N7 (le profil cible du graphique joue ce rôle, curseur compris) ; en SIM, il montre les 10 dernières minutes sans profil.
- Trois tailles, changées par une touche et par un geste du Click choisi avec le propriétaire : masqué, réduit (cible + puissance), complet (cible, puissance, FC, cadence, légende avec valeurs courantes) ; choix gardé dans `~/OpenRide/config.toml` (`[render] chart`, par O3 si livré).
- Couleurs : puissance en blanc épais, FC en rouge, cadence en bleu clair ; profil coloré par zone, atténué.
- Dessin redemandé au plus une fois par seconde ; aucun impact mesurable sur les images par seconde en qualité basse.
- Capture ajoutée à `engine/tests/run_visual_tests.sh` (faux core en ERG).

## 5. Fichiers concernés

Nouveau `engine/scripts/workout_chart_view.gd` ; modifiés `main.gd`, `erg_view.gd`, tests graphiques, `README.md`, `docs/SUIVI_AVANCEMENT.md`.

## 6. Critères d'acceptation

1. Suites de l'engine et tests graphiques passent (nouvelle capture).
2. Sur une séance ERG réelle : courbes justes à la seconde près, trous visibles quand la ceinture décroche, profil et curseur alignés avec le bandeau.
3. Les trois tailles se changent au clavier et au Click ; la route reste visible en taille complète.

**Sur le PC cible (le propriétaire) :** lisibilité à 2 m, images par seconde inchangées.

## 7. Hors périmètre

- Graphiques détaillés après la séance (GoldenCheetah reste l'outil d'analyse).
