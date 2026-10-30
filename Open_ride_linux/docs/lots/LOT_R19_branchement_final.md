# Lot R19 – Branchement final du Cyber-Rogue : progression, dernière run, volumes

Série R (version 2.0). Demande du propriétaire du 30 octobre : « terminer le mode rogue ». Ce lot ferme les
écarts laissés par R9, R13, R16 et R18 côté code ; il ne change aucune règle de jeu.

## 1. Constat (30 octobre)

- R9 : la table des châssis, les statistiques des runs et les vies existaient, mais `rogue_provider` de la
  session n'était jamais branché : seul le châssis standard était proposé et `start_run` refusait tout autre
  châssis (`item_locked`) ; les vies utilisées pendant une run n'étaient pas retirées du profil.
- R16 : `estimate_w_prime()` n'était appelé nulle part ; `w_prime_estimate_j` valait toujours `null`.
- R13 : objectif, durée et châssis choisis n'étaient gardés que le temps du programme, l'avertissement du
  premier lancement revenait à chaque lancement d'OpenRide.
- R18 : les réglages `audio.rogue_sfx_pct` et `audio.rogue_music_pct` n'existaient pas côté core.

## 2. Ce qui est fait

- `ProgressionService.rogue_progress()` (table des châssis, statistiques, vies) devient le `rogue_provider`
  par défaut de la session ; progression coupée ou table invalide : châssis standard seul, comme avant.
- `ProgressionService.use_lives(n)` retire du profil les vies consommées par la run (`engine.lives_used`) à la
  fin de la séance ; plus que la réserve : rien n'est écrit, avertissement au journal.
- `RogueStats.last` : objectif, durée et châssis de la dernière run, relus dans le journal (lignes
  `rogue_run`, dans l'ordre des séances). Rien de neuf n'est stocké : tout se recalcule, comme le reste de la
  progression.
- `hello_ack.config.rogue` (révision 1.5) : champ facultatif `last` (`{objective, duration_min}` ou `null`) ;
  `chassis.selected` donne le châssis de la dernière run s'il est toujours débloqué. Le bloc est recalculé
  après chaque séance (bilan d'expérience) pour la connexion suivante de l'engine.
- W' estimé : calculé au lancement du core hors de la boucle (`asyncio.to_thread`), attendu au plus 3 s avant
  d'ouvrir les ports pour être dans le premier `hello_ack` ; dossier des activités (`~/OpenRide/Activities`,
  FIT et journaux), cache `~/.cache/openride/mmp.json` de l'outil.
- Engine (`rogue_menu_model.gd`) : `last` non nul reprend l'objectif et la durée et vaut avertissement déjà
  accepté ; `null` : avertissement au premier lancement.
- Réglages `audio.rogue_sfx_pct` (« Cyber-Rogue : bruitages », défaut 70) et `audio.rogue_music_pct`
  (« Cyber-Rogue : musique », défaut 40) dans le sous-écran Son ; l'engine les applique déjà sur les bus
  `RogueSfx` et `RogueMusic`.
- 26 réglages et les thèmes installés passaient 4 096 octets : `settings` rejoint `plans` parmi les messages
  d'un seul datagramme de 60 000 octets au plus (contrat §2), liste portée à 32 éléments au plus.

## 3. Tests

- `core/tests/test_rogue_progression_session.py` : premier lancement (`last` nul, standard seul), dernière
  run et châssis débloqué repris au lancement suivant, `start_run` accepte le châssis débloqué, vies retirées
  du profil, W' estimé publié, échec de l'estimation sans effet.
- `core/tests/test_rogue_progress.py` : `last` dans `config_block`, châssis plus débloqué remplacé par le
  standard ; `core/tests/test_settings.py` : volumes du Cyber-Rogue, `settings` au-delà de 4 096 octets.
- `engine/tests/unit/test_rogue_menu_model.gd` : choix repris depuis `last`, avertissement sauté (à passer
  sur le PC, Godot absent du cloud).

## 4. Reste (hors code de ce lot)

- Essais du propriétaire : R0 et R14 sur le vélo, contrôle visuel R10–R13, accord sur la charte R17,
  mesures sur la GTX 1060, écoute des sons R18.
- Constats du banc visuel X41 à revoir avec les captures : hologramme et jauges superposés en vue subjective,
  HUD classique visible pendant la run, portes du couloir coupées en 720p ; purge et coffre sans
  déclencheur de son.
- Achat d'une vie depuis le Garage : `coins.buy_life` existe, aucune commande ne l'appelle.
