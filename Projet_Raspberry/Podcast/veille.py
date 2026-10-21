#!/usr/bin/env python3
"""Veille pour les podcasts personnalisés.

Les émissions et leurs sources sont décrites dans le Google Sheet « Configuration podcasts »
(voir commun.py). Sans --emission, chaque commande traite toutes les émissions actives.

Commandes :
  check       teste chaque source et affiche le dernier élément trouvé
  collect     collecte quotidienne des nouveautés (à lancer chaque jour)
  build-week  compile les 7 derniers jours et l'envoie sur le Drive, pour les
              émissions dont c'est le jour (ou celle donnée par --emission)
  upload      renvoie sur le Drive les compilations récentes dont l'envoi a échoué
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import feedparser
from bs4 import BeautifulSoup

from commun import (alerte, load_emissions, load_json, log, publier_etat, rclone_copy, save_json,
                    select, today_name)

UA = "Mozilla/5.0 (X11; Linux aarch64) veille-podcast/1.0"
NOW = dt.datetime.now(dt.timezone.utc)


# ---------- utilitaires ----------

def data_dir(cfg):
    d = Path(cfg["data_dir"]).expanduser()
    (d / "daily").mkdir(parents=True, exist_ok=True)
    (d / "weekly").mkdir(parents=True, exist_ok=True)
    return d


def html_to_text(raw):
    soup = BeautifulSoup(raw or "", "html.parser")
    for tag in soup(["script", "style", "figure", "img", "iframe"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def truncate(text, limit):
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " […tronqué]"


def compile_keywords(keywords):
    """'mot*' = préfixe, sinon mot entier. Insensible à la casse."""
    parts = []
    for k in keywords:
        if k.endswith("*"):
            parts.append(r"(?<!\w)" + re.escape(k[:-1]))
        else:
            parts.append(r"(?<!\w)" + re.escape(k) + r"(?!\w)")
    return re.compile("|".join(parts), re.IGNORECASE)


def entry_date(entry):
    if entry.get("_date"):  # vidéo YouTube datée par yt_video_date
        return entry["_date"]
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    return dt.datetime(*t[:6], tzinfo=dt.timezone.utc) if t else None


def item_id(src, entry):
    key = entry.get("id") or entry.get("link") or entry.get("title", "")
    return hashlib.sha1(f"{src['name']}|{key}".encode()).hexdigest()[:16]


# ---------- YouTube ----------

def run_ytdlp(args, timeout=300):
    return subprocess.run([sys.executable, "-m", "yt_dlp", *args],
                          capture_output=True, text=True, timeout=timeout)


def yt_channel_id(handle, cache):
    if handle in cache:
        return cache[handle]
    res = run_ytdlp(["--print", "channel_id", "--playlist-items", "1",
                     f"https://www.youtube.com/@{handle}/videos"], timeout=120)
    lines = res.stdout.strip().splitlines()
    if res.returncode != 0 or not lines:
        raise RuntimeError(f"chaîne @{handle} introuvable ({res.stderr.strip()[-150:]})")
    cache[handle] = lines[0]
    return lines[0]


def vtt_to_text(vtt):
    out, prev = [], None
    for line in vtt.splitlines():
        line = line.strip()
        if (not line or "-->" in line or line.isdigit()
                or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE"))):
            continue
        line = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
        if line and line != prev:  # les sous-titres auto répètent les lignes
            out.append(line)
            prev = line
    return " ".join(out)


def yt_transcript(url, lang):
    with tempfile.TemporaryDirectory() as tmp:
        run_ytdlp(["--skip-download", "--write-subs", "--write-auto-subs",
                   "--sub-langs", lang, "--sub-format", "vtt",
                   "-o", f"{tmp}/%(id)s.%(ext)s", url])
        files = sorted(Path(tmp).glob("*.vtt"))
        if not files:
            return None
        return vtt_to_text(files[0].read_text(encoding="utf-8", errors="ignore"))


def yt_list_videos(src, cache):
    """Dernières vidéos d'une chaîne, via yt-dlp (le flux RSS de YouTube renvoie 404).

    Les entrées imitent celles de feedparser (id « yt:video:… », link, title) pour que
    les vidéos déjà vues avec l'ancien flux RSS soient reconnues. La date est ajoutée
    plus tard par yt_video_date, seulement pour les vidéos nouvelles."""
    cid = src.get("channel_id") or cache.get(src.get("handle"))
    if src.get("playlist_id"):
        url = f"https://www.youtube.com/playlist?list={src['playlist_id']}"
    elif cid:
        url = f"https://www.youtube.com/channel/{cid}/videos"
    else:
        url = f"https://www.youtube.com/@{src['handle']}/videos"
    # youtube:lang : titres dans la langue de la source, pas traduits automatiquement
    res = run_ytdlp(["--flat-playlist", "--playlist-items", f"1:{src.get('max_items', 5)}",
                     "--extractor-args", f"youtube:lang={src.get('lang', 'fr')}",
                     "--print", "%(id)s\t%(title)s", url], timeout=180)
    entries = []
    for line in res.stdout.splitlines():
        vid, _, title = line.partition("\t")
        if vid.strip():
            entries.append({"id": f"yt:video:{vid.strip()}",
                            "link": f"https://www.youtube.com/watch?v={vid.strip()}",
                            "title": title.strip() or "(sans titre)"})
    if not entries:
        raise RuntimeError(f"aucune vidéo trouvée ({res.stderr.strip()[-150:]})")
    return entries


def yt_video_date(entry):
    """Date de publication d'une vidéo (un appel yt-dlp). None si introuvable."""
    res = run_ytdlp(["--skip-download", "--print", "%(timestamp)s %(upload_date)s",
                     entry["link"]], timeout=120)
    parts = (res.stdout.strip().splitlines() or [""])[-1].split()
    if parts and parts[0].isdigit():
        date = dt.datetime.fromtimestamp(int(parts[0]), tz=dt.timezone.utc)
    elif len(parts) > 1 and parts[1].isdigit():
        date = dt.datetime.strptime(parts[1], "%Y%m%d").replace(tzinfo=dt.timezone.utc)
    else:
        return None
    entry["_date"] = date
    return date


