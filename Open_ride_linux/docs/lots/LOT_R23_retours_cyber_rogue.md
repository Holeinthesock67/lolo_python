# Lot R23 – Retours du Cyber-Rogue : chaque Z répond, surchauffe expliquée, vitesse et vue sur le vélo

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Retours du Cyber-Rogue : événements jamais perdus entre deux trames, chaque Z accepté ou refusé avec son, animation et raison, surchauffe et tendance de l'adrénaline affichées, vitesse toujours affichée, vue sur le vélo (contrat révision 1.17) | Python, GDScript | R22 | Moyenne | En revue le 14 novembre, **version 2.0** |

## 1. Constat

Essai sur le vélo du 14 novembre (R22 noté 2/5) :

1. Z ne donne ni son ni animation : on ne sait pas s'il a marché.
2. L'adrénaline baisse sans explication.
3. La vue du joueur sur le vélo n'existe pas dans le mode.
4. La vitesse (braquet) engagée ne se voit pas assez.
5. Le guide vocal de l'essai partait du lancement sans compter les 6 min d'échauffement (corrigé à part, dans le guide de l'essai, hors dépôt).

## 2. Causes trouvées dans le code

- **Événements perdus.** Le core fait un pas toutes les 20 ms (50 Hz) et envoie la trame `state` toutes les 33 ms (30 Hz). L'objet `rogue` de la trame était celui du **dernier pas** seulement : les événements d'un pas sur deux ou trois (environ 40 %) n'arrivaient jamais à l'engine. Un Z accepté (`hit`) ou refusé (`z_refused`), une arche ratée, un Perfect Shift : ni son, ni texte, ni impact. Le contrat dit pourtant « événements de la dernière **trame** ».
- **Z sans réponse hors combat.** À l'échauffement (hors relique), au couloir une fois la porte prise et au retour au calme, Z court était ignoré sans rien dire. Un rocher touché sans être brisé (armure restante) et la relance des cartes réussie n'avaient pas d'événement non plus.
- **Un Z accepté n'avait pas de retour propre** : seulement le son `rogue_hit` (bas, sous la musique) et le choc sur l'ennemi, quand l'événement arrivait.
- **Surchauffe muette, règle contradictoire.** En endurance, au-dessus de 75 % de la FTP pendant 5 s, l'adrénaline fond de 2 par seconde et Z est refusé ; mais la consigne affichait « garde ≥ 70 % FTP », sans plafond. Pire, les phases 2 et 3 du boss d'endurance demandent jusqu'à 85 % de la FTP (plus de la moitié de leur longueur au-dessus de 75 %) : tenir la consigne faisait fondre l'adrénaline. Le banc l'a montré : le cycliste simulé, qui tient la cible, passait 161 s en surchauffe sur une run de 30 min.
- **Vitesse.** Elle n'apparaissait qu'en petit dans la ligne du panneau d'état (« Vitesse 06 … »), et disparaissait avec le panneau au couloir et à la relique.
- **Vues.** Les 3 vues du mode (derrière, haute, proche) sont toutes derrière le vélo.

## 3. Travail

Principe : une seule règle pour tous les appuis, sans cas particulier. **Chaque Z court d'une run produit exactement un retour** : `z_ok` (accepté, avec son action) ou `z_refused` (avec sa raison).

### 3.1 Core (contrat révision 1.17, ajouts compatibles)

- `rogue/mode.py` : les événements, `z_reason`, `z_action` et `shift_miss` s'accumulent entre deux trames ; la session les vide à l'envoi de chaque trame `state` (`take_frame`). Plus aucun événement perdu, chacun envoyé une seule fois.
- `rogue/run.py`, `rogue/combat.py` : événement `z_ok` et champ `z_action` (`strike`, `charges` (Diesel), `rock` (rocher brisé), `rock_chip` (armure entamée), `parry`, `purge`, `reroll`) ; Z sans effet à l'échauffement, au couloir sans choix et au retour au calme : `z_refused` avec `no_target`.
- Champ `adrenaline_trend` : `{rate_per_s, cause, overheat_in_s}` ; `cause` parmi `gain` (à la cible), `below` (sous la cible : stable), `overheat` (fond), `stopped` (arrêt), `full`, `none` (hors combat) ; `overheat_in_s` : secondes avant la surchauffe quand on est déjà au-dessus du seuil, sinon `null`.
- Seuil de surchauffe : le plus haut de 75 % et de la cible + 10 points (`overheat_margin` de `balance.toml`, `overheat_limit`). Une seule règle, jamais contraire à la consigne ; le bonus du châssis Endurant (+3 points) s'applique toujours.
- `target_pct.hi` en endurance : ce seuil ; la consigne devient une plage.

### 3.2 Engine

- `rogue_guide_model.gd` : retour pour chaque `z_ok` (« FRAPPE ! −6 % », « Charges : −N % », « Rocher brisé », « Rocher entamé », « Parade ! », « Piratage purgé », « Cartes relancées ») ; texte de `no_target` selon la phase (« Z sert en salle : première salle dans 4:12 ») ; bandeau de surchauffe permanent en rouge (« SURCHAUFFE : adrénaline −2/s, Z bloqué · descends sous 75 % FTP ») et alerte orange avant (« Au-dessus de 75 % FTP : surchauffe dans 3 s ») ; consigne en plage « 70–75 % FTP » en endurance.
- Jauge d'adrénaline : tendance écrite à côté (« +0,5/s », « −2/s surchauffe », « stable : sous la cible »).
- `rogue_hud_view.gd` : anneau qui s'ouvre au centre de l'écran à chaque Z (or si accepté, rouge si refusé) et pastille Z qui clignote ; pavé **VITESSE NN** toujours visible en bas à droite, dans toutes les phases, qui s'allume à chaque changement.
- Sons : `rogue_z_ok` (nouveau, net et court) à chaque Z accepté, en plus du son de l'action ; priorité de `rogue_refused` et `rogue_z_ok` relevée pour ne jamais être couverts.
- `rogue_scene.gd` : 4e vue « sur le vélo » (yeux à 1,4 m, avatar caché), ordre derrière, haute, proche, sur le vélo ; le nom de la vue s'affiche 1,5 s à chaque changement.

## 4. Tests

- `core/tests/test_rogue_r23_retours.py` : aucun événement perdu à 50 Hz / 30 Hz, chaque Z donne un seul retour dans toutes les phases, actions de `z_ok`, tendance de l'adrénaline (gain, sous la cible, surchauffe, compte à rebours), plage de la consigne en endurance, schéma.
- `engine/tests/unit/test_rogue_guide_model.gd`, `test_rogue_hud_model.gd`, `test_rogue_sound_model.gd` : textes et sons des retours, tendance, surchauffe, vitesse, vue sur le vélo.
- `rogue_bout_en_bout` : un Z sans cible à l'échauffement, puis un seul retour par Z court dans les trames ; en endurance, 20 s trop fort dans la première salle : surchauffe annoncée, dite, finie.
- `rogue_bench.py` : nouveaux moments (Z refusé à l'échauffement, Z accepté, surchauffe proche, surchauffe, vue sur le vélo) et vérifications (pavé VITESSE, retour du Z, bandeau de surchauffe, vue).
- Captures low, medium et high (`engine/tests/rogue_galerie.py --objective endurance`).

## 5. Reste au propriétaire

- Validation des captures, puis essai sur le vélo (10 min, consignes calées après l'échauffement).

## Livraison

En revue le 14 novembre.
