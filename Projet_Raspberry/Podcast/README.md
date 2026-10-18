# Podcast IA (Raspberry Pi + Claude)

Podcast hebdomadaire sur l'IA : débat de 20 min entre Camille (A) et Thomas (B), puis revue de sujets.

## Chaîne de production

1. **`veille.py`** (Pi) : collecte chaque nuit les sources (YouTube, RSS, newsletters), classées par camp.
   Le dimanche, il compile la semaine dans `~/podcast-data/weekly/AAAA-Wss_source.md`.
2. **rclone** envoie ce fichier dans `Drive > Podcast IA > sources` (remote `podcast:`).
3. **Skill Claude `podcast-debat-ia`** (tâche planifiée le dimanche à 9 h 52) : lit le fichier et écrit
   `AAAA-Wss_script.txt` dans `Drive > Podcast IA > scripts`.
4. **`podcast.py`** (Pi) récupère le script, génère les voix avec Piper (une voix à la fois),
   produit le MP3 et l'envoie dans `Drive > Podcast IA > episodes`.

## Fichiers

| Fichier | Où il tourne | Rôle |
|---|---|---|
| `veille.py` | Pi, `~/veille/` | collecte et compilation hebdo |
| `sources.json` | Pi, `~/veille/` | liste des sources, camps, mots-clés, réglages |
| `podcast.py` | Pi, `~/veille/` | synthèse vocale et MP3 |
| `SKILL_podcast-debat-ia.md` | Claude (skill) | consignes d'écriture du script |

## Environnements Python sur le Pi

- `~/veille-env` : `feedparser beautifulsoup4 yt-dlp` (+ `piper-tts` pour podcast.py)
- Voix Piper dans `~/piper-voices/` : `fr_FR-siwis-medium` (A) et `fr_FR-tom-medium` (B)
- La synchro Garmin garde son propre environnement (`~/garmin_coach/.venv`), sans interaction.

## Crontab du Pi (au moment de la sauvegarde)

```
15 7 * * *  synchro Garmin (inchangée)
15 8 * * *  ~/veille-env/bin/python ~/veille/veille.py collect    >> ~/podcast-data/veille.log 2>&1
15 9 * * 0  ~/veille-env/bin/python ~/veille/veille.py build-week >> ~/podcast-data/veille.log 2>&1
45 10 * * 0 ~/veille-env/bin/pip install -q -U yt-dlp
```

Vérifier la version réelle avec `crontab -l` sur le Pi (l'envoi rclone et `podcast.py` peuvent y avoir été ajoutés).

## Accès Drive (rclone)

- `gdrive:` : remote de la synchro Garmin, `scope = drive.file` (ne voit que ses propres fichiers).
- `podcast:` : remote dédié, `scope = drive`, racine = dossier « Podcast IA »
  (`root_folder_id = 1nmED0Eokrr8kyCm4YbacvyRl0PFtX0Ko`).
  Configuré via tunnel SSH : `ssh -L 53682:localhost:53682 utilisateur@coachpi`.

## Commandes utiles

```bash
~/veille-env/bin/python ~/veille/veille.py check        # teste chaque source
~/veille-env/bin/python ~/veille/podcast.py --test      # lit seulement l'ouverture du dernier script
~/veille-env/bin/python ~/veille/podcast.py             # produit les épisodes manquants
```

## Rapatrier les fichiers du Pi vers ce PC

```bash
scp utilisateur@coachpi:~/veille/{veille.py,sources.json,podcast.py} .
```
