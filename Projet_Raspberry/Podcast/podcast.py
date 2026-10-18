#!/usr/bin/env python3
"""Génère le MP3 du podcast à partir du script déposé sur le Drive.

Usage :
  podcast.py            récupère les scripts sur le Drive et produit les épisodes manquants
  podcast.py --test     ne lit que l'ouverture du dernier script (pour tester les voix)
  podcast.py --file X   produit l'épisode d'un script local précis

Voix : edge-tts (Vivienne et Rémy, service en ligne de Microsoft) par défaut.
Si edge-tts échoue, tout l'épisode est refait avec Piper en local, et le log le dit.

Économe en mémoire (Pi 3, 1 Go) : avec Piper, une seule voix chargée à la fois et
répliques découpées en morceaux courts. Fichiers de travail sur la carte SD. Si le
programme est interrompu, il reprend là où il s'était arrêté, avec le même moteur.
"""
import argparse
import datetime as dt
import gc
import json
import re
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

# ---------- réglages ----------
HOME = Path.home()
DATA = HOME / "podcast-data"
ENGINE = "edge"        # "edge" (edge-tts) ou "piper" (local)
EDGE_VOICES = {"A": "fr-FR-VivienneMultilingualNeural",   # Camille
               "B": "fr-FR-RemyMultilingualNeural"}       # Thomas
EDGE_CHUNK_CHARS = 1500  # edge-tts lit les répliques entières : meilleure intonation
EDGE_RETRIES = 3
VOICE_DIR = HOME / "piper-voices"
VOICES = {"A": "fr_FR-siwis-medium",   # Camille (secours Piper)
          "B": "fr_FR-tom-medium"}     # Thomas (secours Piper)
REMOTE_SCRIPTS = "podcast:scripts"
REMOTE_EPISODES = "podcast:episodes"
PAUSE_LINE = 0.35      # silence entre deux répliques (secondes)
PAUSE_SECTION = 1.2    # silence aux changements de section
PAUSE_CHUNK = 0.12     # silence entre deux morceaux d'une même réplique
CHUNK_CHARS = 220      # taille visée d'un morceau de texte lu d'un coup
MP3_BITRATE = "64k"    # largement suffisant pour de la voix

SCRIPTS = DATA / "scripts"
EPISODES = DATA / "episodes"
WORK = DATA / "work"
STATE = EPISODES / "state.json"
NAME_RE = re.compile(r"^(\d{4}-W\d{2})_script(?:_v(\d+))?\.txt$")


def log(msg):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M}] {msg}", file=sys.stderr, flush=True)


def run(cmd, timeout=None):
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"{cmd[0]} a échoué : {res.stderr.strip()[-300:]}")
    return res


RCLONE_TIMEOUT = 300   # durée maximale d'un transfert (secondes) avant abandon
RCLONE_TRIES = 3


def rclone_copy(src, dst):
    """rclone copy avec délai maximal et nouvelles tentatives.
    --contimeout / --timeout : rclone abandonne lui-même une connexion muette."""
    cmd = ["rclone", "copy", "--contimeout", "30s", "--timeout", "60s", src, dst]
    for attempt in range(1, RCLONE_TRIES + 1):
        try:
            return run(cmd, timeout=RCLONE_TIMEOUT)
        except (subprocess.TimeoutExpired, RuntimeError) as exc:
            reason = (f"bloqué plus de {RCLONE_TIMEOUT} s" if isinstance(exc, subprocess.TimeoutExpired)
                      else str(exc)[:200])
            if attempt == RCLONE_TRIES:
                raise RuntimeError(f"rclone {src} -> {dst} : échec après {RCLONE_TRIES} essais ({reason})")
            log(f"  rclone essai {attempt}/{RCLONE_TRIES} raté ({reason}), nouvel essai dans {30 * attempt} s")
            time.sleep(30 * attempt)


# ---------- choix et lecture des scripts ----------

def latest_versions():
    """Pour chaque semaine, garde la version la plus récente (_v2 > original)."""
    best = {}
    for f in SCRIPTS.glob("*.txt"):
        m = NAME_RE.match(f.name)
        if not m:
            continue
        week, version = m.group(1), int(m.group(2) or 1)
        if week not in best or version > best[week][0]:
            best[week] = (version, f)
    return {week: f for week, (_, f) in sorted(best.items())}


def parse_script(path, stop_at_debate=False):
    """Renvoie une liste de ('A'|'B', texte) et ('SECTION', nom). None si script incomplet."""
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines or lines[-1] != "FIN":
        return None
    items = []
    for line in lines[:-1]:
        if line.startswith("## "):
            if stop_at_debate and line[3:].strip() == "DEBAT":
                break
            items.append(("SECTION", line[3:].strip()))
        elif line[:2] in ("A:", "B:"):
            text = line[2:].strip()
            if text:
                items.append((line[0], text))
        else:
            log(f"ligne ignorée : {line[:60]}")
    return items


