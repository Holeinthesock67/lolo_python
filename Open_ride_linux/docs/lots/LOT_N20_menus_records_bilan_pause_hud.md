# Lot N20 – Présentation des menus, étape 4 : records, bilan, pause, confirmation, couleurs du HUD et du globe

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Présentation des menus, étape 4 : records, bilan, pause, confirmation ; couleurs du HUD et du globe ramenées au thème | GDScript | N19 | Moyenne | En partie : 4a à 4e fusionnées (PR #483, #511, #531, #631, #634) ; reste le bilan en tuiles et le profil du segment (§9) |

## 1. Objectif

Dernière étape de la présentation des menus (demande du propriétaire du 27 octobre, `docs/PRESENTATION_MENUS.md`). Après N19, il reste des écrans en lignes de texte et des couleurs écrites en dur hors du thème commun :

- **Records** (lot T10) : cartes par segment et par parcours, record en or ;
- **Bilan de fin de séance** (lot N4, `summary_view.gd`) : tuiles de chiffres et graphique, records battus mis en valeur ;
- **Pause** et **confirmation** : titre, raison de la pause, curseur de la difficulté, action dangereuse repérée ;
- **HUD et globe** : couleurs ramenées aux jetons de `ui_theme.gd`, avec une table à part pour les couleurs de données (zones de Coggan, courbes).

## 2. À lire

1. `docs/PRESENTATION_MENUS.md`, N19 (étape 3), `docs/SPECIFICATION_GENERALE.md` §7.1, cahiers `LOT_N4_modele_fin_seance.md`, `LOT_T10_menu_records_bonus.md`, `LOT_Q1_difficulte_en_jeu.md`, `LOT_O14_affichage_courbes.md`, `LOT_V9_fin_de_seance_progression.md` (bloc de progression du bilan, PR #458 en cours).
2. Code : `engine/scripts/menu_view.gd`, `menu_flow.gd`, `records_view_model.gd`, `summary_view.gd`, `summary_view_model.gd`, `settings_view_model.gd` (`PAUSE_DIFFICULTY`), `detail_card.gd`, `ui_theme.gd`, `hud_view.gd`, `erg_view.gd`, `workout_chart_view.gd`, `junction_view.gd`, `world_menu_view.gd`, `banner.gd` ; `engine/tests/visual_check.py` (scènes `pause`, `bilan`, `erg`, `erg_courbes`).

## 3. Prérequis

N19 fusionné (mêmes fichiers `menu_view.gd` et `menu_flow.gd`). V9 n'est pas nécessaire : si sa PR est fusionnée avant, son bloc de progression prend la même présentation ; sinon V9 s'y conforme.

## 4. Travail demandé

### 4.1 Records

- Liste des parcours et des segments avec, en carte, le record personnel en grand chiffre `GOLD`, sa date, l'écart du deuxième temps en `DIM`, et le profil du segment ; une montée montre aussi sa catégorie ; un segment sans temps s'écrit « pas encore de temps », sans zéro.
- Fait (étape 4f) : profil d'altitude du segment dans la carte (calculé par `main.gd` au chargement du parcours), longueur et pente moyenne dans l'en-tête (« Montée · cat. 3 · 3,1 km à 5,8 % »).

### 4.2 Bilan de fin de séance

- En-tête « Bilan de la séance » et nom du parcours ; six tuiles (distance, durée, dénivelé, puissance moyenne et normalisée, fréquence cardiaque moyenne, cadence moyenne ; une tuile sans donnée est retirée, pas affichée vide) ; graphique de la puissance de la séance (même trait que les courbes d'O14, réduit) ; records battus en lignes `GOLD` avec l'ancien temps ; résultat du test de FTP s'il y en a un (offre de N19).
- La logique reste dans `summary_view_model.gd` ; `summary_view.gd` ne fait que l'affichage, avec les jetons du thème.
- Fait (étape 4f, maquette `/mnt/project-files/menus/n20-bilan-tuiles/` du 8 novembre) : tuiles sur trois colonnes (dénivelé nul retiré, NP en complément de la puissance), courbe réduite `power_profile` en trait blanc avec la ligne pointillée de la FTP et, en ERG, le profil cible coloré par zone ; records battus du dernier au premier (trois au plus, « avant 6:58,9 » ou « premier temps ») ; ligne des autres chiffres (IF, TSS, puissance max, abri) ; lignes propres au mode (Cyber-Rogue, WTF, Dernier survivant) dessous ; bandeau du test de FTP (valeur, ancienne FTP, écart, fiabilité ou avertissements) à la place de la ligne d'état. Si la carte ne tient pas au-dessus du bandeau des boutons (bilan détaillé avec progression en 1280×720), polices puis écarts réduits, puis tuiles basses, blocs ERG sur deux colonnes et enfin courbe cachée.

### 4.3 Pause et confirmation

- **Pause** : titre, raison de la pause sous le titre (`PAUSE_REASONS`, déjà en place), entrées actuelles (Reprendre, Terminer et enregistrer, Abandonner, Difficulté), la difficulté en curseur dans sa rangée avec l'édition en place de N19 ; carte de détail avec les chiffres de la séance en cours (distance, durée, puissance moyenne).
- **Confirmation** : petite carte centrée sur le voile, question en `TEXT`, deux choix ; l'action qui perd des données (« Abandonner », « Quitter ») en `DANGER`, jamais sélectionnée par défaut.

### 4.4 Couleurs du HUD et du globe

- `ui_theme.gd` gagne une table `DATA` : couleurs des zones de Coggan (Z1 à Z7, celles d'`erg_view.gd` aujourd'hui), des courbes (cible, puissance, fréquence cardiaque, cadence, celles de `workout_chart_view.gd`), de l'abri et du vent (`hud_view.gd`). Leurs valeurs ne changent pas dans ce lot : elles changent seulement de place.
- `hud_view.gd`, `erg_view.gd`, `workout_chart_view.gd`, `junction_view.gd`, `world_menu_view.gd` et `banner.gd` prennent toutes leurs couleurs dans `ui_theme.gd` (jetons ou `DATA`) : fonds des panneaux du HUD en `SURFACE` translucide, textes en `TEXT` et `DIM`, alertes en `WARN` et `DANGER`, carte du globe dans les tons du thème.

### 4.5 Tests et captures

- `test_menu_style.gd` : aucune couleur écrite en dur (`Color(` hors de `ui_theme.gd`) dans les vues des menus, du HUD et du globe, avec une liste d'exceptions vide à la fin du lot ; record en `GOLD` ; action dangereuse en `DANGER`.
- `visual_check.py` : captures de référence `pause` et `bilan` refaites ; nouvelles scènes `records` et `confirmation`, vérifiées par textes et pixels ; `erg` et `erg_courbes` vérifiées sans changement de couleur des zones.
- `menu_bench.py` sur le PC : temps d'image des menus et du HUD avant et après, sans hausse de plus de 1 ms.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/menu_view.gd`, `menu_flow.gd`, `records_view_model.gd`, `summary_view.gd`, `summary_view_model.gd`, `detail_card.gd`, `ui_theme.gd`, `ui_icons.gd`, `button_help.gd`, `hud_view.gd`, `erg_view.gd`, `workout_chart_view.gd`, `junction_view.gd`, `world_menu_view.gd`, `banner.gd` ; `engine/tests/unit/test_menu_style.gd`, `test_menu_flow.gd`, `test_records_view_model.gd`, `test_summary_view_model.gd`, `test_hud_view.gd`, `test_erg_view.gd`, `test_workout_chart_view.gd`, `test_world_menu_view.gd`, `engine/tests/visual_check.py` ; `docs/PRESENTATION_MENUS.md`, `docs/GUIDE_UTILISATION.md` (captures décrites), `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** le core et le contrat IPC ; la disposition du HUD (positions et tailles des cadrans, lot E3) ; les scènes 3D, le rendu Cyber-Rogue (charte néon de R17, scène à part).

## 6. Modifications de contrat autorisées

Plan des boutons et réglages inchangés. Décision du propriétaire du 8 novembre (bilan en tuiles, étape 4f) : la courbe du graphique et l'ancien temps des records battus viennent du core, pour que le bilan relu dans l'Historique soit le même qu'en fin de séance. Ajouts compatibles de la révision 1.10 du contrat IPC (1.8 : BC2, 1.9 : N17/N18) : `summary.power_profile` (au plus 50 points, cible ERG comprise, aussi dans `history_session`) et `pr_time_s` dans `summary.segments.passes` ; la courbe est retirée avant le bilan entier d'une trame trop lourde (`ipc_budget`).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` et `visual_check.py` passent en entier.
2. Bilan d'une séance simulée de 10 min : six tuiles ou moins, sans tuile vide ; un record battu en `GOLD` avec l'ancien temps.
3. Pause : Difficulté réglable en place, Y revient à la pause sans rien changer ; « Abandonner » demande une confirmation où le choix par défaut ne perd rien.
4. Aucune couleur écrite en dur dans les vues listées au §5 ; couleurs des zones de Coggan identiques à l'avant (comparaison pixel des scènes `erg`).

**Sur le PC cible (le propriétaire) :** fin d'une séance courte, lecture du bilan à 2 m ; écran Records ; pause au Click avec réglage de la difficulté ; avis sur la lisibilité.

## 8. Hors périmètre

- Bloc de progression (XP, pièces, niveau) du bilan : V9 ; garage : V8.
- Nouvelles données dans le bilan (puissance par zone, courbe de puissance maximale) : lot à part si le propriétaire le demande.
- Disposition du HUD et nouveaux cadrans.

## 9. État (point du 8 novembre)

Fusionné sur `main` (titres « Présentation des menus, étape 4a… 4e », sans « N20 ») :

- 4a, PR #483 (28 octobre) : difficulté de la pause réglée dans sa rangée, groupe Graphisme ;
- 4b, PR #511 (28 octobre) : table `DATA` de `ui_theme.gd`, plus de couleur en dur dans le HUD, l'ERG, les courbes, le carrefour et le globe (§4.4) ;
- 4c, PR #531 (29 octobre) : cartes des records (record en `GOLD`, écart au deuxième, date), scènes `records` et `records_table`, double légende Click / clavier ;
- 4d, PR #631 (31 octobre) : carte de confirmation centrée, « Non » d'office, « Oui » en `DANGER`, scène `confirmation` ;
- 4e, PR #634 (31 octobre) : carte de la pause (durée, distance, puissance moyenne).

Reste à faire (une PR, engine seul, sans vélo) :

- **bilan en tuiles** (§4.2) : `summary_view.gd` affiche encore les lignes sur deux colonnes ; à faire : six tuiles sans tuile vide, graphique de la puissance (série à accumuler côté engine), records battus en `GOLD` avec l'ancien temps, résultat du test de FTP ; capture de référence `bilan` à refaire et à faire valider ;
- **profil du segment** et catégorie de la montée dans la carte des records (§4.1) ;
- `menu_bench.py` avant/après sur le PC (3 qualités) et lecture du bilan à 2 m par le propriétaire.
