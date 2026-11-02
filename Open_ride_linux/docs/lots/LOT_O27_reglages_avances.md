# Lot O27 – Sous-écran « Avancé » et réglages en parties

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Sous-écran « Avancé » : monde ouvert hors ligne, plafonds du cache et des thèmes, progression ; `settings` en parties ; renvoi de la consigne laissé aux essais | Python + GDScript | O26 | Petite | Livré le 31 octobre (PR #660) |

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, décision 2 validée par le propriétaire) : quatre clés utiles à un joueur sans terminal n'existaient que dans `config.toml`. Ce sont le monde ouvert hors ligne, les deux plafonds de disque et la progression. La liste `settings` arrivait au plafond de 32 éléments d'un seul datagramme. Elle part maintenant en parties, comme `routes`.

## 2. Spécification

| # | Règle |
| --- | --- |
| O27-1 | Réglages › Avancé (groupe `advanced`, dernier sous-écran) : « Télécharger les cartes » (`open_world.network`, oui / non, hors ligne : cache seulement), « Cache du monde » (`open_world.cache_max_gb`, Go), « Place pour les thèmes » (`render.theme_library_gb`, Go), « Progression et Garage » (`progression.enabled`, oui / non, sans Garage). |
| O27-2 | Prise en compte : le téléchargement s'applique à la prochaine recherche ou carte du monde ouvert, sans relancer, et les plafonds à la prochaine écriture du cache ou à la prochaine installation de thème. La progression est lue au démarrage du core : `applies` = `relaunch`, avec la ligne « Relancer OpenRide maintenant » du lot O26. |
| O27-3 | Règles générales, sans cas par clé : tout booléen sans légende propre s'affiche oui / non. Les bornes d'un nombre sont arrondies vers l'intérieur (cache de 0,5 à 500 Go → 1 à 500). |
| O27-4 | `settings` en parties de 60 000 octets au plus (`part`, `parts`, `truncated`), découpées par `chunk_list_message` comme `routes`. L'engine réunit les parties avec la fonction qui sert au menu du monde ouvert. Un message en une partie, même envoyé sans demande, est livré tel quel. Le plafond de 32 réglages disparaît. |
| O27-5 | `trainer.resend_s` (renvoi de la consigne) reste un réglage d'essai des décrochages du trainer (`EXPERT_KEYS`). Il entrera dans Avancé si l'essai le garde réglable. Les cinq clés quittent `PENDING_KEYS`. |

## 3. Contrat

`docs/contracts/ipc_v1.md` (révision 1.5) et `settings.schema.json` : champs `part`, `parts` et `truncated`, groupe `advanced`, 64 éléments au plus par partie. Ce changement est compatible : tant que la liste tient en 60 000 octets, le core n'envoie qu'une partie.

## 4. Fichiers

- Core : `settings.py`, `config.py` (`PENDING_KEYS`, `EXPERT_KEYS`), `session.py` (`_send_settings` en parties, monde ouvert relu à chaque demande).
- Engine : `ipc_client.gd` (`_assemble_parts`, `_on_settings_part`), `settings_view_model.gd` (groupe Avancé, booléens oui / non).
- Docs : contrat, schéma, `GUIDE_UTILISATION.md`, `SRS_v1.1.md` §11, `CHANGELOG.md`.
- Tests : `core/tests/test_settings.py`, `engine/tests/unit/test_menu_flow.gd`, `engine/tests/unit/test_world_menu_view.gd` ; banc des menus `reglages`.

## 5. Critères d'acceptation

1. Le sous-écran Avancé montre les quatre réglages, et les écrire met à jour `config.toml` (`network = false`, `cache_max_gb = 20`, `enabled = false`).
2. Avec la progression coupée, « Relancer OpenRide maintenant » apparaît. Après le relancement, le Garage n'est plus proposé.
3. Une liste `settings` découpée en plusieurs parties est réunie par l'engine, dans l'ordre.

## Livraison

PR #660, fusionnée le 31 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Audit des options du 31 octobre, décision 2 validée par le propriétaire ; en PR ».
