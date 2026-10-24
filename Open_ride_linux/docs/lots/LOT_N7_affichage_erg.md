# Lot N7 – Entraînement ERG à l'écran : bandeau, histogramme des blocs et bip à T − 3 s (ancien F2)

## 1. Objectif

Le core pilote déjà l'ERG (lot F) et le HUD affiche la cible, le bloc et le temps restant en texte (PR #73). Il manque ce que la SRS demande au sprint 4 : le bandeau d'entraînement, l'histogramme des blocs avec la position courante, et le bip trois secondes avant chaque changement de bloc. La logique existe et est testée sans écran (`erg_view_model.gd`, lot I6) : ce lot l'affiche et la fait entendre.

**Lot interne :** affichage et son dans la scène principale après E3 (HUD final), recette à l'œil et à l'oreille sur une vraie séance ERG.

## 2. À lire

1. `docs/SRS_v1.1.md` §6 (ERG) et §13 (critère du sprint 4).
2. `docs/lots/LOT_I6_logique_erg_godot.md` et `docs/lots/LOT_F_erg_zwo.md`.
3. Code : `engine/scripts/erg_view_model.gd`, `engine/scripts/main.gd`, le HUD final d'E3, `engine/scripts/sound_model.gd` (niveaux sonores).

## 3. Prérequis

PR #91 (E3/E4, HUD final) fusionnée.

## 4. Travail demandé

- Bandeau : nom de l'entraînement, bloc `i/n`, type, cible (biais compris), temps restant, cible suivante.
- Histogramme `profile_bars` sur toute la largeur, bloc en cours mis en évidence, curseur de position ; couleurs par zone de Coggan (mêmes seuils que `openride-core summary`).
- Bip unique à T − 3 s (déclenchement de `erg_view_model.gd`), distinct des bips d'appui, au-dessus du vent et de la roue libre.
- En SIM, rien de tout cela n'apparaît.

## 5. Fichiers concernés

`main.gd`, HUD final d'E3, nouveau `erg_view.gd`, tests graphiques (capture ERG de référence), `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune : l'objet `erg` du contrat v1 suffit.

## 7. Critères d'acceptation

1. Suites de l'engine et tests graphiques passent (nouvelle capture ERG avec `fake_core.py --erg-workout`).
2. Sur le Victory : `sweet_spot_3x10` exécuté en entier ; bip entendu avant chaque bloc, jamais deux fois ; histogramme et curseur justes à la seconde près (critère 11 du lot F et critère du sprint 4).
3. Biais ± 2 % au Click : cible du bandeau mise à jour à la trame suivante.

## 8. Hors périmètre

- Choix de l'entraînement dans le menu (N3, N6).
