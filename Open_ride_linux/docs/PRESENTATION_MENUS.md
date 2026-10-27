# Présentation des menus

Demande du propriétaire du 27 octobre : les menus sont « trop basiques », et l'aide des boutons ne se voit pas (« comment valider ? »). Maquettes validées le 27 octobre, sélection en cyan : [Maquettes des menus OpenRide](https://claude.ai/artifact/TEJk2ZXfxJky2BCFEjyEs1).

## Défauts de départ

- Aide des boutons en gris 16 px, sur une ligne plus large que le panneau : « A long valider » était coupé. Elle disait « − » alors que le boîtier gauche ne répond pas (spécification générale §7.1 : B double « − »).
- Accueil tronqué : 4 entrées visibles sur 8 quand les appareils étaient affichés.
- Panneau de 600 × 435 (base 1280 × 720) entre les cadrans du HUD, qui restaient affichés à zéro.
- Peu de hiérarchie (titre, entrées et détails de tailles voisines), détail collé au libellé puis coupé.
- Couleurs écrites en dur dans cinq vues, chacune un peu différente.

## Système commun

Tout menu passe par `engine/scripts/menu_view.gd`, réécrit sur ces pièces :

| Fichier | Rôle |
| --- | --- |
| `engine/scripts/ui_theme.gd` | Jetons de couleur, de taille et d'espacement, fabriques des styles (entrée, carte, pastille, touche, bandeau). Aucune vue de menu n'écrit de couleur en dur |
| `engine/scripts/ui_icons.gd` | Pictogrammes tracés par le code (grille 32 × 32), table « identifiant d'entrée → pictogramme » |
| `engine/scripts/button_help.gd` | Aide des boutons par écran, sans nœud, d'après §7.1 : seule table à changer si le plan ou le clavier change (lot O17) |
| `engine/scripts/button_bar.gd` | Bandeau des boutons en bas de l'écran : touches dessinées, anneau de l'appui long, action principale en tête |
| `engine/scripts/devices_view.gd` | Pastilles des appareils : point de la couleur du niveau, état écrit seulement s'il n'est pas « prêt » |
| `engine/scripts/detail_card.gd` | Carte de détail à droite (étape 2) : en-tête, nom, trois tuiles de chiffres clés, graphique tracé par le code (profil d'altitude ou blocs colorés par zone), lignes de texte ; le bilan s'y ajoute |

Couleurs (charte R17 en version sobre, une couleur par rôle) : fond `void` #05060F, cartes #10173A, filets #24305E, texte `neutral` #E8F0FF, secondaire #8E9AC0, désactivé #5D688C, sélection `player` #18F0FF, records `gold` #FFD23C, prêt #45E08A, recherche #FFB347, erreur `danger` #FF2E4C.

Tailles en unités de la base 1280 × 720 : titre 40, entrée 28, détail et carte 22, bandeau 21, pastilles 18, rien sous 16. Marges de 64, rangées de 46, rayon 10.

Le menu occupe tout l'écran sur un voile sombre ; il est sur sa propre couche au-dessus du HUD, qui est caché tant qu'un menu est affiché (`main.gd`). Le bandeau d'alerte reste au-dessus de tout. Sur l'écran de pause, la raison de la pause (`state.pause_reason`) s'écrit sous le titre (`menu_flow.gd`, `PAUSE_REASONS`).

La carte de détail (étape 2) suit l'écran et le focus (`menu_flow.card()`, fiches de `catalog_model.gd`) :

| Écran | Carte |
| --- | --- |
| Prêt | Fiche du parcours choisi : distance, dénivelé, pente max ; profil d'altitude du parcours entier quand il est chargé (`main.gd`, `HudViewModel.profile`) ; montée principale, difficulté et durée estimée, région et étiquettes |
| Parcours | Fiche du parcours sous le focus (sans profil tant qu'il n'est pas chargé : la liste du core n'a pas la géométrie) ; rien sur « Trier par » et « Étiquette » |
| Session ERG : entraînement | Durée, nombre de blocs, intensité maximale (en watts pour un fichier en watts), blocs dessinés à leur durée et à leur cible, couleur de la zone de Coggan (`erg_view.gd`) |
| Créer un entraînement | Aperçu des blocs du `.zwo` que le core écrira (`workout_builder.profile()`), mis à jour à chaque réglage ; valeurs des paramètres alignées à droite |
| Fin de séance | En-tête « Bilan de la séance », puis le bilan (`summary_view.gd`) |

Contraintes tenues : plan des boutons et contrat IPC inchangés, aucune texture ni police ajoutée, menus sans animation continue.

## Étapes

| Étape | Contenu | État |
| --- | --- | --- |
| 1 | Thème, pictogrammes, bandeau des boutons, pastilles, menus en plein écran, accueil entier | Fusionnée (PR #433) |
| 2 | Prêt et fiche du parcours en carte (chiffres, profil d'altitude), parcours, entraînements ERG, création et import | En revue |
| 3 | Réglages (valeur alignée à droite, édition en place, curseur de la difficulté), Appareils et connexion, plans et test de FTP | À faire |
| 4 | Records, bilan, pause, confirmation ; couleurs du HUD et du globe ramenées au thème | À faire |

Chaque étape : une branche et une PR, `engine/tests/unit/test_menu_style.gd` à jour, captures de référence des tests graphiques (`menu_accueil`, `pause`, `bilan` ; `menu_parcours` et `pret` vérifiées par textes et pixels, sans image de référence) refaites sur le PC avec `run_visual_tests.sh --golden … --update-golden`.
