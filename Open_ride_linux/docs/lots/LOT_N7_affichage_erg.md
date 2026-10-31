# Lot N7 – Entraînement ERG à l'écran : bandeau, histogramme des blocs et bip à T − 3 s (ancien F2)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Entraînement ERG à l'écran : bandeau, histogramme et bip à T − 3 s (ancien F2) | GDScript | E3, I6 (livrés) | Moyenne | **Livré le 25 octobre** (interne, PR #116) |

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
2. Sur le HomeTrainer : `sweet_spot_3x10` exécuté en entier ; bip entendu avant chaque bloc, jamais deux fois ; histogramme et curseur justes à la seconde près (critère 11 du lot F et critère du sprint 4).
3. Biais ± 2 % au Click : cible du bandeau mise à jour à la trame suivante.

## 8. Hors périmètre

- Choix de l'entraînement dans le menu (N3, N6).

## 9. Livraison (25 octobre 2026, code et tests ; essai sur le HomeTrainer à faire)

- Nouveau `engine/scripts/erg_view.gd` : bandeau en bas de l'écran, au-dessus du profil d'altitude (nom, bloc `i/n`, type en français, cible biais compris, temps restant, cible suivante, « (pause) »), et histogramme des blocs sur toute la largeur : bloc en cours entouré, blocs faits assombris, curseur au temps écoulé, couleurs des zones de Coggan aux seuils de `session_summary.ZONES`. Caché en SIM.
- `main.gd` : bandeau ajouté au HUD ; bip unique à T − 3 s (1 320 Hz, 0,3 s, niveau 0,6 contre 0,3 pour les bips d'appui) déclenché par `erg_view_model.gd`, journalisé (`erg_beep block=N` en mode test). La ligne ERG du panneau central est cachée (`hud_view.gd`, `show_erg_line`), le bandeau la remplace.
- Tests : `engine/tests/unit/test_erg_view.gd` (38 vérifications) ; scène `erg` de `visual_check.py` complétée (textes du bandeau, ligne centrale cachée, histogramme sur toute la largeur au-dessus du profil, bloc en cours en couleur de zone). La scène ERG reste hors des images de référence (la caméra roule et le temps restant défile).
- **Écart au cahier :** l'objet `erg` du contrat v1 ne donne pas la durée des autres blocs. Les vraies largeurs viennent du `profile` des éléments `workouts` (contrat v1.1), donné par `set_profiles(items)` ; tant que la liste n'est pas reçue (core v1, ou N2/N3/N6 pas encore fusionnés), l'histogramme se replie sur `block_count` cases égales, bloc en cours coloré par sa cible. Le branchement de `set_profiles` se fait dans N6, avec le client des listes de N3.
