"""Test guidé des boutons du Zwift Click : chaque appui reconnu s'affiche avec son action, et bipe.

    python -m openride_core.tools.boutons_click              # Click réel, environ 5 min
    python -m openride_core.tools.boutons_click --sim        # sans matériel (Click simulé)
    python -m openride_core.tools.boutons_click --materiel   # matériel à préparer

L'outil demande les 17 appuis du plan des boutons (spécification générale §7.1) un par un : bip de
départ à chaque étape, consigne en grand avec compte à rebours, puis étape suivante dès que l'appui
demandé est reçu et lu (`--lecture`, 4 s), ou au bout de `--delai` secondes (30). Chaque appui reçu, demandé ou non, s'affiche dans
un encadré : événement décodé par le core, bouton et boîtier, et l'action qu'il commande dans chaque
mode (menus, SIM, ERG, Cyber-Rogue, monde ouvert) ; il bipe avec les notes du jeu (court, long, ou
appui ni court ni long). Le boîtier gauche passe d'abord : sans déblocage par l'appli Zwift, il se
tait environ une minute après la connexion (SRS §4.2).

Mêmes fournisseurs que le core (deux boîtiers, comme la recette X8 `click_recette`). Écrit
`rapport.txt`, `rapport.json` et `guide.jsonl` dans `~/OpenRide/boutons_click/<date>_<heure>/` ;
l'adresse des boîtiers n'est écrite que dans ce dossier local. Code de sortie : 0 si les 17 appuis
sont reconnus, 1 sinon.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..zwift_click import InputEvent
from .click_recette import Recorder, TracedClickProvider, make_providers
from .guide import Guide

DEFAULT_OUT = Path.home() / "OpenRide" / "boutons_click"
STEP_TIMEOUT_S = 30.0
NEXT_STEP_S = 4.0        # temps de lecture de l'encadré avant l'étape suivante
SIM_THINK_S = 3.0        # --sim : le cycliste simulé lit la consigne avant d'appuyer

# --- plan des boutons (spécification générale §7.1, seule référence) -------------------------

MODES = ("Menus", "Classique SIM", "ERG", "Cyber-Rogue", "Monde ouvert")


@dataclass(frozen=True)
class Action:
    row: str                   # première colonne de la ligne du tableau §7.1 ("" : hors tableau)
    family: str
    modes: tuple[str, ...]     # une action par mode, dans l'ordre de MODES


_SAME = "Comme le mode roulé (SIM ou ERG)"
_UNCLEAR = Action("", "Appui ni court ni long (0,5 à 0,9 s)",
                  ("Rien : l'écran explique l'appui",) * len(MODES))

# Les cellules du tableau qui valent pour les deux sens (« ± », « suivant, précédent ») sont écrites
# ici pour un seul sens ; `test_boutons_click` compare le reste du tableau mot pour mot.
PLAN: dict[InputEvent, Action] = {
    InputEvent.PLUS_SHORT: Action("+ / B (ou −), court", "Déplacer ou doser, petit pas", (
        "Élément suivant", "Braquet + 1", "Biais + 2 %", "Vitesse du frein + 1", _SAME)),
    InputEvent.MINUS_SHORT: Action("+ / B (ou −), court", "Déplacer ou doser, petit pas", (
        "Élément précédent", "Braquet − 1", "Biais − 2 %", "Vitesse du frein − 1", _SAME)),
    InputEvent.PLUS_LONG: Action("+ / B (ou −), long", "Déplacer ou doser, grand pas", (
        "Cinq éléments plus loin", "Braquet + 10", "Biais + 10 %", "Vitesse du frein + 3", "Comme le mode roulé")),
    InputEvent.MINUS_LONG: Action("+ / B (ou −), long", "Déplacer ou doser, grand pas", (
        "Cinq éléments plus haut", "Braquet − 10", "Biais − 10 %", "Vitesse du frein − 3", "Comme le mode roulé")),
    InputEvent.PLUS_UNCLEAR: _UNCLEAR,
    InputEvent.MINUS_UNCLEAR: _UNCLEAR,
    InputEvent.Y_SHORT: Action("Y court", "Interrompre et revenir", (
        "Écran précédent ; sur l'écran de pause, reprendre", "Pause et reprise", "Pause et reprise",
        "Pause et reprise", "Pause et reprise")),
    InputEvent.Z_SHORT: Action("Z court", "Action du mode", (
        "Aucune (un menu n'est pas un mode)", "Bonus (T)", "Bloc suivant", "Attaque", "Bonus (T)")),
    InputEvent.Z_LONG: Action("Z long", "Action spéciale du mode", (
        "Aucune", "Aucune", "Aucune", "Carte ou relique active (T1)", "Aucune")),
    InputEvent.A_SHORT: Action("A court", "Choisir : option suivante du choix affiché", (
        "Élément suivant", "Vue de caméra suivante", "Vue de caméra suivante", "Couloir ou carte suivant",
        "Branche suivante au carrefour, sinon vue suivante")),
    InputEvent.A_LONG: Action("A long", "Valider le choix affiché", (
        "Valider l'élément", "Revenir à la vue par défaut", "Revenir à la vue par défaut",
        "Valider le couloir ou la carte", "Valider la branche, sinon revenir à la vue par défaut")),
    InputEvent.LEFT_SHORT: Action("Flèches gauche, droite (boîtier gauche)", "Choisir, raccourci", (
        "Élément précédent", "Aucune", "Aucune", "Couloir ou carte précédent", "Branche à gauche")),
    InputEvent.RIGHT_SHORT: Action("Flèches gauche, droite (boîtier gauche)", "Choisir, raccourci", (
        "Élément suivant", "Aucune", "Aucune", "Couloir ou carte suivant", "Branche à droite")),
    InputEvent.UP_SHORT: Action("Flèches haut, bas (boîtier gauche)", "Vue, raccourci", (
        "Aucune (pas de vue dans un menu)", "Vue suivante", "Vue suivante", "Vue suivante", "Vue suivante")),
    InputEvent.DOWN_SHORT: Action("Flèches haut, bas (boîtier gauche)", "Vue, raccourci", (
        "Aucune (pas de vue dans un menu)", "Vue précédente", "Vue précédente", "Vue précédente",
        "Vue précédente")),
}

EVENT_LABELS = {
    "PLUS": "+", "MINUS": "−", "A": "A", "Z": "Z", "Y": "Y",
    "LEFT": "flèche gauche", "RIGHT": "flèche droite", "UP": "flèche haut", "DOWN": "flèche bas",
}
KIND_LABELS = {"SHORT": "court", "LONG": "long", "UNCLEAR": "ni court ni long"}


def event_label(ev: InputEvent) -> str:
    button, kind = ev.value.rsplit("_", 1)
    if button in ("Y", "LEFT", "RIGHT", "UP", "DOWN"):
        return EVENT_LABELS[button]
    return f"{EVENT_LABELS[button]} {KIND_LABELS[kind]}"


def beep_kind(ev: InputEvent) -> str:
    """Bip d'un appui reçu : mêmes notes que le jeu pour un appui court ou long."""
    if ev.value.endswith("_LONG"):
        return "appui_long"
    if ev.value.endswith("_UNCLEAR"):
        return "appui_flou"
    return "appui"


