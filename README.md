# lolo_python

Mes programmes Python personnels.

| Dossier | Contenu |
|---|---|
| `Projet_Raspberry/Sport/` | Coach hybride : synchro Garmin + météo, base locale, rapports (tourne sur la Raspberry) |
| `Projet_Raspberry/Podcast/` | Veille IA et génération du podcast hebdo |
| `Jeux/` | Arena of Life, Battle Royale 3.0 (IA d'agents, PyTorch) |
| `Jeux/Cours_camarade/` | « Cours, camarade » : runner façon Subway Surfers pour navigateur (ouvrir `index.html`) |
| `Photos/` | Pré-tri de photos par date / GPS |
| `hasch/` | Vérification d'empreintes de fichiers |
| `QR/` | Générateurs de QR codes (SVG, STL, Wi-Fi) |
| `curve_digitilizer/` | Numérisation de courbes à partir d'images |

Restent en local uniquement (voir `.gitignore`) : `Export/`, `Extract_youtube/`,
`lolo_python_old/`, `Map/`, `Scripts_windows/`.

## Règles du dépôt

- **Secrets** : jamais dans Git. Chaque projet lit ses identifiants dans un `.env` local
  (voir `Projet_Raspberry/Sport/.env.example`), à recréer à la main sur chaque PC.
- **Environnements** : un `.venv` par projet, non versionné. Les dépendances vont dans
  `requirements.txt`.
- **Données générées** (bases, exports, logs, modèles `.pth`) : non versionnées,
  sauvegardées par le disque externe.

## Flux de travail

```bash
git pull          # en commençant, sur n'importe quel PC
git add -A
git commit -m "..."
git push          # en terminant
```
