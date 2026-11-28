# Lot CH7 – Ligue d'hiver : rappel de la manche de la semaine

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CH : notification bureau le samedi à 18 h et le dimanche à midi si la manche de la semaine n'est pas courue | Python, shell | CH3 | Petite | **Livré le 25 novembre** (PR #1046) |

Ce lot répond au choix du propriétaire du 24 novembre 2026 (« ok pour les deux ») : un rappel le samedi à 18 h
et un autre le dimanche à midi. Il doit servir dès la semaine 2 (samedi 5 décembre). Cadrage :
`plans/ch-ligue/CADRAGE_PALMARES_RAPPEL_2026-11-23.md` (dossier du projet).

## 1. Ce que le lot fait

- `core/src/openride_core/league_reminder.py` lit `ligue.json` du profil, celui que le core prendrait au
  lancement ou celui donné par `--profil`. Si la manche de la semaine n'est pas faite, il affiche une
  notification bureau (`notify-send`) :
  - le samedi : « Manche 2 sur 8 (Dernier survivant) à courir avant demain soir. Elle compte au bilan. » ;
  - le dimanche : « … à courir avant ce soir, dernier jour. Elle compte au bilan. »
- Pas de rappel dans ces cas :
  - aucune saison ;
  - saison close ou en pause ;
  - manche déjà faite ;
  - un jour qui n'est ni samedi ni dimanche. Ainsi, un minuteur rattrapé le lundi ne parle pas de la semaine
    nouvelle.
- Le module ne fait que lire. Il ne réécrit jamais `ligue.json` et ne met jamais de côté un fichier illisible,
  par exemple pendant que le core l'écrit : `league.load` le ferait, d'où sa propre lecture.
- Le minuteur systemd de l'utilisateur vient de `scripts/systemd/openride-rappel-ligue.timer` et de son
  `.service.in` : `OnCalendar` le samedi à 18:00 et le dimanche à 12:00. Avec `Persistent=true`, un rappel
  manqué parce que le PC était éteint part au démarrage suivant. Il fonctionne même OpenRide fermé.
- `scripts/install-rappel-ligue.sh` installe le minuteur dans `~/.config/systemd/user`, avec le Python de
  `openride-core`. Ses options :
  - `--uninstall` retire le minuteur, ce qui coupe le rappel ;
  - `--essai` affiche le rappel du jour sans rien installer.
- L'installateur final (J9) appellera ce script. D'ici là, on le lance une fois à la main sur le PC.

## 2. Recette

- Core : `core/tests/test_league_reminder.py` vérifie :
  - les textes du samedi et du dimanche, et l'absence de texte les autres jours ;
  - manche faite, pause, saison close : rien ;
  - le fichier n'est pas touché, et un fichier abîmé ne donne pas de rappel ;
  - le profil est le bon ;
  - le minuteur et le script.
- PC (passage court) :
  - `scripts/install-rappel-ligue.sh`, puis `systemctl --user list-timers openride-rappel-ligue.timer` pour
    voir les prochains rappels ;
  - `--essai` pour lire le texte ;
  - une vraie notification avec `systemctl --user start openride-rappel-ligue.service` un samedi ou un
    dimanche, ou `python -m openride_core.league_reminder --jour 2026-11-28` un autre jour.

## 3. Pour plus tard

- Un réglage « Rappel de la ligue : oui / non » dans le menu. Aujourd'hui, on installe ou on retire le minuteur.

## Livraison

Fusionné dans `main` le 25 novembre 2026 (PR #1046), relevé par la passe de doc du 27 novembre 2026 (statut précédent : « En revue »).
