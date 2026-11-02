# Lot X39 – Écart de progression avant/après une PR (`openride-core xp --compare`)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Écart de progression avant/après une PR (`openride-core xp --compare`) | Python | V2, V3b | Petite | Livré le 28 octobre (PR #505) |

## 1. Objectif

L'expérience, les pièces et les défis sont recalculés depuis les journaux des séances (lots V2 et V3b). Une PR qui touche à `progression.py`, `coins.py`, `data/progression.toml` ou au journal peut changer, sans le dire, ce que vaut l'historique déjà roulé. Proposition du fil V5 (28 octobre) : rejouer le recalcul sur un même dossier de journaux avant et après une PR, et sortir l'écart séance par séance. L'outil sert aussi sur le PC, avec les vrais journaux, sans rien publier.

## 2. À lire

`core/src/openride_core/tools/xp.py` (commande `openride-core xp`, sortie `--json` aux clés stables), `progression.py`, `coins.py`, cahiers V2 (§4.7) et V3b.

## 3. Travail demandé

- **`openride-core xp --save FICHIER`** : écrit l'instantané (la sortie `--json`) puis affiche la progression comme d'habitude.
- **`openride-core xp --compare FICHIER`** : recalcule et compare à l'instantané (ou à une ancienne sortie `--json`). Écart des totaux (XP, niveau, pièces gagnées, solde), des défis (gagnés en plus, perdus), des journaux devenus illisibles, et des séances (par nom de journal : comptée ou refusée, raison, XP, pièces ; séance ajoutée ou disparue). `--json` donne l'écart en JSON (clés en tête du module).
- Codes : 0 sans écart, 1 avec écart, 2 si l'instantané est illisible. `--save` et `--compare` s'excluent.
- Usage : sur `main`, `openride-core xp --save /tmp/xp-avant.json` ; sur la branche de la PR, `openride-core xp --compare /tmp/xp-avant.json`. Un écart voulu par la PR (barème changé) est écrit dans sa description.

## 4. Fichiers

- **Modifiés :** `core/src/openride_core/tools/xp.py`, `core/src/openride_core/__main__.py`, `docs/OUTILS_DE_TEST.md`, `docs/lots/LOT_V2_moteur_experience.md` (§4.7), `00_INDEX.md`, `README.md` et `SUIVI_AVANCEMENT.md` (nombre de tests).
- **Nouveaux :** `core/tests/test_xp_compare.py`, ce cahier.

## 5. Critères d'acceptation

1. Un instantané comparé au même dossier donne « aucun écart » et le code 0.
2. Une séance ajoutée, une séance dont l'XP change, un défi perdu ou gagné, une séance qui passe de comptée à refusée sont listés, avec le code 1.
3. Un instantané illisible ou absent donne le code 2.
4. Rien n'est écrit hors du fichier de `--save` ; l'instantané des vrais journaux reste sur le PC (règle de confidentialité).

## 6. Hors périmètre

Le scénario `sim_bench` « équipé » et les scènes `visual_check` du gain d'équipement et du record : outils locaux des séries V et T10, livrés par leurs fils (règle de partage du 28 octobre).

## 7. Réalisation

- `xp.run` construit toujours la sortie `--json` ; `--save` l'écrit, `--compare` la compare (`compare_snapshots`, `has_changes`, `format_diff`).
- Tests : `core/tests/test_xp_compare.py` (4 tests : instantané sans écart, séance ajoutée et XP changée en texte et en JSON, défis et refus, instantané illisible).

## Livraison

PR #505, fusionnée le 28 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Oui ».
