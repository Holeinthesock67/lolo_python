# Bascule vers la configuration par Google Sheet

À faire en une fois, un jour de semaine, en dehors de 8 h 15 à 9 h 30 (collecte et compilation).
Compter 15 minutes. Chaque étape se vérifie avant de passer à la suivante.

## 0. Avant de commencer

- Le skill **podcast-ecriture** est enregistré (carte proposée par Claude).
- Le Google Sheet **Configuration podcasts** est dans le dossier **Podcasts** du Drive.

## 1. Sauvegarde sur le Pi

```bash
cp -r ~/veille ~/veille.bak
crontab -l > ~/crontab.bak
```

## 2. Déposer les nouveaux programmes

Depuis le PC, dans le dossier du projet :

```bash
scp commun.py veille.py podcast.py utilisateur@coachpi:~/veille/
```

Puis sur le Pi, installer la lecture des fichiers Excel dans les deux environnements :

```bash
~/veille-env/bin/pip install openpyxl
~/piper-env/bin/pip install openpyxl
```

## 3. Ranger les données par émission

```bash
cd ~/podcast-data && mkdir -p ia
for f in daily weekly seen.json yt_channels.json scripts episodes work; do [ -e "$f" ] && mv "$f" ia/; done
ls ~/podcast-data/ia
cd ~
```

Le `ls` doit montrer `daily`, `episodes`, `scripts`, `seen.json`, `weekly`, `yt_channels.json`.

## 4. Déplacer « Podcast IA » dans « Podcasts » (Drive)

Demander à Claude de le faire, ou le glisser à la main dans Google Drive.
Les identifiants des dossiers ne changent pas.

## 5. Faire pointer rclone sur « Podcasts »

```bash
rclone config update podcast root_folder_id 1K2xwn7U5MN-irF0ZSy3o6cTHKBkRhIOi
rclone lsf podcast:
```

Le `lsf` doit afficher `Configuration podcasts.xlsx` et `Podcast IA/`.

## 6. Tester

```bash
~/veille-env/bin/python ~/veille/veille.py check
~/piper-env/bin/python ~/veille/podcast.py
```

- `check` : les 11 sources de « Podcast IA » en `OK`, aucune ligne « Problèmes dans le Sheet ».
- `podcast.py` : `[ia] Rien de nouveau.` (l'épisode de la semaine est déjà fait).

## 7. Nouvelle crontab

`crontab -e`, garder la ligne de la synchro Garmin et remplacer les lignes du podcast par :

```
15 8 * * *  ~/veille-env/bin/python ~/veille/veille.py collect >> ~/podcast-data/veille.log 2>&1
15 9 * * *  ~/veille-env/bin/python ~/veille/veille.py build-week >> ~/podcast-data/veille.log 2>&1
35 9-21 * * *  ~/veille-env/bin/python ~/veille/veille.py upload >> ~/podcast-data/veille.log 2>&1
45 10 * * 0  ~/veille-env/bin/pip install -q -U yt-dlp
30 10-22 * * *  flock -n /tmp/podcast.lock ~/piper-env/bin/python ~/veille/podcast.py >> ~/podcast-data/podcast.log 2>&1
```

Changements : la compilation tourne chaque jour mais ne traite que les émissions dont c'est le jour
dans le Sheet, et envoie elle-même le fichier sur le Drive (plus de `rclone` dans la crontab) ;
`podcast.py` tourne chaque jour, pour les émissions qui ne sont pas le dimanche.

## 8. Tâche planifiée Claude

Demander à Claude de passer la tâche « Podcast IA – script du dimanche » au skill
**podcast-ecriture**, tous les jours à 9 h 52. Les jours sans émission, elle s'arrête sans rien écrire.

## Retour en arrière

```bash
rm -rf ~/veille && mv ~/veille.bak ~/veille
cd ~/podcast-data && mv ia/* . && rmdir ia && cd ~
rclone config update podcast root_folder_id 1nmED0Eokrr8kyCm4YbacvyRl0PFtX0Ko
crontab ~/crontab.bak
```

Et remettre « Podcast IA » à la racine du Drive, puis la tâche planifiée sur le skill **podcast-debat-ia**.

## Après une semaine sans problème

```bash
rm -rf ~/veille.bak ~/crontab.bak ~/veille/sources.json
```
