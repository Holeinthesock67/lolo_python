# Sons et volumes

Chaque son d'OpenRide appartient à une **catégorie de volume**. Une catégorie est un bus audio de
l'engine, envoyé au bus `Master`, et un réglage `audio.*` de `config.toml` que l'utilisateur change dans
« Réglages ». Tout lot qui ajoute un son le range dans une catégorie existante ; une catégorie nouvelle
se déclare ici, dans `engine/scripts/audio_mix.gd` et dans `core/src/openride_core/config.py` en même
temps.

## Catégories

| Catégorie | Réglage (`config.toml`, menu) | Bus de l'engine | Sons |
| --- | --- | --- | --- |
| Général | `[audio] master_pct`, « Volume général » | `Master` | tous les sons |
| Vent et roue libre | `[audio] ride_pct`, « Volume vent et roue libre » | `Ride` | vent dans les oreilles, roue libre, « clac » de reprise (`sound_player.gd`) |
| Ambiance | `[audio] ambience_pct`, « Volume de l'ambiance » | `Ambience` | fonds d'ambiance, cloches, points sonores (`sound_player.gd`), véhicules (`traffic_renderer.gd`), foule et passants (`crowd_renderer.gd`) |
| Bips et événements | `[audio] events_pct`, « Volume bips et événements » | `Events` | bips d'appui du Click, bip de changement de bloc ERG, consignes d'essai (`main.gd`) ; jingles d'événements (sommet de col, arche, fin de sprint, fin de séance) |
| Rogue, bruitages | `[audio] rogue_sfx_pct`, « Cyber-Rogue : bruitages » (défaut 70) | `RogueSfx` | bruitages du mode Cyber-Rogue (`rogue_audio.gd`) |
| Rogue, musique | `[audio] rogue_music_pct`, « Cyber-Rogue : musique » (défaut 40) | `RogueMusic` | musique du mode Cyber-Rogue (`rogue_audio.gd`) |

Les deux dernières catégories sont plus basses par défaut (confort, lot R18) ; leurs curseurs sont dans « Réglages », sous-écran Son, avec les autres volumes.

## Règles

- Valeurs entières de 0 à 100 %, par pas de 10 dans le menu ; 100 % garde le niveau d'origine des sons,
  0 % coupe le bus. Défaut : 100 % partout, sauf le Cyber-Rogue (70 % et 40 %).
- Courbe quadratique : gain = (volume / 100)², soit environ −12 dB à 50 %, plus proche de l'oreille
  qu'une échelle linéaire. Le volume d'une catégorie se multiplie par le volume général.
- Réglages `applies` = `now` : l'engine les applique dès qu'il reçoit le message `settings`, donc au
  démarrage (liste demandée à la première trame) et à chaque modification dans « Réglages ».
- Un lecteur prend son bus par `AudioMix.bus(AudioMix.RIDE)` (ou `AMBIENCE`, `EVENTS`) au moment où il
  est créé ; aucun lecteur ne reste sur `Master` sauf s'il n'appartient à aucune catégorie.
- `[render] living = false` coupe toujours le décor vivant et ses sons, quels que soient les volumes.
- Sons synthétisés en boucle (`sound_player.gd`) : raccord sans saut ni fondu au silence. Fréquences et
  modulations à un nombre entier de cycles par boucle, bruits filtrés périodiques (`_periodic_lowpass`),
  événements (chants, gouttes, cliquets) qui débordent de la fin repris au début. Le « tac-tac » régulier
  entendu le 28/10 venait du fondu au silence de 10 ms aux bords de chaque fond (un creux toutes les 2 s) ;
  les insectes gardent leurs salves à 2 Hz, préférées à l'écoute. Le vent n'a plus de fondu enchaîné ni de
  « respiration » à 0,5 Hz : tous deux revenaient toutes les 4 s et s'entendaient comme une vague.
  Les sons continus (vent, eau, rumeur, vent d'altitude, pluie, avion, voitures, roues) gardent un niveau
  constant : leur volume ne varie que par les modèles (vitesse, altitude, distance). Le vent d'altitude qui
  ondulait de 14 dB toutes les 2 s faisait la « vague » entendue à l'arrêt le 29/10 au-dessus de 1 200 m.
  Les sons à bruit des points sonores et du décor (rivière, voitures, foule, hélicoptère, avion, péniche) bouclent
  sur 3 s à 11 025 Hz, chacun décalé dans un bruit commun : un bruit figé d'une seconde se répétait et faisait une
  pulsation régulière d'une seconde (mesure du 30/10, autocorrélation 0,98 à 1 s). Un son joué une fois (`ONE_SHOT_KINDS` : corne, cloche) n'est
  jamais relancé par les points sonores : la cloche ne sonne qu'aux coups de l'heure pleine.
- Abri (lot AS5) : dans la roue d'un bot, le vent (`sound_model.gd`) suit la vitesse de l'air ressentie,
  `va × (1 − draft)^0,5`, avec `draft` déjà lissé à 1 s par le core : − 3,7 dB à 0,35 d'abri, à vitesse égale.
  La variation reste bornée à 12 dB/s comme tout volume : pas de saut, donc pas de « tac-tac ».

Tests : `engine/tests/unit/test_audio_mix.gd` (bus, courbe, lecteurs), `test_sound_player.gd`
(`_test_seamless_loops`, raccords ; `_test_steady_levels`, niveau stable sur trois tours de boucle) et `core/tests/test_settings.py`
(`test_audio_volumes_in_menu`).
