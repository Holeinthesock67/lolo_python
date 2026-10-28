#!/usr/bin/env python3
"""Garde-fou de la qualité réellement appliquée par l'engine (lot X32).

Le 28 octobre, `sim_bench.py` passait `--quality` à l'engine mais pas au core, qui renvoyait
`[render] quality = "low"` au démarrage : tous les bancs « medium » et « high » mesuraient du
`low` sans que rien ne le dise (corrigé par la PR #481). Ce module lit le journal de l'engine et
vérifie la qualité appliquée au moment de chaque capture :

- `Qualité appliquée : medium (demandée medium, source cli)` : ligne toujours écrite par `main.gd`
  à chaque application d'un préréglage (démarrage, réglage reçu du core) ;
- `[test] quality applied=medium requested=medium source=cli` : la même en `--test-mode` ;
- `[test] screenshot {…, "quality": "medium", …}` : qualité au moment de la capture.

Usage : quality_guard.py JOURNAL_ENGINE QUALITÉ  (code 0 si la qualité appliquée est celle voulue,
1 sinon, 2 si le journal ne dit rien de la qualité). Bibliothèque standard seulement.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

APPLIED = re.compile(r"Qualité appliquée : (\w+) \(demandée (\S+), source (\w+)\)")
SHOT = re.compile(r"\[test\] screenshot (\{.*\})\s*$")


def applied_sequence(log: str) -> list[tuple[str, str, str]]:
    """Qualités appliquées dans l'ordre du journal : (appliquée, demandée, source)."""
    return [(m.group(1), m.group(2), m.group(3)) for m in APPLIED.finditer(log)]


def qualities_at_captures(log: str) -> list[str]:
    """Qualité appliquée au moment de chaque capture : champ `quality` de la capture, ou à défaut
    la dernière ligne « Qualité appliquée » qui la précède (journaux d'avant le champ)."""
    current = ""
    out: list[str] = []
    for line in log.splitlines():
        m = APPLIED.search(line)
        if m:
            current = m.group(1)
            continue
        s = SHOT.search(line)
        if s:
            try:
                q = str(json.loads(s.group(1)).get("quality") or current)
            except ValueError:
                q = current
            out.append(q)
    return out


def check(log: str, wanted: str) -> tuple[bool | None, str]:
    """(ok, message). ok vaut None si le journal ne dit rien de la qualité (engine trop ancien)."""
    seq = applied_sequence(log)
    shots = qualities_at_captures(log)
    if not seq and not any(shots):
        return None, "aucune ligne « Qualité appliquée » au journal de l'engine"
    seen = [q for q in shots if q] or [seq[-1][0]]
    wrong = sorted({q for q in seen if q != wanted})
    last = seq[-1] if seq else None
    trail = f" ; dernière ligne : {last[0]} (demandée {last[1]}, source {last[2]})" if last else ""
    if wrong:
        bad = sum(q != wanted for q in seen)
        return False, (f"qualité demandée {wanted}, appliquée {', '.join(wrong)} "
                       f"({bad}/{len(seen)} {'capture(s)' if shots else 'relevé'}){trail}")
    what = f"{len(seen)} capture(s)" if shots else "fin du journal"
    return True, f"{wanted} appliquée ({what}){trail}"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Usage : quality_guard.py JOURNAL_ENGINE QUALITÉ", file=sys.stderr)
        return 2
    ok, msg = check(Path(args[0]).read_text(encoding="utf-8", errors="replace"), args[1])
    print(f"[{'INFO' if ok is None else 'OK' if ok else 'ÉCHEC'}] qualité appliquée : {msg}")
    return 2 if ok is None else 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
