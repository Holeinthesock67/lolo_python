"""Guidage des essais sur le PC et sur le vélo : consignes à l'écran, bips, chronométrage, journal.

Les outils de test (lots X4, X5, X8, X16) disent au cycliste ce qu'il doit faire, quand, et pendant
combien de temps, sans qu'il ait à lire un terminal en pédalant :
- un écran plein terminal, lisible de loin : consigne en cours, gros compte à rebours, étape k/n,
  valeurs en direct (puissance, cadence…) et derniers relevés ;
- des bips : début d'étape, 3, 2, 1 avant la fin, fin d'étape, alerte, réussite, échec ;
- un journal `guide.jsonl` (une ligne par étape, relevé, alerte, avec l'heure) dans le dossier de l'essai ;
- la liste du matériel à préparer et la durée de chaque essai, à lire à l'avance :

    python -m openride_core.tools.guide materiel            # tous les essais
    python -m openride_core.tools.guide materiel click_recette
    python -m openride_core.tools.guide bips                # écouter les bips

Bibliothèque standard seulement (le script `scripts/recette_pc.py` l'importe sans le venv). Le son passe
par pw-play, paplay ou aplay ; sinon la cloche du terminal. `OPENRIDE_GUIDE_MUET=1` coupe le son.
Hors terminal (tests, redirection), l'écran devient de simples lignes et aucun son n'est joué.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import textwrap
import time
import wave
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO


@dataclass(frozen=True)
class Trial:
    title: str
    duration: str
    commands: tuple[str, ...]
    materials: tuple[str, ...]
    notes: tuple[str, ...] = ()


TRIALS: dict[str, Trial] = {
    "trainer_steps": Trial(
        "Banc de latence du trainer (lot X5, essai R0)", "environ 15 min, échauffement compris",
        ("python -m openride_core.tools.trainer_steps --mode sim",
         "python -m openride_core.tools.trainer_steps --mode erg --cadence 85"),
        ("vélo installé sur le HomeTrainer, trainer branché",
         "Bluetooth du PC allumé, aucune autre application reliée au trainer (Zwift, téléphone)",
         "un braquet moyen choisi d'avance et gardé pendant tout l'essai",
         "bidon et serviette : 5 min d'échauffement avant de lancer"),
        ("SIM : 7 paliers de pente, environ 4 min ; ERG : 5 paliers de puissance, environ 3 min",
         "tout est chronométré par l'outil : rien à relever à la main")),
    "click_recette": Trial(
        "Recette du Zwift Click (lot X8)", "environ 35 min",
        ("python -m openride_core.tools.click_recette",),
        ("les deux boîtiers Click, piles chargées (une pile CR2032 de secours)",
         "le jeu fermé : l'outil tient seul le Click",
         "vélo sur le HomeTrainer conseillé : on roule pendant la surveillance"),
        ("6 appuis guidés, puis 30 min de surveillance avec un appui demandé toutes les 5 min",
         "délais, silences et coupures de chaque boîtier sont mesurés par l'outil")),
    "fc_recette": Trial(
        "Recette de la fréquence cardiaque (lot X9)", "environ 5 min",
        ("python -m openride_core.tools.fc_recette",),
        ("vélo sur le HomeTrainer, trainer branché, aucune autre application reliée au trainer",
         "la ceinture cardio portée, électrodes mouillées",
         "un peu d'eau pour remouiller la ceinture à la remise"),
        ("4 phases d'une minute : ceinture portée, retirée, remise, portée ; on roule tout du long",
         "absence, valeur figée et retour de la FC sont mesurés par l'outil")),
    "endurance": Trial(
        "Endurance d'une heure (lot X16)", "1 h 05",
        ("engine/tests/sim_bench.py --native --scenario endurance --probe",),
        ("rien sur le vélo : trainer simulé",
         "le PC libre pendant une heure, mise en veille de l'écran coupée",
         "la carte graphique GTX 1060 utilisée (pas l'affichage logiciel)"),
        ("un bip au départ et à la fin ; rien à faire pendant l'essai",)),
    "recette_pc": Trial(
        "Recette du PC (lot X4)", "15 à 25 min",
        ("scripts/recette_pc.py",),
        ("rien : tout tourne sur le PC, on peut faire autre chose",),
        ("bip et verdict à la fin",)),
    "boutons_click": Trial(
        "Test guidé des boutons du Click", "environ 5 min",
        ("python -m openride_core.tools.boutons_click",),
        ("les deux boîtiers Click, piles chargées",
         "le jeu fermé : l'outil tient seul le Click",
         "le son du PC allumé : un bip à chaque étape et à chaque appui reçu"),
        ("17 appuis demandés tour à tour, le boîtier gauche d'abord, flèches en tête (il se tait environ une minute après la connexion)",
         "chaque appui reçu s'affiche avec son action dans chaque mode (spécification générale §7.1)")),
}


def materials_text(keys: list[str] | None = None) -> str:
    lines: list[str] = []
    for key in keys or list(TRIALS):
        tr = TRIALS[key]
        lines += [f"{tr.title} ({key}) : {tr.duration}", "  À préparer :"]
        lines += [f"    [ ] {m}" for m in tr.materials]
        lines += ["  Commande :"] + [f"    {c}" for c in tr.commands]
        lines += [f"  {n[0].upper()}{n[1:]}." for n in tr.notes]
        lines.append("")
    return "\n".join(lines)


# --- sons ------------------------------------------------------------------------------------

# Un bip : suite de (fréquence en Hz, durée en s) ; 0 Hz est un silence.
BEEPS: dict[str, tuple[tuple[float, float], ...]] = {
    "debut": ((880, 0.18),),
    "compte": ((660, 0.08),),
    "fin": ((990, 0.12), (0, 0.06), (990, 0.12)),
    "alerte": ((330, 0.35), (0, 0.1), (330, 0.35)),
    "reussite": ((660, 0.12), (880, 0.12), (1320, 0.25)),
    "echec": ((440, 0.25), (330, 0.4)),
    # Appui reçu (test des boutons) : mêmes notes que les bips d'appui du jeu (engine `main.gd`).
    "appui": ((880, 0.08),),
    "appui_long": ((660, 0.10), (990, 0.14)),
    "appui_flou": ((300, 0.15),),
}
RATE = 22050


def wav_bytes(tones: tuple[tuple[float, float], ...], rate: int = RATE) -> bytes:
    """Fichier WAV mono 16 bits ; chaque son a une attaque et une chute de 5 ms (pas de clic)."""
    frames = bytearray()
    for freq, dur in tones:
        n = int(dur * rate)
        ramp = max(1, int(0.005 * rate))
        for i in range(n):
            amp = 0.0 if freq <= 0 else 0.45 * min(1.0, i / ramp, (n - 1 - i) / ramp)
            frames += struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * freq * i / rate)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def find_player() -> list[str] | None:
    for cmd in (["pw-play"], ["paplay"], ["aplay", "-q"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


class Sound:
    """Joue les bips sans bloquer l'essai ; `played` garde la liste (tests)."""

    def __init__(self, enabled: bool, bell: Callable[[], None] | None = None) -> None:
        self.enabled = enabled and os.environ.get("OPENRIDE_GUIDE_MUET", "") in ("", "0")
        self.player = find_player() if self.enabled else None
        self.bell = bell
        self.played: list[str] = []

    @staticmethod
    def _file(kind: str) -> Path:
        """Fichiers gardés en cache : un bip encore en lecture à la fin de l'essai n'est pas coupé."""
        cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "openride" / "bips"
        path = cache / f"{kind}.wav"
        if not path.exists():
            cache.mkdir(parents=True, exist_ok=True)
            path.write_bytes(wav_bytes(BEEPS[kind]))
        return path

    def play(self, kind: str) -> None:
        self.played.append(kind)
        if not self.enabled:
            return
        if self.player is None:
            if self.bell:
                self.bell()
            return
        try:
            subprocess.Popen([*self.player, str(self._file(kind))], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:
            self.player = None


# --- grands chiffres -------------------------------------------------------------------------

_BIG = {
    "0": ("█████", "█   █", "█   █", "█   █", "█████"),
    "1": ("  █  ", " ██  ", "  █  ", "  █  ", " ███ "),
    "2": ("█████", "    █", "█████", "█    ", "█████"),
    "3": ("█████", "    █", " ████", "    █", "█████"),
    "4": ("█   █", "█   █", "█████", "    █", "    █"),
    "5": ("█████", "█    ", "█████", "    █", "█████"),
    "6": ("█████", "█    ", "█████", "█   █", "█████"),
    "7": ("█████", "    █", "   █ ", "  █  ", "  █  "),
    "8": ("█████", "█   █", "█████", "█   █", "█████"),
    "9": ("█████", "█   █", "█████", "    █", "█████"),
    ":": ("     ", "  █  ", "     ", "  █  ", "     "),
}


def big_text(text: str) -> list[str]:
    return ["  ".join(_BIG[c][row] for c in text if c in _BIG) for row in range(5)]


def clock_text(seconds: float) -> str:
    s = max(0, math.ceil(seconds))
    return f"{s // 60}:{s % 60:02d}" if s >= 60 else str(s)


# --- guide -----------------------------------------------------------------------------------

@dataclass
class _Step:
    text: str
    detail: str
    started: float
    seconds: float | None
    index: int | None
    total: int | None
    counted: set[int] = field(default_factory=set)
    ended: bool = False


class Guide:
    """Consignes, compte à rebours, bips et journal d'un essai.

    `step()` annonce une étape (bip de début), `tick()` fait vivre le compte à rebours (bips 3, 2, 1
    et fin), `measure()` note un relevé, `alert()` signale un problème, `finish()` donne le verdict.
    L'écran plein terminal n'est dessiné que si `screen` est vrai (par défaut : sortie sur un terminal).
    """

    def __init__(self, title: str, journal: Path | None = None, *, sound: bool | None = None,
                 screen: bool | None = None, out: TextIO | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.title = title
        self.out = out or sys.stdout
        tty = self.out.isatty() if hasattr(self.out, "isatty") else False
        self.screen = tty if screen is None else screen
        self.sound = Sound(tty if sound is None else sound, bell=lambda: self._write("\a"))
        self.clock = clock
        self.t0 = clock()
        self.journal_path = journal
        self._journal: TextIO | None = None
        self.step_: _Step | None = None
        self.live: dict[str, str] = {}
        self.measures: list[tuple[str, bool | None]] = []
        self.notes: list[str] = []
        self.banner = ""
        self.panel: list[str] = []      # encadré sous la consigne (test des boutons : appui reçu)
        self.panel_ok: bool | None = None
        self._last_draw = -1.0

    # journal
    def log(self, kind: str, **data: Any) -> None:
        if self.journal_path is None:
            return
        if self._journal is None:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            self._journal = self.journal_path.open("a", encoding="utf-8")
        row = {"t_s": round(self.clock() - self.t0, 3), "heure": datetime.now().isoformat(timespec="seconds"),
               "type": kind, **data}
        self._journal.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._journal.flush()

    def _write(self, text: str) -> None:
        self.out.write(text)
        self.out.flush()

    def _line(self, text: str) -> None:
        if not self.screen:
            self._write(text + "\n")

    # étapes
    def step(self, text: str, seconds: float | None = None, detail: str = "", *,
             index: int | None = None, total: int | None = None, beep: bool = True) -> None:
        self._end_step()
        self.step_ = _Step(text, detail, self.clock(), seconds, index, total)
        self.banner = ""
        self.panel = []
        self.log("etape", texte=text, detail=detail, duree_s=seconds, numero=index, total=total)
        if beep:
            self.sound.play("debut")
        where = f"[{index}/{total}] " if index is not None and total else ""
        self._line(f">>> {where}{text}" + (f" ({clock_text(seconds)})" if seconds else "")
                   + (f" : {detail}" if detail else ""))
        self.draw(force=True)

    def remaining(self) -> float | None:
        st = self.step_
        if st is None or st.seconds is None:
            return None
        return st.seconds - (self.clock() - st.started)

    def tick(self, live: dict[str, Any] | None = None) -> None:
        """À appeler souvent (boucle de l'outil) : bips 3, 2, 1 puis fin, écran à jour."""
        if live is not None:
            self.live = {k: str(v) for k, v in live.items()}
        left = self.remaining()
        st = self.step_
        if st is not None and left is not None and not st.ended:
            for n in (3, 2, 1):
                if left <= n and n not in st.counted and st.seconds is not None and st.seconds > n + 1:
                    st.counted.add(n)
                    self.sound.play("compte")
            if left <= 0:
                st.ended = True
                self.sound.play("fin")
                self.log("fin_etape", texte=st.text, duree_s=round(self.clock() - st.started, 3))
        self.draw()

    def _end_step(self) -> None:
        st = self.step_
        if st is not None and not st.ended:
            st.ended = True
            self.log("fin_etape", texte=st.text, duree_s=round(self.clock() - st.started, 3))

    def wait(self, seconds: float, live: Callable[[], dict[str, Any]] | None = None, period: float = 0.1) -> None:
        """Attente bloquante qui fait vivre le compte à rebours (outils sans asyncio)."""
        end = self.clock() + seconds
        while self.clock() < end:
            self.tick(live() if live else None)
            time.sleep(min(period, max(0.0, end - self.clock())))
        self.tick(live() if live else None)

    # relevés
    def measure(self, name: str, value: Any, unit: str = "", ok: bool | None = None) -> None:
        text = f"{name} : {value}{(' ' + unit) if unit else ''}"
        self.measures.append((text, ok))
        self.log("releve", nom=name, valeur=value, unite=unit, ok=ok)
        mark = "" if ok is None else ("OK  " if ok else "NON ")
        self._line(f"    {mark}{text}")
        self.draw(force=True)

    def note(self, text: str) -> None:
        self.notes.append(text)
        self.log("note", texte=text)
        self._line(f"    {text}")
        self.draw(force=True)

    def alert(self, text: str, beep: bool = True) -> None:
        self.banner = text
        self.log("alerte", texte=text)
        if beep:
            self.sound.play("alerte")
        self._line(f"!!! {text}")
        self.draw(force=True)

    def show_panel(self, lines: list[str], ok: bool | None = None) -> None:
        """Encadré bien visible sous la consigne : vert si `ok`, jaune si faux, neutre sinon."""
        self.panel, self.panel_ok = list(lines), ok
        for line in lines:
            self._line(f"    | {line}")
        self.draw(force=True)

    def finish(self, ok: bool, text: str) -> None:
        self._end_step()
        self.step_ = _Step(text, "", self.clock(), None, None, None, ended=True)
        self.banner = ""
        self.log("verdict", ok=ok, texte=text)
        self.sound.play("reussite" if ok else "echec")
        self.draw(force=True)
        if self.screen:
            self._write("\n")
        self._line(f"=== {text}")

    def close(self) -> None:
        self._end_step()
        if self._journal is not None:
            self._journal.close()
            self._journal = None

    # matériel
    def prepare(self, key: str, wait: bool, auto_s: float = 10.0,
                ask: Callable[[str], str] | None = None) -> None:
        """Rappelle le matériel de l'essai ; attend « Entrée » si `wait`, puis compte 10 s avant le départ."""
        tr = TRIALS[key]
        self.log("materiel", essai=key, liste=list(tr.materials))
        if self.screen:
            self._write("\033[2J\033[H")
        self._write(f"\n{tr.title} : {tr.duration}\n\nÀ préparer :\n"
                    + "".join(f"  [ ] {m}\n" for m in tr.materials) + "\n")
        if wait:
            (ask or input)("Entrée quand tout est prêt (Ctrl+C pour annuler) ")
        if auto_s > 0:
            self.step("Départ de l'essai", auto_s, "installe-toi")
            self.wait(auto_s)

    # écran
    def render(self) -> list[str]:
        width = max(40, min(shutil.get_terminal_size((100, 30)).columns, 120))
        lines = [f"\033[1m{self.title}\033[0m", ""]
        st = self.step_
        if st is not None:
            head = f"Étape {st.index}/{st.total}" if st.index is not None and st.total else ""
            if head:
                lines.append(head)
            lines += [f"\033[1;97m{w}\033[0m" for w in textwrap.wrap(st.text.upper(), width)] or [""]
            if st.detail:
                lines += textwrap.wrap(st.detail, width)
            left = self.remaining()
            if left is not None:
                color = "\033[1;32m" if left > 10 else "\033[1;33m" if left > 3 else "\033[1;31m"
                lines += [""] + [f"{color}{row}\033[0m" for row in big_text(clock_text(left))]
        if self.panel:
            color = "" if self.panel_ok is None else ("\033[1;32m" if self.panel_ok else "\033[1;33m")
            inner = min(width - 4, max(len(p) for p in self.panel))
            lines += ["", f"{color}┌{'─' * (inner + 2)}┐\033[0m"]
            lines += [f"{color}│\033[0m {p[:inner].ljust(inner)} {color}│\033[0m" for p in self.panel]
            lines.append(f"{color}└{'─' * (inner + 2)}┘\033[0m")
        if self.banner:
            lines += ["", f"\033[1;41;97m {self.banner} \033[0m"]
        if self.live:
            lines += ["", "   ".join(f"{k} \033[1m{v}\033[0m" for k, v in self.live.items())]
        if self.measures:
            lines += ["", "Relevés :"]
            for text, ok in self.measures[-6:]:
                mark = "  " if ok is None else ("\033[32mOK\033[0m" if ok else "\033[31mNON\033[0m")
                lines.append(f"  {mark} {text}")
        if self.notes:
            lines += ["", *[f"  {n}" for n in self.notes[-3:]]]
        return lines

    def draw(self, force: bool = False) -> None:
        if not self.screen:
            return
        now = self.clock()
        if not force and now - self._last_draw < 0.2:
            return
        self._last_draw = now
        self._write("\033[2J\033[H" + "\n".join(self.render()) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Guidage des essais : matériel à préparer, bips.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("materiel", help="matériel, durée et commande de chaque essai")
    m.add_argument("essais", nargs="*", help=f"parmi {', '.join(TRIALS)} (défaut : tous)")
    sub.add_parser("bips", help="joue chaque bip, pour régler le volume")
    args = ap.parse_args(argv)
    if args.cmd == "materiel":
        unknown = [e for e in args.essais if e not in TRIALS]
        if unknown:
            print(f"essai inconnu : {', '.join(unknown)} (connus : {', '.join(TRIALS)})", file=sys.stderr)
            return 2
        print(materials_text(args.essais or None), end="")
        return 0
    sound = Sound(True, bell=lambda: print("\a", end="", flush=True))
    for kind in BEEPS:
        print(kind, flush=True)
        sound.play(kind)
        time.sleep(1.2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