# --- étapes ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class ButtonStep:
    key: str
    prompt: str
    event: InputEvent
    button: str           # touche attendue dans la trame (nom de KEYPAD_BITS)
    press_s: float        # durée d'appui du cycliste simulé

    @property
    def left(self) -> bool:
        return self.button in ("MINUS", "LEFT", "RIGHT", "UP", "DOWN")


SHORT, LONG, MEDIUM = 0.12, 1.1, 0.7
STEPS = (
    # Boîtier gauche d'abord : il peut se taire une minute après la connexion.
    ButtonStep("moins", "Appuie brièvement sur − (boîtier gauche)", InputEvent.MINUS_SHORT, "MINUS", SHORT),
    ButtonStep("moins_long", "Appui long sur − (une seconde)", InputEvent.MINUS_LONG, "MINUS", LONG),
    ButtonStep("moins_moyen", "Appui moyen sur − (environ 0,7 s : ni court ni long)",
               InputEvent.MINUS_UNCLEAR, "MINUS", MEDIUM),
    ButtonStep("gauche", "Appuie sur la flèche gauche (boîtier gauche)", InputEvent.LEFT_SHORT, "LEFT", SHORT),
    ButtonStep("droite", "Appuie sur la flèche droite (boîtier gauche)", InputEvent.RIGHT_SHORT, "RIGHT", SHORT),
    ButtonStep("haut", "Appuie sur la flèche haut (boîtier gauche)", InputEvent.UP_SHORT, "UP", SHORT),
    ButtonStep("bas", "Appuie sur la flèche bas (boîtier gauche)", InputEvent.DOWN_SHORT, "DOWN", SHORT),
    ButtonStep("plus", "Appuie brièvement sur + (boîtier droit)", InputEvent.PLUS_SHORT, "PLUS", SHORT),
    ButtonStep("plus_long", "Appui long sur + (une seconde)", InputEvent.PLUS_LONG, "PLUS", LONG),
    ButtonStep("plus_moyen", "Appui moyen sur + (environ 0,7 s : ni court ni long)",
               InputEvent.PLUS_UNCLEAR, "PLUS", MEDIUM),
    ButtonStep("b", "Appuie brièvement sur B (boîtier droit, double le −)", InputEvent.MINUS_SHORT, "B", SHORT),
    ButtonStep("b_long", "Appui long sur B (une seconde)", InputEvent.MINUS_LONG, "B", LONG),
    ButtonStep("a", "Appuie brièvement sur A (boîtier droit)", InputEvent.A_SHORT, "A", SHORT),
    ButtonStep("a_long", "Appui long sur A (une seconde)", InputEvent.A_LONG, "A", LONG),
    ButtonStep("y", "Appuie sur Y (boîtier droit)", InputEvent.Y_SHORT, "Y", SHORT),
    ButtonStep("z", "Appuie brièvement sur Z (boîtier droit)", InputEvent.Z_SHORT, "Z", SHORT),
    ButtonStep("z_long", "Appui long sur Z (une seconde)", InputEvent.Z_LONG, "Z", LONG),
)


