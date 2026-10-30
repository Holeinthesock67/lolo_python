# Lot R13 – Engine : lancement du mode depuis le menu, écran de départ, couloirs et cartes, pause, fin de run

## 1. Objectif

Rendre le mode Cyber-Rogue jouable de bout en bout depuis le menu, au Click seul : entrée « Cyber-Rogue » à l'accueil, écran de départ (objectif, durée, W', châssis), écran « Prêt », run, couloirs avec cartes et portes, pause par Y comme dans les autres modes, bilan et retour à l'accueil. Lot interne : il touche `main.gd` et le menu.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_R17_direction_artistique.md` (charte, jetons de couleur, matériaux, catalogue des objets et des effets : à suivre partout), `docs/contracts/ipc_v1.md` (révision 1.4, lot T1), `docs/lots/LOT_T1_contrat_1_4.md` (§4.1 et §4.3, §4.6).
2. `docs/2.0/PLAN_SERIE_R.md` §6 (parcours de lancement), `docs/lots/LOT_N6_affichage_menus.md`, `LOT_N4_modele_fin_seance.md`, `LOT_O4_menu_reglages.md`.
3. Code : `engine/scripts/menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `summary_view_model.gd`, `main.gd`, `ipc_client.gd`.

## 3. Prérequis

T1, R8, R10, R11 et R17 livrés (portes, cartes, coffres et écrans du mode suivent le catalogue de R17) ; N6 et O4 (réglages, pour W') livrés ; l'accueil construit à partir de `hello_ack.config.modes` (préparé dans la 1.0, voir le plan §6 ; sinon ce lot le fait).

## 4. Travail demandé

### 4.1 Parcours de lancement

```text
Accueil ── « Cyber-Rogue » (affiché seulement si le core annonce "rogue")
   └─► Départ Cyber-Rogue : Objectif · Durée · W' · Châssis · Lancer
          └─► cmd start_run ─► LOADING (« Composition de la run… ») ─► READY
                 └─► Prêt : Démarrer · Changer les choix
                        └─► cmd start ─► RUNNING, mode ROGUE : main.gd instancie rogue.tscn (R10)
                               ├─► Y ou Échap : Pause (Reprendre · Terminer et enregistrer · Abandonner)
                               ├─► Couloirs : cartes et portes (au Click, géré par le core)
                               └─► RESULTS ─► FINISHED : bilan de run ─► Accueil (rogue.tscn libérée)
```

- **Départ Cyber-Rogue :** `Objectif` (Endurance, Seuil, VO2max ; + et − font défiler), `Durée` (30, 45, 60, 90 min), `W'` (valeur de `hello_ack.config.rogue`, avec l'estimation de R16 affichée à côté si elle existe : « estimé 18,4 kJ, utiliser ? »), `Châssis` (R9), `Lancer`. Les derniers choix sont gardés pour la fois suivante.
- **Avertissement au premier lancement** (risque 5 du plan) : efforts au-delà de 140 % de la FTP possibles en VO2max ; sortie sans pénalité à tout moment ; test de FTP conseillé si la FTP n'a jamais été mesurée (lot O10).
- **Prêt :** rappel de l'objectif, de la durée, du nombre de salles prévu et de la graine (pour rejouer la même run).
- **Pause :** Y ou Échap, comme dans les autres modes (décision R-Q6). « Terminer et enregistrer » et « Abandonner » passent par l'écran de confirmation (N6) ; les deux envoient `end_session` (`save` vrai ou faux) et la run finit en `abandoned`.
- **Bilan :** écran de fin de séance (N4) complété de `summary.rogue` : résultat, salles gagnées, boss, or, cartes, déblocages, puis retour à l'accueil.

### 4.2 Couloirs

