# Série MJ : profils de joueurs et profil d'essai (version 2.0)

29 octobre 2026, mis à jour le 29 octobre à 16 h avec tes réponses (§10). Demande du propriétaire : pouvoir utiliser OpenRide à plusieurs, chacun avec ses réglages (FTP, FC max, poids, équipement, réglages) et sa progression enregistrée à part ; et un **profil d'essai** utilisable en simulation pour vérifier le cumul d'expérience, les achats avec les pièces, etc. Étude seulement, aucun code. État lu sur `main` du 29 octobre (`bcd13269`, après la PR #564).

Maquettes des écrans : https://claude.ai/artifact/GhbjhMXyyb5GALuhhqoMqj ; toutes validées le 29 octobre (A à D à 16 h, E et F à 16 h 32).

Cahiers des lots : `docs/lots/LOT_MJ1_*.md` à `LOT_MJ10_*.md` (lot MJ0, 29 octobre). Un ajustement au découpage du §8, décidé à la rédaction des cahiers : la « Session simulée » du menu passe sur le profil d'essai dès MJ2 (et non MJ9), pour que le profil d'essai soit utilisable depuis le menu dès MJ3.

## 0. En bref

- **Aujourd'hui il n'y a qu'un joueur, et ses données sont éparpillées** dans `~/OpenRide/` : réglages du cycliste dans `config.toml` (mêlés à ceux de la machine), équipement et achats dans `profile.json`, records dans `records.json`, plan actif dans `plan_state.toml`, séances dans `Activities/` (FIT et journaux `.jsonl`). L'expérience, le niveau et les pièces gagnées ne sont stockés nulle part : ils se recalculent depuis les journaux. C'est une très bonne base : **un profil = un dossier**, il suffit de ranger ces fichiers dans `~/OpenRide/Profils/<id>/`.
- **Le vrai profil est déjà pollué par les essais.** La « Session simulée » du menu écrit ses séances, FIT et records dans les mêmes dossiers que les vraies séances (elles ne rapportent pas d'expérience, mais elles comptent dans l'historique, les records, le fantôme et le suivi du plan). La recette V10 modifie le vrai `profile.json` puis le restaure depuis une sauvegarde. Le profil d'essai règle ces deux problèmes.
- **Profil d'essai = un profil comme les autres**, dans son propre dossier, avec une seule différence décrite par une donnée : les séances simulées y rapportent de l'expérience et des pièces (dans un vrai profil, elles ne comptent pas). Il ne devient jamais le profil par défaut, il est signalé à l'écran (« ESSAI »), et un garde-fou automatique vérifie que le vrai profil n'a pas changé d'un octet après une campagne d'essai.
- **Campagne simulée en temps accéléré** (outil nouveau, sur le modèle de `rogue_bout_en_bout`) : vingt séances variées sur le profil d'essai en quelques minutes, sans vélo ni PC, puis contrôle de l'expérience, des niveaux, des défis, des pièces, des achats refusés et acceptés, de l'équipement appliqué et de la reprise après redémarrage. Je peux la lancer dans le cloud.
- **Choix du profil au lancement :** écran « Qui roule ? » après la connexion des appareils, **seulement s'il y a au moins deux profils** (rien ne change pour toi seul). Mêmes boutons que les autres menus (+ et − pour choisir, A maintenu pour valider), aucun bouton nouveau. Le dernier profil utilisé est présélectionné : un seul appui maintenu sur A.
- **Migration :** au premier lancement de la nouvelle version, ton profil actuel devient `Profils/principal/` (déplacement des fichiers, sauvegarde complète avant, rien n'est recalculé). Ton niveau, tes pièces, tes records et ton historique restent identiques, vérifié par `openride-core xp --compare` (lot X39).
- **IPC :** ajouts compatibles seulement (un objet `profile` dans `hello_ack.config`, un message `profiles`, trois commandes). À placer dans la révision ouverte au moment de la fusion, la **1.5** si elle l'est encore.
- **Version cible : 2.0**, avec la progression de la série V. Le profil d'essai (lots MJ1 à MJ3) passe en premier, tout de suite, car il sert à tester la série V. Le multi-joueur (MJ4 à MJ9) suit. Dix lots, série « MJ » (multi-joueurs), §8.

## 1. Ce qui existe aujourd'hui

| Donnée | Où | Par joueur ? | Remarque |
| --- | --- | --- | --- |
| FTP, poids du cycliste, poids et CdA du vélo | `config.toml` `[rider]`, `[bike]` | **Oui** | Réglages du menu, groupe « Cycliste » |
| FC max | `config.toml` `[rider] hr_max_bpm` | **Oui** | En revue dans la PR #561 (zones de FC du HUD) |
| Difficulté, braquet de départ, bonus, niveau des bots, vent | `config.toml` `[trainer]`, `[gearing]`, `[powerups]`, `[bots]`, `[wind]` | Oui (préférences) | Groupes « Séance » et « Vent » |
| Vue de caméra, courbes de la séance | `config.toml` `[render] camera`, `chart` | Oui (préférences) | |
| Qualité graphique, mode d'affichage, images/s, thème, volumes | `config.toml` `[render]`, `[audio]` | Non : la machine | Dépend de l'écran et de la carte graphique |
| Trainer, Click, ports IPC, Godot, journal de latence | `config.toml` `[drivers]`, `[ipc]`, `[engine]`, `[log]` | Non : la machine | |
| Ceinture cardio | `config.toml` `[drivers] hr`, `hr_address`, `hr_name` | **Oui** | Chacun a sa ceinture |
| Équipement porté, achats, vies, avatar | `profile.json` (lot V4, version 1, écriture sûre, migration) | **Oui** | Format gardé tel quel |
| Expérience, niveau, défis, pièces gagnées | recalculés depuis les journaux (`progression.py`, `coins.py`), cache `Activities/.journal/.progression.json` | **Oui** | Rien à migrer : suit les journaux |
| Records par segment | `records.json` (lot T5) | **Oui** | Écrits aussi en session simulée aujourd'hui |
| Séances | `Activities/*.fit`, `Activities/.journal/*.jsonl` | **Oui** | En-tête `source` = `live`, `simulated` ou `replay` |
| Plan actif | `plan_state.toml` (lot O11) | **Oui** | |
| Historique (cache) | `~/.cache/openride/history.json` | **Oui** | À ranger par profil |
| Reprise après plantage | journal le plus récent de `Activities/.journal/` (lot N8) | **Oui** | Suit les journaux |
| Bibliothèques : GPX, parcours compilés, entraînements, plans, thèmes | `GPX/`, `~/.local/share/openride/routes`, `Workouts/`, `Plans/`, `Themes/` | Non : partagées | Un entraînement créé par l'un sert à tous |
| Tables d'équilibrage | `progression.toml`, `powerups.toml`, `rogue_balance.toml` | Non, sauf essai | Surcharges facultatives |
| Journaux du lanceur | `Logs/`, `~/run_trainer.log` | Non : la machine | |

**Constats techniques**

1. **Chemins figés au chargement.** Environ 120 références du core utilisent des constantes calculées à l'import (`OPENRIDE_HOME`, `PROFILE_PATH`, `JOURNAL_DIR`, `RECORDS_FILE`, `ACTIVITIES_DIR`, `plans.STATE_PATH`…). Changer de profil sans relancer le core demande de les remplacer par un objet de contexte passé aux services. C'est le gros du travail du premier lot, sans changement visible.
2. **La séance simulée ne rapporte pas d'expérience** (`progression.ineligible_reason` : `simulated` et `replay` refusés). Bonne règle pour un vrai profil ; elle empêche aujourd'hui de tester le cumul en simulation, d'où la règle propre au profil d'essai (§4).
3. **Les outils de test sont déjà isolés** (`sim_bench`, `e2e_check`, `rogue_bout_en_bout`, suites pytest : HOME temporaire et garde-fou d'écriture, `test_isolation.py`). Mais l'utilisateur, lui, n'a aucun moyen de jouer « pour du faux » sans toucher ses vraies données.
4. **L'engine ne stocke rien** (aucun `user://`) : tout ce qui est propre au joueur est dans le core. Les profils ne touchent l'engine que par l'IPC et les menus.
5. **La recette V10** (`tools/recette_v10.py`, PR #564) pose l'équipement dans le vrai `profile.json`, avec sauvegarde et restauration, même après Ctrl+C. Ça marche, mais c'est exactement le genre de manipulation qu'un profil d'essai rend inutile.

## 2. Modèle de données recommandé

### 2.1 Arborescence

```
~/OpenRide/
  config.toml              machine : [drivers] (sans la ceinture), [ipc], [engine], [render] qualité/affichage/fps/thème, [audio], [log], [open_world]
                           + [profils] dernier = "principal"
  GPX/  Workouts/  Plans/  Themes/  Logs/  Cache/      partagés, inchangés
  progression.toml  powerups.toml  rogue_balance.toml  surcharges partagées (inchangées)
  Profils/
    principal/
      profil.toml          identité + réglages du joueur (§2.2)
      profile.json         équipement, achats, vies, avatar (format V4 inchangé)
      records.json
      plan_state.toml
      Activities/          FIT, et .journal/ (journaux .jsonl, cache .progression.json)
      .verrou              verrou de la séance en cours
    cycliste-2/ …
    _essai/                profil d'essai (§4), même structure
      progression.toml     surcharge facultative, propre au profil d'essai
```

Règle unique : **tout ce qui appartient à un joueur est sous `Profils/<id>/`, tout le reste est à la machine.** Pas de fichier de profil ailleurs, pas de cas particulier pour le premier profil.

### 2.2 `profil.toml`

```toml
[profil]
id = "principal"            # nom du dossier : minuscules, chiffres, tirets ; jamais changé
nom = "Cycliste 1"          # nom affiché, libre, modifiable ; jamais publié
type = "joueur"             # "joueur" ou "essai"
cree = 2026-10-29
seances_comptees = ["live"] # sources qui rapportent expérience et pièces ; profil d'essai : ["live", "simulated"]

[rider]                     # mêmes sections et mêmes clés que config.toml, validées par config.py
ftp_w = 250
mass_kg = 75
hr_max_bpm = 185
[bike]
mass_kg = 9
[drivers]
hr = "ble"
hr_address = ""
[trainer]
difficulty_pct = 50
[gearing]
start_gear = 12
[powerups]
mode = "on"
[bots]
level_pct = 100
[wind]
mode = "off"
[render]
camera = "follow_near"
chart = "reduced"
```

- **Configuration effective = valeurs par défaut ← `config.toml` ← `profil.toml`**, lue par le même `config.load()` (mêmes bornes, mêmes messages d'erreur, lot J3). Une clé « joueur » trouvée dans `config.toml` reste lue (compatibilité), mais le profil l'emporte.
- **Chaque réglage du menu porte sa portée** dans `settings.py` (`scope = "profil"` ou `"machine"`), et `set_setting` écrit dans le bon fichier avec `config_edit` (commentaires gardés, copie `.bak`). L'engine n'a rien à savoir de cette répartition.
- La liste des clés « joueur » est une table (`PROFILE_KEYS` dans `config.py`), pas une suite de `if`.
- **Aucune donnée personnelle dans le dépôt** : `profil.toml` reste local comme `config.toml` aujourd'hui ; les tests utilisent « Cycliste A », « Cycliste B » et des valeurs par défaut (règle de confidentialité du projet).

### 2.3 Journaux

L'en-tête du journal `.jsonl` gagne `profile_id` (et `profile_type`). La progression d'un profil ne compte que les journaux de son dossier **et** dont `profile_id` est le sien ; un journal sans `profile_id` (toutes les séances d'avant) appartient au profil migré. Un journal copié par erreur d'un dossier à l'autre est donc ignoré, avec un avertissement dans `openride-core xp`.

## 3. Choisir le profil

### 3.1 Au lancement

1. Le lanceur et le core prennent `--profil <id>` (et la variable `OPENRIDE_PROFIL`). Sans option : `[profils] dernier` de `config.toml`, sinon le seul profil, sinon `principal`.
2. Écran « Connexion des appareils » (lot N13), inchangé : il doit passer en premier puisque c'est lui qui relie le Click.
3. **Écran « Qui roule ? »** (maquette A), seulement s'il existe au moins deux profils de type `joueur`. Une ligne par profil : nom, niveau, date de la dernière séance, couleur du maillot de l'avatar. Le dernier profil est présélectionné. Mêmes boutons que tous les menus (`menu_model.gd`, spécification §7.1) : + ou A court au suivant, − (ou B du boîtier droit) au précédent, **A maintenu valide**, Y revient ; aucun bouton nouveau. Avec le profil présélectionné, un seul A maintenu suffit. Dernière ligne : « Nouveau profil ».
4. L'accueil affiche le profil dans son titre (« OpenRide — Cycliste 1 ») et gagne une ligne « Profil : Cycliste 1 » qui rouvre « Qui roule ? » (maquette B).

Raccourcis de bureau : `openride --profil cycliste-2` saute l'écran (une icône par cycliste, facultatif).

### 3.2 Changer de profil sans relancer

Le changement est accepté hors séance seulement (`IDLE`, `READY`, comme le Garage), sinon `busy`. Le core recharge en place la configuration effective, le service de progression, les records, le plan actif et le dossier des journaux, puis renvoie un `hello_ack` complet : l'engine le traite comme une nouvelle poignée de main (listes, réglages, Garage rafraîchis). La liaison Bluetooth du trainer et du Click n'est pas coupée. Si le profil a une autre ceinture cardio, le core la recherche comme au démarrage.

Le profil en cours est écrit dans un petit fichier de session (`~/OpenRide/.profil_actif`), lu par le lanceur pour relancer le core avec le bon profil après un plantage (lot N8). `[profils] dernier`, lui, n'est mis à jour que pour un profil `joueur`.

### 3.3 Créer, nommer, renommer, supprimer : tout dans le menu (décision du 29 octobre)

- **Créer** : « Nouveau profil » ouvre d'abord l'écran **« Nom du profil »** (maquette E), puis l'écran du profil créé : FTP, poids, FC max, avatar (maquette C). Le nom proposé est « Cycliste N » : A maintenu tout de suite le garde.
- **Saisie du nom** (maquette E), pensée pour le Click : une grille de lettres (A à Z, é è ê à ç, chiffres, espace, tiret). + et − passent à la lettre suivante ou précédente, + et − maintenus sautent d'une ligne, **Z écrit la lettre** (Z est le bouton « action » de la spécification §7.1), Y efface la dernière lettre, **A maintenu valide le nom**. Au clavier, on tape le nom directement (Entrée valide, Retour arrière efface) ; à la souris, on clique les lettres. Exemple « Thomas » : environ 25 appuis courts au Click, quelques secondes au clavier.
- **Nom** : 1 à 16 caractères, lettres (accents compris), chiffres, espace et tiret ; deux profils ne peuvent pas avoir le même nom. L'identifiant du dossier est tiré du nom (« Thomas » → `thomas`) et ne change plus, même si le nom change.
- **Gérer le profil** (maquette F) : depuis « Qui roule ? » ou la ligne « Profil » de l'accueil, A maintenu sur un profil puis « Gérer » : **Renommer** (même écran E, nom actuel déjà écrit), **Supprimer**.
- **Supprimer** : écran de confirmation qui rappelle ce qui part (niveau, séances, pièces), « Non » a le focus, il faut aller sur « Oui, supprimer » et maintenir A. Le dossier part dans `~/OpenRide/Profils/.corbeille/` (récupérable à la main pendant 30 jours) ; le profil en cours et le profil d'essai ne se suppriment pas (le profil d'essai se vide : « Vider le profil d'essai » dans son accueil). Le dernier profil joueur ne se supprime pas non plus.
- Les commandes `openride-core profil …` restent pour les outils et les essais, mais rien ne les exige.
- Huit profils au plus (le menu et le message `profiles` restent courts).

## 4. Le profil d'essai

### 4.1 Ce qu'il est

Un profil normal, dossier `Profils/_essai/`, `type = "essai"`, `seances_comptees = ["live", "simulated"]`. Tout le reste est le code commun : même Garage, mêmes achats, même calcul de l'expérience, mêmes records. Pas de « triche » (pas de commande qui donne des pièces) : pour avoir des pièces, on roule, en simulé et en accéléré. La seule souplesse permise est déjà prévue par le code : une surcharge `progression.toml` propre au profil (par exemple des gains ×10 pour atteindre vite les niveaux élevés), qui reste de la donnée.

### 4.2 Comment on s'en sert

| Usage | Commande | Où |
| --- | --- | --- |
| Jouer pour du faux depuis le menu | « Session simulée » de l'accueil : le lanceur relance avec le matériel simulé **et** `--profil _essai` | PC |
| Lancer un essai à la main | `openride --profil _essai` (matériel réel ou simulé) | PC |
| Campagne automatique | `python -m openride_core.tools.campagne_profil [--seances 20] [--graine 7] [--json]` | Cloud ou PC |
| Remettre à zéro | `openride-core profil essai --vider` (dossier vidé, réglages gardés) | Cloud ou PC |
| Voir la progression | `openride-core xp --profil _essai` | Cloud ou PC |
| Recette V10 et suivantes | les outils de recette roulent sur `_essai` au lieu de sauvegarder et restaurer ton profil | PC |

### 4.3 La campagne simulée (lot MJ3)

Sur le modèle de `rogue_bout_en_bout` (lot X40) : la vraie séance du core tourne sans engine, au pas d'une seconde, avec le cycliste simulé (`sim_rider`, lot X27) et le trainer simulé. Une campagne enchaîne, dans un HOME temporaire (cloud) ou sur le profil `_essai` (PC) :

1. sessions libres sur un parcours plat et un parcours vallonné, avec segments, sprints, bonus et bots ;
2. une séance ERG terminée et une abandonnée ;
3. une run Cyber-Rogue ;
4. une séance trop courte (ne doit rien rapporter) ;
5. entre les séances : `list_garage`, `buy` refusé faute de pièces (`not_enough_coins`), puis accepté quand le solde suffit, `equip`, `set_avatar` ;
6. arrêt et relance du core au milieu (le profil et le solde doivent survivre).

**Contrôles :** expérience de chaque `xp_result` = expérience recalculée par `openride-core xp` ; niveaux franchis au bon seuil ; défis débloqués une seule fois ; solde de pièces = gagnées − dépensées ; pièce achetée présente dans `profile.json` et effet appliqué à la physique (masse, CdA dans l'en-tête `loadout` du journal) ; `equipment_gain_s` non nul avec l'équipement acheté ; records écrits dans le profil d'essai ; **empreinte du vrai profil identique avant et après** (§4.4). Sortie lisible et `--json`, code 0 ou 1, entrée dans `docs/OUTILS_DE_TEST.md`.

### 4.4 Isolement : le profil d'essai ne pollue jamais le vrai profil

Plusieurs barrières, chacune suffisante seule :

1. **Un dossier à lui.** Le core ne reçoit qu'un contexte de profil (§2.1) ; aucun module ne garde de chemin vers un autre profil. Les seuls fichiers communs écrits par une séance sont les journaux du lanceur (`Logs/`).
2. **Jamais le profil par défaut.** `[profils] dernier` n'enregistre jamais `_essai` ; il n'apparaît pas dans « Qui roule ? ». Après un essai, un lancement normal ouvre toujours ton profil.
3. **Signalé à l'écran.** Titre « OpenRide — PROFIL D'ESSAI » et petit bandeau « ESSAI » dans le HUD pendant la séance (maquette D) ; nom des FIT suffixé `_essai`.
4. **Journaux marqués.** `profile_id = "_essai"` en en-tête : même copié dans un vrai profil, un journal d'essai n'y compte pas (§2.3).
5. **Garde-fou automatique.** Un test (pytest, et la campagne elle-même) prend l'empreinte SHA-256 de `Profils/principal/` et de `config.toml`, lance la campagne sur `_essai`, et échoue si un seul octet a changé. Le test d'isolation existant (`test_isolation.py`) gagne le cas « écriture hors du dossier du profil pendant une séance d'essai ».
6. **Verrou.** `Profils/<id>/.verrou` empêche deux séances d'écrire le même profil.

La « Session simulée » du menu passe automatiquement sur `_essai` : le matériel simulé et le profil d'essai vont ensemble. Ça corrige au passage la pollution actuelle des records et de l'historique (§0).

## 5. Migration de ton profil actuel (lot MJ5)

Au premier lancement de la version avec profils, s'il n'y a pas de `Profils/` :

1. **Sauvegarde** : archive `~/OpenRide/Sauvegardes/avant_profils_AAAAMMJJ.tar.gz` de `config.toml`, `profile.json`, `records.json`, `plan_state.toml` et `Activities/` (fichiers petits : FIT et journaux).
2. **Création** de `Profils/principal/` ; `profil.toml` reçoit les clés « joueur » de `config.toml` (§2.2) ; nom affiché « Cycliste 1 » (à renommer par la commande si tu veux).
3. **Déplacement** (renommage sur le même disque, instantané, sans recopie) de `profile.json` et `plan_state.toml` dans le profil ; **chaque séance selon l'en-tête de son journal** : `live` (et FIT sans journal) dans `principal/Activities/`, `simulated` et `replay` dans `_essai/Activities/` ; `records.json` de `principal` recalculé depuis ses seuls journaux réels (l'ancien gardé dans la sauvegarde) ; cache d'historique invalidé.
4. **`config.toml` allégé** : les clés passées au profil sont retirées par `config_edit` (copie `.bak`), avec un commentaire qui dit où elles sont parties.
5. **Contrôle** : progression recalculée avant et après (`xp --save` puis `--compare`, lot X39) ; toute différence annule la migration et remet les fichiers en place.
6. **Reprise sûre** : chaque étape est notée dans `Profils/.migration` ; une migration interrompue (coupure de courant) reprend là où elle s'est arrêtée.

Rien n'est recalculé ni réécrit dans les journaux : les anciens journaux sans `profile_id` appartiennent à `principal`. Un retour à une version d'avant n'est pas prévu (elle repartirait d'un profil vide) ; la sauvegarde permet de revenir en arrière à la main.

**Vérifié le 29 octobre (§10, point 4) :** aucun outil du dossier `~/OpenRide/` ne lit `Activities/`, qui ne contient que des séances d'essai ; le nouveau chemin `~/OpenRide/Profils/principal/Activities/` ne casse rien de connu.

## 6. Impact sur l'IPC

Ajouts compatibles seulement, à noter dans la **révision ouverte au moment de la fusion du lot de contrat** : la 1.5 si elle l'est encore (elle reçoit encore des ajouts compatibles, O18 et T12/T13 le 28 octobre), sinon la première révision libre (§6.1 de la spécification ; attention, la 1.6 est déjà réservée provisoirement à la série U et proposée pour les power-ups tactiques).

| Ajout | Sens | Contenu |
| --- | --- | --- |
| `hello_ack.config.profile` | core → engine | `{id, name, type ("joueur" ou "essai"), count}` ; absent : engine d'avant, rien d'affiché |
| `list_profiles` | engine → core | `{}` ; réponse `profiles` |
| `profiles` | core → engine | `v`, `request_cmd_id`, `active`, `items` : `{id, name, type, level, last_ride, kit_primary}` (huit au plus, environ 600 octets, un seul datagramme) ; `_essai` n'y figure que s'il est actif |
| `select_profile` | engine → core | `{id}` ; hors séance seulement (`busy` sinon) ; réponse : un nouveau `hello_ack` complet, puis `settings` et `progression` |
| `create_profile` | engine → core | `{name}` ; crée le profil et le rend actif ; réponse : `hello_ack` puis `profiles` |
| `rename_profile` | engine → core | `{id, name}` ; réponse `profiles` |
| `delete_profile` | engine → core | `{id}` ; hors profil en cours, profil d'essai et dernier profil joueur ; réponse `profiles` |
| code `profile_invalid` | core → engine | profil inconnu, illisible, verrouillé, plus de huit profils, suppression refusée |
| code `name_invalid` | core → engine | nom vide, trop long, caractère refusé, ou déjà pris |

Pas de nouvel événement de bouton : l'écran du nom utilise Z court, déjà émis par le core dans les menus. Le journal (`.jsonl`) gagne `profile_id` et `profile_type` dans l'en-tête : c'est le format du journal, pas l'IPC. Le core peut renvoyer un `hello_ack` en cours de route : à préciser dans le contrat (§5), l'engine doit alors repartir de zéro sur ses listes.

## 7. Version cible

**2.0**, avec la série V (progression, Garage, avatar) dont les profils sont le prolongement :

- les lots du **profil d'essai** (MJ1 à MJ3) servent tout de suite à tester la série V et la recette V10 sans toucher ton profil : à faire en premier ;
- le **multi-joueur** (MJ4 à MJ9) suit, avant la sortie de la 2.0 : migrer une fois, avant que d'autres joueurs n'aient de la progression, est plus simple que plus tard ;
- la 1.0 (séries N et O) n'est pas touchée.

## 8. Découpage en lots (série MJ)

| Lot | Contenu | Langage | Dépend de | Taille | Validé par |
| --- | --- | --- | --- | --- | --- |
| MJ0 | Cahiers des charges MJ1–MJ9, lignes de la spécification générale (2.0-PRF-1…), index des lots | doc | cette étude | Petite | toi |
| MJ1 | Contexte de profil dans le core : objet `ProfileContext` (dossiers), fin des chemins figés à l'import, option `--profil` du core et du lanceur, verrou ; sans profil, chemins d'aujourd'hui (aucun changement visible) | Python | — | Moyenne | pytest, suites existantes inchangées |
| MJ2 | Profil d'essai : `Profils/_essai/`, `profil.toml` minimal, `seances_comptees`, `profile_id` dans l'en-tête du journal, `openride-core profil essai --vider`, `xp --profil`, « Session simulée » du menu sur `_essai` | Python | MJ1 | Petite | pytest |
| MJ3 | Campagne simulée accélérée (`tools/campagne_profil.py`) et garde-fou d'empreinte du vrai profil | Python | MJ2 | Moyenne | cloud |
| MJ4 | Configuration à deux couches : `config.toml` + `profil.toml`, table `PROFILE_KEYS`, portée de chaque réglage du menu, `set_setting` écrit dans le bon fichier ; FC max (#561) comprise | Python | MJ1 | Moyenne | pytest |
| MJ5 | Migration du profil actuel (§5) et contrôle X39 | Python | MJ2, MJ4 | Moyenne | pytest + PC (avec sauvegarde) |
| MJ6 | Contrat IPC (§6) : texte, schémas, journal des changements | doc, JSON | MJ0 | Petite | toi |
| MJ7 | Core : `list_profiles`, `select_profile` (rechargement à chaud), `create_profile`, `.profil_actif`, relance après plantage avec le bon profil, commandes `openride-core profil …` | Python | MJ4, MJ6 | Moyenne | pytest, e2e |
| MJ8 | Engine : écran « Qui roule ? », ligne « Profil » de l'accueil, saisie du nom au Click, au clavier et à la souris, gestion (renommer, supprimer avec confirmation), bandeau ESSAI ; scénarios `menu_bench` (Click, clavier, souris), captures `visual_check` | GDScript | MJ7, **maquettes validées** | Moyenne | captures validées par toi |
| MJ9 | Outils et docs : recette V10 sur `_essai`, guide d'utilisation (raccourcis vérifiés par `test_docs_coherence`), `OUTILS_DE_TEST.md`, suivi | Python, doc | MJ7, MJ8 | Petite | pytest |
| MJ10 | Recette PC : migration réelle (sauvegarde d'abord), deux profils, changement au Click, une séance de 10 min max sur le vélo | PC | MJ5, MJ9 | Petite | toi, via la file des mesures PC |

Ordre conseillé : MJ0 → MJ1 → MJ2 → MJ3 (profil d'essai utilisable) ; MJ6 en parallèle dès MJ0 ; puis MJ4 → MJ5 → MJ7 → MJ8 → MJ9 → MJ10. Aucune mesure de performance nécessaire (rien ne change dans la boucle à 50 Hz ni dans le rendu, hors un bandeau de texte) ; si un banc est demandé quand même, il couvrira low, medium et high.

## 9. Questions posées le 29 octobre (réponses au §10)

1. **Quels réglages suivent le joueur ?** Recommandation : Cycliste (FTP, poids, FC max, poids du vélo), Séance (difficulté, braquet de départ, bonus, niveau des bots), Vent, vue de caméra, courbes, ceinture cardio, équipement et avatar → le profil ; qualité graphique, mode d'affichage, images/s, thème, volumes, trainer et Click → la machine.
2. **La « Session simulée » du menu passe-t-elle automatiquement sur le profil d'essai ?** Recommandation : oui (corrige la pollution actuelle des records et de l'historique).
3. **Création et suppression :** création au menu avec un nom automatique, renommage et suppression en ligne de commande seulement. D'accord, ou tu veux aussi renommer au Click ?
4. **Un outil à toi lit-il `~/OpenRide/Activities/` ?** (son chemin change à la migration, §5)
5. **Maquettes A à D** : à valider ou à corriger avant tout code d'écran.

## 10. Réponses du propriétaire (29 octobre, 16 h) et conséquences

1. **Réglages qui suivent le joueur : d'accord, avec le poids, la FTP et la FC max.** Ils y étaient (groupe Cycliste : FTP, poids, poids du vélo, FC max de la PR #561) ; ils sont maintenant écrits noir sur blanc et affichés sur l'écran du profil créé (maquette C). Reste à la machine : qualité graphique, affichage, images/s, thème, volumes, trainer et Click.
2. **Session simulée → profil d'essai : oui.**
3. **Le joueur nomme son profil (« Thomas ») et tout se fait dans le menu** : création, nom, renommage, suppression. §3.3 réécrit, deux écrans de plus à valider (maquettes E et F), commandes IPC `create_profile {name}`, `rename_profile`, `delete_profile` et code `name_invalid` (§6).
4. **Outil qui lit `~/OpenRide/Activities/` : vérifié sur le PC.** Le dossier `~/OpenRide/` ne contient aucun outil d'envoi ni de synchronisation (pas de profil Garmin, Strava ou autre, pas de lien) ; `Activities/` ne contient que 58 FIT d'essais (`demo`, `seance`, `essai-69`) et le journal. Pas de `profile.json` encore (la progression n'a jamais tourné sur une vraie séance). Je n'ai pas accès au reste du PC (tâches planifiées) : si tu n'as rien installé toi-même pour envoyer tes FIT, il n'y a rien à adapter. **Conséquence pour la migration :** presque tout est de l'essai. La migration range donc chaque séance selon l'en-tête de son journal : `simulated` et `replay` vont dans `_essai`, `live` dans `principal` ; les records de `principal` sont recalculés depuis ses seuls journaux réels (`records.py` sait le faire), ce qui retire les records d'essai. Un FIT sans journal reste dans `principal`.
5. **Maquettes A à D : validées.** E et F (nom, gestion du profil) : **validées le 29 octobre à 16 h 32.** Toutes les maquettes sont validées ; les vraies captures du jeu seront montrées avant fusion du lot MJ8.