def panel_lines(ev: InputEvent, key: str | None, side: str, expected: ButtonStep | None) -> list[str]:
    """Encadré d'un appui reçu : ce que le core a reconnu et ce que l'appui commande dans chaque mode."""
    act = PLAN[ev]
    where = f"touche {EVENT_LABELS.get(key or '', key or '?')}" + (f", boîtier {side}" if side != "?" else "")
    lines = [f"REÇU : {event_label(ev).upper()}   ({ev.value}, {where})", f"Famille : {act.family}", ""]
    width = max(len(m) for m in MODES)
    lines += [f"{m.ljust(width)} : {a}" for m, a in zip(MODES, act.modes)]
    if expected is not None:
        lines.append("")
        if expected.event == ev and key == expected.button:
            lines.append("✔ C'est l'appui demandé")
        else:
            lines.append(f"✘ Attendu : {event_label(expected.event)} (touche {EVENT_LABELS.get(expected.button, expected.button)})")
    return lines


# --- déroulé ---------------------------------------------------------------------------------

@dataclass
class StepResult:
    key: str
    prompt: str
    expected: str
    ok: bool
    delay_s: float | None
    received: list[str]   # événements reçus pendant l'étape, dans l'ordre
    side: str | None
    detail: str


def _key_counts(rec: Recorder) -> dict[str, dict[str, int]]:
    return {a: dict(u.buttons) for a, u in rec.units.items()}


def _new_key(rec: Recorder, before: dict[str, dict[str, int]], wanted: str | None = None) -> tuple[str | None, str]:
    """Touche apparue dans les trames depuis `before` (la touche voulue d'abord) et côté du boîtier."""
    found: list[tuple[str, str]] = []
    for address, u in rec.units.items():
        old = before.get(address, {})
        found += [(name, u.side) for name, n in u.buttons.items() if n > old.get(name, 0)]
    # « + » arrive aussi par le boîtier gauche (relais) : le boîtier reconnu passe d'abord.
    found.sort(key=lambda f: (f[0] != wanted, f[1] == "?"))
    return found[0] if found else (None, "?")


Prompter = Callable[[ButtonStep | None], None]


