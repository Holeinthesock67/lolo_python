# Coach sportif hybride – mémo du système

Mis à jour le 21/10/2026 (synthèse v2.3, mise à jour automatique du Pi depuis GitHub). Ce document est la référence pour reprendre le système dans une nouvelle conversation : le donner à Claude, ou lui dire de lire `claude/README_coach.md` dans le projet « Coach Sportif ».

## Vue d'ensemble

### 1. Synthèse Intégrale (le programme)
- Version qui fait foi : texte dans le projet Claude « Coach Sportif » (`claude/Synthèse Intégrale v2.3 - …txt`). C'est la seule synthèse du projet. Historique : v2.2 (16/10) ; v2.3 (20/10) : 4×4 piloté par la charge « aérobie intense » sur 4 semaines, plus de décompte des séances intenses, rapport de charge aiguë / chronique Garmin, calories Garmin exclues.
- PDF v2.3 et script générateur `build.py` (reportlab + polices DejaVu) : `D:\Sauvegarde\Documents\utilisateur\lolo_python\Projet_Raspberry\Sport\sources\`.
- Pour une nouvelle version : donner `build.py` à Claude dans une conversation du projet, il le modifie et régénère le PDF et le texte.

### 2. Carnet du coach (saisies manuelles)
- Page de saisie (téléphone), épinglée dans Claude : https://claude.ai/artifact/WAux9mehWeAnC7DU3vJ65e
  Onglets : Aujourd'hui (recommandation du coach du matin, programme prévu, check-in matin, bilan soir RPE × durée), Mesures (tour de taille et poids préremplis avec les dernières valeurs), Perf, Tendances.
  L'onglet Perf affiche aussi « Charge et intensité » (Garmin), lu dans `coach_metrics.json` du Drive « Coach - Garmin export » via le connecteur Google Drive : charge aiguë / chronique, répartition sur 4 semaines comparée aux cibles de l'onglet Réglages (avec la recommandation 4×4 qui en découle), minutes OMS, FTP estimé. Le nombre de séances intenses a été retiré le 20/10 (faussé par le CrossFit).
- Données : feuille Google « Coach – Carnet », dans le dossier Drive « Santé et Musculation ».
  ID `1rwXH-2Fop758Bk-6VTDATiySnkO9D7eyVEHn7yuZCt8`.
  Onglets :
  - Quotidien (A:J) : date, charge mentale, fatigue, sommeil ressenti, zones et intensité de douleur, maladie, score de sommeil Garmin, remarque, sommeil consolidé (calculé).
  - Soir (A:D) : date, RPE, durée, charge RPE × min (calculée).
  - Mesures, Tension, FTP, Biologie.
  - Réglages (valeurs personnelles lues par le coach et le carnet) : taille, tour de cou de référence, semaines ISO du 4×4, début de la créatine, âge, protéines par jour, seuil de poids pour [2–2–2] au déjeuner, Zone 2 au home trainer (% FTP), cible aérobie intense sur 4 semaines, plafond anaérobie sur 4 semaines. Les modifier dans la feuille suffit.
  - Coach (A:G) : date, verdict, séance du jour, pourquoi, nutrition, à faire, fiabilité — écrit chaque matin par la tâche planifiée.
  La feuille est en paramètres français : formules avec `;` et virgule décimale.
- Source de la page : `Sport\sources\carnet-du-coach.html` (à donner à Claude pour la modifier).

### 3. Skill « coach-hybride » (la méthode du coach)
- Contient : rôle et posture, sources à lire, procédure en 4 étapes, grille de décision, règles fixes, nutrition, rappels de mesures, format du point du jour.
- Il ne recopie pas le programme : il renvoie à la synthèse, qui fait foi.
- Pour le modifier : le demander à Claude, qui propose une version complète à valider et enregistrer d'un clic. Ne pas éditer de fichier.

### 4. Tâche planifiée « Point coach du matin »
- Tous les jours à 7 h 24 (heure de Paris), notification sur le téléphone.
- Lit : le skill, la synthèse, `coach_snapshot.md` (Drive « Coach - Garmin export »), le carnet (y compris l'onglet Coach), la météo.
- Écrit une seule chose : une ligne par jour dans l'onglet « Coach » de la feuille (pas de doublon si la ligne du jour existe), que le carnet affiche en haut de l'onglet Aujourd'hui. Rien d'autre n'est modifié.
- Répond en 10 lignes : Verdict, Séance du jour, Pourquoi, Nutrition, À faire, Fiabilité.
- La ligne **Fiabilité** signale les sources manquantes ou périmées et les conclusions à moins de 70 % de certitude. Le même problème plusieurs jours de suite = chaîne cassée.
- Modifier, mettre en pause ou supprimer : dans la liste des tâches planifiées de Claude. Elle ne dépend d'aucune conversation.
- Faire le check-in du matin avant 7 h 24 pour un point à jour.

### 4 bis. Tâche planifiée « Propreté des données coach »
- Tous les soirs à 21 h 56, skill « verif-donnees-coach ».
- Contrôle la feuille « Coach – Carnet » (en-têtes, dates, plages plausibles, doublons) et l'export Garmin du Pi (fraîcheur, trous, doublons d'activités).
- Corrige seulement le sans-ambiguïté (format de date, nombre écrit avec un point, espaces, doublon strictement identique), après une copie de sauvegarde dans le dossier Drive « Coach - Sauvegardes du carnet ». Ne touche jamais à l'export Garmin.
- Silencieuse si tout est propre ; sinon un message avec des points numérotés à valider (« 1 oui, 2 non »).

### 5. Le PC Windows
- Dossier : `D:\Sauvegarde\Documents\utilisateur\lolo_python\Projet_Raspberry\Sport` (script, `.venv` Windows, `data\coach.db` = sauvegarde du 17/10/2026).
- Rôle : sauvegarde, et seul endroit pour refaire la connexion Garmin (`.venv\Scripts\python coach.py login`, voir « Pannes possibles »).
- Python Windows : `.venv\Scripts\python …` (le Pi utilise `.venv/bin/python …`).
- Fichier `.env` : identifiants Garmin. Ne jamais le copier sur le Pi, ni le partager, ni l'envoyer à Claude.
- Commandes du script : `login`, `sync`, `garmin`, `activities` (rattrapage de l'effet d'entraînement et des zones, `--days 120` par défaut), `weather`, `report`, `integrity` (rapport `export\integrite.html`), option `--days N`.
- Ne plus lancer `sync` sur le PC : la base de référence est celle du Pi.

### 6. Règles de travail
- Toute modification du programme, des documents, du skill, du carnet ou de la tâche planifiée est d'abord proposée, puis validée par le propriétaire.
- On ne touche pas au dossier Drive « Santé et Musculation », sauf : la ligne quotidienne du coach dans l'onglet « Coach », et les corrections sûres de la tâche du soir (après sauvegarde). rclone n'écrit que dans « Coach - Garmin export ».
- Une conversation par sujet dans le projet « Coach Sportif » : coaching au quotidien d'un côté, script / Pi de l'autre.

### Ce qui reste ouvert
- Séance B dans Garmin (constat du 17/10) : élévations latérales 6 séries (synthèse 3), RDL 5 séries (synthèse 3 / jambe), leg curl 1 série (synthèse 2 / jambe), rowing anneaux 2 séries (synthèse 3) ; le lat prayer était enregistré comme « barbell upright row » ; il sera enregistré comme « tirage à la poulie » (Lat pulldown), le plus proche dans le catalogue Garmin. Reste à trancher le nombre de séries : corriger Garmin ou la synthèse.
- 4×4 : piloté depuis le 20/10 par la charge « aérobie intense » sur 4 semaines (sous la cible de Réglages → 4×4 recommandé au prochain créneau ; dans la cible → semainier normal ; au-dessus → remplacé par 45 min en Zone 2). Plus de détection des séances 4×4 : les home trainer étaient classés « Tempo » sans zone 5. Premier 4×4 le 18/10 (aérobie intense passée de 0 à 85). La synthèse recommande un avis cardiologique avant le 4×4 régulier.
- Calories Garmin volontairement non utilisées (erreur de 20 à 40 %) : le poids moyen 15 j sert de bilan énergétique.
- Idées pour plus tard : efficacité aérobie (EF) et découplage Pa:HR à partir des données seconde par seconde ; suivi de la double progression à partir des séries confirmées.

### 7. Code sur GitHub
- Dépôt privé `Holeinthesock67/lolo_python`, dossier `Projet_Raspberry/Sport` (script, README, `sources/` : carnet, `build.py`, PDF de la synthèse).
- Jamais sur GitHub (exclus par `.gitignore`) : `.env`, jeton Garmin, `data/` (base), `export/`, fichiers `.db`.
- Claude peut lire et mettre à jour le dépôt depuis le projet, même PC éteint.
- **Déploiement automatique (depuis le 21/10/2026)** : le Pi garde une copie du dossier `Projet_Raspberry` dans `~/lolo_python` (clé de déploiement GitHub en lecture seule `~/.ssh/github_deploy`, titre « coachpi »). Chaque matin à 7 h 05, `update_code.sh` récupère GitHub, compare le code à celui installé, teste chaque programme modifié (test hors ligne pour Sport, vérification de syntaxe pour Podcast) et ne le remplace que si le test passe. Seul le code est copié : données, environnements, jeton Garmin, rclone et crons ne bougent pas.
  - Sport → `~/garmin_coach` : `coach.py`, `db.py`, `garmin_source.py`, `report.py`, `training.py`, `integrity.py`, `exercises.py`, `weather_source.py`, `test_offline.py` (pas `config.toml`).
  - Podcast → `~/veille` : `commun.py`, `veille.py`, `podcast.py`.
  - Une modification poussée sur GitHub est donc en place le lendemain à 7 h 05. Pour l'appliquer tout de suite : `bash ~/lolo_python/Projet_Raspberry/update_code.sh`.
  - Voir ce qui changerait sans rien modifier : `bash ~/lolo_python/Projet_Raspberry/update_code.sh check`. Journal : `~/update_code.log`.
  - Ne jamais modifier le code directement sur le Pi : il serait écrasé par la version GitHub. Passer par GitHub (Claude ou le PC).
- Sur le PC, `git pull` dans `lolo_python` pour garder une copie à jour (plus nécessaire pour le Pi).

---

# Partie technique : Raspberry Pi

## La chaîne automatique

| Heure | Étape | Où |
|---|---|---|
| nuit | La montre enregistre ; le téléphone envoie à Garmin Connect | montre / téléphone |
| 7 h 05 | Mise à jour du code depuis GitHub (`update_code.sh`), après test | Raspberry Pi (cron) |
| 7 h 15 | Synchro Garmin + météo, exports, puis copie sur Google Drive | Raspberry Pi (cron) |
| 7 h 24 | « Point coach du matin » : verdict du jour envoyé sur le téléphone | tâche planifiée Claude |

Le Pi remplit le dossier Drive **« Coach - Garmin export »** avec `coach_snapshot.md`, `coach_metrics.json`, `integrite.html`, `daily.csv`, `activities.csv` et `weather_daily.csv`.

Données Garmin importées : FC repos, VFC, sommeil, Body Battery, stress, pas, Training Readiness, VO2max, poids, minutes d'intensité OMS, statut d'entraînement (charge aiguë/chronique, rapport, répartition sur 4 semaines et cibles), FTP estimé, activités (durée, FC, puissance, charge, effet d'entraînement aérobie/anaérobie et étiquette, temps en zones cardiaques) et séries de musculation. Calculs dans `training.py` : minutes OMS, FTP en W/kg. L'intensité se pilote uniquement par la répartition Garmin sur 4 semaines (aérobie intense et anaérobie) : ni détection des 4×4, ni décompte des séances intenses. Le coach lit ce dossier, ton carnet (feuille « Coach – Carnet ») et la Synthèse Intégrale.

## Le Raspberry Pi

- Modèle : Raspberry Pi 3, Raspberry Pi OS Lite 64 bits (Debian Trixie), Python 3.13
- Nom réseau : `coachpi` ; adresse IP : `192.168.1.44` (elle peut changer, voir l'interface de la box)
- Utilisateur : `utilisateur` (le mot de passe est celui choisi dans Raspberry Pi Imager)
- Pas d'écran : l'accès se fait par SSH depuis le PC

## Se connecter

Depuis PowerShell sur le PC :

```
ssh utilisateur@coachpi
```

- Si le nom ne répond pas : `ssh utilisateur@192.168.1.44`
- Rien ne s'affiche quand tu tapes le mot de passe : c'est normal.
- « Connection refused » juste après un redémarrage : attends 1 minute.
- Tu es sur le Pi quand l'invite affiche `utilisateur@coachpi:~ $`.
- Pour te déconnecter : `exit` (le Pi continue de tourner).

## Vérifier que tout tourne

| But | Commande (sur le Pi) |
|---|---|
| Dernière synchro et envoi Drive | `tail -20 ~/garmin_coach/data/sync.log` |
| Voir la programmation | `crontab -l` |
| Synchro manuelle | `cd ~/garmin_coach && .venv/bin/python coach.py sync` |
| Renvoyer les exports sur le Drive | `rclone copy ~/garmin_coach/export "gdrive:Coach - Garmin export" -v` |
| Test hors ligne du script | `cd ~/garmin_coach && .venv/bin/python test_offline.py` |
| Dernière mise à jour du code | `tail -5 ~/update_code.log` |

Programmation complète du Pi (`crontab -l`, sauvegarde dans `~/crontab.bak2`) :

```
5 7 * * * bash ~/lolo_python/Projet_Raspberry/update_code.sh >> ~/update_code.log 2>&1
15 7 * * * cd /home/utilisateur/garmin_coach && { .venv/bin/python coach.py sync; rclone copy export "gdrive:Coach - Garmin export" -v; } >> data/sync.log 2>&1
15 8 * * *  ~/veille-env/bin/python ~/veille/veille.py collect >> ~/podcast-data/veille.log 2>&1
15 9 * * *  ~/veille-env/bin/python ~/veille/veille.py build-week >> ~/podcast-data/veille.log 2>&1
45 10 * * 0  ~/veille-env/bin/pip install -q -U yt-dlp
30 10-22 * * *  flock -n /tmp/podcast.lock ~/piper-env/bin/python ~/veille/podcast.py >> ~/podcast-data/podcast.log 2>&1
```

Les lignes 8 h 15 à 22 h 30 concernent les podcasts (voir `Projet_Raspberry/Podcast/README.md`).

## Pannes possibles

**Jeton Garmin expiré** (le journal affiche « Jeton Garmin expiré », en général après plusieurs mois)
1. Sur le PC, dans `D:\Sauvegarde\Documents\utilisateur\lolo_python\Projet_Raspberry\Sport` : `.venv\Scripts\python coach.py login`
2. Toujours dans PowerShell sur le PC : `scp -r $HOME\.garminconnect utilisateur@coachpi:~/`

**Garmin répond 429** (trop de requêtes) : rien à faire. La synchro suivante relit les 3 derniers jours.

**rclone n'a plus accès à Google** : sur le Pi, `rclone config reconnect gdrive:`. Copie ensuite la commande `rclone authorize …` affichée, lance-la dans PowerShell sur le PC, valide dans le navigateur et recolle le résultat sur le Pi.

**Le point du matin signale « instantané daté d'hier »** : regarde `sync.log` sur le Pi (synchro ou Drive en échec ?).

**`update_code.log` affiche « TEST ÉCHOUÉ »** : l'ancienne version est restée en place, rien n'est cassé. Donner les lignes du journal à Claude, qui corrige sur GitHub.

**`update_code.log` affiche « GitHub injoignable »** : pas de mise à jour ce jour-là, le Pi tourne avec la version précédente. Si ça dure : vérifier la clé de déploiement (`ssh -T git@github.com` doit répondre « successfully authenticated »).

## Entretien

- Mises à jour (environ une fois par mois) : `sudo apt update && sudo apt full-upgrade -y`
- Avant de débrancher : `sudo shutdown -h now`, puis attendre que la LED verte s'arrête. Une coupure brutale peut abîmer la carte SD.
- Changer l'heure de la synchro : `crontab -e`, modifier `15 7`, puis Ctrl+O, Entrée, Ctrl+X. Garder la synchro avant 7 h 24, l'heure du point du matin.
- Vérifier l'heure du Pi : `date`. Si elle n'est pas à l'heure de Paris : `sudo timedatectl set-timezone Europe/Paris`

## Où sont les fichiers sur le Pi

| Élément | Emplacement |
|---|---|
| Script installé | `~/garmin_coach/` |
| Copie du dépôt GitHub (`Projet_Raspberry`) | `~/lolo_python/` |
| Clé de déploiement GitHub (lecture seule) | `~/.ssh/github_deploy` |
| Réglages (lieu, jours relus, chemins) | `~/garmin_coach/config.toml` |
| Base de données (**référence**) | `~/garmin_coach/data/coach.db` |
| Journal | `~/garmin_coach/data/sync.log` |
| Exports | `~/garmin_coach/export/` |
| Jeton Garmin | `~/.garminconnect/` |
| Configuration rclone (accès Google limité à ses propres fichiers) | `~/.config/rclone/rclone.conf` |

La base du PC (`Sport\data\coach.db`) n'est qu'une sauvegarde du 17/10/2026. Ne pas lancer `sync` sur le PC, sinon les deux bases divergent.

## Sauvegarder la base du Pi sur le PC

Dans PowerShell sur le PC :

```
scp utilisateur@coachpi:~/garmin_coach/data/coach.db D:\Sauvegarde\Documents\utilisateur\lolo_python\Projet_Raspberry\Sport\data\coach_pi.db
```

## Tout réinstaller (carte SD morte, nouveau Pi)

1. **Raspberry Pi Imager** : Raspberry Pi OS Lite 64 bits, nom d'hôte `coachpi`, utilisateur `utilisateur`, Wi-Fi, SSH activé par mot de passe, fuseau Europe/Paris. Ne pas activer Raspberry Pi Connect.
2. Si besoin, effacer l'ancienne empreinte SSH sur le PC : `ssh-keygen -R coachpi`, puis se connecter.
3. Sur le Pi : `sudo apt update && sudo apt full-upgrade -y && sudo apt install -y cron rclone`
4. Sur le PC, dans le dossier Sport :
   ```
   tar -czf $HOME\coach.tgz --exclude=.venv --exclude=__pycache__ --exclude=.env .
   scp $HOME\coach.tgz utilisateur@coachpi:~/
   scp -r $HOME\.garminconnect utilisateur@coachpi:~/
   ```
   Si tu as une sauvegarde plus récente de la base du Pi, remplace d'abord `data\coach.db` par celle-ci.
5. Sur le Pi :
   ```
   mkdir -p ~/garmin_coach && tar -xzf ~/coach.tgz -C ~/garmin_coach && cd ~/garmin_coach
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python coach.py sync
   ```
6. rclone : `rclone config`, puis nouveau remote `gdrive`, type `drive`, scope `drive.file`, pas de navigateur automatique (autorisation via `rclone authorize` sur le PC).
   Avec le scope `drive.file`, un nouveau rclone ne voit pas l'ancien dossier : il en créera un nouveau. Supprime l'ancien « Coach - Garmin export » dans le Drive avant le premier envoi.
7. Remettre les lignes cron (section « Vérifier que tout tourne ») : `crontab -e`.
8. GitHub : `sudo apt install -y git`, nouvelle clé `ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C coachpi`, l'ajouter dans GitHub (dépôt → Settings → Deploy keys, sans accès en écriture), `printf 'Host github.com\n  IdentityFile ~/.ssh/github_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config`, puis `git clone --filter=blob:none --sparse git@github.com:Holeinthesock67/lolo_python.git ~/lolo_python && cd ~/lolo_python && git sparse-checkout set Projet_Raspberry`. Avec GitHub en place, les étapes 4 et 5 peuvent copier le code depuis `~/lolo_python/Projet_Raspberry/Sport` au lieu du PC (le jeton Garmin vient toujours du PC).
