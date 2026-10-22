# Podcasts personnalisés (Raspberry Pi + Claude)

Des podcasts audio produits automatiquement à partir d'une veille de sources (YouTube, flux RSS).
Chaque émission a son thème, ses sources et son format (débat ou revue). Premier podcast : « Podcast IA »,
un débat de 30 minutes chaque dimanche entre Camille (A) et Thomas (B).

## Configuration : le Google Sheet « Configuration podcasts »

Dans le dossier **Podcasts** du Drive. Rien n'est à modifier sur le Pi pour ajouter une émission ou une source.

- Onglet **Émissions** : une ligne par podcast (format, jour, durée, voix, prénoms, mots-clés, consignes).
- Un onglet de sources par émission (ex. **Sources IA**) : une ligne par source (type, chaîne ou URL,
  langue, camp, thèse, filtre, active).
- Onglet **Mode d'emploi** : le sens de chaque colonne.

Le Pi télécharge le Sheet en .xlsx avant chaque passage et garde la dernière copie en secours.
Claude le lit avec le connecteur Google Sheets.

## Chaîne de production

1. **Chaque jour à 8 h 15, `veille.py collect`** (Pi) : nouveautés de chaque source des émissions actives,
   dans `~/podcast-data/<émission>/daily/`.
2. **Chaque jour à 9 h 15, `veille.py build-week`** (Pi) : pour les émissions dont c'est le jour, compile les
   7 derniers jours en `AAAA-Wss_source.md` et l'envoie dans `Podcasts/<dossier>/sources`.
   **Toutes les heures de 9 h 35 à 21 h 35, `veille.py upload`** (Pi) : renvoie une compilation dont l'envoi
   a échoué. Ne fait rien si tout est déjà parti.
3. **Chaque jour à 9 h 52, tâche planifiée Claude + skill `podcast-ecriture`** : pour les émissions du jour,
   écrit `AAAA-Wss_script.txt` dans `Podcasts/<dossier>/scripts`, selon le format (débat ou revue).
   Signale aussi les problèmes du Pi (voir « Alertes »).
4. **Toutes les heures de 10 h 30 à 22 h 30, `podcast.py`** (Pi) : récupère les nouveaux scripts, génère les
   voix (edge-tts, Piper en secours), produit le MP3 et l'envoie dans `Podcasts/Episodes`, dossier commun
   à toutes les émissions, sous le nom `AAAA-Wss <Nom de l'émission>.mp3`.
   Si edge-tts échoue, le passage s'arrête et reprend à l'heure suivante ; Piper ne prend le relais
   qu'après 3 passages ratés, et seulement si ses voix sont installées.

## Alertes

À la fin de chaque passage, le Pi met à jour `Podcasts/etat_du_pi.md` sur le Drive : pour chaque programme,
l'heure du dernier passage et ses alertes (source en panne, Sheet injoignable, envoi raté, épisode non
produit, repli sur Piper…). Les alertes d'un passage remplacent celles du passage précédent du même
programme. Le skill `podcast-ecriture` lit ce fichier chaque matin et termine sa réponse par une ligne
« Pi : … » s'il y a un problème, ou si un programme n'a pas tourné depuis plus de 26 heures.
Copie locale : `~/podcast-data/etat_du_pi.md`. Les essais à la main (`check`, `podcast.py --test`,
`--file`) ne modifient pas l'état publié.

Une émission en panne ne bloque pas les autres : l'erreur devient une alerte et le programme continue.

## Fichiers

| Fichier | Où il tourne | Rôle |
|---|---|---|
| `commun.py` | Pi, `~/veille/` | journal, rclone avec délai et 3 essais, lecture du Sheet |
| `veille.py` | Pi, `~/veille/` | collecte, compilation hebdo, envoi des sources |
| `podcast.py` | Pi, `~/veille/` | synthèse vocale et MP3, par émission |
| `SKILL_podcast-ecriture.md` | Claude (skill) | consignes d'écriture, formats débat et revue |
| `BASCULE.md` | — | procédure de passage de l'ancien système (sources.json) au Sheet |

## Environnements Python sur le Pi

- `~/veille-env` : `feedparser beautifulsoup4 yt-dlp openpyxl` (veille.py)
- `~/piper-env` : `piper-tts edge-tts openpyxl` (podcast.py)
- Voix Piper de secours dans `~/piper-voices/` : `fr_FR-siwis-medium` (A) et `fr_FR-tom-medium` (B)
- La synchro Garmin garde son propre environnement (`~/garmin_coach/.venv`).

## Données sur le Pi

`~/podcast-data/<identifiant de l'émission>/` : `daily/`, `weekly/` (avec `envoyes.json`), `seen.json`, `scripts/`, `episodes/`
(avec `state.json`), `work/` (fichiers temporaires de synthèse). Journaux : `~/podcast-data/veille.log`
et `~/podcast-data/podcast.log`.

## Accès Drive (rclone)

- `podcast:` : remote dédié, `scope = drive`, racine = dossier **Podcasts**
  (`root_folder_id = 1K2xwn7U5MN-irF0ZSy3o6cTHKBkRhIOi`).
- `gdrive:` : remote de la synchro Garmin, `scope = drive.file`, sans rapport avec les podcasts.

## Commandes utiles

```bash
~/veille-env/bin/python ~/veille/veille.py check                   # teste toutes les sources et le Sheet
~/veille-env/bin/python ~/veille/veille.py check --emission ia     # une seule émission
~/veille-env/bin/python ~/veille/veille.py build-week --emission ia   # compile et envoie, quel que soit le jour
~/veille-env/bin/python ~/veille/veille.py upload                  # renvoie les compilations pas encore envoyées
cat ~/podcast-data/etat_du_pi.md                                   # alertes du dernier passage de chaque programme
~/piper-env/bin/python ~/veille/podcast.py --test                  # ouverture du dernier script seulement
~/piper-env/bin/python ~/veille/podcast.py --emission ia           # produit les épisodes manquants
tail -f ~/podcast-data/podcast.log                                 # suivre la génération
```

## Ajouter une émission

1. Une ligne dans l'onglet **Émissions** (identifiant court, sans espace ni accent).
2. Un onglet de sources, avec les mêmes colonnes que **Sources IA**, dont le nom va dans « Onglet des sources ».
3. Sur le Pi : `veille.py check --emission <identifiant>`.

Le dossier de l'émission dans **Podcasts** et ses sous-dossiers sont créés automatiquement à la première
compilation (sources), puis à la première écriture du script (scripts). Les MP3 vont dans le dossier
commun `Podcasts/Episodes`.
