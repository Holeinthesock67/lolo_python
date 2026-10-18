# Coach sportif hybride – mémo du système

Mis à jour le 18/10/2026. Ce document est la référence pour reprendre le système dans une nouvelle conversation : le donner à Claude, ou lui dire de lire `claude/README_coach.md` dans le projet « Coach Sportif ».

## Vue d'ensemble

### 1. Synthèse Intégrale (le programme)
- Version qui fait foi : texte dans le projet Claude « Coach Sportif » (`claude/Synthèse Intégrale v2 - …txt`, contenu v2.2).
- PDF v2.2 et script générateur `build.py` (reportlab + polices DejaVu) : `D:\Sauvegarde\Documents\utilisateur\lolo_python\Projet_Raspberry\Sport\sources\`.
- Pour une nouvelle version : donner `build.py` à Claude dans une conversation du projet, il le modifie et régénère le PDF et le texte.

### 2. Carnet du coach (saisies manuelles)
- Page de saisie (téléphone), épinglée dans Claude : https://claude.ai/artifact/WAux9mehWeAnC7DU3vJ65e
  Onglets : Aujourd'hui (séance du jour, check-in matin, bilan soir RPE × durée), Mesures, Perf, Tendances.
  L'onglet Perf affiche aussi « Charge et intensité » (Garmin), lu dans `coach_metrics.json` du Drive « Coach - Garmin export » via le connecteur Google Drive.
- Données : feuille Google « Coach – Carnet », dans le dossier Drive « Santé et Musculation ».
  ID `1rwXH-2Fop758Bk-6VTDATiySnkO9D7eyVEHn7yuZCt8`.
  Onglets : Quotidien, Soir, Mesures, Tension, FTP, Biologie, Réglages (taille 176, cou 40, semaines du 4×4, début créatine, âge).
  La feuille est en paramètres français : formules avec `;` et virgule décimale.
- Source de la page : `Sport\sources\carnet-du-coach.html` (à donner à Claude pour la modifier).

### 3. Skill « coach-hybride » (la méthode du coach)
- Contient : rôle et posture, sources à lire, procédure en 4 étapes, grille de décision, règles fixes, nutrition, rappels de mesures, format du point du jour.
- Il ne recopie pas le programme : il renvoie à la synthèse, qui fait foi.
- Pour le modifier : le demander à Claude, qui propose une version complète à valider et enregistrer d'un clic. Ne pas éditer de fichier.

### 4. Tâche planifiée « Point coach du matin »
- Tous les jours à 7 h 24 (heure de Paris), notification sur le téléphone.
- Lit, sans rien modifier : le skill, la synthèse, `coach_snapshot.md` (Drive « Coach - Garmin export »), le carnet, la météo.
- Répond en 10 lignes : Verdict, Séance du jour, Pourquoi, Nutrition, À faire, Fiabilité.
- La ligne **Fiabilité** signale les sources manquantes ou périmées et les conclusions à moins de 70 % de certitude. Le même problème plusieurs jours de suite = chaîne cassée.
- Modifier, mettre en pause ou supprimer : dans la liste des tâches planifiées de Claude. Elle ne dépend d'aucune conversation.
- Faire le check-in du matin avant 7 h 24 pour un point à jour.

### 5. Le PC Windows
- Dossier : `D:\Sauvegarde\Documents\utilisateur\lolo_python\Projet_Raspberry\Sport` (script, `.venv` Windows, `data\coach.db` = sauvegarde du 17/10/2026).
- Rôle : sauvegarde, et seul endroit pour refaire la connexion Garmin (`.venv\Scripts\python coach.py login`, voir « Pannes possibles »).
- Python Windows : `.venv\Scripts\python …` (le Pi utilise `.venv/bin/python …`).
- Fichier `.env` : identifiants Garmin. Ne jamais le copier sur le Pi, ni le partager, ni l'envoyer à Claude.
- Commandes du script : `login`, `sync`, `garmin`, `activities` (rattrapage de l'effet d'entraînement et des zones, `--days 120` par défaut), `weather`, `report`, `integrity` (rapport `export\integrite.html`), option `--days N`.
- Ne plus lancer `sync` sur le PC : la base de référence est celle du Pi.

### 6. Règles de travail
- Toute modification du programme, des documents, du skill ou du carnet est d'abord proposée, puis validée par le propriétaire.
- On ne touche pas au dossier Drive « Santé et Musculation » (seul rclone écrit, et uniquement dans « Coach - Garmin export »).
- Une conversation par sujet dans le projet « Coach Sportif » : coaching au quotidien d'un côté, script / Pi de l'autre.

### Ce qui reste ouvert
- Séance B dans Garmin : nombre de tours à aligner sur la synthèse (élévations latérales, leg curl, rowing anneaux) ou synthèse à aligner sur Garmin.
- Calories Garmin volontairement non utilisées (erreur de 20 à 40 %) : le poids moyen 15 j sert de bilan énergétique.
- Idées pour plus tard : efficacité aérobie (EF) et découplage Pa:HR à partir des données seconde par seconde ; suivi de la double progression à partir des séries confirmées.

---

# Partie technique : Raspberry Pi

## La chaîne automatique

| Heure | Étape | Où |
|---|---|---|
| nuit | La montre enregistre ; le téléphone envoie à Garmin Connect | montre / téléphone |
| 7 h 15 | Synchro Garmin + météo, exports, puis copie sur Google Drive | Raspberry Pi (cron) |
| 7 h 24 | « Point coach du matin » : verdict du jour envoyé sur le téléphone | tâche planifiée Claude |

Le Pi remplit le dossier Drive **« Coach - Garmin export »** avec `coach_snapshot.md`, `coach_metrics.json`, `integrite.html`, `daily.csv`, `activities.csv` et `weather_daily.csv`.

Données Garmin importées : FC repos, VFC, sommeil, Body Battery, stress, pas, Training Readiness, VO2max, poids, minutes d'intensité OMS, statut d'entraînement (charge aiguë/chronique, rapport, répartition sur 4 semaines et cibles), FTP estimé, activités (durée, FC, puissance, charge, effet d'entraînement aérobie/anaérobie et étiquette, temps en zones cardiaques) et séries de musculation. Calculs dans `training.py` : séances intenses de la semaine, dernier 4×4 probable (étiquette VO2max ou ≥ 8 min en zone 5, vélo ou course), conformité Zone 2 de la sortie longue du week-end (zones 3 à 5 ≤ 10 % du temps) ; le CrossFit compte comme séance intense, la natation suit l'étiquette Garmin. Le coach lit ce dossier, ton carnet (feuille « Coach – Carnet ») et la Synthèse Intégrale.

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

Ligne programmée (cron) :

```
15 7 * * * cd /home/utilisateur/garmin_coach && { .venv/bin/python coach.py sync; rclone copy export "gdrive:Coach - Garmin export" -v; } >> data/sync.log 2>&1
```

## Pannes possibles

**Jeton Garmin expiré** (le journal affiche « Jeton Garmin expiré », en général après plusieurs mois)
1. Sur le PC, dans `D:\Sauvegarde\Documents\utilisateur\lolo_python\Projet_Raspberry\Sport` : `.venv\Scripts\python coach.py login`
2. Toujours dans PowerShell sur le PC : `scp -r $HOME\.garminconnect utilisateur@coachpi:~/`

**Garmin répond 429** (trop de requêtes) : rien à faire. La synchro suivante relit les 3 derniers jours.

**rclone n'a plus accès à Google** : sur le Pi, `rclone config reconnect gdrive:`. Copie ensuite la commande `rclone authorize …` affichée, lance-la dans PowerShell sur le PC, valide dans le navigateur et recolle le résultat sur le Pi.

**Le point du matin signale « instantané daté d'hier »** : regarde `sync.log` sur le Pi (synchro ou Drive en échec ?).

## Entretien

- Mises à jour (environ une fois par mois) : `sudo apt update && sudo apt full-upgrade -y`
- Avant de débrancher : `sudo shutdown -h now`, puis attendre que la LED verte s'arrête. Une coupure brutale peut abîmer la carte SD.
- Changer l'heure de la synchro : `crontab -e`, modifier `15 7`, puis Ctrl+O, Entrée, Ctrl+X. Garder la synchro avant 7 h 24, l'heure du point du matin.
- Vérifier l'heure du Pi : `date`. Si elle n'est pas à l'heure de Paris : `sudo timedatectl set-timezone Europe/Paris`

## Où sont les fichiers sur le Pi

| Élément | Emplacement |
|---|---|
| Script | `~/garmin_coach/` |
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
7. Remettre la ligne cron (section « Vérifier que tout tourne ») : `crontab -e`
