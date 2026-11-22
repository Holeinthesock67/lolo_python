# Lot NI1 – HUD sans éléments inutiles

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| HUD sans éléments inutiles ni doublons : ligne d'état technique, case CIBLE ERG, encart du vent, PENTE au vélodrome, vitesse en double au Cyber-Rogue, jauge d'abri des bots | GDScript, Python | P16, P17, VD9, R23 | Petite | En revue, **version 2.0** |

## 1. Constat

Audit des éléments inutiles du 21 novembre (dossier du projet, `plans/AUDIT_ELEMENTS_INUTILES_2026-11-21.md`,
lignes H2 à H7 et C1), décision du propriétaire du 21 novembre : « HUD et réglages d'abord ». H1 (jauge
« Réserve W' » du Cyber-Rogue) est fait à part (lot R25).

## 2. Travail

| # | Élément | Fait |
| --- | --- | --- |
| H2 | Ligne « ÉTAT: RUNNING \| TRAINER: CONNECTED \| ENTRÉE: … » du bandeau central (mots du core, rien à faire pour le joueur) | Retirée. Une ligne `notice_label` ne parle que d'un problème : « En attente du core… » avant la première trame, « Trainer perdu : reconnexion en cours… » (même texte que la raison de pause) ; jamais le Click (choix du propriétaire). Le bandeau central se cache quand il n'a rien à dire (ni montée ni problème). Les pertes uniformes restent au lot RT4. |
| H3 | Vitesse deux fois au Cyber-Rogue (ligne « Vitesse 05 · … » et pavé VITESSE) | La ligne garde % FTP, cadence et posture ; la vitesse n'est plus qu'au pavé VITESSE. |
| H4 | Encart du vent en cinq morceaux (flèche, « 12 km/h face », barres, « modéré », pastille « Vent défavorable ») | Flèche teintée du verdict, « 12 km/h » et « de face » / « de dos » / « de gauche » / « de droite » : le sens est écrit, jamais la couleur seule. `wind_view_model.gd` : `direction_text` ajouté, niveau d'intensité et texte du verdict retirés. Encart de 92 px au lieu de 132. |
| H5 | Cible ERG à deux places (case « CIBLE ERG » et bandeau ERG) | Case retirée, le bandeau ERG la montre (entraînement et ERG libre). |
| H6 | « PENTE » toujours à 0 % au vélodrome | Cachée sur la piste plate, en épreuve comme en séance libre au vélodrome (`route.is_track()`), comme le profil d'altitude. |
| H7 | Jauge d'abri au-dessus du bot et réglage « Jauge d'abri des bots » (doublon de la pastille « Abri 30 % ») | Retirés : `draft_gauge.gd`, `draft_gauge_model.gd`, son shader et son test, points d'ancrage des véhicules et cyclistes du décor, réglage `render.draft_gauge` (core : `config.RETIRED_KEYS`, un `config.toml` d'avant se lit sans avertissement de faute de frappe ; après la fusion du lot NI2, même règle que les réglages retirés du menu : la ligne est mise en commentaire au lancement par `migration_reglages.RETIRED`). Contrat IPC : le core n'envoie plus ce réglage, sans changement de schéma ni de révision. |
| C1 | Ligne de texte ERG du bandeau central, calculée à chaque image et jamais affichée | Retirée (`erg_label`, `show_erg_line`, champ `erg` de `session_lines`). |

Bancs : la capture donne `session_state` (le banc simulé lisait l'état sur la ligne retirée) ; widgets
`notice` et `wind_direction` à la place de `status`, `wind_level` et `wind_verdict` ; plus de `target` ni de
`erg`.

## 3. Tests

- `test_hud_view.gd` (ligne d'état, CIBLE ERG et ligne ERG absentes, avis « core attendu » et « trainer perdu »,
  Click perdu sans message, bandeau central caché, PENTE cachée en épreuve et au vélodrome sans épreuve),
  `test_hud_view_model.gd`, `test_wind_view_model.gd` (sens écrit), `test_living_world.gd`,
  `core/tests/test_settings.py` (réglage retiré, ancienne clé lue sans avertissement).
- `visual_check.py`, `hud_galerie.py`, `hud_lisibilite.py`, `sim_bench.py` adaptés ; vignettes de référence
  Xvfb `low` refaites pour les scènes touchées.

## 4. Livraison

PR à venir. Risque de conflit d'une ligne avec #956 (R25) dans `rogue_hud_view.gd` (ligne de route du
Cyber-Rogue, juste sous la jauge W' retirée) : garder la ligne de ce lot, sans « Vitesse ».