def chunks(text, limit=CHUNK_CHARS):
    """Découpe une réplique en morceaux de quelques phrases, pour limiter la mémoire."""
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    pieces = []
    for s in sentences:
        if len(s) <= limit * 1.3:
            pieces.append(s)
        else:  # phrase très longue : on coupe aux virgules et deux-points
            part = ""
            for frag in re.split(r"(?<=[,;:])\s+", s):
                if part and len(part) + len(frag) > limit:
                    pieces.append(part)
                    part = frag
                else:
                    part = f"{part} {frag}".strip()
            if part:
                pieces.append(part)
    out, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        out.append(cur)
    return out


# ---------- synthèse ----------

def load_voice(speaker):
    from piper import PiperVoice
    model = VOICE_DIR / f"{VOICES[speaker]}.onnx"
    if not model.exists():
        raise SystemExit(f"Voix introuvable : {model}")
    return PiperVoice.load(str(model))


def edge_to_wav(text, voice, wav_path):
    """Un morceau de texte -> WAV via edge-tts. Réessaie avant d'abandonner."""
    import asyncio
    import edge_tts
    mp3 = wav_path.with_suffix(".mp3")
    last = None
    for attempt in range(EDGE_RETRIES):
        try:
            asyncio.run(edge_tts.Communicate(text, voice).save(str(mp3)))
            if not mp3.exists() or mp3.stat().st_size == 0:
                raise RuntimeError("fichier audio vide")
            break
        except Exception as exc:
            last = exc
            time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"échec après {EDGE_RETRIES} essais : {last}")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
         "-ac", "1", "-ar", "24000", "-sample_fmt", "s16", str(wav_path)])
    mp3.unlink()


def synthesize_edge(items, workdir):
    total = sum(1 for k, _ in items if k != "SECTION")
    done = 0
    t0 = time.time()
    for i, (kind, text) in enumerate(items):
        if kind == "SECTION":
            continue
        done += 1
        if (workdir / f"{i:03d}.done").exists():
            continue
        for j, piece in enumerate(chunks(text, EDGE_CHUNK_CHARS)):
            edge_to_wav(piece, EDGE_VOICES[kind], workdir / f"{i:03d}_{j:02d}.wav")
        (workdir / f"{i:03d}.done").touch()
        if done % 10 == 0:
            log(f"  {done}/{total} répliques ({time.time() - t0:.0f} s)")
    log(f"  synthèse edge-tts terminée en {(time.time() - t0) / 60:.1f} min")


def synthesize_parts(items, workdir):
    """Choisit le moteur. Un épisode commencé avec un moteur est fini avec le même,
    pour ne jamais mélanger deux jeux de voix."""
    engine_file = workdir / "engine.txt"
    engine = engine_file.read_text().strip() if engine_file.exists() else ENGINE
    if engine == "edge":
        engine_file.write_text("edge")
        try:
            log("  moteur : edge-tts")
            synthesize_edge(items, workdir)
            return
        except Exception as exc:
            log(f"  edge-tts indisponible ({str(exc)[:200]}) : épisode entièrement refait avec Piper")
            for f in workdir.iterdir():
                if f.is_file():
                    f.unlink()
    engine_file.write_text("piper")
    log("  moteur : Piper")
    synthesize_piper(items, workdir)


def synthesize_piper(items, workdir):
    """Écrit un fichier WAV par morceau, voix par voix. Saute ce qui existe déjà."""
    total = sum(1 for k, _ in items if k != "SECTION")
    done = 0
    t0 = time.time()
    for speaker in VOICES:
        todo = [(i, t) for i, (k, t) in enumerate(items) if k == speaker]
        missing = [(i, t) for i, t in todo if not (workdir / f"{i:03d}.done").exists()]
        done += len(todo) - len(missing)
        if not missing:
            continue
        log(f"  voix {speaker} ({VOICES[speaker]}) : {len(missing)} répliques à lire")
        voice = load_voice(speaker)
        for i, text in missing:
            for j, piece in enumerate(chunks(text)):
                with wave.open(str(workdir / f"{i:03d}_{j:02d}.wav"), "wb") as wf:
                    voice.synthesize_wav(piece, wf)
            (workdir / f"{i:03d}.done").touch()
            done += 1
            if done % 10 == 0:
                log(f"  {done}/{total} répliques ({time.time() - t0:.0f} s)")
        del voice
        gc.collect()
    log(f"  synthèse terminée en {(time.time() - t0) / 60:.1f} min")