- Écran en surimpression dans la scène : 3 cartes puis 2 portes, sélection suivie de `state.rogue.loot_focus` (le core gère les boutons ; l'engine ne fait qu'afficher). Le clavier envoie les mêmes `input_event`.
- Deck et métriques de la run (temps, NP, W'bal) : dans l'écran de pause (Y), avec « Reprendre » en premier ; en couloir, A court fait défiler et A long valide (plan de boutons commun).

### 4.3 Accueil construit à partir des modes

- Si la 1.0 ne l'a pas déjà fait : `menu_model.gd` construit les entrées de l'accueil depuis une table locale `{mode: entrée}` filtrée par `hello_ack.config.modes` (absent : `["ride", "erg"]`). L'entrée « Cyber-Rogue » n'existe que si `"rogue"` est annoncé : jamais d'entrée grisée.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `summary_view_model.gd`, `main.gd`, `ipc_client.gd` (`start_run`) ; `engine/tests/fake_core.py` ; `docs/SUIVI_AVANCEMENT.md`.
- **Créés :** `engine/scripts/rogue/rogue_menu_model.gd`, `engine/tests/unit/test_rogue_menu_model.gd`.

## 6. Modifications de contrat autorisées

Aucune au-delà de la révision 1.4 (lot T1).

## 7. Critères d'acceptation

1. Tests sans écran : `hello_ack` sans `modes` = accueil de la 1.0 inchangé ; avec `"rogue"` = entrée « Cyber-Rogue » ; écran de départ qui envoie `start_run` avec les bons arguments ; pause par Y ; abandon confirmé qui envoie `end_session`.
2. Essai de bout en bout sans écran avec le faux core (lot J8) : accueil, départ, prêt, une salle, un couloir, bilan, accueil.
3. Run complète au Click seul, sans clavier (contrôle du propriétaire en R14).

## 8. Hors périmètre

- Garage et avatar (série V), statistiques détaillées des runs (après R9).

## 9. Livraison (28 octobre 2026)

- **Menu de départ :** `engine/scripts/rogue/rogue_menu_model.gd` (sans nœud) : objectif, durée, W' (avec l'estimation de R16 quand `hello_ack.config.rogue` en donne une) et châssis (R9) à faire défiler, arguments de `start_run` (`seed` nul, `w_prime_j` nul sauf estimation choisie, `chassis` seulement s'il y a des châssis), texte de l'écran Prêt. `menu_flow.gd` en fait l'écran « Départ Cyber-Rogue » ; « Lancer » demande une confirmation au premier lancement (efforts au-delà de 140 % de la FTP possibles en VO2max, sortie sans pénalité), envoie `start_run`, affiche « Composition de la run… » puis l'écran Prêt quand le core passe en `READY`. Une erreur `run_invalid`, `item_locked` ou `busy` ramène au départ avec le message.
- **Accueil :** `menu_model.gd` : l'entrée « Cyber-Rogue » est dans `HOME_MODES` et n'apparaît que si `"rogue"` est annoncé (sans `modes`, l'accueil de la 1.0 est inchangé) ; l'écran Prêt du mode propose « Démarrer » et « Changer les choix ». `ipc_client.gd` : `start_run()` ; `main.gd` : configuration depuis `hello_ack` et envoi de la commande.
- **Couloirs :** `rogue_corridor_view.gd` affiche les trois cartes et les deux portes en surimpression avec le style des menus (`ui_theme.gd`), la sélection suit `loot_focus` (0 à 2 : cartes, 3 et 4 : portes) et le coût de relance. Le message `loot` passe par `rogue_host.gd` jusqu'au modèle du HUD (R11).
- **Pause et bilan :** la pause reste celle des autres modes (Y, Reprendre en premier, Terminer et enregistrer, Abandonner avec confirmation, `end_session`). `summary_view_model.gd` ajoute les lignes de `summary.rogue` : objectif et durée, résultat, salles gagnées, fuies ou manquées, boss, or, cartes, Perfect Shifts, déblocages.
- **Écarts :** les derniers choix n'étaient gardés que le temps du programme et l'avertissement se redemandait à chaque lancement d'OpenRide (réglé par R19 le 30 octobre : dernière run relue dans le journal) ; le deck et les métriques de la run ne sont pas dans la pause (le contrat 1.4 ne les envoie pas) ; l'essai de bout en bout avec le faux core n'est pas fait, le déroulé est couvert par `test_rogue_menu_flow.gd` (accueil, départ, avertissement, `start_run`, chargement, Prêt, erreur, pause, abandon, bilan) ; la mise en page du couloir reste à contrôler à l'écran (R14).
- Tests : `engine/tests/unit/test_rogue_menu_model.gd` et `test_rogue_menu_flow.gd`.
