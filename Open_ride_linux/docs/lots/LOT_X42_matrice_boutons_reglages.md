# Lot X42 – Matrice des boutons et des réglages, par mode et par phase

## 1. Objectif

Le propriétaire a fait cette demande le 28 octobre : « Dans les cas de test il faut essayer les divers boutons dans tous les modes et phase de jeu. Il faut également tester l'effet de chaque option dans chaque phase. Par exemple en fin de mode ERG. »

Les outils existants vérifient chaque bouton en un seul endroit :
- `boutons_click` sur le vélo ;
- les tests O17 du clavier ;
- le banc des menus ;
- la run du lot X40.

Ils vérifient aussi la persistance des réglages (X37). Aucun ne croisait chaque bouton avec chaque mode et chaque phase, ni chaque réglage avec chaque phase.

## 2. À lire

- Spécification générale, §7.1 (plan des boutons, seule référence) ;
- `core/src/openride_core/session.py` (`_handle_input`, `_set_setting`) et `settings.py` ;
- `rogue/mode.py` et `rogue/run.py` ;
- `open_world.py` ;
- contrat IPC (`set_setting`) ;
- cahiers X37 et X40.

## 3. Travail demandé

**Appel :** `python -m openride_core.tools.matrice_boutons [--partie boutons|reglages|tout] [--mode sim|erg|rogue|monde|tous] [--json] [--md RAPPORT.md]`.

### Boutons

La vraie séance du core est amenée à chaque phase de chaque mode, sans trainer ni engine.

| Mode | Phases |
| --- | --- |
| Classique SIM | prêt, en route, bonus en réserve, pause, bilan |
| ERG | prêt, bloc, pause, roue libre, dernier bloc, fin de l'entraînement, bilan |
| Cyber-Rogue | prêt, échauffement, salle, pause, couloir sans carte choisie, couloir avec carte choisie, boss, retour au calme, résultats, bilan |
| Monde ouvert | prêt, en route, carrefour proposé, pause |

Le monde ouvert utilise la doublure du générateur des tests du lot W9.

**À chaque phase :**
- La séance est copiée une fois pour chacun des 16 événements du Click : courts, longs et ambigus. Le clavier suit le même chemin.
- Chaque copie reçoit son appui par `_handle_input`, puis avance d'une seconde en Cyber-Rogue, pour que le moteur de run le traite.
- L'effet relevé est comparé à la case du §7.1, **lue dans la spécification**.

**Choix de la colonne :**
- En séance, la colonne est celle du mode roulé : monde ouvert, ERG tant qu'un entraînement est en cours, sinon le mode annoncé.
- Hors séance (prêt, pause, bilan), l'écran est un menu de l'engine. Le core doit alors relayer l'appui sans rien changer. Les menus eux-mêmes sont vérifiés par `menu_bench`.

**Effets vérifiés :**
- braquet, biais, vitesse du frein ;
- pause ;
- bonus activé ;
- bloc suivant ;
- bouton reçu par le moteur de run ;
- option suivante ou précédente et validation au couloir ou au carrefour ;
- sinon, relais seul (vue de caméra) ou aucun effet.

**En plus de l'effet :**
- aucune autre grandeur du core ne doit changer ;
- l'appui doit être relayé à l'engine ;
- aucune erreur ne doit être envoyée.

Une case que l'outil ne sait pas lire est signalée « non décrite ».

### Réglages

Chaque réglage de `settings.SETTINGS` est changé d'un pas aux phases suivantes : accueil, prêt en SIM, prêt en ERG, en route, pause, bilan.

**Règle vérifiée :**
- Hors séance, tout réglage est accepté.
- En séance, les réglages appliqués tout de suite par l'engine (`applies = now`) sont acceptés, les autres sont refusés (`busy`).

**Un réglage accepté doit :**
- être relu à sa nouvelle valeur ;
- être écrit dans `config.toml` ;
- avoir son effet dans la séance qui suit : FTP de la cible ERG, masse de la physique, difficulté, braquet de départ, bonus, vent. Pour un réglage appliqué par l'engine, c'est la valeur annoncée à l'engine qui est vérifiée.

### Sortie

- Une ligne par case en écart.
- Le total des cases conformes.
- `--md` : le tableau complet.
- `--json`.
- Codes de sortie : 0 si tout est conforme, 1 sinon, 2 pour un appel invalide.

## 4. Fichiers

- **Nouveaux :**
  - `core/src/openride_core/tools/matrice_boutons.py` ;
  - `core/tests/test_matrice_boutons.py` ;
  - ce cahier.
- **Modifiés :**
  - corrections du §7 : `session.py`, `rogue/mode.py`, `rogue/run.py`, `core/tests/test_rogue_run.py` ;
  - spécification générale §7.1 (roue libre en ERG) ;
  - contrat IPC (`set_setting` en séance) ;
  - `docs/OUTILS_DE_TEST.md`, `00_INDEX.md`, `README.md` et `SUIVI_AVANCEMENT.md` (nombre de tests).

## 5. Critères d'acceptation

1. Toutes les cases sont conformes, en moins de 30 s au cloud.
2. Chaque défaut corrigé est rejoué par un test, et l'outil le signale.
3. Un changement du §7.1 change la matrice sans toucher à l'outil, tant que la case garde une forme connue. Sinon, la case est signalée « non décrite ».

## 6. Hors périmètre

- Les menus de l'engine (banc des menus).
- L'affichage de l'effet à l'écran (bancs visuels).
- Le boîtier gauche réel, bridé sans Zwift (décision du 28 octobre : report en 4.0).

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x42`, empilée sur X41).

### Défauts trouvés et corrigés

**Cyber-Rogue : les flèches gauche et droite ne choisissaient rien au couloir.**
- Le §7.1 dit « couloir ou carte précédent, suivant ».
- Correction : elles déplacent la carte choisie, sans boucle. La première flèche choisit la première carte. À l'étape des portes, elles choisissent la porte de gauche ou de droite.

**Vent réglé au menu sans effet avant un redémarrage du core.**
- Le modèle de vent n'était construit qu'au lancement.
- Correction : il est reconstruit après chaque réglage, comme la masse ou le braquet de départ.

**Réglages appliqués par l'engine refusés pendant une séance.**
- Exemple : la vue de caméra choisie en roulant (lot V12), que l'engine écrit dans `[render] camera`. Elle recevait `busy`, s'affichait en bandeau d'erreur, et n'était pas retenue.
- Correction : en séance, seuls les réglages de la séance suivante sont refusés. Le contrat IPC est précisé dans ce sens.

### Écart au plan levé

Le §7.1 ne disait rien d'un bloc de roue libre dans un entraînement ERG. Le core y fait :
- ± = braquet, car il n'y a pas de cible à biaiser ;
- Z = bloc suivant.

Il annonce pourtant le mode SIM. La règle est ajoutée au §7.1, en attente de la confirmation du propriétaire.

### Constat laissé tel quel

En Cyber-Rogue, Z court au couloir relance l'offre de cartes. L'action du mode y est la relance, pas l'attaque. Cela est cohérent avec la famille « action du mode », mais le §7.1 ne l'écrit pas.

### Mesuré au cloud

- 390 appuis sur 26 phases et 132 réglages : tout est conforme, en 4 s.
- Tests : `core/tests/test_matrice_boutons.py`, 9 tests :
  - lecture du plan ;
  - plan illisible ;
  - boutons des quatre modes ;
  - réglages ;
  - les trois défauts rejoués ;
  - appels invalides.
