#!/usr/bin/env python3
"""Génère les MP3 des podcasts à partir des scripts déposés sur le Drive.

Usage :
  podcast.py                      toutes les émissions actives : récupère les scripts et
                                  produit les épisodes manquants
  podcast.py --emission ia        une seule émission
  podcast.py --test               ne lit que l'ouverture du dernier script (pour tester les voix)
  podcast.py --file X --emission ia   produit l'épisode d'un script local précis

Émissions, voix et dossiers : Google Sheet « Configuration podcasts » (voir commun.py).
Voix : edge-tts (service en ligne de Microsoft) par défaut. Si edge-tts échoue, le passage
s'arrête et reprend au suivant ; après EDGE_MAX_PASSES passages ratés, tout l'épisode est
refait avec Piper en local, et une alerte le dit.

Économe en mémoire (Pi 3, 1 Go) : avec Piper, une seule voix chargée à la fois et
répliques découpées en morceaux courts. Fichiers de travail sur la carte SD. Si le
programme est interrompu, il reprend là où il s'était arrêté, avec le même moteur.
"""
import argparse
import gc
import re
import shutil
import time
import wave
from pathlib import Path

from commun import (HOME, alerte, load_emissions, load_json, log, publier_etat, rclone_copy,
                    run, save_json, select)

# ---------- réglages ----------
ENGINE = "edge"        # "edge" (edge-tts) ou "piper" (local)
EDGE_CHUNK_CHARS = 1500  # edge-tts lit les répliques entières : meilleure intonation
EDGE_RETRIES = 3
EDGE_MAX_PASSES = 3    # passages ratés d'edge-tts (un par heure) avant de basculer sur Piper
VOICE_DIR = HOME / "piper-voices"
VOICES = {"A": "fr_FR-siwis-medium",   # voix A de secours (Piper)
          "B": "fr_FR-tom-medium"}     # voix B de secours (Piper)
PAUSE_LINE = 0.35      # silence entre deux répliques (secondes)
PAUSE_SECTION = 1.2    # silence aux changements de section
PAUSE_CHUNK = 0.12     # silence entre deux morceaux d'une même réplique
CHUNK_CHARS = 220      # taille visée d'un morceau de texte lu d'un coup
MP3_BITRATE = "64k"    # largement suffisant pour de la voix

NAME_RE = re.compile(r"^(\d{4}-W\d{2})_script(?:_v(\d+))?\.txt$")


# ---------- choix et lecture des scripts ----------

def latest_versions(scripts_dir):
    """Pour chaque semaine, garde la version la plus récente (_v2 > original)."""
    best = {}
    for f in scripts_dir.glob("*.txt"):
        m = NAME_RE.match(f.name)
        if not m:
            continue
        week, version = m.group(1), int(m.group(2) or 1)
        if week not in best or version > best[week][0]:
            best[week] = (version, f)
    return {week: f for week, (_, f) in sorted(best.items())}


def parse_script(path, first_section_only=False):
    """Renvoie une liste de ('A'|'B', texte) et ('SECTION', nom). None si script incomplet.
    first_section_only : s'arrête au deuxième marqueur ## (ouverture seule, pour les tests)."""
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines or lines[-1] != "FIN":
        return None
    items = []
    for line in lines[:-1]:
        if line.startswith("## "):
            if first_section_only and any(k == "SECTION" for k, _ in items):
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
    # un morceau sans lettre ni chiffre (« … » seul) ne produit aucun son : edge-tts échoue dessus
    return [c for c in out if re.search(r"\w", c)]


# ---------- synthèse ----------

def piper_models():
    return {speaker: VOICE_DIR / f"{name}.onnx" for speaker, name in VOICES.items()}


def load_voice(speaker):
    from piper import PiperVoice
    model = piper_models()[speaker]
    if not model.exists():
        raise RuntimeError(f"voix Piper introuvable : {model}")
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


def synthesize_edge(items, workdir, voices):
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
            edge_to_wav(piece, voices[kind], workdir / f"{i:03d}_{j:02d}.wav")
        (workdir / f"{i:03d}.done").touch()
        if done % 10 == 0:
            log(f"  {done}/{total} répliques ({time.time() - t0:.0f} s)")
    log(f"  synthèse edge-tts terminée en {(time.time() - t0) / 60:.1f} min")


def synthesize_parts(items, workdir, voices):
    """Choisit le moteur. Un épisode commencé avec un moteur est fini avec le même,
    pour ne jamais mélanger deux jeux de voix.

    Si edge-tts échoue, le passage s'arrête (RuntimeError) en gardant les répliques déjà lues,
    et le suivant reprend. Piper ne prend le relais qu'après EDGE_MAX_PASSES passages ratés,
    et seulement si ses voix sont installées."""
    engine_file = workdir / "engine.txt"
    engine = engine_file.read_text().strip() if engine_file.exists() else ENGINE
    if engine == "edge":
        engine_file.write_text("edge")
        fails_file = workdir / "edge_echecs.txt"
        try:
            log(f"  moteur : edge-tts ({voices['A']} / {voices['B']})")
            synthesize_edge(items, workdir, voices)
            return
        except Exception as exc:
            fails = (int(fails_file.read_text()) if fails_file.exists() else 0) + 1
            reason = str(exc)[:200]
            missing = [str(m) for m in piper_models().values() if not m.exists()]
            if fails < EDGE_MAX_PASSES or missing:
                fails_file.write_text(str(fails))
                fallback = (f"voix Piper absentes ({', '.join(missing)}), pas de repli possible"
                            if missing and fails >= EDGE_MAX_PASSES
                            else f"passage raté {fails}/{EDGE_MAX_PASSES} avant repli sur Piper")
                raise RuntimeError(f"edge-tts indisponible ({reason}) ; {fallback}. "
                                   "Nouvel essai au prochain passage")
            alerte(f"edge-tts indisponible {fails} passages de suite ({reason}) : "
                   f"{workdir.name} entièrement refait avec Piper (voix moins bonne, plusieurs heures)")
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


