# Lot P21 – Passants dans les villages et le long de la route

## 1. Objectif

Demande du propriétaire du 25 octobre, pendant les essais simulés : un peu de vie au bord de la route **en dehors des cols**. P15 met une foule dans le dernier kilomètre des grandes montées ; ce lot ajoute, partout ailleurs, quelques personnes isolées avec des gestes et des sons simples :
- au village : des passants qui marchent sur le trottoir, quelqu'un assis sur un banc, un jardinier, des enfants qui font signe au passage ;
- en campagne : un promeneur avec son chien, un joggeur, un agriculteur près d'un champ ;
- au passage du cycliste : un geste de la main, parfois un « Allez ! » ou un aboiement.

Coût très faible sur la GTX 1060 : mêmes silhouettes en `MultiMesh` et même shader que P15, quelques dizaines de personnes à la fois au plus, animations en boucle dans le shader.

## 2. À lire

1. `docs/lots/00_INDEX.md` (budget de la série P), `docs/lots/LOT_P15_spectateurs.md` (`crowd_renderer.gd`, `crowd.gdshader`), `docs/lots/LOT_P9_ambiance_sonore.md` (voisinage sonore), `docs/lots/LOT_P4_modele_vent_engine.md` §4.3 (budgets).
2. Code : `engine/scripts/crowd_renderer.gd` (P15), `engine/scripts/sound_player.gd`, `engine/scripts/osm_layers.gd` (bâti, chemins, champs), `engine/scripts/route_data.gd`.

## 3. Prérequis

P15 livré (silhouettes et shader réutilisés). Version 1.0 publiée.

## 4. Travail demandé

- Nouveau modèle pur `engine/scripts/passersby_model.gd` :
  - placement déterministe (graine du parcours) par tronçon : au village (bâti à moins de 60 m de la route), 2 à 6 personnes pour 100 m ; en campagne, une personne tous les 300 à 800 m en moyenne ; jamais sur la chaussée ni dans l'eau, de 1 à 6 m du bord ;
  - rôles : `walker` (marche lentement le long de la route, sur 20 à 60 m, puis fait demi-tour), `dog_walker` (promeneur et chien qui le suit), `jogger` (va plus vite, en sens inverse du cycliste le plus souvent), `sitter` (assis sur un banc ou un muret), `gardener` (geste répété près d'une maison), `farmer` (près d'un champ), `kid` (sautille et fait signe) ; proportions selon le lieu (village ou campagne) ;
  - réaction : à moins de 15 m du cycliste, une partie des personnes tourne la tête et lève la main (décalage aléatoire, une seule fois par passage) ;
  - sons ponctuels : au plus un toutes les 20 s, choisis parmi « Allez ! », « Bonjour ! », aboiement, rire d'enfant, selon le rôle le plus proche, et jamais pendant un bip du Click ;
  - sortie : liste des personnes visibles (position, rôle, phase d'animation, état « salue »), au plus `living(preset).passersby`, les plus proches en priorité.
- `crowd_renderer.gd` (P15) : accepte une deuxième instance pour les passants, avec les rôles comme variantes d'animation dans `crowd.gdshader` (marche, course, assis, salut de la main, geste de jardinage) ; chien en silhouette simple (quatre pattes, boucle de marche).
- Son : quatre courts sons de voix et d'aboiement dans `sound_player.gd`, synthétisés ou remplaçables par des `.ogg` libres de droits (CC0) déposés dans le thème, source 3D sur la personne ; volume réglé par la clé `ambience.volume` du thème (P1).
- Budget : clé `passersby` ajoutée à la table `LIVING` (P4) : 24 en `low`, 48 en `medium`, 80 en `high`, 0 quand le décor vivant est coupé.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/passersby_model.gd`, `engine/tests/unit/test_passersby_model.gd`.
- **Modifiés :** `engine/scripts/crowd_renderer.gd`, `engine/shaders/crowd.gdshader`, `engine/scripts/sound_player.gd` (quatre sons, après P15), `engine/tests/unit/test_sound_player.gd`, `engine/scripts/quality_presets.gd` (clé `passersby` seule), `engine/tests/unit/test_quality_presets.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Tronçon de village de 500 m : entre 10 et 30 personnes ; tronçon de campagne de 5 km : entre 6 et 17 ; même graine, même placement.
3. Aucune personne à moins de 1 m du bord de la chaussée ni dans l'eau ; les marcheurs restent sur leur segment.
4. Cycliste à moins de 15 m : une partie des personnes passe à « salue », une seule fois par passage.
5. Sons : jamais deux à moins de 20 s d'écart ; aucun hors de 30 m d'une personne.
6. Jamais plus que le budget ; mise à jour sous 0,1 ms par image pour 80 personnes.

**Sur le PC cible (le propriétaire) :** traversée de village en `low` : passants visibles, gestes au passage, un « Allez ! » de temps en temps, perte de moins de 1 image/s.

## 8. Hors périmètre

- Personnes qui traversent la route, voitures garées, terrasses de café, cyclistes croisés (bots dans N9 et O7).
- Dialogues, voix nommées ou personnalisées, personnes réelles.
