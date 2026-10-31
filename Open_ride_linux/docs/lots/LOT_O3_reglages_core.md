# Lot O3 – Réglages côté core : lire et écrire FTP, thème et qualité dans la configuration locale

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Réglages côté core : FTP, masse, braquet de départ, thème et qualité écrits dans `~/OpenRide/config.toml` | Python | N12 ; N10 pour les thèmes | Petite | **Livré le 26 octobre** (avec O4, issue #121) |

## 1. Objectif

Après la série N, OpenRide se lance et se pilote sans terminal, mais la FTP, le thème et la qualité graphique ne se changent qu'en éditant `~/OpenRide/config.toml` à la main. Ce lot écrit la partie core d'un écran « Réglages » : une liste fermée de réglages, leur lecture, leur validation et leur écriture dans la configuration locale, en conservant le reste du fichier et ses commentaires. L'écran du menu viendra au lot O4.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_N12_appairage_core.md` (écriture de `config.toml` avec commentaires conservés et sauvegarde `.bak`), `docs/lots/LOT_N10_packs_themes.md` (`theme-list`), `docs/lots/LOT_L4_prereglages_qualite.md`.
2. `docs/SRS_v1.1.md` §11 (configuration) ; code : `core/src/openride_core/config.py` (`ftp_w`, `quality`, `theme`, table des bornes et des choix, `validate`), `core/src/openride_core/pairing.py` (N12), `core/src/openride_core/__main__.py`.

## 3. Prérequis

N12 fusionné (on réutilise son écriture de `config.toml`) ; N10 fusionné pour la liste des thèmes installés (sinon, seul `default` est proposé et le lot le dit).

## 4. Travail demandé

- Extraire l'écriture de `config.toml` de `pairing.py` dans un module commun `config_writer.py` (livré : `core/src/openride_core/config_edit.py`, voir §9 ; `update_config(changes: dict[tuple[str, str], object], path=None) -> list[str]` : sauvegarde `.bak`, commentaires et clés inconnues conservés, validation par `config.validate` avant d'écrire, rien n'est écrit en cas d'erreur). `pairing.save` l'appelle ; ses tests restent verts sans modification.
- Nouveau module `core/src/openride_core/settings.py` :
  - `SETTINGS` : liste ordonnée des réglages proposés au menu, chacun avec sa clé (`rider.ftp_w`, `rider.mass_kg`, `trainer.difficulty_pct`, `render.quality`, `render.theme`, `gearing.start_gear`), un libellé français, son type, ses bornes ou ses choix (tirés de `config.py`, jamais recopiés), son pas pour un réglage au Click (`ftp_w` : 5 W ; `mass_kg` : 1 kg ; `difficulty_pct` : 10 %, affiché en curseur de 0 à 100 % ; braquet : 1) et l'indication « pris en compte à la prochaine séance » ou « immédiatement » ;
  - `current(cfg) -> list[dict]` : valeur actuelle de chaque réglage, prête pour l'IPC (même forme que celle proposée au lot O4, §4) ;
  - `step(key, value, direction) -> valeur` : valeur suivante ou précédente, bornée, choix parcourus en boucle ;
  - `apply(changes, path=None)` : valide puis écrit via `config_writer`.
- Commande `openride-core settings [--json]` (affiche les réglages) et `openride-core settings set CLÉ VALEUR [--config FICHIER]` (écrit un réglage, refuse une clé hors de `SETTINGS`).
- Documentation : `README.md` (section configuration).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/settings.py`, `core/tests/test_settings.py` (prévus aussi : `config_writer.py` et ses tests, remplacés par `config_edit.py`, voir §9).
- **Modifiés :** `core/src/openride_core/pairing.py` (appel du module commun), `core/src/openride_core/__main__.py`, `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** l'engine, le contrat IPC, `session.py`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Fichier de départ avec commentaires, section inconnue et appareils appairés : `settings set rider.ftp_w 265 --config TMP` ne change que cette ligne, crée `config.toml.bak`, et les tests de N12 passent toujours.
3. Valeur hors bornes (`ftp_w` 20) ou choix inconnu (`quality ultra`) : rien n'est écrit, message qui cite la clé et les bornes, code de sortie non nul.
4. `step` : `ftp_w` 600 + 5 reste à 600 ; `quality` `high` → `low` en boucle ; thème parcouru dans l'ordre de `theme-list`.
5. Les bornes et choix de `SETTINGS` sont lus dans `config.py` (un test change une borne dans `config.py` simulé et la retrouve dans `SETTINGS`).
6. `settings --json` est stable et documenté dans le module.

## 8. Hors périmètre

- Écran du menu et messages IPC (lot O4).
- Profil de plusieurs cyclistes.

## 9. Livraison (26 octobre 2026)

Fait avec O4 (demande du propriétaire du 26 octobre : « un menu qui permet de modifier les options »).

- `settings.py` : `SETTINGS` (FTP, poids du cycliste, difficulté en SIM, braquet de départ, qualité, thème), bornes et choix lus dans `config.py` (`BOUNDS`, `CHOICES` ; braquet de départ borné par `n_gears` ; thèmes : `default` et les dossiers de `~/OpenRide/Themes/` avec un `theme.json`), `current`, `step`, `check`, `apply`.
- Écart au §4 : pas de module `config_writer.py` ; `config_edit.py` (N12/N14) sert d'écriture commune et accepte maintenant des valeurs typées (nombre, booléen, texte).
- Commandes `openride-core settings [--json]` et `openride-core settings set CLÉ VALEUR [--config FICHIER]`.
- Tests : `core/tests/test_settings.py` (critères 2 à 5, refus sans écriture, messages IPC).
