# Coach Garmin – Raspberry Pi : mémo d'exploitation

Mis à jour le 17/10/2026.

## La chaîne automatique

| Heure | Étape | Où |
|---|---|---|
| nuit | La montre enregistre ; le téléphone envoie à Garmin Connect | montre / téléphone |
| 7 h 15 | Synchro Garmin + météo, exports, puis copie sur Google Drive | Raspberry Pi (cron) |
| 7 h 24 | « Point coach du matin » : verdict du jour envoyé sur le téléphone | tâche planifiée Claude |

Le Pi remplit le dossier Drive **« Coach - Garmin export »** avec `coach_snapshot.md`, `integrite.html`, `daily.csv`, `activities.csv` et `weather_daily.csv`. Le coach lit ce dossier, ton carnet (feuille « Coach – Carnet ») et la Synthèse Intégrale.

## Le Raspberry Pi

- Modèle : Raspberry Pi 3, Raspberry Pi OS Lite 64 bits (Debian Trixie), Python 3.13
- Nom réseau : `coachpi` ; adresse IP : `192.168.1.44` (elle peut changer, voir l'interface de la box)
- Utilisateur : `laurent` (le mot de passe est celui choisi dans Raspberry Pi Imager)
- Pas d'écran : l'accès se fait par SSH depuis le PC

## Se connecter

Depuis PowerShell sur le PC :

```
ssh laurent@coachpi
```

- Si le nom ne répond pas : `ssh laurent@192.168.1.44`
- Rien ne s'affiche quand tu tapes le mot de passe : c'est normal.
- « Connection refused » juste après un redémarrage : attends 1 minute.
- Tu es sur le Pi quand l'invite affiche `laurent@coachpi:~ $`.
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
15 7 * * * cd /home/laurent/garmin_coach && { .venv/bin/python coach.py sync; rclone copy export "gdrive:Coach - Garmin export" -v; } >> data/sync.log 2>&1
```

## Pannes possibles

**Jeton Garmin expiré** (le journal affiche « Jeton Garmin expiré », en général après plusieurs mois)
1. Sur le PC, dans `D:\Sauvegarde\Documents\Laurent\lolo_python\Sport` : `.venv\Scripts\python coach.py login`
2. Toujours dans PowerShell sur le PC : `scp -r $HOME\.garminconnect laurent@coachpi:~/`

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
scp laurent@coachpi:~/garmin_coach/data/coach.db D:\Sauvegarde\Documents\Laurent\lolo_python\Sport\data\coach_pi.db
```

## Tout réinstaller (carte SD morte, nouveau Pi)

1. **Raspberry Pi Imager** : Raspberry Pi OS Lite 64 bits, nom d'hôte `coachpi`, utilisateur `laurent`, Wi-Fi, SSH activé par mot de passe, fuseau Europe/Paris. Ne pas activer Raspberry Pi Connect.
2. Si besoin, effacer l'ancienne empreinte SSH sur le PC : `ssh-keygen -R coachpi`, puis se connecter.
3. Sur le Pi : `sudo apt update && sudo apt full-upgrade -y && sudo apt install -y cron rclone`
4. Sur le PC, dans le dossier Sport :
   ```
   tar -czf $HOME\coach.tgz --exclude=.venv --exclude=__pycache__ --exclude=.env .
   scp $HOME\coach.tgz laurent@coachpi:~/
   scp -r $HOME\.garminconnect laurent@coachpi:~/
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