async def run_steps(providers: list[TracedClickProvider], rec: Recorder, guide: Guide,
                    prompt: Prompter | None = None, step_timeout: float = STEP_TIMEOUT_S,
                    connect_timeout: float = 120.0, next_step_s: float = NEXT_STEP_S,
                    poll_s: float = 0.05) -> dict[str, Any]:
    g = guide
    tasks = [asyncio.create_task(p.run()) for p in providers]
    link: dict[int, bool] = {}

    def watch_links() -> None:
        for i, p in enumerate(providers):
            up = p.status == "CONNECTED"
            if up != link.get(i, False):
                link[i] = up
                rec.link(p.unit_address, up)
                side = rec.unit(p.unit_address).side
                if up:
                    g.note(f"boîtier {side} connecté à {rec.t():.0f} s")
                else:
                    g.alert(f"Boîtier {side} coupé à {rec.t():.0f} s")

    async def pause(seconds: float) -> None:
        end = rec.t() + seconds
        while rec.t() < end:
            watch_links()
            g.tick()
            await asyncio.sleep(poll_s)

    results: list[StepResult] = []
    try:
        g.step("Appuie sur un bouton de chaque boîtier pour les réveiller", connect_timeout,
               "le boîtier gauche (−) puis le droit (+)")
        if prompt:
            prompt(None)
        end = rec.t() + connect_timeout
        while rec.t() < end and sum(link.values()) < len(providers):
            watch_links()
            g.tick()
            await asyncio.sleep(0.2)
        connected = sum(link.values())
        g.measure("boîtiers connectés", f"{connected} sur {len(providers)}", ok=connected == len(providers))
        await pause(1.0)
        for k, step in enumerate(STEPS):
            after = rec.t()
            seen = len(rec.events)
            keys = _key_counts(rec)
            g.step(step.prompt, step_timeout, f"attendu : {event_label(step.event)}", index=k + 1, total=len(STEPS))
            if prompt:
                prompt(step)
            res: StepResult | None = None
            received: list[str] = []
            while rec.t() < after + step_timeout and res is None:
                watch_links()
                g.tick()
                for t, _address, ev in rec.events[seen:]:
                    seen += 1
                    key, side = _new_key(rec, keys, step.button)
                    keys = _key_counts(rec)
                    received.append(ev.value)
                    ok = ev == step.event and key == step.button
                    g.show_panel(panel_lines(ev, key, side, step), ok=ok)
                    g.log("appui", evenement=ev.value, touche=key, boitier=side, attendu=step.event.value, ok=ok)
                    g.sound.play(beep_kind(ev) if ok else "alerte")
                    if ok:
                        res = StepResult(step.key, step.prompt, step.event.value, True, t - after, received, side,
                                         f"reconnu : {event_label(ev)}")
                        break
                if res is None:
                    await asyncio.sleep(poll_s)
            if res is None:
                why = f"non reçu en {step_timeout:.0f} s (attendu : {event_label(step.event)})"
                if received:
                    why += f" (reçu : {', '.join(received)})"
                res = StepResult(step.key, step.prompt, step.event.value, False, None, received, None, why)
                g.sound.play("echec")
            delay = f" en {res.delay_s:.1f} s" if res.delay_s is not None else ""
            g.measure(step.prompt, f"{res.detail}{delay}", ok=res.ok)
            results.append(res)
            await pause(next_step_s)
    finally:
        for p in providers:
            p.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
        rec.close()
    return build_report(results)


def build_report(results: list[StepResult]) -> dict[str, Any]:
    ok = sum(r.ok for r in results)
    missed_left = [r.key for r in results if not r.ok and next(s for s in STEPS if s.key == r.key).left]
    return {"ok": bool(results) and ok == len(results), "steps_ok": ok, "steps_total": len(results),
            "missed_left": missed_left, "steps": [asdict(r) for r in results]}


def report_text(report: dict[str, Any]) -> str:
    head = "tout passe" if report["ok"] else "À REVOIR"
    lines = [f"Test guidé des boutons du Click : {head}", "",
             f"Appuis reconnus : {report['steps_ok']}/{report['steps_total']}"]
    for s in report["steps"]:
        delay = f" en {s['delay_s']:.1f} s" if s["delay_s"] is not None else ""
        side = f", boîtier {s['side']}" if s["side"] and s["side"] != "?" else ""
        lines.append(f"  {'OK ' if s['ok'] else 'NON'} {s['prompt']} : {s['detail']}{side}{delay}")
    if report["missed_left"]:
        lines += ["", "Boîtier gauche : appuis manqués. S'il s'est tu après environ une minute, c'est le",
                  "bridage connu sans déblocage Zwift (docs/DIAG_CLICK_GAUCHE.md) ; B du boîtier droit fait « − »."]
    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "rapport.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "rapport.txt").write_text(report_text(report), encoding="utf-8")