def assemble(items, workdir, out_mp3, title):
    full = workdir / "episode.wav"
    out, params = None, None

    def silence(seconds):
        out.writeframes(b"\x00" * int(params[2] * seconds) * params[1] * params[0])

    for i, (kind, _) in enumerate(items):
        if kind == "SECTION":
            if out:
                silence(PAUSE_SECTION)
            continue
        parts = sorted(workdir.glob(f"{i:03d}_*.wav"))
        for n, part in enumerate(parts):
            with wave.open(str(part), "rb") as w:
                p = (w.getnchannels(), w.getsampwidth(), w.getframerate())
            if params is None:
                params = p
                out = wave.open(str(full), "wb")
                out.setnchannels(p[0]); out.setsampwidth(p[1]); out.setframerate(p[2])
            if p != params:  # voix à une autre fréquence : on la convertit
                conv = workdir / "conv.wav"
                run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(part),
                     "-ac", str(params[0]), "-ar", str(params[2]), "-sample_fmt", "s16", str(conv)])
                part = conv
            with wave.open(str(part), "rb") as w:
                out.writeframes(w.readframes(w.getnframes()))
            if n < len(parts) - 1:
                silence(PAUSE_CHUNK)
        silence(PAUSE_LINE)
    if out is None:
        raise RuntimeError("aucune réplique à lire")
    out.close()
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(full),
         "-ac", "1", "-codec:a", "libmp3lame", "-b:a", MP3_BITRATE,
         "-metadata", f"title={title}", "-metadata", "artist=Camille et Thomas",
         "-metadata", "album=Podcast IA", str(out_mp3)])
    full.unlink()


# ---------- programme principal ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="lire seulement l'ouverture du dernier script")
    ap.add_argument("--file", type=Path, help="script local à lire")
    args = ap.parse_args()

    for d in (SCRIPTS, EPISODES, WORK):
        d.mkdir(parents=True, exist_ok=True)

    if args.file:
        m = NAME_RE.match(args.file.name)
        todo = {m.group(1) if m else args.file.stem: args.file}
    else:
        try:
            rclone_copy(REMOTE_SCRIPTS, str(SCRIPTS))
        except RuntimeError as exc:
            log(f"RÉCUPÉRATION DES SCRIPTS ÉCHOUÉE : {exc}. Nouvel essai au prochain passage.")
            return
        todo = latest_versions()
        if args.test:
            todo = dict(list(todo.items())[-1:])

    state = {} if args.test or args.file else json.loads(STATE.read_text()) if STATE.exists() else {}
    pending = {w: f for w, f in todo.items() if state.get(w) != f.name}
    if not pending:
        log("Rien de nouveau.")
        return

    for week, path in pending.items():
        items = parse_script(path, stop_at_debate=args.test)
        if items is None:
            log(f"{path.name} : pas de ligne FIN, script incomplet, ignoré pour l'instant.")
            continue
        suffix = "_test" if args.test else ""
        mp3 = EPISODES / f"{week}{suffix}.mp3"
        # dossier de travail propre à cette version du script : permet la reprise
        workdir = WORK / f"{path.stem}{suffix}"
        workdir.mkdir(parents=True, exist_ok=True)
        year, wk = (week.split("-W") + [""])[:2]
        title = f"Podcast IA — semaine {wk} de {year}" if wk else week
        # trace du script dont est issu le MP3 : si seul l'envoi a échoué, on ne resynthétise pas
        made_from = mp3.with_suffix(".src")
        if (not args.test and mp3.exists() and made_from.exists()
                and made_from.read_text().strip() == path.name):
            log(f"{path.name} : {mp3.name} déjà produit, nouvel essai d'envoi seulement")
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            log(f"{path.name} : génération de {mp3.name}")
            synthesize_parts(items, workdir)
            assemble(items, workdir, mp3, title)
            shutil.rmtree(workdir)
            made_from.write_text(path.name)
            log(f"  MP3 prêt : {mp3.name}")
        if args.test or args.file:
            continue
        try:
            rclone_copy(str(mp3), REMOTE_EPISODES)
        except RuntimeError as exc:
            # le MP3 reste sur le Pi ; l'envoi sera retenté au prochain passage (sans resynthèse)
            log(f"  ENVOI ÉCHOUÉ : {exc}. MP3 conservé : {mp3}")
            continue
        state[week] = path.name
        STATE.write_text(json.dumps(state, indent=1))
        log(f"  envoyé sur le Drive : {REMOTE_EPISODES}/{mp3.name}")


if __name__ == "__main__":
    main()