# ---------- collecte ----------

class YouTubeFeed:
    def __init__(self, entries):
        self.entries = entries


def fetch_feed(src, cache):
    if src["type"] == "youtube":
        return YouTubeFeed(yt_list_videos(src, cache))
    url = src["url"]
    feed = feedparser.parse(url, agent=UA)
    if not feed.entries:
        reason = feed.get("bozo_exception") or f"HTTP {feed.get('status', '?')}"
        raise RuntimeError(f"flux vide ou illisible ({reason})")
    return feed


def entry_body(src, entry):
    if src["type"] == "youtube":
        return yt_transcript(entry.get("link", ""), src.get("lang", "fr"))
    if entry.get("content"):
        return html_to_text(entry["content"][0].get("value", ""))
    return html_to_text(entry.get("summary", ""))


def cmd_check(cfg):
    d = data_dir(cfg)
    cache = load_json(d / "yt_channels.json", {})
    ok = 0
    for src in cfg["sources"]:
        if not src.get("enabled", True):
            print(f"—       {src['name']} — désactivée dans le Sheet, non testée")
            continue
        try:
            feed = fetch_feed(src, cache)
            last = feed.entries[0]
            date = entry_date(last)
            if date is None and src["type"] == "youtube":
                date = yt_video_date(last)
            print(f"OK      {src['name']} — {len(feed.entries)} éléments, dernier : "
                  f"{last.get('title', '?')[:60]} ({date:%Y-%m-%d})" if date else
                  f"OK      {src['name']} — {len(feed.entries)} éléments")
            ok += 1
        except Exception as exc:
            print(f"ERREUR  {src['name']} — {exc}")
    save_json(d / "yt_channels.json", cache)
    print(f"\n{ok}/{len(cfg['sources'])} sources fonctionnelles.")


def cmd_collect(cfg):
    d = data_dir(cfg)
    seen = load_json(d / "seen.json", {})
    cache = load_json(d / "yt_channels.json", {})
    kw = compile_keywords(cfg["keywords"])
    cutoff = NOW - dt.timedelta(days=cfg["max_age_days"])
    new_items, errors = [], []

    for src in cfg["sources"]:
        if not src.get("enabled", True):
            continue
        try:
            feed = fetch_feed(src, cache)
        except Exception as exc:
            errors.append(f"{src['name']} : {exc}")
            continue

        for entry in feed.entries[:src.get("max_items", 5)]:
            iid = item_id(src, entry)
            if iid in seen:
                continue
            date = entry_date(entry)
            if date is None and src["type"] == "youtube":
                try:
                    date = yt_video_date(entry)
                except Exception as exc:
                    errors.append(f"{src['name']} / date de {entry.get('title', '?')[:40]} : {exc}")
            if date and date < cutoff:
                seen[iid] = NOW.isoformat()
                continue
            title = entry.get("title", "(sans titre)")
            try:
                body = entry_body(src, entry)
            except Exception as exc:
                errors.append(f"{src['name']} / {title[:40]} : {exc}")
                continue
            if body is None:
                # sous-titres YouTube pas encore prêts, ou date inconnue : on réessaiera demain
                if date is None or NOW - date < dt.timedelta(days=2):
                    continue
                body = html_to_text(entry.get("summary", ""))
            if not body.strip():
                # pas de texte du tout (vidéo sans sous-titres, article vide) : rien à en dire
                log(f"  {src['name']} / {title[:40]} : aucun texte, ignoré")
                seen[iid] = NOW.isoformat()
                continue
            if src.get("filter") and not kw.search(f"{title}\n{body}"):
                seen[iid] = NOW.isoformat()
                continue
            new_items.append({
                "source": src["name"], "camp": src["camp"], "lang": src.get("lang", "?"),
                "title": title, "link": entry.get("link", ""),
                "date": date.isoformat() if date else None,
                "text": truncate(body, cfg["max_chars_per_item"]),
            })
            seen[iid] = NOW.isoformat()

    # on oublie les identifiants de plus de 90 jours
    limit = (NOW - dt.timedelta(days=90)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= limit}

    out = d / "daily" / f"{dt.date.today()}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        for item in new_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    save_json(d / "seen.json", seen)
    save_json(d / "yt_channels.json", cache)

    log(f"{len(new_items)} nouveaux éléments -> {out.name}")
    for err in errors:
        alerte(f"[{cfg['id']}] {err}")