def assemble(items, workdir, out_mp3, title, artist, album):
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
        if out:  # une réplique sans texte lisible n'a aucun morceau
            silence(PAUSE_LINE)
    if out is None:
        raise RuntimeError("aucune réplique à lire")
    out.close()
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(full),
         "-ac", "1", "-codec:a", "libmp3lame", "-b:a", MP3_BITRATE,
         "-metadata", f"title={title}", "-metadata", f"artist={artist}",
         "-metadata", f"album={album}", str(out_mp3)])
    full.unlink()


# ---------- programme principal ----------

def process(em, args):
    """Produit les épisodes manquants d'une émission."""
    data = Path(em["data_dir"])
    scripts, episodes, work = data / "scripts", data / "episodes", data / "work"
    state_file = episodes / "state.json"
    for d in (scripts, episodes, work):
        d.mkdir(parents=True, exist_ok=True)
    voices = {"A": em["voix_a"], "B": em["voix_b"]}

    if args.file:
        m = NAME_RE.match(args.file.name)
        todo = {m.group(1) if m else args.file.stem: args.file}
    else:
        try:
            rclone_copy(f"{em['remote']}/scripts", str(scripts))
        except FileNotFoundError:
            log(f"[{em['id']}] Pas encore de dossier scripts sur le Drive.")
            return
        except RuntimeError as exc:
            alerte(f"[{em['id']}] récupération des scripts échouée : {exc}. Nouvel essai au prochain passage")
            return
        todo = latest_versions(scripts)
        if args.test:
            todo = dict(list(todo.items())[-1:])

    state = {} if args.test or args.file else load_json(state_file, {})
    pending = {w: f for w, f in todo.items() if state.get(w) != f.name}
    if not pending:
        log(f"[{em['id']}] Rien de nouveau.")
        return

    for week, path in pending.items():
        items = parse_script(path, first_section_only=args.test)
        if items is None:
            log(f"[{em['id']}] {path.name} : pas de ligne FIN, script incomplet, ignoré pour l'instant.")
            continue
        suffix = "_test" if args.test else ""
        mp3 = episodes / f"{week}{suffix}.mp3"
        # dossier de travail propre à cette version du script : permet la reprise
        workdir = work / f"{path.stem}{suffix}"
        workdir.mkdir(parents=True, exist_ok=True)
        year, wk = (week.split("-W") + [""])[:2]
        title = f"{em['nom']} — semaine {wk} de {year}" if wk else f"{em['nom']} — {week}"
        artist = f"{em['prenom_a']} et {em['prenom_b']}"
        # trace du script dont est issu le MP3 : si seul l'envoi a échoué, on ne resynthétise pas
        made_from = mp3.with_suffix(".src")
        if (not args.test and mp3.exists() and made_from.exists()
                and made_from.read_text().strip() == path.name):
            log(f"[{em['id']}] {path.name} : {mp3.name} déjà produit, nouvel essai d'envoi seulement")
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            log(f"[{em['id']}] {path.name} : génération de {mp3.name}")
            try:
                synthesize_parts(items, workdir, voices)
                assemble(items, workdir, mp3, title, artist, em["nom"])
            except Exception as exc:
                # le dossier de travail est gardé : le prochain passage reprend là où on en est
                alerte(f"[{em['id']}] {path.name} : épisode non produit ({str(exc)[:300]})")
                continue
            shutil.rmtree(workdir)
            made_from.write_text(path.name)
            log(f"  MP3 prêt : {mp3.name}")
        if args.test or args.file:
            continue
        try:
            rclone_copy(str(mp3), f"{em['remote']}/episodes")
        except RuntimeError as exc:
            # le MP3 reste sur le Pi ; l'envoi sera retenté au prochain passage (sans resynthèse)
            alerte(f"[{em['id']}] envoi de {mp3.name} échoué : {exc}. MP3 conservé, nouvel essai au prochain passage")
            continue
        state[week] = path.name
        save_json(state_file, state)
        log(f"  envoyé sur le Drive : {em['dossier']}/episodes/{mp3.name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--emission", help="identifiant d'une émission (sinon : toutes les actives)")
    ap.add_argument("--test", action="store_true", help="lire seulement l'ouverture du dernier script")
    ap.add_argument("--file", type=Path, help="script local à lire (avec --emission)")
    args = ap.parse_args()
    if args.file and not args.emission:
        ap.error("--file demande --emission, pour savoir quelles voix utiliser")

    try:
        run_all(args)
    finally:
        if not (args.test or args.file):   # les essais à la main ne touchent pas à l'état publié
            publier_etat("podcast")


def run_all(args):
    try:
        emissions, warnings = load_emissions()
    except RuntimeError as exc:
        alerte(f"configuration illisible : {exc}")
        return
    for w in warnings:
        alerte(f"CONFIGURATION : {w}")
    todo = select(emissions, args.emission)
    if not todo:
        log("Aucune émission active dans le Sheet.")
    for em in todo:
        try:   # une émission en panne ne bloque pas les suivantes
            process(em, args)
        except Exception as exc:
            alerte(f"[{em['id']}] erreur inattendue : {type(exc).__name__} : {str(exc)[:300]}")


if __name__ == "__main__":
    main()
