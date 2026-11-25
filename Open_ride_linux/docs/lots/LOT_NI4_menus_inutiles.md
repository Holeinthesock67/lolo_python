# Lot NI4 – Menus : session simulée rangée, QWKcode et décor vivant retirés, son coupé d'un seul choix

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série NI (éléments inutiles) : « Session simulée » sortie de l'accueil (Réglages › Appareils), « Saisir du QWKcode » et « Décor vivant » retirés, « Perfect Shifts » renommé, réglage « Son : oui / non » | Python, GDScript | NI2 (#962) | Petite | En revue (PR à valider : captures des menus) |

## 1. Objectif

Audit des éléments inutiles du 21 novembre 2026 (`plans/AUDIT_ELEMENTS_INUTILES_2026-11-21.md` des fichiers du projet),
lignes M2, M3, M4 et R10. Décisions du propriétaire du 21 novembre : retirer la saisie QWKcode (« Créer un entraînement »
couvre le besoin) et le réglage « Décor vivant », en gardant un moyen simple de couper le son (« Je veux pouvoir couper
le son »). Empilé sur NI2 (#962), dont il reprend la migration des réglages retirés.

## 2. Spécification

| # | Règle |
| --- | --- |
| NI4-1 | **Session simulée (M2).** Plus sur l'accueil : dernière ligne de Réglages › Appareils, « Session simulée (sans matériel) », ou « Revenir au matériel réel » en session simulée (le titre de l'accueil le dit toujours). Grisée pendant une recherche, comme les autres lignes ; confirmation avant la relance (codes 65 et 64 inchangés). |
| NI4-2 | **QWKcode au clavier (M3).** « Saisir du QWKcode (clavier) » retiré de la liste des entraînements, avec son écran (`qwk_editor.gd`) et la saisie au clavier. Un fichier `.qwk` posé dans `~/OpenRide/Workouts/` reste lu (`workout_formats.py`) ; l'aide ERG garde la syntaxe sous « Fichier QWKcode (GoldenCheetah) ». La commande `create_workout_qwk` reste au contrat (le core y répond toujours), l'engine ne l'envoie plus. |
| NI4-3 | **Perfect Shifts (M4).** Libellés en français : « Changements parfaits » au bilan du Cyber-Rogue, « changement parfait » dans le guide, les cartes, la légende et le bandeau (« CHANGEMENT PARFAIT +10 »). Les clés (`perfect_shifts`, `perfect_shift_adrenaline`…) ne changent pas. |
| NI4-4 | **Décor vivant (R10).** Retiré de Réglages › Graphisme : toujours actif, son coût réglé par la Qualité graphique. `[render] living` passe dans `migration_reglages.RETIRED` (ligne mise en commentaire au lancement, copie `.bak`) et dans `config.EXPERT_KEYS` ; `--living=off` reste pour les bancs. La ligne « Abri derrière les véhicules » ne dépend plus de lui. |
| NI4-5 | **Son : oui / non.** Nouveau réglage `audio.enabled` (booléen, `true` par défaut), première ligne de Réglages › Son, appliqué tout de suite : « non (silence) » coupe le bus Master, les volumes gardent leur valeur et se cachent (règle commune `WHEN` de NI2). |

## 3. Fichiers

- `core/src/openride_core/settings.py`, `config.py`, `migration_reglages.py`, `rogue/cards.py`, `data/progression.toml`, `tools/rogue_bout_en_bout.py` ;
- `engine/scripts/menu_model.gd`, `menu_flow.gd`, `pairing_view_model.gd`, `main.gd`, `ipc_client.gd`, `button_help.gd`, `workout_help.gd`, `audio_mix.gd`, `settings_view_model.gd`, `summary_view_model.gd`, `rogue/rogue_guide_model.gd` ; `qwk_editor.gd` supprimé ;
- tests : `core/tests/test_settings.py`, `test_migration_reglages.py` ; `engine/tests/unit/test_menu_flow.gd`, `test_menu_model.gd`, `test_menu_style.gd`, `test_audio_mix.gd`, `test_rogue_guide_model.gd` ; scénarios du banc des menus `ni4_menus` (nouveau, captures `ni4_*`), `reglages`, `erg`, `sessions`, `appareils`, `connexion_auto` ; `erg_qwkcode` supprimé ;
- `docs/GUIDE_UTILISATION.md`, `docs/SRS_v1.1.md`, `docs/contracts/ipc_v1.md`, `CHANGELOG.md`.

## 4. Critères d'acceptation

1. Accueil sans « Session simulée » ; Réglages › Appareils la propose en dernière ligne avant Retour, avec confirmation.
2. Liste des entraînements : « Créer un entraînement (intervalles) » puis « Comment ça marche ? », sans QWKcode ; un `.qwk` déposé apparaît toujours.
3. Réglages › Graphisme sans « Décor vivant » ; un `config.toml` avec `living = false` est remis par défaut au lancement (copie `.bak`).
4. Réglages › Son : « Son — oui » en tête ; « non (silence) » coupe tout le son et cache les volumes ; « oui » rend les volumes d'avant.
5. Bilan du Cyber-Rogue : « Changements parfaits ».

## 5. Recette PC (catégorie : logique + captures des menus)

Pas de rendu ni de physique touchés : fumée, puis banc des menus en medium et captures des menus touchés à valider par le propriétaire.

```bash
cd ~/Games/lolo_python/Open_ride_linux
python3 engine/tests/menu_bench.py --scenario ni4_menus --scenario reglages --scenario erg --scenario sessions --scenario appareils --qualite medium --captures ecrans
```

Captures à valider : `ni4_accueil`, `ni4_liste_erg`, `ni4_graphisme`, `ni4_son_oui`, `ni4_son_non`, `ni4_appareils`.
