# Lot R18 – Bruitages et musique du mode Cyber-Rogue : sons de jeu synthétisés, musique d'ambiance par couches, volumes réglables

## 1. Objectif

Demande du propriétaire du 27 octobre : penser aux bruitages du mode Cyber-Rogue. Les cahiers R n'en prévoient que quatre (R11 §4.2 : bip de Perfect Shift, impact, parade, alarme du Firewall, plus l'échec de la salle manquée) et R12 renvoie les sons des ennemis « après la recette R14 ». Ce lot dresse la liste complète des sons du mode, les génère par synthèse (comme les autres sons du projet : aucun fichier audio dans le dépôt, aucune œuvre ni marque), règle leur budget et les rend réglables en volume.

Principe de confort, tiré de la recette P16 (sons jugés désagréables puis refaits) : **doux d'abord**. Aucun son aigu et strident, aucun son plus fort que le vent à haute vitesse, une seule alarme continue à la fois, et tout le mode se joue à un niveau de départ bas (−18 dB par rapport au plein niveau).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_R11_hud_diegetique.md` §4.2 (sons déjà prévus), `LOT_R12_ennemis_boss.md`, `LOT_R17_direction_artistique.md` §4.5 (catalogue des effets : un son par effet visuel), `docs/lots/LOT_P10_sons_velo.md` (vent et roue libre, à rester audibles).
2. Code : `engine/scripts/sound_model.gd` (modèle sonore, lissage 12 dB/s, 4 sources spatialisées), `engine/scripts/sound_player.gd` (synthèse au lancement, remplacement par `~/OpenRide/Sounds/<nom>.ogg`), `engine/scripts/ambience_model.gd`.
3. Le réglage de volume général de l'écran Réglages (fil séparé, 27 octobre) : `engine/scripts/audio_mix.gd`, `docs/AUDIO.md` (bus `RogueSfx` et `RogueMusic`), voir §4.5.

## 3. Prérequis

R8 livré (événements `state.rogue.events`), R17 livré (catalogue des effets). R10 à R13 pour brancher les sons dans la scène, mais le modèle (§4.2) se fait avant.

## 4. Travail demandé

### 4.1 Liste des sons

