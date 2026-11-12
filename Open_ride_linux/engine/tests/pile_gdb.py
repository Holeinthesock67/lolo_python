"""Pile `gdb` d'un Godot qui ne se ferme pas, sans `sudo` (lot X58).

Sous Ubuntu, `ptrace` n'est permis qu'aux ancêtres du processus (`kernel.yama.ptrace_scope = 1`) : `gdb -p` sur
le Godot du banc est refusé sans `sudo`. Le banc des menus (`menu_bench.py --gdb`) lance donc Godot SOUS gdb dès le
départ : gdb en est le parent. Godot tourne normalement ; s'il sort seul, gdb sort avec son code (le banc lit le
même code de sortie ; tué par un signal, comme l'engine qui s'arrête lui-même par SIGKILL au lot X58, 128 + le
signal, comme un shell). S'il reste bloqué après sa ligne de fin, le banc lui envoie SIGINT : gdb l'arrête, écrit la
pile de tous ses fils entre deux repères, le tue et sort avec le code `CODE_PILE`.

`resume_pile` réduit cette sortie à une ligne par fil (nom, puis fonctions du haut de la pile avec leur bibliothèque),
les fils identiques regroupés, le fil principal d'abord : de quoi savoir qui attend qui (pilote NVIDIA, Vulkan, libc).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

DEBUT = "==== PILE GDB ===="
FIN = "==== FIN PILE GDB ===="
CODE_PILE = 99   # code de sortie de gdb après la pile (Godot tué) : jamais un code d'OpenRide (0, 64, 65)

# Commandes de gdb, lues par `-x`. Une commande inconnue arrête un fichier `-x` : celles qui dépendent de la version
# de gdb (debuginfod, gdb 12+) passent par `-ex`, dont une erreur n'arrête que la commande.
SCRIPT = f"""set pagination off
set confirm off
set print thread-events off
set print inferior-events off
handle SIGPIPE SIGUSR1 SIGUSR2 SIGALRM SIGCHLD nostop noprint pass
handle SIGINT stop print nopass
run
if !$_isvoid($_exitsignal)
  quit 128 + $_exitsignal
end
if $_isvoid($_exitcode)
  echo {DEBUT}\\n
  info threads
  thread apply all bt 30
  echo {FIN}\\n
  kill
  quit {CODE_PILE}
else
  quit $_exitcode
end
"""


def gdb_prefix(script_path: Path) -> list[str] | None:
    """Début de commande qui lance un programme sous gdb (`... --args PROGRAMME ARGS`) ; None sans gdb."""
    gdb = shutil.which("gdb")
    if gdb is None:
        return None
    script_path.write_text(SCRIPT, encoding="utf-8")
    return [gdb, "-q", "-batch", "-ex", "set debuginfod enabled off", "-x", str(script_path), "--args"]


def extraire(lines: list[str]) -> str:
    """Texte de la pile entre les repères (vide si gdb ne l'a pas écrite)."""
    try:
        start = lines.index(DEBUT)
    except ValueError:
        return ""
    end = lines.index(FIN, start) if FIN in lines[start:] else len(lines)
    return "\n".join(lines[start + 1:end]) + "\n"


_THREAD = re.compile(r'^Thread (\d+) \(.*?"(.*)"\):$|^Thread (\d+) \((.*)\):$')
_FRAME = re.compile(r"^#(\d+)\s+(?:0x[0-9a-f]+ in )?(\S+) \(.*?\)(?: (?:from|at) (\S+))?")


def _frame(m: re.Match[str]) -> str:
    func, where = m.group(2), m.group(3)
    lib = Path(where.split(":")[0]).name if where else ""
    return f"{func}@{lib}" if lib and func == "??" else (f"{func} ({lib})" if lib else func)


def resume_pile(text: str, frames: int = 6, main_frames: int = 14) -> list[str]:
    """Une ligne par fil (ou groupe de fils identiques) : « nom [×n] : f0 ← f1 ← … ». Fil 1 (principal) d'abord,
    avec plus d'images : c'est lui qui est dans l'arrêt de Godot."""
    threads: list[tuple[int, str, list[str]]] = []
    for line in text.splitlines():
        m = _THREAD.match(line.strip())
        if m:
            num = int(m.group(1) or m.group(3))
            threads.append((num, m.group(2) or "?", []))
            continue
        f = _FRAME.match(line.strip())
        if f and threads:
            threads[-1][2].append(_frame(f))
    out: list[str] = []
    groups: dict[str, int] = {}
    for num, name, fr in sorted(threads, key=lambda t: t[0] != 1):
        key = f"{name} : " + " ← ".join(fr[:main_frames if num == 1 else frames] or ["(pile vide)"])
        if num == 1:
            out.append("principal " + key)
        else:
            groups[key] = groups.get(key, 0) + 1
    for key, n in groups.items():
        name, rest = key.split(" : ", 1)
        out.append(f"{name} ×{n} : {rest}" if n > 1 else key)
    return out
