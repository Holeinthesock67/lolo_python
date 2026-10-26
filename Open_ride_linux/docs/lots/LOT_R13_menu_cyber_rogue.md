# Lot R13 – Engine : lancement du mode depuis le menu, écran de départ, couloirs et cartes, pause, fin de run

## 1. Objectif

Rendre le mode Cyber-Rogue jouable de bout en bout depuis le menu, au Click seul : entrée « Cyber-Rogue » à l'accueil, écran de départ (objectif, durée, W', châssis), écran « Prêt », run, couloirs avec cartes et portes, pause par Y comme dans les autres modes, bilan et retour à l'accueil. Lot interne : il touche `main.gd` et le menu.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` (révision 1.4 de R1), `docs/lots/LOT_R1_contrat_ipc_rogue.md` (§4.1 à §4.3, §4.6).
2. `docs/2.0/PLAN_SERIE_R.md` §6 (parcours de lancement), `docs/lots/LOT_N6_affichage_menus.md`, `LOT_N4_modele_fin_seance.md`, `LOT_O4_menu_reglages.md`.
3. Code : `engine/scripts/menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `summary_view_model.gd`, `main.gd`, `ipc_client.gd`.

## 3. Prérequis

R1, R8, R10 et R11 livrés ; N6 et O4 (réglages, pour W') livrés ; l'accueil construit à partir de `hello_ack.config.modes` (préparé dans la 1.0, voir le plan §6 ; sinon ce lot le fait).

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

Aucune au-delà de la révision 1.4 de R1.

## 7. Critères d'acceptation

1. Tests sans écran : `hello_ack` sans `modes` = accueil de la 1.0 inchangé ; avec `"rogue"` = entrée « Cyber-Rogue » ; écran de départ qui envoie `start_run` avec les bons arguments ; pause par Y ; abandon confirmé qui envoie `end_session`.
2. Essai de bout en bout sans écran avec le faux core (lot J8) : accueil, départ, prêt, une salle, un couloir, bilan, accueil.
3. Run complète au Click seul, sans clavier (contrôle du propriétaire en R14).

## 8. Hors périmètre

- Garage et avatar (série V), statistiques détaillées des runs (après R9).
