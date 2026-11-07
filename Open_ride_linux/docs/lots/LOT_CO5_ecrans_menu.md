# Lot CO5 – Écrans du menu de la séance conseillée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : ligne de l'accueil, écran du conseil, détail du calcul, autre besoin, prochaine course | GDScript | CO3, CO4, CO8, CO9 | Moyenne | En PR, captures à valider (version 5.0) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Afficher le conseil dans le menu selon les maquettes validées (CO4).

## 2. Travail demandé

- `menu_model.gd` : ligne « Séance conseillée » en tête de l'accueil (détail : besoin et séance), envoi de `get_coach` à chaque ouverture.
- `coach_view_model.gd` (nouveau), `menu_flow.gd`, `menu_view.gd` : écran du conseil, « Lancer cette séance » (ERG pour un entraînement, SIM pour un parcours), autre séance du même besoin, autre besoin, objectif, temps disponible, prochaine course, suggestion de la montre (CO8), « Lancer la course » pour une séance de jeu calibrée (CO9), détail du calcul.
- Couleurs par jetons de `ui_theme.gd` seulement (`test_menu_style.gd`).
- `GUIDE_UTILISATION.md` : section du menu ; scénarios `menu_scenarios/` de l'accueil.

## 3. Critères d'acceptation

`run_engine_tests.sh` passe ; captures low, medium et high validées par le propriétaire avant la fusion ; banc des menus (X55) sans régression.

## 4. Réalisation (7 novembre, en PR avec CO3, CO4, CO6 et CO9)

- `coach_view_model.gd` (nouveau) : mise en forme du message `coach` selon les maquettes validées (CO4) ; écrans
  `coach` (conseil : raison en ligne d'état, lancer l'entraînement ou la course, autre séance, autre besoin, montre,
  prochaine course, objectif, temps disponible, détail du calcul), `coach_detail`, `coach_need`, `coach_race_date`,
  `coach_watch` et `coach_other`, avec leurs cartes. Les champs des saisies (date et type de la course ; type, durée
  et puissance de la montre) se modifient en place comme un réglage (clés `conseil.…`, action interne `coach_set`).
- `menu_model.gd` : ligne « Séance conseillée » en tête de l'accueil, sous le profil, dès la première réponse du
  core (comme la séance interrompue : sans core qui répond, l'accueil ne change pas) ; `choose_workout()` (liste
  des entraînements et entraînement conseillé, même chemin) ; mode « coach » de l'écran Prêt (course conseillée :
  « Démarrer » avec les tours et la durée, fantôme), bots du format passés tels quels à `start`.
- `menu_flow.gd` : `get_coach` à chaque ouverture de l'écran du conseil et avec les listes de l'accueil (`list`) ;
  « Lancer l'entraînement » : ERG (séance du plan si le besoin est `plan`, écran du test de FTP si `ftp_test`) ;
  « Lancer la course » : `select_route` et SIM, puis bots à profil au niveau du format (tactique Y10), ou à
  puissance constante quand le format n'a pas de tactique ; Dernier survivant : adversaires et écart des arches
  du format écrits dans ses réglages (`set_setting`, visibles sur son écran Prêt) ; objectif et temps disponible
  changés : `set_setting` puis conseil recalculé. Une saisie enregistrée ou effacée oublie le besoin choisi et
  ramène au conseil. Action `sequence` de `main.gd` : plusieurs actions d'un même choix, dans l'ordre.
- Pictogramme de la ligne de l'accueil (drapeau), seul ajout à la planche.
- Tests : `test_coach_menu.gd` (39 vérifications) ; `fake_core.py` répond aux cinq commandes du conseil ;
  `visual_check.py --menus` capture les sept écrans (scène réelle derrière le voile) ; scénario du banc des menus
  `menu_scenarios/seance_conseillee.json` (vrai core, à jouer sur le PC).
- `GUIDE_UTILISATION.md` : paragraphe « Séance conseillée » (§5).
- Captures du vrai jeu (Forward+ sous Xvfb, faux core, 1280 × 720) en low, medium et high : `/mnt/project-files/menus/co5-captures-conseil/` (fichiers du projet), `planche_low_medium_high.png` ; raison sur deux lignes, date de la course sans « dans n jours » (dans la carte).
- Reste : captures à valider par le propriétaire avant la fusion ; banc des menus (X55) et suite complète sur le PC.
