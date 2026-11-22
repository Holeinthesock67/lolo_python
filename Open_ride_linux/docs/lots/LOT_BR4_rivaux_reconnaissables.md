# Lot BR4 – Rivaux reconnaissables (lot R4 de la note des bots)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Rivaux reconnaissables : les bots à profil gardent nom, équipe, caractère et cote d'une course à l'autre, dans tous les modes et la ligue d'hiver | Python | BOT-elo (#941) | Petite | PR du 22 novembre |

## 1. Objectif

Note de stratégie des bots (21/11), lot R4 : retrouver **les mêmes rivaux** d'une course à l'autre, pour que le
jeu raconte une histoire (« Vidal m'a encore battu au sprint ») au lieu d'un « Grimpeur 2 » anonyme.
Critères du propriétaire : ludique, défi quand il le veut, peu d'ajouts à l'écran.

**Décision du propriétaire du 22/11 (carte) : « Mêmes rivaux partout ».** Un seul groupe de rivaux nommés pour
tous les modes à bots ; la ligue d'hiver (série CH, `docs/6.0/PLAN_SERIE_CH.md` §3.3) les reprend et en change 3 à
chaque nouvelle saison.

## 2. La règle

- **Identité** : celle de la cote Elo (`bot_elo.bot_key`) : profil et rang parmi les bots du même profil du
  plateau (`climber#1`, `climber#2`…). C'est déjà ce qui porte la cote du bot ; R4 y accroche un visage.
- **Un rival** = nom fictif (16 caractères au plus, aucun coureur réel), équipe (nom écrit **et** couleur, la
  couleur ne sert jamais seule), caractère (le profil : grimpeur, rouleur, sprinteur, diesel) et tempérament
  (attaquant, suiveur, opportuniste). Le tempérament est celui que les tactiques tirent déjà du nom
  (`bot_tactics.personality_of`, lot VD7) : un nom fixe donne donc un comportement fixe, sans nouvelle règle.
- **Création** : un rival naît la première fois que son identité court, puis reste dans `rivaux.json` du profil
  (à côté de `elo.json`). Graine 0 par défaut : un nouveau profil voit toujours les mêmes premiers noms.
- **Où** : tous les bots à profil : plateaux composés par le core (Dernier survivant, Grand Prix, Course,
  épreuves de piste) et bots à profil choisis au menu (session libre, ERG, WTF, écran de pause). Les bots à
  puissance fixe (« Bot 200 W ») et le fantôme ne changent pas. Pas d'exception par mode (principe du 27/10).
- **Affichage** : le nom remplace « Grimpeur 2 » partout où le nom du bot s'affiche déjà (bandes de course,
  liste du Dernier survivant, encart des bots, éliminations, bilan). **Aucun élément nouveau à l'écran.** La fiche
  écrite d'un rival (nom, « Grimpeur, attaquant », équipe, cote) est prête pour l'écran de la ligue (CH4) :
  `Roster.describe`.
- **Ligue d'hiver** : `Roster.renew(keys, 3, rng)` remplace 3 rivaux tirés au sort à chaque nouvelle saison ; le
  nouveau venu reprend l'identité, donc le profil et la cote du partant, et un rival parti ne revient pas (sauf
  si les 44 noms sont épuisés). CH1 (#972) doit lire ses rivaux ici au lieu de les tirer lui-même.
- **Plus de 44 rivaux d'un même profil** (impossible aujourd'hui : 11 bots au plus) : repli sur « Grimpeur 45 ».
- **Séance simulée sans configuration** : noms donnés, rien d'écrit (même règle que la cote).

## 3. Livraison

- Core : `rivals.py` (module pur hors `rivaux.json`) : `Roster.names_for`, `ensure`, `renew`, `describe`,
  `load`, `save` ; `CoreSession._rival_names` (plateaux composés `_profile_field`, `_track_field`, bots du menu
  `_start_bots`, `set_bots`) ; `bots.bots_from_menu(names=…)`.
- Contrat IPC inchangé : seul le texte du champ `name` des bots change.
- Tests : `core/tests/test_rivals.py` ; `test_survivor_session.py` (mêmes noms d'une course à l'autre, fichier
  du profil).

## 4. Recette

- Cloud : core `not slow`. Pas d'essai vélo (règle du 21/11 pour les bots).
- PC : le nom change dans les HUD existants : catégorie « menus/HUD seuls » de la règle du 21/11 (banc medium
  seul). Captures low/medium/high de la bande du Grand Prix et de la liste du Dernier survivant avec des noms
  longs (« Florent Gauthier »), à valider par le propriétaire avant fusion.

## 5. Reste

- CH1 (#972) : remplacer `league._draw_rivals` et ses listes `NAMES`/`TEAMS` par `rivals.Roster` (identités
  `league.field_keys`, `renew` à la nouvelle saison).
- CH4 : fiches des rivaux à l'écran de la ligue (`Roster.describe` avec les cotes de `elo.json`).
