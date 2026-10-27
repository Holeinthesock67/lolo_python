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

## 9. Livraison

**27 octobre 2026** (thread « Développer les lots O restants »), lot interne sans issue ; les essais Godot sur le PC sont reportés à la demande du propriétaire.

- **Écart au cahier (choisi pour garder le plan des boutons, spécification §7.1) :** la taille ne se change ni par une touche ni par un geste du Click, mais dans **Réglages > Courbes de la séance** (`[render] chart` : `hidden`, `reduced` par défaut, `full`), appliqué tout de suite. Aucune touche ni geste de plus, pas d'exception au plan des boutons ; la valeur reste dans `~/OpenRide/config.toml` (O3/O4). Le critère 3 se lit donc « au menu Réglages » ; le clavier, qui double le Click, n'a rien de plus.
- **Contrat (révision 1.3) :** `hello_ack.config.chart` (facultatif) donne la taille au démarrage et après chaque `set_setting` ; sans ce champ (core plus ancien), l'engine garde l'histogramme de N7. Le message `settings` gagne un élément et dépasse 1 400 octets : il rentre dans la limite unique de 4 096 octets de la révision 1.5 (décision du 27 octobre), sans règle particulière.
- **Vue** `workout_chart_view.gd` : dessine la géométrie de `workout_chart_model.gd` (O13) : profil des watts cibles par zone, atténué ; puissance en blanc épais ; en taille complète FC rouge, cadence bleu clair, graduations en watts et légende des valeurs courantes ; en taille réduite cible et puissance, valeur en watts. Curseur de position quand le profil est connu. Dessin redemandé une fois par seconde de séance (changement du nombre de points), jamais à chaque image.
- **ERG :** la vue prend la place de l'histogramme dans le bandeau (`erg_view.set_chart`), le profil vient de la liste `workouts` retrouvée par le nom de l'entraînement ; masqué (`hidden`), l'histogramme revient. **SIM :** panneau semi-transparent centré (de 340 px du bord gauche à 340 px du bord droit, au-dessus du profil d'altitude) pour ne couvrir ni les panneaux latéraux ni les bots ; 10 dernières minutes, sans profil.
- **Alimentation (`main.gd`) :** une mesure par trame `RUNNING` (`t`, puissance, FC, cadence, cible ERG hors roue libre) ; modèle remis à zéro au départ d'une séance (pas à la reprise après une pause).
- **Tests :** `core/tests/test_settings.py` (réglage, `hello_ack.config.chart`, choix refusé), `engine/tests/unit/test_workout_chart_view.gd` (légende, taille, remplacement de l'histogramme, profil par nom), scènes « erg_courbes » et « sim_courbes » du test graphique (pixels blancs et rouges, profil coloré, pas de chevauchement). La scène « erg » existante garde l'histogramme (le faux core n'annonce pas `chart`).
- **À faire sur le PC :** `UNIT=test_workout_chart_view engine/tests/run_engine_tests.sh`, tests graphiques, puis une vraie séance ERG avec ceinture (trous quand elle décroche, lisibilité à 2 m, images par seconde en qualité basse).