Un son par événement du jeu (noms de l'IPC 1.4). Durées courtes, synthèse monophonique à 22 050 Hz.

| Son | Événement | Description synthétique | Durée |
| --- | --- | --- | --- |
| `rogue_shift_tick` | changement de vitesse | « tic » sec à 1,2 kHz, très bas niveau | 40 ms |
| `rogue_perfect_shift` | `perfect_shift` | deux notes montantes (quinte) sinus + harmonique douce, déclin rapide | 250 ms |
| `rogue_hit` | `hit` | impact grave : sinus qui descend de 180 à 70 Hz + clic de bruit filtré | 150 ms |
| `rogue_crit` | `crit` | même impact, plus long, plus une note brillante courte | 280 ms |
| `rogue_parry` | `parry` | tintement métallique (trois sinus inharmoniques, déclin 200 ms) | 300 ms |
| `rogue_parry_miss` | `parry_miss` | « bonk » sourd descendant | 220 ms |
| `rogue_shield_hit` | bouclier touché | coup mat et souffle court | 120 ms |
| `rogue_overheat` | surchauffe | grésillement doux qui monte, en boucle tant que la surchauffe dure | boucle 1 s |
| `rogue_firewall_hum` | Firewall à moins de 30 m | ronflement grave (50 Hz modulé) dont le volume monte quand le mur approche ; alarme de contact : battement lent (2 Hz) ajouté pendant `firewall_contact` | boucle 2 s |
| `rogue_hack` | début du piratage | rafale de bruit blanc haché (quatre éclats) | 400 ms |
| `rogue_purge` | balise de purge réussie | balayage descendant puis note claire | 350 ms |
| `rogue_card_pick` | carte choisie | « bip » doux double | 150 ms |
| `rogue_door` | porte choisie | souffle grave montant | 300 ms |
| `rogue_reroll` | relance de carte | trois cliquetis rapides | 200 ms |
| `rogue_room_won` | `room_won` | arpège majeur montant de trois notes | 600 ms |
| `rogue_room_fled` | `room_fled` | note unique qui s'éteint (filtre qui se ferme) | 500 ms |
| `rogue_room_skipped` | `room_skipped` | deux notes descendantes, plus sèches que la défaite | 450 ms |
| `rogue_gold` | or gagné | « ding » très court, un par pièce d'or groupée | 80 ms |
| `rogue_boss_phase` | changement de phase du boss | accord grave qui s'ouvre (quinte puis octave) | 900 ms |
| `rogue_boss_won` | boss battu | fanfare de quatre notes, la plus longue du mode | 1,8 s |
| `rogue_defeat` | `defeat` | descente grave de deux secondes, filtre qui se ferme | 2 s |
| `rogue_recovery_end` | fin de la récupération forcée | note claire douce (retour au jeu) | 300 ms |
| `rogue_chest` | coffre de fin | éventail de notes montantes | 900 ms |
| `rogue_result` | bilan | accord résolu (victoire) ou note tenue (défaite) | 1,2 s |

Les sons de vent et de roue libre de P10 restent inchangés et continuent dans le mode.

### 4.2 Modèle (`engine/scripts/rogue/rogue_sound_model.gd`, sans nœud)

- Table événement → son, avec priorité et plafond de voix simultanées.
- **Budget :** au plus **8 voix** en même temps (hors vent et musique) ; à saturation, on garde les plus prioritaires (`defeat` > `boss_*` > `room_*` > `perfect_shift` > `parry` > `hit` > autres) ; le même son ne se redéclenche pas avant **60 ms**.
- Boucles (`overheat`, `firewall_hum`) : une seule de chaque, volume lissé comme le reste de `sound_model.gd` (12 dB/s).
- Le modèle ne dépend que des événements du core : testable sans écran.

### 4.3 Musique d'ambiance par couches

- Boucle synthétisée de 8 mesures à 96 bpm (tempo fixe, indépendant de la cadence pour ne pas la concurrencer), trois couches : **basse** (toujours), **pulsation** (en salle), **arpège** (boss et fin de run).
- Une musique par archétype de salle n'est pas prévue : la couche suit le type d'étape (échauffement, salle, couloir, boss, retour au calme), avec un fondu de 2 s.
- Gamme et timbres fixés dans la charte (sinus et triangle filtrés), pas de mélodie reconnaissable d'une œuvre existante.

### 4.4 Budget

| Ressource | Plafond |
| --- | --- |
| Synthèse au lancement du mode | 300 ms au plus sur la GTX 1060 (sinon différer les sons rares) |
| Mémoire des sons (PCM mono 22 050 Hz, 16 bits) | 8 Mo au plus pour tous les sons et la musique |
| Voix simultanées | 8 + vent + roue libre + musique |
| Coût par image du modèle sonore | moins de 0,2 ms (budget X2) |

### 4.5 Volumes réglables

Alignés sur le réglage de volume général de l'écran Réglages (fil séparé, `engine/scripts/audio_mix.gd` et `docs/AUDIO.md`) : deux **bus** réservés, `RogueSfx` (les sons de jeu du §4.1) et `RogueMusic` (la musique du §4.3), dont le volume final est `rogue_sfx_pct` ou `rogue_music_pct` (0 à 100) multiplié par `master_pct`, comme les autres catégories. Réglages `[audio] rogue_sfx_pct` et `rogue_music_pct` dans `config.toml` (défauts 70 et 40), aussi réglables à la manette depuis l'écran Réglages et l'écran de pause du mode. Le vent et la roue libre de P10 restent sur le bus d'ambiance existant. Ce lot n'ajoute aucun bus ni réglage de son côté : il joue ses sons sur ces deux bus. Muet total : `master_pct` à 0.

### 4.6 Remplacement

Comme pour les autres sons : `~/OpenRide/Sounds/<nom>.ogg` remplace le son synthétisé du même nom (fichiers CC0 du propriétaire, jamais dans le dépôt).

## 5. Fichiers concernés

- **Créés :** `engine/scripts/rogue/rogue_sound_model.gd`, `engine/scripts/rogue/rogue_sound_synth.gd` (formes d'onde), `engine/tests/unit/test_rogue_sound_model.gd`, `engine/tests/unit/test_rogue_sound_synth.gd` (durées, niveaux, absence de saturation).
- **Modifiés :** `engine/scripts/rogue/rogue_audio.gd` (lecteurs du mode sur les bus du volume général), `engine/scripts/audio_mix.gd`, `docs/SUIVI_AVANCEMENT.md` (une ligne), `docs/lots/00_INDEX.md`.

## 6. Modifications de contrat autorisées

Aucune (les événements existent déjà dans l'IPC 1.4). Réglages `[audio] rogue_sfx_pct` et `rogue_music_pct` : ajoutés par le lot du volume général (SRS §11, `config.py`) ; ce lot ne fait que les lire.

## 7. Critères d'acceptation

1. Chaque événement de la liste §4.1 a un son, une durée dans la plage annoncée et un niveau crête sous −3 dBFS (test sur les formes d'onde).
2. Plafond de 8 voix et délai de 60 ms respectés ; priorités testées.
3. Volumes : les sons de jeu passent par le bus `RogueSfx`, la musique par `RogueMusic` ; `rogue_*_pct` × `master_pct` multiplient bien, 0 coupe la catégorie.
4. Synthèse au lancement sous 300 ms et mémoire sous 8 Mo (mesure du test de rendu).
5. Écoute par le propriétaire (douceur, pas de son strident) lors de la recette R14.

## 8. Hors périmètre

- Voix et paroles, sons des menus hors mode (série O), bruits d'ennemis détaillés au-delà du §4.1 (après R14).

## 9. Livraison (28 octobre)

Livré : synthèse de 25 sons et de 3 couches de musique (20 s, 96 battements par minute), modèle de déclenchement (un son par événement, sons dérivés des changements d'état, plafond de 8 voix, 60 ms entre deux sons identiques, priorités, boucles lissées à 12 dB/s, couches de musique avec fondu de 2 s), bus `RogueSfx` (70 %) et `RogueMusic` (40 %), remplacement par `~/OpenRide/Sounds/<nom>.ogg`.

Écarts avec le cahier d'origine : les tests de synthèse sont dans `tests/unit` et non `tests/render`, un nœud séparé `rogue_audio.gd` porte les lecteurs au lieu de `sound_player.gd` ; la purge et le coffre ont un son mais aucun déclencheur (pas de signal) ; les clés `audio.rogue_sfx_pct` et `audio.rogue_music_pct` n'existent pas encore côté core (l'engine crée les bus et sait lire les clés) ; la mesure de synthèse est donnée par le test (limite large de 2 s), l'objectif de 300 ms se vérifie sur le PC. Reste : écoute par le propriétaire.
