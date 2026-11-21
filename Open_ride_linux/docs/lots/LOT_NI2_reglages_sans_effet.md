# Lot NI2 – Réglages sans effet et doublons retirés ou unifiés

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série NI (éléments inutiles) : une seule place par réglage, règle commune des lignes sans effet (cachées), choix d'essai et plafond en Avancé, « Textures du décor » retiré avec migration des fichiers | Python, GDScript | O4, O27, MJ4 (livrés) | Moyenne | En revue (PR à valider : recette PC et captures des Réglages) |

## 1. Objectif

Audit des éléments inutiles du 21 novembre 2026 (`plans/AUDIT_ELEMENTS_INUTILES_2026-11-21.md` des fichiers du projet,
section 2), découpage validé par le propriétaire : « HUD et réglages d'abord ». Ce lot prend les lignes R1 et R3 à R9 ;
R2 (« Grand Prix : distance en ligne ») part avec GPL1 (#942) et R11 (trois réglages de difficulté des bots) avec NI3,
après le classement Elo (#941). Aucune règle de jeu ne change : seules les lignes du menu bougent.

## 2. Spécification

| # | Règle |
| --- | --- |
| NI2-1 | **Une seule place par réglage (R1).** Les réglages d'un écran qui a les siens (`survivor.*`, `grandprix.*`, `race.*`, `coach.*` : écrans Prêt du Dernier survivant, du Grand Prix et de la Course, écran de la séance conseillée) vont au groupe `screen` (`settings.SCREEN_SECTIONS`) : absents de « Réglages », toujours dans la liste `settings` pour leur écran et pour `set_setting`. Une section, pas une liste de clés : un réglage ajouté à ces sections suit la règle. |
| NI2-2 | **Règle commune des lignes sans effet (R3, R6).** `Setting.when` (champ `when` des éléments de `settings`) : la ligne n'agit que si l'un des réglages dont elle dépend a une des valeurs données ; l'engine la cache sinon (`settings_view_model.is_active`), valeur gardée, et la liste suit la valeur en cours de modification. Un choix à une seule valeur est caché de la même façon (Thème sans pack installé). Lignes concernées : force et direction du vent (vent constant ou en rafales), rafales (en rafales), ressenti du vent (vent présent), mois (saisons « selon la date » ou jour et nuit allumé), cadence de départ (départ au pédalage), abri derrière les véhicules (décor vivant : pas de circulation sans lui). |
| NI2-3 | **Difficulté à la pause (R4).** Même règle : la ligne « Difficulté » de la pause est cachée quand un ERG tourne (entraînement, ERG libre, ERG cadence) et revient dès que SIM est choisi. |
| NI2-4 | **Textures du décor (R5).** Retiré du menu : « auto » suit la Qualité graphique (basses et moyennes avaient la même taille). `migration_reglages.py` met en commentaire `[render] texture_level` dans `config.toml` et dans chaque `profil.toml` au lancement (copie `.bak`, reste du fichier gardé) ; la clé reste lue par `config.py` et `--texture-level` pour les bancs. |
| NI2-5 | **Choix d'essai en Avancé (R7, R8, R9).** « Pilotage du trainer » et « Ressenti du vent » passent dans Avancé ; « Plafond du vent » devient « Pente ajoutée max » (il borne vent, abri et gravel), dans Avancé, avec une légende. `SETTINGS` est rangé par groupe dans l'ordre de `GROUPS` : les lignes restent écrites près de leurs voisines du fichier. |
| NI2-6 | **Contrat.** Ajouts compatibles sans changement de `rev` (journal du contrat, 21 novembre) : valeur `screen` de `group`, champ facultatif `when`, schéma `settings.schema.json`. Un engine plus ancien montre les réglages `screen` dans « Autres réglages » et ignore `when`. |

## 3. Fichiers

- `core/src/openride_core/settings.py`, `core/src/openride_core/migration_reglages.py` (nouveau), `core/src/openride_core/launcher.py` ;
- `engine/scripts/settings_view_model.gd`, `engine/scripts/menu_flow.gd` ;
- tests : `core/tests/test_settings.py`, `core/tests/test_migration_reglages.py` (nouveau), `core/tests/test_resistance_calculee.py`,
  `engine/tests/unit/test_settings_rules.gd` (nouveau), `engine/tests/unit/test_free_erg_menu.gd`, scénarios `reglages`, `persistance` et
  `erg_libre` du banc des menus (captures `ni2_*` dans `reglages`) ;
- `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/settings.schema.json`, `docs/GUIDE_UTILISATION.md`, `docs/SRS_v1.1.md`, `CHANGELOG.md`.

## 4. Critères d'acceptation

1. Réglages › Séance sans aucune ligne « Survivant : », « Grand Prix : », « Conseil : » ni « Pilotage du trainer » ; les écrans Prêt du Dernier survivant et du Grand Prix gardent leurs réglages, l'écran du conseil les siens.
2. Réglages › Vent avec le vent coupé : la seule ligne « Vent » ; constant : force et direction ; en rafales : les rafales en plus, tout de suite pendant le choix.
3. Réglages › Graphisme : ni « Textures du décor », ni « Thème » sans pack de thème, ni « Mois » quand saisons et jour et nuit sont coupés.
4. Réglages › Avancé : « Pilotage du trainer », « Pente ajoutée max », « Ressenti du vent » (si le vent n'est pas coupé), puis les lignes d'avant.
5. Pause d'une séance ERG : pas de « Difficulté » ; en SIM, elle est là.
6. Un `config.toml` qui porte `texture_level = "low"` : la ligne est en commentaire après le lancement, copie `config.toml.bak`, rien d'autre ne change.

## 5. Recette PC (catégorie : logique + captures des menus)

Pas de rendu ni de physique touchés : banc des menus seulement, en medium, puis captures des sous-écrans touchés à valider par le propriétaire.

```bash
cd ~/Games/lolo_python/Open_ride_linux
python3 engine/tests/menu_bench.py --scenario reglages --scenario persistance --scenario erg_libre --scenario dernier_survivant --scenario grand_prix --qualite medium --captures ecrans
```

Captures à valider : `ni2_seance`, `ni2_graphisme`, `ni2_vent_coupe`, `ni2_vent_rafales`, `ni2_avance`.
