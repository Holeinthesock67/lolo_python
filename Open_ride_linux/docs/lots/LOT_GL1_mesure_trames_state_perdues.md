# Lot GL1 : mesure des trames state perdues entre le core et l'engine (gels du monde ouvert)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Gels du monde ouvert : l'engine et le core notent chaque minute les trames state reçues, sautées, en retard, la taille max et les erreurs d'envoi UDP ; un trou de plus de 2 s est noté avec ses seq | Python, GDScript | X17, X25 | Petite | En cours (codé le 22 novembre, banc PC à faire) |

Fil global « Supprimer les à-coups récurrents de main » (22/11), après l'essai vélo du 22/11.

## Constat (essai du 22/11, monde ouvert de Biarritz en high)
- Le cycliste voit l'image « geler » plusieurs secondes vers 9 min.
- Le journal de l'engine montre, trois minutes de suite, des écarts de 9,1 s, 10,4 s et 9,5 s entre deux trames
  `state` reçues, et 1 688, 1 450 puis 1 398 trames par minute au lieu de 1 800.
- Pendant ce temps le core envoie normalement (ligne `Gigue` : state max 25 ms, boucle saine, aucun avertissement)
  et le rendu ne gèle pas (image max 128 à 150 ms). Les six autres balades de l'après-midi n'ont rien de tel.
- Le journal ne permet pas de dire où les trames se perdent : l'erreur d'envoi UDP du core n'est écrite qu'en
  débogage, et l'engine ne note ni les trames rejetées (seq en retard) ni la taille des datagrammes.

## Ce que fait le lot (mesure seule, aucun changement de comportement)
- Engine (`ipc_client.gd`) : à chaque ligne `[gigue]` de la minute, une ligne
  `[ipc] state reçues N ; en retard L ; seq sautés S ; trous de plus de 2 s T ; plus gros datagramme X o`.
  Un écart de plus de 2 s est noté tout de suite :
  `[ipc] trou de N ms entre deux trames state : seq A -> B (C trames du core manquantes : perdues en route |
  le core n'a rien envoyé)`. Le seq tranche : s'il a avancé, le core a envoyé et la trame s'est perdue ; sinon
  le core n'a rien envoyé.
- Core (`ipc_server.py`) : compteurs d'émission et ligne de la minute, écrite par la session après `Gigue` :
  `IPC émis : state N (max X o, allégées A, ignorées I) ; autres M (max Y o) ; erreurs d'envoi : EAGAIN 3 …`.
  Une erreur d'envoi UDP est comptée par cause et donne un avertissement au plus toutes les 10 s.
- `log_report --gigue` réunit les deux côtés : trames envoyées par le core, reçues par l'engine, seq sautés,
  plus grosse trame, erreurs d'envoi et liste des trous.

## Tests
- `engine/tests/unit/test_state_gap.gd` : seq qui se suivent, trou de 10 s avec seq sautés (perdues en route),
  trou sans seq sauté (le core n'a rien envoyé), écart sous 2 s sans ligne, ligne de la minute, remise à zéro.
- `core/tests/test_ipc_tx_stats.py` : trames et taille max comptées, erreur `EAGAIN` comptée par cause,
  un seul avertissement par période, remise à zéro.
- `core/tests/test_jitter.py` : `log_report --gigue` lit les lignes `[ipc]` et `IPC émis`.

## Recette PC
Catégorie : logique
- De nuit : balade du monde ouvert au départ de Biarritz en high, 12 min, sonde active (`sim_bench.py`), puis
  `python -m openride_core.tools.log_report ~/run_trainer.log --gigue`. Attendu : les lignes `[ipc]` et
  `IPC émis` chaque minute ; si un trou apparaît, sa ligne dit si les trames sont perdues en route ou jamais
  envoyées. La correction viendra dans un lot suivant, selon ce résultat.
