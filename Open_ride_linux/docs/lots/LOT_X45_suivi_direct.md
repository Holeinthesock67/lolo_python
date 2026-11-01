# Lot X45 – Fenêtre de suivi en direct d'un essai, qui reste ouverte

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : fenêtre de suivi en direct d'un essai guidé, qui reste ouverte après la fin (`suivi_direct`, `trainer_steps --fenetre`) | Python | X43, X44 | Petite | Livré le 29 octobre (PR #587) |

## 1. Objectif

Séance du 29 octobre : le banc du trainer a été lancé à distance, sans terminal visible pour le cycliste. Il ne voyait donc ni le palier, ni le compte à rebours, ni la puissance. Et l'écran de guidage disparaissait à la fin de l'essai. Il faut une fenêtre à part, lisible de loin, qui reste ouverte après la fin.

## 2. Spécification

| # | Règle |
| --- | --- |
| X45-1 | `Guide` (module `guide`) accepte `live_file`. L'état de son écran est alors écrit dans un fichier JSON, au plus 5 fois par seconde, par écriture atomique (`os.replace`). L'état comprend l'étape, le compte à rebours, les valeurs en direct, l'alerte, l'encadré, les relevés, les notes et le verdict. |
| X45-2 | Nouvel outil `python -m openride_core.tools.suivi_direct DOSSIER\|live.json`. Il rejoue cet état sur un `Guide` local : même écran plein terminal, mêmes bips (début, 3, 2, 1, fin, alerte, verdict). |
| X45-3 | Après le verdict, la fenêtre reste ouverte jusqu'à « Entrée » (ou sa fermeture). Si l'essai se tait plus de 5 s avant son verdict, la fenêtre affiche « Plus de nouvelles de l'essai depuis N s ». |
| X45-4 | `trainer_steps --fenetre` écrit `live.json` dans le dossier de l'essai et ouvre la fenêtre. Le terminal utilisé est `OPENRIDE_TERMINAL` (commande avec `{cmd}`), sinon le premier trouvé parmi gnome-terminal, x-terminal-emulator, konsole, xfce4-terminal et xterm. Sans terminal, l'outil affiche la commande à lancer. En fin d'essai, les décrochages relevés (lot X44) s'ajoutent aux notes de la fenêtre. |

## 3. Fichiers

- `core/src/openride_core/tools/guide.py` (`live_file`, `state`, `publish`, `verdict`) ;
- `core/src/openride_core/tools/suivi_direct.py` (nouveau) ;
- `tools/trainer_steps.py` (`--fenetre`) ;
- `core/tests/test_suivi_direct.py` ;
- `docs/OUTILS_DE_TEST.md`.

## 4. Critères d'acceptation

1. `pytest` passe. L'état publié se relit, et le lecteur rejoue étape, alerte, relevés et verdict sans doublon. Il signale un essai muet et demande « Entrée » à la fin.
2. `trainer_steps --trainer sim --fast --fenetre` produit un `live.json` avec le verdict.
3. Sur le PC (via le fil de fusion) : banc lancé à distance avec `--fenetre`. La fenêtre s'ouvre sur le bureau et reste ouverte à la fin.

## 5. Hors périmètre

`--fenetre` pour les autres outils guidés (`click_recette`, `coupures`, `boutons_click`, `fc_recette`) : même mécanisme, à brancher outil par outil si le besoin se présente.

## Livraison

PR #587, fusionnée le 29 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Séance du 29 octobre ; en PR ».
