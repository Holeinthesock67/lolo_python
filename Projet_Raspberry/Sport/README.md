# Coach : import Garmin + météo

Chaque matin, le script récupère tes données Garmin (VFC, FC repos, sommeil, Body Battery, readiness, VO2max, poids, activités) et la météo (heure par heure + prévisions 4 jours), les range dans une base SQLite (`data/coach.db`) et écrit dans `export/` :

- `coach_snapshot.md` : l'instantané lisible par le coach (VFC 7 j vs corridor 28 j, sommeil, charge, météo des sorties, météo à venir)
- `daily.csv`, `activities.csv`, `weather_daily.csv`

Prérequis : **Python 3.11 ou plus** (`tomllib`).

## 1. Installation sur ton PC Windows (test + première connexion)

```powershell
cd garmin_coach
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # puis édite .env (email + mot de passe Garmin)
```
1. Édite `config.toml` : coordonnées de ta ville (section `[location]`).
2. `python test_offline.py` : doit finir par « TOUS LES TESTS OK ».
3. `python coach.py login` : première connexion (saisis le code MFA si demandé). Le jeton est enregistré dans `C:\Users\<toi>\.garminconnect`.
4. `python coach.py sync` : premier import (≈ 90 jours, quelques minutes). Ouvre `export\coach_snapshot.md`.

Si tu veux plus d'historique : `python coach.py sync --days 365`.

## 2. Déploiement sur le Raspberry Pi 3 (tourne tout seul)

Raspberry Pi OS **Bookworm** (Python 3.11). Depuis ton PC :
```bash
scp -r garmin_coach pi@raspberrypi.local:~/
scp -r ~/.garminconnect pi@raspberrypi.local:~/      # jeton (Windows : C:\Users\<toi>\.garminconnect)
```
Sur le Pi :
```bash
cd ~/garmin_coach
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python coach.py sync
crontab -e
```
Ligne à ajouter (tous les jours à 7h15, après la VFC nocturne) :
```
15 7 * * * cd ~/garmin_coach && .venv/bin/python coach.py sync >> data/sync.log 2>&1
```
Le Pi éteint ou hors ligne ne perd rien : le lancement suivant rattrape les jours manqués. Le fichier `.env` n'est plus nécessaire sur le Pi tant que le jeton est valide (il dure en général plusieurs mois ; sinon relance `login` sur le PC et recopie le dossier `.garminconnect`).

## 3. Donner les données au coach

- **Simple** : dépose `export/coach_snapshot.md` dans le projet « Coach Sportif » (ou colle son contenu dans la conversation).
- **Automatique** : sur le Pi, synchronise `export/` vers Google Drive avec [rclone](https://rclone.org/drive/) en ajoutant à la tâche : `&& rclone copy export gdrive:Coach`. Le coach lit alors le dossier via le connecteur Drive.

## Notes

- Bibliothèque **non officielle** (`garminconnect`) : Garmin peut changer son service. Les réponses brutes sont conservées dans `raw_garmin`, donc en cas de changement on corrige le parseur sans perdre l'historique.
- Erreur 429 : Garmin demande de ralentir, réessaie quelques heures plus tard.
- Données de santé : tout reste sur tes machines (base locale, `.env` et jeton jamais partagés). `.gitignore` les exclut si tu versionnes le code.
- Météo : [Open-Meteo](https://open-meteo.com) (gratuit, non commercial, sans clé).