async def sim_user(world: Any, prompts: asyncio.Queue[ButtonStep | None], think_s: float = 0.3) -> None:
    """Cycliste simulé : réveille les boîtiers puis fait l'appui demandé, avec sa durée."""
    right, left = world._box("+"), world._box("-")
    loop = asyncio.get_running_loop()
    names = {"PLUS": "+", "MINUS": "-"}

    def tap(box: Any, button: str, duration: float) -> None:
        box.set_button(button, True)
        loop.call_later(duration, box.set_button, button, False)

    while True:
        step = await prompts.get()
        await asyncio.sleep(think_s)
        if step is None:
            tap(right, "+", SHORT)
            tap(left, "-", SHORT)
        else:
            tap(left if step.left else right, names.get(step.button, step.button), step.press_s)


async def main_async(args: argparse.Namespace) -> int:
    from .. import config as config_mod

    cfg = config_mod.load(args.config)
    out = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    guide = Guide("Test des boutons du Click", out / "guide.jsonl", sound=False if args.muet else None)
    guide.prepare("boutons_click", wait=not args.sim and not args.sans_attente and sys.stdin.isatty(),
                  auto_s=0 if args.sim else 5.0)
    rec = Recorder(time.monotonic)
    prompt: Prompter | None = None
    extra: list[asyncio.Task[Any]] = []
    sim = None
    if args.sim:
        from .. import sim_scenarios
        spec = sim_scenarios.load_scenario(args.scenario) if args.scenario else {
            "click": {"appear_at": 0.0}, "trainer": None, "hr": None, "events": []}
        sim = sim_scenarios.build_world(spec, trainer=False, hr=False)
        prompts: asyncio.Queue[ButtonStep | None] = asyncio.Queue()
        prompt = prompts.put_nowait
        extra = [asyncio.create_task(sim.run()), asyncio.create_task(sim_user(sim, prompts, SIM_THINK_S))]
    providers = make_providers(rec, cfg, sim)
    try:
        report = await run_steps(providers, rec, guide, prompt, step_timeout=args.delai,
                                 connect_timeout=20.0 if args.sim else 120.0, next_step_s=args.lecture)
    finally:
        if sim is not None:
            sim.stop()
        for t in extra:
            t.cancel()
        await asyncio.gather(*extra, return_exceptions=True)
    guide.finish(report["ok"], f"Test fini : {report['steps_ok']}/{report['steps_total']} appuis reconnus"
                 + ("" if report["ok"] else ", voir le rapport"))
    guide.close()
    write_outputs(report, out)
    print()
    print(report_text(report), end="")
    print(f"Rapport : {out}")
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Test guidé des boutons du Zwift Click (action affichée, bip).")
    ap.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    ap.add_argument("--delai", type=float, default=STEP_TIMEOUT_S,
                    help=f"secondes laissées pour chaque appui (défaut {STEP_TIMEOUT_S:g})")
    ap.add_argument("--lecture", type=float, default=NEXT_STEP_S,
                    help=f"secondes pour lire l'encadré avant l'étape suivante (défaut {NEXT_STEP_S:g})")
    ap.add_argument("--sim", action="store_true", help="Click simulé (ble_sim), cycliste simulé")
    ap.add_argument("--scenario", help="avec --sim : scénario (nom ou fichier JSON) pour le Click simulé")
    ap.add_argument("--out", type=Path, help=f"dossier de sortie (défaut : {DEFAULT_OUT}/<date>)")
    ap.add_argument("-v", "--verbose", action="store_true", help="journal du Click à l'écran")
    ap.add_argument("--materiel", action="store_true", help="affiche le matériel à préparer et quitte")
    ap.add_argument("--sans-attente", action="store_true", help="démarre sans attendre « Entrée »")
    ap.add_argument("--muet", action="store_true", help="sans bips")
    args = ap.parse_args(argv)
    if args.materiel:
        from .guide import materials_text
        print(materials_text(["boutons_click"]), end="")
        return 0
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    try:
        return asyncio.run(main_async(args))
    except (KeyboardInterrupt, EOFError):
        print("\nInterrompu.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