def cmd_build_week(cfg, days):
    d = data_dir(cfg)
    today = dt.date.today()
    items = []
    for i in range(days - 1, -1, -1):
        f = d / "daily" / f"{today - dt.timedelta(days=i)}.jsonl"
        if not f.exists():
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:   # ligne abîmée (coupure pendant l'écriture) : on saute
                alerte(f"[{cfg['id']}] {f.name}, ligne {n} illisible, ignorée")
    if not items:
        log("Aucun élément cette semaine, rien à compiler.")
        return

    # budget par élément pour rester sous la taille totale
    budget = min(cfg["max_chars_per_item"], cfg["max_total_chars"] // len(items))
    year, week, _ = today.isocalendar()
    start = today - dt.timedelta(days=days - 1)

    lines = [f"# Veille {cfg.get('nom', '')} — semaine {year}-S{week:02d}",
             f"Période : du {start} au {today} — {len(items)} éléments.", "",
             "## Sources et positions", ""]
    for src in cfg["sources"]:
        n = sum(1 for it in items if it["source"] == src["name"])
        lines.append(f"- **{src['name']}** — camp : {src['camp']} — {src['these']} ({n} éléments)")
    lines += ["", "## Contenus", ""]
    for it in sorted(items, key=lambda x: (x["camp"], x["source"], x["date"] or "")):
        lines += [f"### [{it['camp']}] {it['source']} — {it['title']}",
                  f"Date : {(it['date'] or '?')[:10]} | Langue : {it['lang']} | Lien : {it['link']}",
                  "", truncate(it["text"], budget), "", "---", ""]

    out = d / "weekly" / f"{year}-W{week:02d}_source.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log(f"Compilation : {len(items)} éléments, {out.stat().st_size // 1024} Ko -> {out.name}")
    return out


def cmd_upload(cfg, max_age_days=8):
    """Envoie les compilations récentes pas encore envoyées, ou refaites depuis le dernier envoi.
    Un envoi raté à 9 h 15 est ainsi retenté aux passages suivants de « upload »."""
    d = data_dir(cfg)
    sent_file = d / "weekly" / "envoyes.json"
    sent = load_json(sent_file, {})
    oldest = NOW.timestamp() - max_age_days * 86400
    for f in sorted((d / "weekly").glob("*_source.md")):
        mtime = f.stat().st_mtime
        if mtime < oldest or sent.get(f.name) == mtime:
            continue
        try:
            rclone_copy(str(f), f"{cfg['remote']}/sources")
        except RuntimeError as exc:
            alerte(f"[{cfg['id']}] envoi de {f.name} échoué : {exc}. Nouvel essai au prochain « veille.py upload »")
            continue
        sent[f.name] = mtime
        save_json(sent_file, sent)
        log(f"  envoyé sur le Drive : {cfg['dossier']}/sources/{f.name}")


def run_command(cfg, args):
    if args.command == "check":
        print(f"\n=== {cfg['nom']} ({cfg['id']}) — {len(cfg['sources'])} sources")
        cmd_check(cfg)
    elif args.command == "collect":
        log(f"[{cfg['id']}] collecte")
        cmd_collect(cfg)
    elif args.command == "upload":
        cmd_upload(cfg)
    else:
        if not args.emission and cfg["jour"] != today_name():
            return
        log(f"[{cfg['id']}] compilation de la semaine")
        if cmd_build_week(cfg, args.days) and not args.no_upload:
            cmd_upload(cfg)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["check", "collect", "build-week", "upload"])
    p.add_argument("--emission", help="identifiant d'une émission (sinon : toutes les actives)")
    p.add_argument("--days", type=int, default=7, help="nombre de jours pour build-week")
    p.add_argument("--no-upload", action="store_true", help="build-week sans envoi sur le Drive")
    args = p.parse_args()
    try:
        run_all(args)
    finally:
        if args.command != "check":   # check se lance à la main et affiche ses résultats
            publier_etat(f"veille {args.command}")


def run_all(args):
    try:
        emissions, warnings = load_emissions()
    except RuntimeError as exc:
        alerte(f"configuration illisible : {exc}")
        return
    if args.command != "check":
        for w in warnings:
            alerte(f"CONFIGURATION : {w}")
    todo = select(emissions, args.emission)
    if not todo:
        log("Aucune émission active dans le Sheet.")
        return

    for cfg in todo:
        try:   # une émission en panne ne bloque pas les suivantes
            run_command(cfg, args)
        except Exception as exc:
            alerte(f"[{cfg['id']}] erreur inattendue : {type(exc).__name__} : {str(exc)[:300]}")
    if args.command == "check" and warnings:
        print("\nProblèmes dans le Sheet :")
        for w in warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
